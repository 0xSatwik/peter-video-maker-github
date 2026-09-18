// test the LIVE Render agent /api/plan with the new style
const KEY = "BloggingJi@7";

(async () => {
  const t0 = Date.now();
  console.log("calling live agent...");
  const r = await fetch("https://peter-agent.onrender.com/api/plan", {
    method: "POST",
    headers: { "x-access-key": KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ topic: "Public APIs GitHub repo free API keys", max_tokens: 600 }),
  });
  const j = await r.json().catch(() => ({}));
  console.log(`status ${r.status} in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  console.log("steps:", (j.steps || []).join(" | "));
  console.log("--- script ---");
  console.log(j.script || JSON.stringify(j).slice(0, 400));
  process.exit(0);
})().catch((e) => { console.error("ERR", e.name, e.message); process.exit(1); });
