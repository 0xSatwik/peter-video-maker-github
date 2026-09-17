// list recent deploys
(async () => {
  const r = await fetch("https://api.render.com/v1/services/srv-dam32667bikc7384vk20/deploys?limit=2", { headers: { Authorization: "Bearer rnd_DfJYZqr2YBxwiMYbaLjTe67800s2" } });
  const j = await r.json();
  console.log(JSON.stringify(j).slice(0, 800));
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });
