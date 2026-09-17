// fetch recent logs (newest first)
(async () => {
  const r = await fetch("https://api.render.com/v1/logs?ownerId=tea-dam1vpdbedkc73acei20&resource=srv-dam32667bikc7384vk20&limit=100&direction=desc", { headers: { Authorization: "Bearer rnd_DfJYZqr2YBxwiMYbaLjTe67800s2" } });
  const j = await r.json();
  const clean = (s) => (s || "").replace(/\u001b\[[0-9;]*m/g, "");
  for (const l of (j.logs || []).slice(0, 40)) console.log(l.timestamp, "|", clean(l.message).slice(0, 160));
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });


