function authed(req, env) {
  const k = req.headers.get("x-access-key") || "";
  return !!env.ACCESS_KEY && k.length > 0 && k.length === env.ACCESS_KEY.length &&
    [...k].every((c, i) => c === env.ACCESS_KEY[i]);
}

export async function onRequestGet({ request, env }) {
  if (!authed(request, env)) return Response.json({ error: "unauthorized" }, { status: 401 });
  const id = new URL(request.url).searchParams.get("id") || "";
  if (!id) return Response.json({ error: "id required" }, { status: 400 });
  const job = await env.DB.prepare("SELECT * FROM jobs WHERE id=?").bind(id).first();
  if (!job) return Response.json({ error: "not found" }, { status: 404 });
  if (job.status === "done" || job.status === "error") return Response.json(job);

  // Live GitHub run state for the Kaggle workflow (matched by recency)
  try {
    const repo = env.GITHUB_REPO;
    const gh = { Authorization: "Bearer " + env.GITHUB_PAT, Accept: "application/vnd.github+json", "User-Agent": "peter-video-maker" };
    const r = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/generate-kaggle.yml/runs?per_page=8`, { headers: gh });
    if (r.ok) {
      const runs = (await r.json()).workflow_runs || [];
      // Ignore de-duped push runs (conclusion "skipped") and stale runs.
      const mine = runs.find(
        (x) => new Date(x.created_at).getTime() > job.created_at - 120000 &&
          !(x.status === "completed" && x.conclusion === "skipped")
      );
      if (mine && (!job.run_id || job.run_id === mine.id)) {
        let status = job.status, progress = job.progress;
        if (mine.status === "queued") { status = "gh_queued"; progress = "GitHub runner queued"; }
        else if (mine.status === "in_progress") { status = "kaggle_tts"; progress = "TTS running (job " + mine.run_number + ")"; }
        else if (mine.status === "completed" && mine.conclusion === "success") { status = "assembling"; progress = "audio done, assembling video"; }
        else if (mine.status === "completed") { status = "error"; progress = "run " + mine.conclusion; }
        await env.DB.prepare("UPDATE jobs SET status=?, progress=?, run_id=?, updated_at=? WHERE id=?")
          .bind(status, progress, mine.id, Date.now(), id).run();
        job.status = status; job.progress = progress; job.run_id = mine.id;
      }
    }
  } catch { /* keep last known state */ }
  return Response.json(job);
}
