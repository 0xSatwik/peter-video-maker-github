// why was the dispatch run (#19) cancelled? show first steps' timing + conclusion trail
const fs = require("fs");
const env = Object.fromEntries(
  fs.readFileSync(process.env.USERPROFILE + "/.peter-deploy/deploy.env", "utf8")
    .split("\n").filter((l) => l.includes("="))
    .map((l) => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
);
const repo = "0xSatwik/peter-video-maker-github";
const GH = { Authorization: "Bearer " + env.GH_PAT, Accept: "application/vnd.github+json", "User-Agent": "pvm" };

(async () => {
  const r = await (await fetch(`https://api.github.com/repos/${repo}/actions/runs/35288017679`, { headers: GH })).json();
  console.log("conclusion:", r.conclusion, "| event:", r.event, "| by:", (r.triggering_actor || {}).login);
  const jobs = await (await fetch(`https://api.github.com/repos/${repo}/actions/runs/35288017679/jobs`, { headers: GH })).json();
  for (const j of jobs.jobs || []) {
    console.log("job:", j.name, j.conclusion, "| started:", j.started_at, "| completed:", j.completed_at);
    for (const s of j.steps || []) console.log("   ", s.number, s.name, "=", s.conclusion);
  }
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });