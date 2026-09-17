// Called by GitHub Actions at the end of generate-kaggle.yml with the temp link.
export async function onRequestPost({ request, env }) {
  let body;
  try { body = await request.json(); } catch { return Response.json({ error: "bad json" }, { status: 400 }); }
  if (!env.CALLBACK_SECRET || body.secret !== env.CALLBACK_SECRET)
    return Response.json({ error: "forbidden" }, { status: 403 });
  if (!body.job_id) return Response.json({ error: "job_id required" }, { status: 400 });
  const now = Date.now();
  await env.DB.prepare(
    "UPDATE jobs SET status='done', progress='video ready', temp_url=?, updated_at=?, done_at=? WHERE id=?"
  ).bind(body.temp_url || "", now, now, body.job_id).run();
  return Response.json({ ok: true });
}
