// trigger a new deploy
(async () => {
  const d = await fetch("https://api.render.com/v1/services/srv-dam32667bikc7384vk20/deploys", {
    method: "POST",
    headers: { Authorization: "Bearer rnd_DfJYZqr2YBxwiMYbaLjTe67800s2", "Content-Type": "application/json" },
    body: "{}",
  });
  const t = await d.text();
  console.log("deploy:", d.status, t.slice(0, 200));
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });
