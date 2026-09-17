// list recent runs of ALL workflows side by side with trigger + timing
const fs = require("fs");
const env = Object.fromEntries(
  fs.readFileSync(process.env.USERPROFILE + "/.peter-deploy/deploy.env", "utf8")
    .split("\n").filter((l) => l.includes("="))
    .map((l) => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
);
const repo = "0xSatwik/peter-video-maker-github";
const GH = { Authorization: "Bearer " + env.GH_PAT, Accept: "application/vnd.github+json", "User-Agent": "pvm" };

(async () => {
  for (const wf of ["generate-kaggle.yml", "generate.yml"]) {
    const d = await (await fetch(`https://api.github.com/repos/${repo}/actions/workflows/${wf}/runs?per_page=4`, { headers: GH })).json();
    console.log(`=== ${wf} ===`);
    for (const r of d.workflow_runs || []) {
      console.log(
        `#${r.run_number} ${r.status}/${r.conclusion} event=${r.event} ` +
        `file=${(r.head_branch || "")} created=${r.created_at} ` +
        `script=${(r.name || "")}`
      );
      // workflow_dispatch inputs (script_file) are visible via the run's jobs env only; print event details
      if (r.event === "workflow_dispatch") console.log("   ^ dispatched manually or by API");
    }
  }
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });