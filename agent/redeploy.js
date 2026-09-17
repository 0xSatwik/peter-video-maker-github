// update the Render agent's ACCESS_KEY to match the frontend gate key
const KEY = process.argv[2] || "BloggingJi@7";
const ID = "srv-dam32667bikc7384vk20";
const RENDER = "rnd_DfJYZqr2YBxwiMYbaLjTe67800s2";
(async () => {
  const r = await fetch(`https://api.render.com/v1/services/${ID}/env-vars/ACCESS_KEY`, {
    method: "PUT",
    headers: { Authorization: "Bearer " + RENDER, "Content-Type": "application/json" },
    body: JSON.stringify({ value: KEY }),
  });
  const t = await r.text();
  console.log("put:", r.status, t.slice(0, 200));
  const d = await fetch(`https://api.render.com/v1/services/${ID}/deploys`, {
    method: "POST", headers: { Authorization: "Bearer " + RENDER, "Content-Type": "application/json" }, body: "{}",
  });
  console.log("redeploy:", d.status);
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });

