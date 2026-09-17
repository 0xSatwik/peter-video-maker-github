// fix a stale job row + show it (admin helper)
const fs = require("fs");
const env = Object.fromEntries(
  fs.readFileSync(process.env.USERPROFILE + "/.peter-deploy/deploy.env", "utf8")
    .split("\n").filter((l) => l.includes("="))
    .map((l) => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
);
const ACCT = env.CLOUDFLARE_ACCOUNT_ID;
const DB = "7725ae79-41d9-4b3e-97f9-be79c5bab94f";
const H = { Authorization: "Bearer " + env.CLOUDFLARE_API_TOKEN, "Content-Type": "application/json" };

const q = async (sql, params = []) => {
  const r = await fetch(`https://api.cloudflare.com/client/v4/accounts/${ACCT}/d1/database/${DB}/query`, {
    method: "POST", headers: H, body: JSON.stringify({ sql, params }),
  });
  const j = await r.json();
  if (!j.success) throw new Error(JSON.stringify(j.errors).slice(0, 300));
  return j.result[0].results;
};

(async () => {
  const argv = process.argv.slice(2);
  if (argv[0] === "reset") {
    await q("UPDATE jobs SET status='gh_queued', run_id=NULL, progress='re-tracking' WHERE id=?", [argv[1]]);
    console.log("reset", argv[1]);
  }
  const rows = await q("SELECT id, topic, status, progress, temp_url FROM jobs ORDER BY created_at DESC LIMIT 8");
  for (const r of rows) console.log(r.id.slice(0, 8), String(r.status).padEnd(10), String(r.progress || "").slice(0, 42).padEnd(44), r.temp_url || "");
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });