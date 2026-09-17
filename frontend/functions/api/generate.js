function authed(req, env) {
  const k = req.headers.get("x-access-key") || "";
  return !!env.ACCESS_KEY && k.length > 0 && k.length === env.ACCESS_KEY.length &&
    [...k].every((c, i) => c === env.ACCESS_KEY[i]);
}

export async function onRequestPost({ request, env }) {
  if (!authed(request, env)) return Response.json({ error: "unauthorized" }, { status: 401 });
  let body;
  try { body = await request.json(); } catch { return Response.json({ error: "bad json" }, { status: 400 }); }
  const topic = (body.topic || "").toString().slice(0, 300);
  const script = (body.script || "").toString().slice(0, 8000);
  if (!topic) return Response.json({ error: "topic required" }, { status: 400 });

  // Script is drafted + approved by the user via the Render agent.
  const lines = script.split("\n").map((l) => l.trim())
    .filter((l) => /^(peter|stewie)\|[^|]+\|[^|]+$/i.test(l));
  if (lines.length < 2)
    return Response.json({ error: "invalid script: need peter|tags|text lines (draft via agent first)" }, { status: 400 });

  // Commit script to repo (job id embedded; '#' lines are ignored by the TTS parser)
  const id = crypto.randomUUID();
  const fname = `config/scripts/AUTO_${Date.now()}.txt`;
  const content = `# JOB:${id}\n# TOPIC:${topic}\n` + lines.join("\n") + "\n";
  const b64 = btoa(unescape(encodeURIComponent(content)));
  const repo = env.GITHUB_REPO;
  const gh = { Authorization: "Bearer " + env.GITHUB_PAT, Accept: "application/vnd.github+json", "Content-Type": "application/json", "User-Agent": "peter-video-maker" };
  const put = await fetch(`https://api.github.com/repos/${repo}/contents/${fname}`, {
    method: "PUT", headers: gh,
    body: JSON.stringify({ message: `Auto script for ${id}`, content: b64 }),
  });
  if (!put.ok) return Response.json({ error: "github commit failed: " + put.status }, { status: 502 });

  // Dispatch Kaggle pipeline (GitHub Actions + Kaggle handle the rest, then auto-stop)
  const disp = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/generate-kaggle.yml/dispatches`, {
    method: "POST", headers: gh,
    body: JSON.stringify({ ref: "main", inputs: { script_file: fname } }),
  });
  if (!disp.ok && disp.status !== 204) return Response.json({ error: "dispatch failed: " + disp.status }, { status: 502 });

  const now = Date.now();
  await env.DB.prepare(
    "INSERT INTO jobs (id, topic, script_file, script, status, progress, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)"
  ).bind(id, topic, fname, lines.join("\n"), "gh_queued", "script approved, pipeline dispatched", now, now).run();

  return Response.json({ id });
}
