function authed(req, env) {
  const k = req.headers.get("x-access-key") || "";
  return !!env.ACCESS_KEY && k.length > 0 && k.length === env.ACCESS_KEY.length &&
    [...k].every((c, i) => c === env.ACCESS_KEY[i]);
}

const SYS = `You write Family Guy short scripts for AI voice cloning.
Output ONLY dialogue lines, nothing else. No headers, no numbering, no blank lines, no commentary.
Each line EXACTLY: SPEAKER|TAGS|DIALOGUE
- SPEAKER is lowercase: peter or stewie. Alternate naturally.
- TAGS: comma list, e.g. male, deep, speech, excited
- DIALOGUE: 1-2 punchy sentences, in character. Peter: manchild logic, non-sequiturs. Stewie: erudite British baby, world domination, contempt for Peter.
6-10 exchanges total. End on a joke.`;

export async function onRequestPost({ request, env }) {
  if (!authed(request, env)) return Response.json({ error: "unauthorized" }, { status: 401 });
  let body;
  try { body = await request.json(); } catch { return Response.json({ error: "bad json" }, { status: 400 }); }
  const topic = (body.topic || "").toString().slice(0, 300);
  if (!topic) return Response.json({ error: "topic required" }, { status: 400 });
  const maxTokens = Math.min(2000, Math.max(200, parseInt(body.max_tokens || "600", 10) || 600));

  // 1. Gemini writes the script
  const g = await fetch(env.GEMINI_PROXY, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: env.GEMINI_MODEL || "gemini-3.7-flash",
      max_tokens: maxTokens,
      messages: [
        { role: "system", content: SYS },
        { role: "user", content: "Topic: " + topic },
      ],
    }),
  });
  if (!g.ok) return Response.json({ error: "gemini proxy HTTP " + g.status }, { status: 502 });
  const gj = await g.json();
  const raw = (gj.choices?.[0]?.message?.content || "").trim();
  const lines = raw.split("\n").map((l) => l.trim())
    .filter((l) => /^(peter|stewie)\|[^|]+\|[^|]+$/i.test(l));
  if (lines.length < 2) return Response.json({ error: "gemini returned no valid lines", raw: raw.slice(0, 500) }, { status: 502 });

  // 2. Commit script to repo (job id embedded; '#' lines are ignored by the TTS parser)
  const id = crypto.randomUUID();
  const fname = `config/scripts/AUTO_${Date.now()}.txt`;
  const content = `# JOB:${id}\n# TOPIC:${topic}\n` + lines.join("\n") + "\n";
  const b64 = btoa(unescape(encodeURIComponent(content)));
  const repo = env.GITHUB_REPO;
  const gh = { Authorization: "Bearer " + env.GITHUB_PAT, Accept: "application/vnd.github+json", "Content-Type": "application/json" };
  const put = await fetch(`https://api.github.com/repos/${repo}/contents/${fname}`, {
    method: "PUT", headers: gh,
    body: JSON.stringify({ message: `Auto script for ${id}`, content: b64 }),
  });
  if (!put.ok) return Response.json({ error: "github commit failed: " + put.status }, { status: 502 });

  // 3. Dispatch Kaggle pipeline
  const disp = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/generate-kaggle.yml/dispatches`, {
    method: "POST", headers: gh,
    body: JSON.stringify({ ref: "main", inputs: { script_file: fname } }),
  });
  if (!disp.ok && disp.status !== 204) return Response.json({ error: "dispatch failed: " + disp.status }, { status: 502 });

  const now = Date.now();
  await env.DB.prepare(
    "INSERT INTO jobs (id, topic, script_file, script, status, progress, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)"
  ).bind(id, topic, fname, lines.join("\n"), "gh_queued", "script committed, pipeline dispatched", now, now).run();

  return Response.json({ id });
}
