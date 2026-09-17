// CF API helpers using deploy.env token
const fs = require("fs");
const env = Object.fromEntries(
  fs.readFileSync(process.env.USERPROFILE + "/.peter-deploy/deploy.env", "utf8")
    .split("\n").filter((l) => l.includes("="))
    .map((l) => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
);
const ACCT = env.CLOUDFLARE_ACCOUNT_ID;
const H = { Authorization: "Bearer " + env.CLOUDFLARE_API_TOKEN };

// grep publish-step output (temp URL + callback response) from latest run logs
(async () => {
  const repo = "0xSatwik/peter-video-maker-github";
  const runs = await (await fetch(`https://api.github.com/repos/${repo}/actions/workflows/generate-kaggle.yml/runs?per_page=1`, { headers: { Authorization: "Bearer " + env.GH_PAT, Accept: "application/vnd.github+json", "User-Agent": "pvm" } })).json();
  const r = runs.workflow_runs[0];
  console.log("run id:", r.id, "number:", r.run_number, r.status, r.conclusion);
  const arts = await (await fetch(`https://api.github.com/repos/${repo}/actions/runs/${r.id}/artifacts`, { headers: { Authorization: "Bearer " + env.GH_PAT, Accept: "application/vnd.github+json", "User-Agent": "pvm" } })).json();
  for (const a of arts.artifacts || []) console.log("artifact:", a.name, a.size_in_bytes, "expired:", a.expired, "| dl:", a.archive_download_url.slice(0, 80));
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });







