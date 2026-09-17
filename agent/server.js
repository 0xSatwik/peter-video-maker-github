// Peter Video Maker — script agent (Render). MULTI-STEP AGENT, not single-shot.
// POST /api/plan    {topic, max_tokens?}          -> {token, script, steps, digest_chars}
// POST /api/revise  {token, instruction, script?} -> {token, script}
// GET  /health                                    -> {ok:true}
// Auth: header x-access-key must equal ACCESS_KEY.
//
// Agent pipeline (5-7 Gemini calls per request):
//   1. PLAN      -> Gemini generates 3 research angles
//   2. SEARCH    -> Monid tinyfish /search, parallel, live web
//   3. FETCH     -> Monid tinyfish /fetch full pages
//   4. EXTRACT   -> Gemini distills fresh facts (numbers, names, dates)
//   5. WRITE     -> Gemini writes the script from the fact sheet
//   6. CRITIQUE  -> Gemini checks format/facts/humor, returns improved final
//   (+ one repair retry if the format is broken)

const http = require("http");
const crypto = require("crypto");

const PORT = process.env.PORT || 3000;
const ACCESS_KEY = process.env.ACCESS_KEY || "";
const GEMINI_PROXY = process.env.GEMINI_PROXY || "";
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || "";
const GEMINI_MODEL = process.env.GEMINI_MODEL || "gemini-3.7-flash";
const MONID_KEY = process.env.MONID_KEY || "";
const MONID_BASE = process.env.MONID_BASE || "https://api.monid.ai/v1";
const MAX_SEARCH_URLS = parseInt(process.env.MAX_SEARCH_URLS || "8", 10);

const WRITER_SYS = `You write Family Guy short scripts for AI voice cloning.
Output ONLY dialogue lines, nothing else. No headers, no numbering, no blank lines, no commentary.
Each line EXACTLY: SPEAKER|TAGS|DIALOGUE
- SPEAKER is lowercase: peter or stewie. Alternate naturally.
- TAGS: comma list, e.g. male, deep, speech, excited
- DIALOGUE: 1-2 punchy sentences, in character. Peter: manchild logic, non-sequiturs. Stewie: erudite British baby, world domination, contempt for Peter.
6-10 exchanges total. Use the FACT SHEET's concrete numbers, names and dates — Peter misquotes them confidently, Stewie corrects him with the real figure. End on a joke.`;

const PLANNER_SYS = `You plan live web research for a comedy script. Given a topic, return 3 short web search queries that surface the FRESHEST concrete facts, numbers, news or stats about it. One query should target the last few days if it is a news topic.
Output ONLY a JSON array of exactly 3 strings, nothing else. Example: ["bitcoin price drop january 2026","bitcoin etf outflows latest","bitcoin regulation news this week"]`;

const EXTRACTOR_SYS = `You are a research analyst. From the raw web page extracts below, distill a FACT SHEET for a comedy writer: the freshest concrete facts only — numbers, dollar amounts, dates, names, quotes, rankings. Max 15 bullets, one line each. Discard boilerplate and anything undated/unclear. If the extracts contradict, prefer the most recent. Output ONLY the bullet list.`;

const CRITIC_SYS = `You are a ruthless script doctor for a Family Guy short. You receive a draft script and a fact sheet.
Check: (1) exact format SPEAKER|TAGS|DIALOGUE, lowercase peter/stewie, 6-10 alternating exchanges; (2) at least 2 fresh concrete facts from the fact sheet used, ideally with Peter getting one wrong and Stewie correcting; (3) actually funny, punchy, ends on a joke.
If the draft passes all checks, output it UNCHANGED. Otherwise output your improved version. Output ONLY dialogue lines, nothing else.`;

const REVISE_SYS = `You revise an existing Family Guy short script per the user instruction.
Output ONLY dialogue lines in the SAME format (SPEAKER|TAGS|DIALOGUE, lowercase peter/stewie, 6-10 exchanges). No commentary.
Keep what works, change what the instruction asks. You may use the fact sheet for fresh facts.`;

const tokens = new Map(); // token -> {topic, facts, digest, steps, ts}
const TOKEN_TTL = 30 * 60 * 1000;

function json(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type, x-access-key",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let d = "";
    req.on("data", (c) => {
      d += c;
      if (d.length > 1e6) reject(new Error("too large"));
    });
    req.on("end", () => {
      try { resolve(d ? JSON.parse(d) : {}); } catch { reject(new Error("bad json")); }
    });
    req.on("error", reject);
  });
}

async function gemini(system, user, maxTokens) {
  // Direct Gemini API (generativelanguage) if key given, else OpenAI-compat proxy.
  if (GEMINI_API_KEY) {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`;
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: system }] },
        contents: [{ role: "user", parts: [{ text: user }] }],
        generationConfig: { maxOutputTokens: maxTokens, temperature: 0.9 },
      }),
    });
    if (!r.ok) throw new Error("gemini HTTP " + r.status);
    const j = await r.json();
    const out = (j.candidates?.[0]?.content?.parts || [])
      .map((p) => p.text || "").join("").trim();
    if (!out) throw new Error("gemini empty response");
    return out;
  }
  if (GEMINI_PROXY) {
    const r = await fetch(GEMINI_PROXY, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: GEMINI_MODEL, max_tokens: maxTokens,
        messages: [{ role: "system", content: system }, { role: "user", content: user }],
      }),
    });
    if (!r.ok) throw new Error("gemini HTTP " + r.status);
    const j = await r.json();
    const out = (j.choices?.[0]?.message?.content || "").trim();
    if (!out) throw new Error("gemini empty response");
    return out;
  }
  throw new Error("no gemini configured: set GEMINI_API_KEY or GEMINI_PROXY");
}

async function monid(payload) {
  const r = await fetch(MONID_BASE.replace(/\/$/, "") + "/run", {
    method: "POST",
    headers: { Authorization: "Bearer " + MONID_KEY, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error("monid HTTP " + r.status);
  const j = await r.json(); // parse ONCE
  return j.output ?? j.result ?? j.data ?? j;
}

async function searchTinyfish(q) {
  try {
    const s = await monid({
      provider: "tinyfish", endpoint: "/search",
      input: { queryParams: { query: q, domain_type: "news", recency_minutes: 10080, purpose: "fresh facts for a comedy script" } },
    });
    const items = s?.results || s?.data?.results || s || [];
    const urls = (Array.isArray(items) ? items : []).slice(0, 3)
      .map((it) => it.url || it.link).filter(Boolean);
    console.log(`[search] "${q}" -> ${urls.length} urls`);
    return urls;
  } catch (e) {
    console.log(`[search] "${q}" failed: ${e.message}`);
    return [];
  }
}

async function fetchPages(urls) {
  if (!urls.length) return "";
  try {
    const fetched = await monid({
      provider: "tinyfish", endpoint: "/fetch",
      input: { body: { urls, format: "markdown", purpose: "fresh facts for a comedy script" } },
    });
    const pages = fetched?.results || fetched?.data?.results || [];
    let digest = "";
    for (const p of Array.isArray(pages) ? pages : []) {
      const t = (p.text || p.content || "").slice(0, 2500);
      if (t) digest += `URL: ${p.url || "?"}\n${t}\n---\n`;
    }
    return digest.slice(0, 14000);
  } catch { return ""; }
}

// Full research pipeline: plan -> parallel search -> fetch -> extract.
async function research(topic, steps) {
  if (!MONID_KEY) { steps.push("research skipped (no MONID_KEY)"); return ""; }

  // 1. PLAN
  const plan = await gemini(PLANNER_SYS, "Topic: " + topic, 300);
  let queries;
  try { queries = JSON.parse(plan.match(/\[[\s\S]*\]/)[0]); } catch { queries = [topic]; }
  queries = queries.filter((q) => typeof q === "string" && q.length > 2).slice(0, 3);
  if (!queries.length) queries = [topic];
  steps.push("planned " + queries.length + " searches");

  // 2. SEARCH (parallel live web)
  const searches = await Promise.allSettled(
    queries.map((q) => searchTinyfish(q))
  );
  const urls = [];
  for (const s of searches)
    for (const u of s.status === "fulfilled" ? s.value : [])
      if (u && urls.length < MAX_SEARCH_URLS && !urls.includes(u)) urls.push(u);
  steps.push("searched " + queries.length + " queries -> " + urls.length + " urls");
  if (!urls.length) { steps.push("no search results"); return ""; }

  // 3. FETCH
  const digest = await fetchPages(urls);
  steps.push("fetched " + (digest ? "pages ok" : "pages failed"));
  if (!digest) return "";

  // 4. EXTRACT (Gemini distills fresh facts)
  let facts = "";
  try {
    facts = await gemini(EXTRACTOR_SYS, "TOPIC: " + topic + "\n\nRAW EXTRACTS:\n" + digest, 700);
  } catch { facts = digest.slice(0, 6000); }
  steps.push("facts extracted (" + facts.length + " chars)");
  return facts;
}

const validLines = (raw) =>
  raw.split("\n").map((l) => l.trim()).filter((l) => /^(peter|stewie)\|[^|]+\|[^|]+$/i.test(l));

async function handle(req, res) {
  if (req.method === "OPTIONS") return json(res, 204, {});
  const url = new URL(req.url, "http://x");

  if (req.method === "GET" && url.pathname === "/health")
    return json(res, 200, { ok: true, agent: "multi-step", gemini: GEMINI_API_KEY ? "direct" : (GEMINI_PROXY ? "proxy" : "none"), research: !!MONID_KEY });

  const key = req.headers["x-access-key"] || "";
  if (!ACCESS_KEY || key !== ACCESS_KEY) return json(res, 401, { error: "unauthorized" });

  if (req.method === "POST" && url.pathname === "/api/plan") {
    const body = await readBody(req);
    const topic = (body.topic || "").toString().slice(0, 300);
    const maxTokens = Math.min(2000, Math.max(200, parseInt(body.max_tokens || "600", 10) || 600));
    if (!topic) return json(res, 400, { error: "topic required" });
    const steps = [];

    // Steps 1-4: plan -> search -> fetch -> extract
    const facts = await research(topic, steps);
    const factBlock = facts ? facts : "(no research available)";

    // 5. WRITE
    const raw = await gemini(
      WRITER_SYS + "\n\nFACT SHEET (freshest live-web facts, may be partial):\n" + factBlock,
      "Topic: " + topic, maxTokens
    );
    steps.push("draft written");

    // 6. CRITIQUE -> improved final
    let finalRaw = raw;
    try {
      const critiqued = await gemini(
        CRITIC_SYS + "\n\nFACT SHEET:\n" + factBlock + "\n\nDRAFT:\n" + raw,
        "Return the final script lines only.", maxTokens
      );
      if (validLines(critiqued).length >= 2) { finalRaw = critiqued; steps.push("critique pass done"); }
    } catch { steps.push("critique skipped"); }

    // 7. repair retry if format broken
    let lines = validLines(finalRaw);
    if (lines.length < 2) {
      steps.push("format repair retry");
      try {
        const retry = await gemini(
          WRITER_SYS, "Topic: " + topic + "\nFACTS:\n" + factBlock +
          "\nYour previous attempt was invalid. Output ONLY valid SPEAKER|TAGS|DIALOGUE lines:", maxTokens
        );
        lines = validLines(retry);
      } catch { /* fall through */ }
    }
    if (lines.length < 2) return json(res, 502, { error: "no valid lines", steps, raw: finalRaw.slice(0, 500) });

    const token = crypto.randomUUID();
    tokens.set(token, { topic, facts: factBlock, steps, ts: Date.now() });
    return json(res, 200, { token, script: lines.join("\n"), digest_chars: factBlock.length, steps });
  }

  if (req.method === "POST" && url.pathname === "/api/revise") {
    const body = await readBody(req);
    const instruction = (body.instruction || "").toString().slice(0, 500);
    const script = (body.script || "").toString().slice(0, 8000);
    if (!instruction) return json(res, 400, { error: "instruction required" });
    if (!script) return json(res, 400, { error: "script required" });
    const t = tokens.get(body.token);
    if (t) tokens.set(body.token, { ...t, ts: Date.now() });
    const facts = t ? t.facts : "(no research available)";
    const steps = [];
    const raw = await gemini(
      REVISE_SYS + "\n\nCURRENT SCRIPT:\n" + script +
      "\n\nFACT SHEET (freshest live-web facts):\n" + facts,
      "Instruction: " + instruction, 800
    );
    let lines = validLines(raw);
    if (lines.length < 2) {
      steps.push("format repair retry");
      try {
        const retry = await gemini(
          REVISE_SYS, "Instruction: " + instruction +
          "\nCURRENT SCRIPT:\n" + script +
          "\nFACTS:\n" + facts +
          "\nYour previous attempt was invalid. Output ONLY valid SPEAKER|TAGS|DIALOGUE lines:", 800
        );
        lines = validLines(retry);
      } catch { /* fall through */ }
    }
    if (lines.length < 2) return json(res, 502, { error: "no valid lines", steps, raw: raw.slice(0, 500) });
    return json(res, 200, { token: body.token || null, script: lines.join("\n"), steps });
  }

  return json(res, 404, { error: "not found" });
}

setInterval(() => {
  const now = Date.now();
  for (const [k, v] of tokens) if (now - v.ts > TOKEN_TTL) tokens.delete(k);
}, 60000);

http.createServer((req, res) => handle(req, res).catch((e) => json(res, 500, { error: String(e.message || e) })))
  .listen(PORT, () => console.log("agent up on", PORT));
