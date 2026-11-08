import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';

const PORT = Number(process.env.PORT || 3000);
const ROOT = new URL('./public/', import.meta.url).pathname;
const KNOWLEDGE = readFileSync(new URL('./knowledge.md', import.meta.url), 'utf8');
const MODEL = process.env.CLAUDE_MODEL || 'claude-sonnet-5-5';
const PHONE = process.env.IBEK_PHONE || '';

const SYSTEM = `You are the iBek assistant on the iBek website. Hackathon judges and visitors use you to ask the questions they could not ask during the team's 3-minute pitch.

Answer from the knowledge base below. Rules:
- Reply in the language the user writes or speaks in (Uzbek, Russian or English).
- Be direct and concise: 2-6 sentences or a short list, unless the user asks for depth. Your answer may be read aloud, so avoid tables and heavy markdown; plain sentences and short "-" lists are fine.
- Use numbers and the worked example when they help.
- Be honest: iBek is a prototype designed for 2035. If something is planned, an estimate, or still an open question, say so. If the knowledge base does not cover something, say you don't know and suggest asking the team; never invent facts, figures, partners or prices.
- Always call the project iBek (never "Aniq").
- The iBek phone number for SMS and calls: ${PHONE || 'shown on this website'}.

<knowledge_base>
${KNOWLEDGE}
</knowledge_base>`;

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.json': 'application/json' };

// simple per-IP rate limit: 30 questions / 10 min
const hits = new Map();
function limited(ip) {
  const t = Date.now(), w = 10 * 60_000;
  const arr = (hits.get(ip) || []).filter((x) => t - x < w);
  arr.push(t); hits.set(ip, arr);
  return arr.length > 30;
}

async function readBody(req, max = 64_000) {
  let s = '';
  for await (const c of req) { s += c; if (s.length > max) throw new Error('too large'); }
  return s ? JSON.parse(s) : {};
}

async function chat(req, res) {
  const ip = (req.headers['x-forwarded-for'] || req.socket.remoteAddress || '').toString().split(',')[0].trim();
  if (limited(ip)) { res.writeHead(429, { 'content-type': 'application/json' }); return res.end(JSON.stringify({ error: 'Too many questions — please wait a few minutes.' })); }
  if (!process.env.ANTHROPIC_API_KEY) { res.writeHead(503, { 'content-type': 'application/json' }); return res.end(JSON.stringify({ error: 'The assistant is not configured yet (missing API key).' })); }
  let body;
  try { body = await readBody(req); } catch { res.writeHead(400); return res.end(); }
  const messages = (Array.isArray(body.messages) ? body.messages : [])
    .filter((m) => (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string' && m.content.trim())
    .slice(-16).map((m) => ({ role: m.role, content: m.content.slice(0, 4000) }));
  if (!messages.length || messages[messages.length - 1].role !== 'user') { res.writeHead(400); return res.end(); }

  const upstream = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-api-key': process.env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01' },
    body: JSON.stringify({ model: MODEL, max_tokens: 1024, stream: true, system: [{ type: 'text', text: SYSTEM, cache_control: { type: 'ephemeral' } }], messages }),
  }).catch((e) => ({ ok: false, status: 502, text: async () => e.message }));

  if (!upstream.ok) {
    const detail = await upstream.text();
    console.error('anthropic error', upstream.status, detail.slice(0, 300));
    res.writeHead(502, { 'content-type': 'application/json' });
    return res.end(JSON.stringify({ error: 'The assistant is unavailable right now. Please try again.' }));
  }

  res.writeHead(200, { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-cache', 'x-accel-buffering': 'no' });
  const reader = upstream.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
        if (!line.startsWith('data:')) continue;
        try {
          const ev = JSON.parse(line.slice(5));
          if (ev.type === 'content_block_delta' && ev.delta?.type === 'text_delta') res.write(ev.delta.text);
        } catch {}
      }
    }
  } catch (e) { console.error('stream error', e.message); }
  res.end();
}

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  try {
    if (url.pathname === '/api/chat' && req.method === 'POST') return await chat(req, res);
    if (url.pathname === '/api/config') { res.writeHead(200, { 'content-type': 'application/json' }); return res.end(JSON.stringify({ phone: PHONE, ready: !!process.env.ANTHROPIC_API_KEY })); }
    if (url.pathname === '/health') { res.writeHead(200); return res.end('ok'); }
    let p = normalize(decodeURIComponent(url.pathname)).replace(/^(\.\.[/\\])+/, '');
    if (p.endsWith('/')) p += 'index.html';
    const file = join(ROOT, p);
    if (!file.startsWith(ROOT)) { res.writeHead(403); return res.end(); }
    const data = await readFile(file).catch(() => null);
    if (!data) { res.writeHead(404); return res.end('Not found'); }
    res.writeHead(200, { 'content-type': TYPES[extname(file)] || 'application/octet-stream' });
    res.end(data);
  } catch (e) {
    console.error(e);
    if (!res.headersSent) res.writeHead(500);
    res.end();
  }
}).listen(PORT, () => console.log('iBek on :' + PORT));
