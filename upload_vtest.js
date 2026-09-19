// upload the 4 voice-test samples to sto.care and print their links
const fs = require("fs");

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36";
const DIR = "C:/Users/akasa/Desktop/MYPROJECTS/peter video maker github/output/vtest/audio";

(async () => {
  for (const f of ["step32_gs20.wav", "step64_gs20.wav", "step32_gs25.wav", "step64_gs25.wav"]) {
    const p = DIR + "/" + f;
    const buf = fs.readFileSync(p);
    const r = await fetch("https://ul.sto.care/" + f, {
      method: "PUT",
      body: buf,
      headers: {
        "User-Agent": UA,
        "Content-Type": "audio/wav",
        "Content-Length": String(buf.length),
      },
    });
    const j = await r.json().catch(() => ({}));
    console.log(f, "->", r.status, j.url || (await r.text()) || "err");
  }
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });