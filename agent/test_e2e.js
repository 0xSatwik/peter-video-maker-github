// CF API helpers using deploy.env token
const fs = require("fs");
const env = Object.fromEntries(
  fs.readFileSync(process.env.USERPROFILE + "/.peter-deploy/deploy.env", "utf8")
    .split("\n").filter((l) => l.includes("="))
    .map((l) => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
);
const ACCT = env.CLOUDFLARE_ACCOUNT_ID;
const H = { Authorization: "Bearer " + env.CLOUDFLARE_API_TOKEN };

// show deployment history logs
(async () => {
  const id = process.argv[2];
  const r = await fetch(`https://api.cloudflare.com/client/v4/accounts/${ACCT}/pages/projects/peter-video-maker/deployments/${id}/history/logs`, { headers: H });
  const j = await r.json();
  console.log(JSON.stringify(j).slice(0, 1200));
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });




