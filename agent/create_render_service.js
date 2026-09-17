// create the Render web service (one-time)
const body = JSON.stringify({
  type: "web_service",
  name: "peter-agent",
  ownerId: "tea-dam1vpdbedkc73acei20",
  repo: "https://github.com/0xSatwik/peter-video-maker-github",
  branch: "main",
  rootDir: "agent",
  buildCommand: "npm install --no-audit --no-fund",
  startCommand: "node server.js",
  autoDeploy: "yes",
  envVars: [
    { key: "ACCESS_KEY", value: "peter2026" },
    { key: "MONID_KEY", value: "monid_live_IIN6Sb2bbP2uoeAXFgLPSyge" },
    { key: "GEMINI_PROXY", value: "https://gemini-web-proxy.dipteshray7.workers.dev/v1/chat/completions" },
    { key: "GEMINI_MODEL", value: "gemini-3.7-flash" },
  ],
  serviceDetails: { plan: "free", region: "oregon", runtime: "node", envSpecificDetails: { buildCommand: "npm install --no-audit --no-fund", startCommand: "node server.js" } },
});
(async () => {
  const r = await fetch("https://api.render.com/v1/services", {
    method: "POST",
    headers: { Authorization: "Bearer rnd_DfJYZqr2YBxwiMYbaLjTe67800s2", "Content-Type": "application/json" },
    body,
  });
  const t = await r.text();
  console.log(r.status, t.slice(0, 400));
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });
