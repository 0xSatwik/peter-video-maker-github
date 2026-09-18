// per-step durations for the last few runs -> find where the time goes
const fs = require("fs");
const env = Object.fromEntries(
  fs.readFileSync(process.env.USERPROFILE + "/.peter-deploy/deploy.env", "utf8")
    .split("\n").filter((l) => l.includes("="))
    .map((l) => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
);
const GH = { Authorization: "Bearer " + env.GH_PAT, Accept: "application/vnd.github+json", "User-Agent": "pvm" };
const repo = "0xSatwik/peter-video-maker-github";

(async () => {
  const runs = await (await fetch(`https://api.github.com/repos/${repo}/actions/workflows/generate-kaggle.yml/runs?per_page=10`, { headers: GH })).json();
  const good = (runs.workflow_runs || []).filter((x) => !(x.status === "completed" && x.conclusion === "skipped")).slice(0, 3);
  for (const r of good) {
    console.log(`\n=== run #${r.run_number} (${r.conclusion}) total ${((new Date(r.updated_at) - new Date(r.created_at)) / 60000).toFixed(1)} min ===`);
    const jobs = await (await fetch(`https://api.github.com/repos/${repo}/actions/runs/${r.id}/jobs`, { headers: GH })).json();
    for (const j of jobs.jobs || []) {
      for (const s of j.steps || []) {
        if (!s.started_at || !s.completed_at) continue;
        const sec = (new Date(s.completed_at) - new Date(s.started_at)) / 1000;
        if (sec >= 1) console.log(`  ${sec.toFixed(0).padStart(5)}s  ${s.name}`);
      }
    }
  }
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });