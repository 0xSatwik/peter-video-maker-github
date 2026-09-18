// quick local test of the updated agent (style examples + new writer)
const fs = require("fs");

(async () => {
  const h = await fetch("http://localhost:3212/health");
  console.log("health:", h.status, await h.text());

  const r = await fetch("http://localhost:3212/api/plan", {
    method: "POST",
    headers: { "x-access-key": "testkey", "Content-Type": "application/json" },
    body: JSON.stringify({ topic: "Claude Code plugins that save tokens", max_tokens: 600 }),
  });
  const j = await r.json();
  fs.writeFileSync(__dirname + "/../output/agent_style.json", JSON.stringify(j, null, 2));
  console.log("plan:", r.status);
  console.log("steps:", (j.steps || []).join(" | "));
  console.log("--- script ---");
  console.log(j.script || JSON.stringify(j).slice(0, 300));
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });



