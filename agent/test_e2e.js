// CF API helpers using deploy.env token
const fs = require("fs");
const env = Object.fromEntries(
  fs.readFileSync(process.env.USERPROFILE + "/.peter-deploy/deploy.env", "utf8")
    .split("\n").filter((l) => l.includes("="))
    .map((l) => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
);
const ACCT = env.CLOUDFLARE_ACCOUNT_ID;
const H = { Authorization: "Bearer " + env.CLOUDFLARE_API_TOKEN };

// show latest generate-kaggle.yml run + failed jobs/logs
(async () => {
  const repo = "0xSatwik/peter-video-maker-github";
  const runs = await (await fetch(`https://api.github.com/repos/${repo}/actions/workflows/generate-kaggle.yml/runs?per_page=1`, { headers: { Authorization: "Bearer " + env.GH_PAT, Accept: "application/vnd.github+json", "User-Agent": "pvm" } })).json();
  const r = runs.workflow_runs[0];
  const jobs = await (await fetch(`https://api.github.com/repos/${repo}/actions/runs/${r.id}/jobs`, { headers: { Authorization: "Bearer " + env.GH_PAT, Accept: "application/vnd.github+json", "User-Agent": "pvm" } })).json();
  const j = jobs.jobs[0];
  console.log("job id:", j.id);
  const lr = await fetch(`https://api.github.com/repos/${repo}/actions/jobs/${j.id}/logs`, { headers: { Authorization: "Bearer " + env.GH_PAT, Accept: "application/vnd.github+json", "User-Agent": "pvm" }, redirect: "manual" });
  console.log("logs redirect:", lr.status);
  const loc = lr.headers.get("location") || lr.headers.get("Location");
  const txt = await (await fetch(loc)).text();
  const lines = txt.split("\n").filter((l) => l.length);
  let i = lines.findIndex((l) => l.includes("TTS on Kaggle"));
  console.log("failing step at line", i);
  // print ERROR lines and lines around the end of the TTS step
  const errs = lines.filter((l) => /error|Error|Traceback|Exception|FATAL|killed|timed?\s?out/i.test(l) && !/punycode|trace-deprecation|secure_node/i.test(l));
  for (const l of errs.slice(-15)) console.log(l.slice(0, 240));
  console.log("--- TTS step context ---");
  const probe = lines.findIndex((l) => /KERNEL|kaggle|Kaggle/i.test(l) && l.indexOf("19:43") >= 0);
  for (const l of lines.slice(Math.max(0, probe - 5), probe + 25)) console.log(l.slice(0, 240));
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });






