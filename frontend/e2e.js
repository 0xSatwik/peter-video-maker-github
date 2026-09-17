// Full end-to-end test: agent draft -> generate -> GitHub Action -> Kaggle TTS -> video -> download
const fs = require("fs");
const KEY = "BloggingJi@7";
const SITE = "https://peter-video-maker.pages.dev";
const AGENT = "https://peter-agent.onrender.com";
const H = { "Content-Type": "application/json", "x-access-key": KEY };
const log = (...a) => { const s = a.join(" "); console.log(s); fs.appendFileSync(__dirname + "/../output/e2e.log", s + "\n"); };

async function j(url, opts, label) {
  const r = await fetch(url, opts);
  const t = await r.text();
  let body; try { body = JSON.parse(t); } catch { body = t; }
  log(`${label || url} -> ${r.status}`);
  return { status: r.status, body };
}

(async () => {
  fs.writeFileSync(__dirname + "/../output/e2e.log", "");
  // 1. draft via Render agent (live web research)
  log("STEP 1: agent drafting...");
  const plan = await j(AGENT + "/api/plan", { method: "POST", headers: H,
    body: JSON.stringify({ topic: "OpenAI safety news this week", max_tokens: 600 }) }, "agent plan");
  if (plan.status !== 200) { log("FAILED plan:", JSON.stringify(plan.body).slice(0, 300)); process.exit(1); }
  log("steps: " + (plan.body.steps || []).join(" | "));
  log("facts chars: " + plan.body.digest_chars);
  log("--- script ---\n" + plan.body.script);

  // 2. approve -> generates video (commits script + dispatches workflow)
  log("\nSTEP 2: dispatching generation...");
  const gen = await j(SITE + "/api/generate", { method: "POST", headers: H,
    body: JSON.stringify({ topic: "OpenAI safety news this week", script: plan.body.script }) }, "generate");
  if (gen.status !== 200) { log("FAILED generate:", JSON.stringify(gen.body).slice(0, 300)); process.exit(1); }
  const id = gen.body.id;
  log("job id: " + id);

  // 3. poll until the workflow lands the temp link
  log("\nSTEP 3: polling status (Kaggle TTS + assembly)...");
  const deadline = Date.now() + 60 * 60 * 1000; // 1h
  let last = "";
  while (Date.now() < deadline) {
    const s = await j(SITE + "/api/status?id=" + id, { headers: H }, "status");
    const b = s.body || {};
    const line = `${b.status} | ${b.progress || ""}`;
    if (line !== last) { log(new Date().toISOString().slice(11, 19) + " " + line); last = line; }
    if (b.status === "done") {
      log("\nVIDEO READY: " + b.temp_url);
      // 4. download it (tmpfiles needs /dl/ for direct file)
      const dl = String(b.temp_url).replace("tmpfiles.org/", "tmpfiles.org/dl/");
      const r = await fetch(dl);
      const buf = Buffer.from(await r.arrayBuffer());
      const out = __dirname + "/../output/e2e_video.mp4";
      fs.writeFileSync(out, buf);
      log(`downloaded ${buf.length} bytes -> ${out} (HTTP ${r.status})`);
      log("HEAD: " + buf.slice(0, 12).toString("hex"));
      process.exit(0);
    }
    if (b.status === "error") { log("RUN FAILED: " + b.progress); process.exit(1); }
    await new Promise((r) => setTimeout(r, 20000));
  }
  log("TIMEOUT waiting for video");
  process.exit(1);
})().catch((e) => { console.error(e.message); process.exit(1); });
