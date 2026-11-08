import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';

const PORT = Number(process.env.PORT || 3000);
const ROOT = new URL('./public/', import.meta.url).pathname;
const KNOWLEDGE = readFileSync(new URL('./knowledge.md', import.meta.url), 'utf8');
const MODEL = process.env.CLAUDE_MODEL || 'claude-sonnet-5-5';
const PHONE = process.env.IBEK_PHONE || '';
const EL = { key: process.env.ELEVENLABS_API_KEY, voice: process.env.ELEVENLABS_VOICE_ID, model: process.env.ELEVENLABS_MODEL || 'eleven_v3' };
const ttsReady = () => !!(EL.key && EL.voice);

const SYSTEM = `You are the iBek assistant on the iBek website. Hackathon judges and visitors use you to ask the questions they could not ask during the team's 3-minute pitch.

Answer from the knowledge base below. Rules:
- Reply in the language the user writes or speaks in (Uzbek, Russian or English).
- Format for a premium answer card. Keep it very short and simple, for a busy judge: 2-3 plain sentences. Use 2-4 short "- " bullets only when the user asks for steps, a list or details. Wrap at most two key numbers or terms in **double asterisks** (they are highlighted). Avoid jargon; explain like to a smart non-expert. No headings, no tables, no emoji, no exclamation marks. Answers may be read aloud.
- When one number or short value is the heart of the answer (a price, a percentage, a count), START the reply with a stat block, then the text:
  \`\`\`stat
  {"value":"$105","label":"clearing price per tonne, paid by every winner"}
  \`\`\`
  Use it only when it genuinely fits; never invent the number.
- Tone: serious, confident, understated, like a senior product lead. Focus on what it means for the user.
- Use numbers and the worked example when they help.
- Be honest: iBek is a prototype designed for 2035. If something is planned, an estimate, or still an open question, say so. If the knowledge base does not cover something, say you don't know and suggest asking the team; never invent facts, figures, partners or prices.
- Always call the project iBek (never "Aniq").
- You can show visuals. You are not limited to text. Only when the user explicitly asks for a picture, graph, chart, infographic, diagram or 'show me', include ONE visual block after the short text answer (visuals are slow to generate, so never add one unprompted). Never say you cannot show pictures.
  Chart: a fenced block with language "chart" containing JSON only:
  \`\`\`chart
  {"type":"bar|hbar|line","title":"short title","unit":"unit label","labels":["A","B"],"series":[{"name":"series","values":[1,2]}],"note":"source or caption"}
  \`\`\`
  Use hbar for long category names, line for change over time, bar for comparisons. Numbers must come from the knowledge base or simple arithmetic on it; never invent data.
  Diagram or infographic: a fenced block with language "svg" containing one complete <svg> with xmlns="http://www.w3.org/2000/svg", viewBox="0 0 640 400" (height can vary up to 640), a white background rect, generous spacing, font-family="Inter, -apple-system, Helvetica, Arial, sans-serif", the iBek visual style: black-and-white hand-drawn line art like a clean sketchbook (stroke #111418, stroke-width 1.6-2, fill #ffffff, optional diagonal hatch pattern defined in <defs> for emphasis, #6b7280 gray for secondary text; no other colors), simple line icons, small corner radius (rx 4-8). No scripts, no external images or fonts. Keep the SVG compact (under about 35 elements) so it finishes fast. Prefer a chart block over SVG whenever the content is numbers. Keep text short (labels, not paragraphs) and make sure no text overlaps or overflows its box; keep every text element at least 24px inside the left and right edges (estimate ~7.5px per character at 13px). Good uses: the auction worked example, the two doors flow, the round lifecycle (open → sealed bids → clear at one price → verify), how limits protect the user.
  Write the text part in the user's language; labels inside visuals may use the same language.
- The iBek phone number for SMS and calls: ${PHONE || 'shown on this website'}.

<knowledge_base>
${KNOWLEDGE}
</knowledge_base>`;

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.json': 'application/json' };

// simple per-IP rate limit: 30 questions / 10 min
const hits = new Map();
function limited(ip, max = 30) {
  const t = Date.now(), w = 10 * 60_000;
  const arr = (hits.get(ip) || []).filter((x) => t - x < w);
  arr.push(t); hits.set(ip, arr);
  return arr.length > max;
}

async function readBody(req, max = 64_000) {
  let s = '';
  for await (const c of req) { s += c; if (s.length > max) throw new Error('too large'); }
  return s ? JSON.parse(s) : {};
}

async function tts(req, res, url) {
  const ip = (req.headers['x-forwarded-for'] || req.socket.remoteAddress || '').toString().split(',')[0].trim();
  if (!ttsReady()) { res.writeHead(503); return res.end(); }
  if (limited('tts:' + ip, 200)) { res.writeHead(429); return res.end(); }
  let text = '', lang = '';
  if (req.method === 'GET') { text = url.searchParams.get('t') || ''; lang = url.searchParams.get('l') || ''; }
  else { try { const b = await readBody(req); text = String(b.text || ''); lang = String(b.lang || ''); } catch { res.writeHead(400); return res.end(); } }
  text = text.slice(0, 1200).trim();
  if (!text) { res.writeHead(400); return res.end(); }
  // Uzbek needs eleven_v3; Russian/English use the much faster flash model
  const isUz = lang === 'uz' || (!/[а-яё]/i.test(text) && /(o['‘’]|g['‘’]|\b(va|uchun|bilan|bu|narx|tonna|qiladi|emas)\b)/i.test(text));
  const model = isUz ? EL.model : (process.env.ELEVENLABS_FAST_MODEL || 'eleven_flash_v2_5');
  const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(EL.voice)}/stream?output_format=mp3_44100_64`, {
    method: 'POST',
    headers: { 'xi-api-key': EL.key, 'content-type': 'application/json', accept: 'audio/mpeg' },
    body: JSON.stringify({ text, model_id: model }),
  }).catch((e) => ({ ok: false, status: 502, text: async () => e.message }));
  if (!r.ok) { console.error('tts error', r.status, model, (await r.text()).slice(0, 300)); res.writeHead(502); return res.end(); }
  res.writeHead(200, { 'content-type': 'audio/mpeg', 'cache-control': 'no-store', 'x-accel-buffering': 'no' });
  const rd = r.body.getReader();
  try { for (;;) { const { done, value } = await rd.read(); if (done) break; res.write(Buffer.from(value)); } } catch (e) { console.error('tts stream', e.message); }
  res.end();
}

function normPhone(p) {
  const d = String(p || '').replace(/\D/g, '');
  if (/^998\d{9}$/.test(d)) return '+' + d;
  if (/^\d{9}$/.test(d)) return '+998' + d;
  if (/^\d{10,15}$/.test(d) && String(p).trim().startsWith('+')) return '+' + d;
  return null;
}
async function call(req, res) {
  const ip = (req.headers['x-forwarded-for'] || req.socket.remoteAddress || '').toString().split(',')[0].trim();
  const send = (code, o) => { res.writeHead(code, { 'content-type': 'application/json' }); res.end(JSON.stringify(o)); };
  if (limited('call:' + ip, 4)) return send(429, { ok: false, reason: 'rate' });
  let b; try { b = await readBody(req); } catch { return send(400, { ok: false }); }
  const phone = normPhone(b.phone);
  if (!phone) return send(200, { ok: false, reason: 'phone' });
  const base = process.env.AUCTION_URL || 'https://aniq-auksion.livops.app';
  try {
    const r = await fetch(base + '/api/voice/call', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ phone, buyer: 'web:' + phone.slice(1), name: 'iBek web' }) });
    const j = await r.json().catch(() => ({}));
    console.log('call', phone.slice(0, 7) + '…', j.ok ? 'ok' : 'fail', j.reason || '');
    return send(200, { ok: !!j.ok, reason: j.ok ? undefined : 'upstream', detail: j.reason });
  } catch (e) { console.error('call error', e.message); return send(200, { ok: false, reason: 'upstream' }); }
}

// ---------- live demo call (hidden /demo page) ----------
async function demoCall(req, res) {
  const send = (code, o) => { res.writeHead(code, { 'content-type': 'application/json', 'cache-control': 'no-store' }); res.end(JSON.stringify(o)); };
  let b; try { b = await readBody(req); } catch { return send(400, { ok: false, reason: 'bad request' }); }
  if (!process.env.DEMO_PIN || String(b.pin || '') !== process.env.DEMO_PIN) return send(403, { ok: false, reason: 'Wrong PIN' });
  const to = normPhone(b.to || process.env.DEMO_TO);
  const agent = process.env.DEMO_AGENT_ID || process.env.ELEVENLABS_AGENT_ID;
  const phoneId = process.env.ELEVENLABS_PHONE_NUMBER_ID;
  if (!to || !agent || !phoneId || !EL.key) return send(200, { ok: false, reason: 'Demo not configured (number/agent/phone id)' });
  const t0 = Date.now();
  try {
    const r = await fetch('https://api.elevenlabs.io/v1/convai/sip-trunk/outbound-call', {
      method: 'POST', headers: { 'xi-api-key': EL.key, 'content-type': 'application/json' },
      body: JSON.stringify({ agent_id: agent, agent_phone_number_id: phoneId, to_number: to,
        conversation_initiation_client_data: { dynamic_variables: { buyer_id: 'demo', purpose: 'demo', lots: '', result_text: '' } },
        telephony_call_config: { ringing_timeout_secs: 45 } }),
    });
    const j = await r.json().catch(() => ({}));
    const ok = r.ok && j.success !== false;
    console.log('demo call', to.slice(0, 7) + '…', ok ? 'ok' : 'fail', r.status, JSON.stringify(j).slice(0, 300));
    return send(200, { ok, ms: Date.now() - t0, conversation: j.conversation_id, reason: ok ? undefined : (j.message || j.detail?.message || JSON.stringify(j.detail || j).slice(0, 200)) });
  } catch (e) { return send(200, { ok: false, reason: e.message }); }
}
async function demoStatus(req, res, url) {
  const send = (code, o) => { res.writeHead(code, { 'content-type': 'application/json', 'cache-control': 'no-store' }); res.end(JSON.stringify(o)); };
  if (!process.env.DEMO_PIN || url.searchParams.get('pin') !== process.env.DEMO_PIN) return send(403, {});
  const id = url.searchParams.get('id'); if (!id) return send(400, {});
  const r = await fetch('https://api.elevenlabs.io/v1/convai/conversations/' + encodeURIComponent(id), { headers: { 'xi-api-key': EL.key } }).catch(() => null);
  if (!r || !r.ok) return send(200, { status: 'unknown' });
  const j = await r.json();
  const last = (j.transcript || []).slice(-2).map((m) => ({ role: m.role, text: (m.message || '').slice(0, 160) }));
  return send(200, { status: j.status, duration: j.metadata?.call_duration_secs, reason: j.metadata?.termination_reason, last });
}

// ---------- app-call backup (/live) ----------
let ringAt = 0;
async function liveRing(req, res, url) {
  const send = (code, o) => { res.writeHead(code, { 'content-type': 'application/json', 'cache-control': 'no-store' }); res.end(JSON.stringify(o)); };
  if (req.method === 'POST') {
    let b; try { b = await readBody(req); } catch { return send(400, {}); }
    if (!process.env.DEMO_PIN || String(b.pin || '') !== process.env.DEMO_PIN) return send(403, { ok: false, reason: 'Wrong PIN' });
    ringAt = b.cancel ? 0 : Date.now(); console.log('live ring', b.cancel ? 'cancel' : 'set');
    return send(200, { ok: true });
  }
  if (!process.env.DEMO_PIN || url.searchParams.get('k') !== process.env.DEMO_PIN) return send(403, {});
  return send(200, { ring: ringAt && Date.now() - ringAt < 45000 ? ringAt : 0 });
}
async function liveToken(req, res, url) {
  const send = (code, o) => { res.writeHead(code, { 'content-type': 'application/json', 'cache-control': 'no-store' }); res.end(JSON.stringify(o)); };
  if (!process.env.DEMO_PIN || url.searchParams.get('k') !== process.env.DEMO_PIN) return send(403, {});
  const agent = process.env.DEMO_AGENT_ID || process.env.ELEVENLABS_AGENT_ID;
  const r = await fetch('https://api.elevenlabs.io/v1/convai/conversation/get-signed-url?agent_id=' + encodeURIComponent(agent), { headers: { 'xi-api-key': EL.key } }).catch((e) => ({ ok: false, status: 0, text: async () => e.message }));
  if (!r.ok) { const t = await r.text(); console.error('live token', r.status, t.slice(0, 200)); return send(502, { error: 'token' }); }
  const j = await r.json(); ringAt = 0;
  return send(200, { signedUrl: j.signed_url });
}

async function chat(req, res) {
  const ip = (req.headers['x-forwarded-for'] || req.socket.remoteAddress || '').toString().split(',')[0].trim();
  if (limited(ip)) { res.writeHead(429, { 'content-type': 'application/json' }); return res.end(JSON.stringify({ error: 'Too many questions — please wait a few minutes.' })); }
  if (!process.env.ANTHROPIC_API_KEY) { res.writeHead(503, { 'content-type': 'application/json' }); return res.end(JSON.stringify({ error: 'The assistant is not configured yet (missing API key).' })); }
  let body;
  try { body = await readBody(req); } catch { res.writeHead(400); return res.end(); }
  const uiLang = { uz: 'Uzbek (Latin script)', ru: 'Russian', en: 'English' }[body.lang] || '';
  const messages = (Array.isArray(body.messages) ? body.messages : [])
    .filter((m) => (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string' && m.content.trim())
    .slice(-16).map((m) => ({ role: m.role, content: m.content.slice(0, 4000) }));
  if (!messages.length || messages[messages.length - 1].role !== 'user') { res.writeHead(400); return res.end(); }

  const upstream = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-api-key': process.env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01' },
    body: JSON.stringify({ model: MODEL, max_tokens: 3500, stream: true, system: [{ type: 'text', text: SYSTEM, cache_control: { type: 'ephemeral' } }, ...(uiLang ? [{ type: 'text', text: `The site interface is set to ${uiLang}. Reply in the language of the user's message; if it is ambiguous (very short, a name, a number), reply in ${uiLang}.` }] : [])], messages }),
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
    if (url.pathname === '/api/tts') return await tts(req, res, url);
    if (url.pathname === '/api/call' && req.method === 'POST') return await call(req, res);
    if (url.pathname === '/api/demo-call' && req.method === 'POST') return await demoCall(req, res);
    if (url.pathname === '/api/demo-status') return await demoStatus(req, res, url);
    if (url.pathname === '/api/live-ring') return await liveRing(req, res, url);
    if (url.pathname === '/api/live-token') return await liveToken(req, res, url);
    if (url.pathname === '/demo' || url.pathname === '/demo/') url.pathname = '/demo.html';
    if (url.pathname === '/live' || url.pathname === '/live/') url.pathname = '/live.html';
    if (url.pathname === '/api/config') { res.writeHead(200, { 'content-type': 'application/json' }); return res.end(JSON.stringify({ phone: PHONE, ready: !!process.env.ANTHROPIC_API_KEY, tts: ttsReady() })); }
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
