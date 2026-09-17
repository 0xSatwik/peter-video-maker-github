// poll the frontend job until done/error, log progress (background watcher)
const fs = require("fs");
const KEY = "BloggingJi@7";
const SITE = "https://peter-video-maker.pages.dev";
const id = process.argv[2];
const LOG = "C:/Users/akasa/Desktop/MYPROJECTS/peter video maker github/output/watch.log";
const t0 = Date.now();

(async () => {
  fs.writeFileSync(LOG, "watching " + id + "\n");
  let last = "";
  while (Date.now() - t0 < 70 * 60 * 1000) {
    try {
      const r = await fetch(SITE + "/api/status?id=" + id, { headers: { "x-access-key": KEY } });
      const j = await r.json();
      const line = `${new Date().toISOString().slice(11, 19)} ${j.status} | ${j.progress || ""}`;
      if (line.slice(11) !== last) {
        fs.appendFileSync(LOG, line + "\n");
        last = line.slice(11);
      }
      if (j.status === "done") {
        fs.appendFileSync(LOG, "TEMP_URL=" + j.temp_url + "\n");
        process.exit(0);
      }
      if (j.status === "error") {
        fs.appendFileSync(LOG, "FAILED: " + j.progress + "\n");
        process.exit(1);
      }
    } catch (e) {
      fs.appendFileSync(LOG, "poll error: " + e.message + "\n");
    }
    await new Promise((r) => setTimeout(r, 20000));
  }
  fs.appendFileSync(LOG, "timeout\n");
  process.exit(1);
})();