// grep the latest run log for TTS engine evidence (OmniVoice vs CPU fallback)
const fs = require("fs");
const env = Object.fromEntries(
  fs.readFileSync(process.env.USERPROFILE + "/.peter-deploy/deploy.env", "utf8")
    .split("\n").filter((l) => l.includes("="))
    .map((l) => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
);
const repo = "0xSatwik/peter-video-maker-github";
const GH = { Authorization: "Bearer " + env.GH_PAT, Accept: "application/vnd.github+json", "User-Agent": "pvm" };

(async () => {
  const runs = await (await fetch(`https://api.github.com/repos/${repo}/actions/workflows/generate-kaggle.yml/runs?per_page=1`, { headers: GH })).json();
  const r = runs.workflow_runs[0];
  console.log("run", r.run_number, r.status, r.conclusion);
  const jobs = await (await fetch(`https://api.github.com/repos/${repo}/actions/runs/${r.id}/jobs`, { headers: GH })).json();
  const lr = await fetch(`https://api.github.com/repos/${repo}/actions/jobs/${jobs.jobs[0].id}/logs`, { headers: GH });
  const txt = await lr.text();
  if (txt.startsWith("<?xml")) { console.log("(logs not ready)"); process.exit(0); }
  for (const l of txt.split("\n")) {
    if (/fallback|OmniVoice|OK \[|DONE:|Kaggle GPU|edge-tts|GPU not attached|Device:|kernels output/i.test(l)) {
      console.log(l.replace(/[^\x20-\x7e]/g, "").slice(0, 190));
    }
  }
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });