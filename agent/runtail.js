// tail the live log of the in-progress run
const fs = require("fs");
const env = Object.fromEntries(
  fs.readFileSync(process.env.USERPROFILE + "/.peter-deploy/deploy.env", "utf8")
    .split("\n").filter((l) => l.includes("="))
    .map((l) => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
);
const repo = "0xSatwik/peter-video-maker-github";
const GH = { Authorization: "Bearer " + env.GH_PAT, Accept: "application/vnd.github+json", "User-Agent": "pvm" };
const target = Number(process.argv[2] || 21);

(async () => {
  const runs = await (await fetch(`https://api.github.com/repos/${repo}/actions/workflows/generate-kaggle.yml/runs?per_page=8`, { headers: GH })).json();
  const r = (runs.workflow_runs || []).find((x) => x.run_number === target);
  if (!r) { console.log("run not found"); process.exit(1); }
  console.log(`#${r.run_number} ${r.status}/${r.conclusion} event=${r.event} started=${r.run_started_at}`);
  const jobs = await (await fetch(`https://api.github.com/repos/${repo}/actions/runs/${r.id}/jobs`, { headers: GH })).json();
  for (const j of jobs.jobs || []) {
    console.log("job:", j.name, j.status, j.conclusion);
    for (const s of j.steps || []) {
      if (s.status === "in_progress" || s.conclusion === "failure") console.log("  ACTIVE/FAILED:", s.name, s.status, s.conclusion);
    }
    const lr = await fetch(`https://api.github.com/repos/${repo}/actions/jobs/${j.id}/logs`, { headers: GH });
    const txt = await lr.text();
    if (txt.startsWith("<?xml")) { console.log("  (logs not downloadable yet)"); continue; }
    const lines = txt.split("\n").filter((l) => l.trim());
    console.log("  --- last 12 log lines ---");
    for (const l of lines.slice(-12)) console.log("  ", l.replace(/[^\x20-\x7e]/g, "").slice(0, 180));
  }
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });