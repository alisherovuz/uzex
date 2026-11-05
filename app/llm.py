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
        self.fast: bool | None = None
        self.tier: str | None = None  # OpenAI service_tier override ("priority" = faster)

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
_EFFORT_OK: dict = {}
_FAST_OK: dict = {"claude-sonnet-5-5": False, "claude-haiku-5-5": False}  # fast mode is Opus-only
_TIER_OK: dict = {}  # OpenAI service_tier support per model (disabled on first rejection)


async def claude_loop(run: Run, emit: Emit | None, deadline: float, max_turns: int = 10) -> Run:
    """Run (or continue) a Claude tool loop until final_answer is accepted."""
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
        if config.CLAUDE_EFFORT and _EFFORT_OK.get(run.model, True):
            kwargs["extra_body"] = {"output_config": {"effort": config.CLAUDE_EFFORT}}
        fast = run.fast if run.fast is not None else bool(config.CLAUDE_FAST)
        if fast and _FAST_OK.get(run.model, True):
            kwargs.setdefault("extra_body", {})["speed"] = "fast"
        try:
            resp = await asyncio.wait_for(client.messages.create(**kwargs), timeout=max(5, remaining))
        except anthropic.BadRequestError as e:
            if "speed" in str(e) and kwargs.get("extra_body", {}).pop("speed", None):
                _FAST_OK[run.model] = False
                resp = await asyncio.wait_for(client.messages.create(**kwargs), timeout=max(5, deadline - time.time()))
            elif "extra_body" in kwargs and ("effort" in str(e) or "output_config" in str(e)):
                _EFFORT_OK[run.model] = False
                kwargs.pop("extra_body")
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


# ------------------------------------------------------------------ GPT (Responses API)
def _openai_resp_tools():
    # Responses API uses a flat function-tool shape (name/description/parameters at top level).
    return [{"type": "function", "name": t["name"], "description": t["description"],
             "parameters": t["input_schema"]} for t in TOOLS]


_REASON_OK: dict = {}  # per-model: does it accept a reasoning param on the Responses API


async def gpt_loop(run: Run, emit: Emit | None, deadline: float, max_turns: int = 10) -> Run:
    """Run an OpenAI tool loop on the Responses API (GPT-5/6 reasoning models need it for tools)."""
    import openai
    client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY, max_retries=2)
    reasoning = None
    if _REASON_OK.get(run.model, True) and run.model.startswith(("gpt-5", "gpt-6", "o")):
        eff = (config.OPENAI_REASONING or "").strip()
        reasoning = {"effort": "minimal" if eff in ("", "none") else eff}
    tier = run.tier if run.tier is not None else (config.OPENAI_TIER or "")
    svc = tier if (tier and _TIER_OK.get(run.model, True)) else None
    tools = _openai_resp_tools()
    prev_id: str | None = None
    pending: list = [{"role": "user", "content": run.question}]
    for turn in range(max_turns):
        remaining = deadline - time.time()
        if remaining < 4:
            break
        if turn == max_turns - 1 or remaining < 15:
            pending.append({"role": "user", "content": "Time is almost up: call final_answer now."})
        kwargs: dict = {"model": run.model, "tools": tools, "input": pending}
        if prev_id:
            kwargs["previous_response_id"] = prev_id
        else:
            kwargs["instructions"] = get_system()
        if reasoning:
            kwargs["reasoning"] = reasoning
        if svc:
            kwargs["service_tier"] = svc
        try:
            resp = await asyncio.wait_for(client.responses.create(**kwargs), timeout=max(5, remaining))
        except openai.BadRequestError as e:
            m = str(e)
            if svc and "service_tier" in m:
                _TIER_OK[run.model] = False  # this key/model can't use the requested tier
                svc = None
                continue
            if reasoning and ("reasoning" in m or "effort" in m):
                _REASON_OK[run.model] = False
                reasoning = None
                continue
            raise
        prev_id = resp.id
        calls = [it for it in (resp.output or []) if getattr(it, "type", None) == "function_call"]
        if not calls:
            pending = [{"role": "user", "content": "Use the tools; finish by calling final_answer."}]
            continue
        args = []
        for c in calls:
            try:
                args.append(json.loads(c.arguments or "{}"))
            except json.JSONDecodeError:
                args.append({})
        results = await asyncio.gather(*[run.exec_tool(c.name, a, emit) for c, a in zip(calls, args)])
        pending = [{"type": "function_call_output", "call_id": c.call_id, "output": _dump(r)}
                   for c, r in zip(calls, results)]
        if run.final is not None:
            break
    return run
