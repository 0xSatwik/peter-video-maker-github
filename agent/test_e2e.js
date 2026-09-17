// quick e2e test of the agent
const fs = require("fs");
(async () => {
  const r = await fetch("http://localhost:3211/api/plan", {
    method: "POST",
    headers: { "x-access-key": "testkey", "Content-Type": "application/json" },
    body: JSON.stringify({ topic: "latest OpenAI news this week", max_tokens: 600 }),
  });
  const j = await r.json();
  fs.writeFileSync(__dirname + "/../output/agent_test.json", JSON.stringify(j, null, 2));
  console.log("done", r.status);
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });
