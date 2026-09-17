// Recent jobs for the history panel (key-gated)
function authed(req, env) {
  const k = req.headers.get("x-access-key") || "";
  return !!env.ACCESS_KEY && k.length > 0 && k.length === env.ACCESS_KEY.length &&
    [...k].every((c, i) => c === env.ACCESS_KEY[i]);
}

export async function onRequestGet({ request, env }) {
  if (!authed(request, env)) return Response.json({ error: "unauthorized" }, { status: 401 });
  const j = await env.DB.prepare(
    "SELECT id, topic, status, progress, created_at, done_at, temp_url FROM jobs ORDER BY created_at DESC LIMIT 20"
  ).all();
  return Response.json({ jobs: j.results || [] });
}