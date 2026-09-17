// show logs of run 13 (the failed dispatch)
const fs = require("fs");
const env = Object.fromEntries(
  fs.readFileSync(process.env.USERPROFILE + "/.peter-deploy/deploy.env", "utf8")
    .split("\n").filter((l) => l.includes("="))
    .map((l) => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
);
const repo = "0xSatwik/peter-video-maker-github";
const GH = { Authorization: "Bearer " + env.GH_PAT, Accept: "application/vnd.github+json", "User-Agent": "pvm" };

(async () => {
  const runs = await (await fetch(`https://api.github.com/repos/${repo}/actions/workflows/generate-kaggle.yml/runs?per_page=3`, { headers: GH })).json();
  const r = (runs.workflow_runs || []).find((x) => x.run_number === 13);
  console.log("run 13:", r.status, r.conclusion);
  const jobs = await (await fetch(`https://api.github.com/repos/${repo}/actions/runs/${r.id}/jobs`, { headers: GH })).json();
  for (const j of jobs.jobs) {
    console.log("job:", j.name, j.conclusion);
    for (const s of j.steps || []) console.log("  step:", s.name, "=", s.conclusion);
    const lr = await fetch(`https://api.github.com/repos/${repo}/actions/jobs/${j.id}/logs`, { headers: GH });
    const txt = await lr.text();
    if (txt.startsWith("<?xml")) { console.log("  (logs not ready)"); continue; }
    const errs = txt.split("\n").filter((l) => /error|Error|Traceback|FATAL|FAIL|exited with|quota|denied/i.test(l) && !/punycode|DEP0040|secure_node|0 errors/i.test(l));
    for (const l of errs.slice(-14)) console.log("  ", l.replace(/[^\x20-\x7e]/g, "").slice(0, 190));
  }
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });