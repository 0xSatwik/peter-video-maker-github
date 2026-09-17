// fetch recent build logs
(async () => {
  const r = await fetch("https://api.render.com/v1/logs?ownerId=tea-dam1vpdbedkc73acei20&resource=srv-dam32667bikc7384vk20&type=build&limit=100", { headers: { Authorization: "Bearer rnd_DfJYZqr2YBxwiMYbaLjTe67800s2" } });
  const j = await r.text();
  console.log(r.status, j.slice(0, 2000));
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });
