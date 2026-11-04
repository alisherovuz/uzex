"""Tool-using agent loops for two independent model providers (Claude and GPT).

The final_answer tool is guarded: if the answer contains a number that is not present in any query
result, the tool returns an error and the model must recompute or remove it (max 2 rejections)."""
import asyncio
import json
import time
from typing import Awaitable, Callable

from . import config, db
from .prompt import TOOLS, system_prompt
from .validate import check_answer

Emit = Callable[[dict], Awaitable[None]]
_SYSTEM = None


def get_system() -> str:
    global _SYSTEM
    if _SYSTEM is None:
        _SYSTEM = system_prompt()
    return _SYSTEM


class Run:
    def __init__(self, tag: str, question: str, model: str):
        self.tag = tag
        self.question = question
        self.model = model
        self.queries: dict[str, dict] = {}
        self.lookups: list[dict] = []
        self.final: dict | None = None
        self.unbacked: list[str] = []
        self.rejections = 0
        self.n = 0
        self.messages: list = []
        self.error: str | None = None

    async def exec_tool(self, name: str, args: dict, emit: Emit | None) -> dict:
        if name == "run_sql":
            self.n += 1
            qid = f"{self.tag}{self.n}"
            res = await asyncio.to_thread(db.run_sql, args.get("sql", ""))
            entry = {"id": qid, "purpose": args.get("purpose", ""), "sql": args.get("sql", ""), **res}
            self.queries[qid] = entry
            if emit:
                await emit({"type": "sql", "by": self.tag, "id": qid, "purpose": entry["purpose"],
                            "ok": "error" not in res, "rows": res.get("row_count", 0), "ms": res.get("ms")})
            out = {"query_id": qid, **res}
            if "rows" in out and len(out["rows"]) > 60:
                out["rows"] = out["rows"][:60]
                out["note"] = "only the first 60 rows are shown to you; aggregate further if needed"
            return out
        if name in ("find_product", "find_company", "find_broker"):
            res = await asyncio.to_thread(getattr(db, name), args.get("query", ""))
            self.lookups.append({"tool": name, "query": args.get("query", ""), "found": len(res.get("matches", []))})
            if emit:
                await emit({"type": "lookup", "by": self.tag, "tool": name, "query": args.get("query", ""),
                            "found": len(res.get("matches", []))})
            return res
        if name == "final_answer":
            unbacked = check_answer(args.get("answer", ""), self.question, self.queries, args.get("key_figures", []))
            if unbacked and self.rejections < 2:
                self.rejections += 1
                if emit:
                    await emit({"type": "guard", "by": self.tag, "unbacked": unbacked[:6]})
                return {"ok": False, "error": "REJECTED by the number guard: these numbers are not present in any "
                        f"query result: {unbacked[:10]}. Compute them with run_sql (or remove them), copy values "
                        "exactly, then call final_answer again."}
            self.unbacked = unbacked
            self.final = args
            return {"ok": True}
        return {"error": f"unknown tool {name}"}


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)[:24000]


# ------------------------------------------------------------------ Claude
_CLAUDE_TEMP_OK = True


async def claude_loop(run: Run, emit: Emit | None, deadline: float, max_turns: int = 10) -> Run:
    """Run (or continue) a Claude tool loop until final_answer is accepted."""
    global _CLAUDE_TEMP_OK
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=2)
    system = [{"type": "text", "text": get_system(), "cache_control": {"type": "ephemeral"}}]
    if not run.messages:
        run.messages = [{"role": "user", "content": run.question}]
    messages = run.messages
    for turn in range(max_turns):
        remaining = deadline - time.time()
        if remaining < 4:
            break
        if turn == max_turns - 1 or remaining < 15:
            nudge = "Time is almost up: call final_answer now with what you have (numbers only from query results)."
            last = messages[-1]
            if isinstance(last["content"], list):
                last["content"].append({"type": "text", "text": nudge})
            else:
                last["content"] += "\n\n" + nudge
        kwargs = dict(model=run.model, max_tokens=3000, system=system, tools=TOOLS, messages=messages)
        if _CLAUDE_TEMP_OK:
            kwargs["temperature"] = 0
        try:
            resp = await asyncio.wait_for(client.messages.create(**kwargs), timeout=max(5, remaining))
        except anthropic.BadRequestError as e:
            if "temperature" in str(e) and kwargs.pop("temperature", None) is not None:
                _CLAUDE_TEMP_OK = False
                resp = await asyncio.wait_for(client.messages.create(**kwargs), timeout=max(5, deadline - time.time()))
            else:
                raise
        messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in resp.content]})
        uses = [b for b in resp.content if b.type == "tool_use"]
        if not uses:
            messages.append({"role": "user", "content": "Use the tools; finish by calling final_answer."})
            continue
        results = await asyncio.gather(*[run.exec_tool(u.name, u.input, emit) for u in uses])
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": u.id, "content": _dump(r)} for u, r in zip(uses, results)]})
        if run.final is not None:
            break
    return run


def claude_followup(run: Run, text: str) -> None:
    """Re-open a finished Claude run with a new instruction (used for reconciliation)."""
    run.final = None
    run.rejections = 0
    last = run.messages[-1]
    if isinstance(last["content"], list):
        last["content"].append({"type": "text", "text": text})
    else:
        last["content"] += "\n\n" + text


# ------------------------------------------------------------------ GPT
def _openai_tools():
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": t["input_schema"]}} for t in TOOLS]


async def gpt_loop(run: Run, emit: Emit | None, deadline: float, max_turns: int = 10) -> Run:
    import openai
    client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY, max_retries=2)
    if not run.messages:
        run.messages = [{"role": "system", "content": get_system()}, {"role": "user", "content": run.question}]
    messages = run.messages
    extra = {}
    if config.OPENAI_REASONING and run.model.startswith(("gpt-5", "o")):
        extra["reasoning_effort"] = config.OPENAI_REASONING
    for turn in range(max_turns):
        remaining = deadline - time.time()
        if remaining < 4:
            break
        if turn == max_turns - 1 or remaining < 15:
            messages.append({"role": "user", "content": "Time is almost up: call final_answer now."})
        try:
            resp = await asyncio.wait_for(client.chat.completions.create(
                model=run.model, messages=messages, tools=_openai_tools(), **extra), timeout=max(5, remaining))
        except openai.BadRequestError as e:
            if extra and "reasoning" in str(e):
                extra = {}
                continue
            raise
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            messages.append({"role": "user", "content": "Use the tools; finish by calling final_answer."})
            continue
        args = []
        for c in msg.tool_calls:
            try:
                args.append(json.loads(c.function.arguments or "{}"))
            except json.JSONDecodeError:
                args.append({})
        results = await asyncio.gather(*[run.exec_tool(c.function.name, a, emit)
                                         for c, a in zip(msg.tool_calls, args)])
        for c, r in zip(msg.tool_calls, results):
            messages.append({"role": "tool", "tool_call_id": c.id, "content": _dump(r)})
        if run.final is not None:
            break
    return run
