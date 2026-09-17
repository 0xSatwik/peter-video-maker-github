// test big-file hosts (>=150MB limits) with the real video
const fs = require("fs");
const path = require("path");

const FILE = "C:/Users/akasa/Desktop/MYPROJECTS/peter video maker github/output/e2e_final/final_reel.mp4";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36";

const hosts = {
  async temposh(buf, name) {
    const r = await fetch("https://temp.sh/" + name, { method: "PUT", body: buf, headers: { "User-Agent": UA } });
    return { status: r.status, out: (await r.text()).slice(0, 200) };
  },
  async bashupload(buf, name) {
    const r = await fetch("https://bashupload.com/" + name, { method: "PUT", body: buf, headers: { "User-Agent": UA } });
    return { status: r.status, out: (await r.text()).slice(0, 300) };
  },
  async pixeldrain(buf, name) {
    const r = await fetch("https://pixeldrain.com/api/file/" + encodeURIComponent(name), {
      method: "PUT", body: buf,
      headers: { "User-Agent": UA, Authorization: "Basic " + Buffer.from(":").toString("base64") },
    });
    return { status: r.status, out: (await r.text()).slice(0, 300) };
  },
  async gofile(buf, name) {
    const s = await (await fetch("https://api.gofile.io/servers", { headers: { "User-Agent": UA } })).json();
    const server = s?.data?.servers?.[0]?.name || s?.data?.server;
    if (!server) return { status: 0, out: "no server: " + JSON.stringify(s).slice(0, 150) };
    const fd = new FormData();
    fd.append("file", new Blob([buf]), name);
    const r = await fetch(`https://${server}.gofile.io/contents/uploadfile`, { method: "POST", body: fd, headers: { "User-Agent": UA } });
    return { status: r.status, out: (await r.text()).slice(0, 300) };
  },
  async stocare(buf, name) {
    const r = await fetch("https://ul.sto.care/" + name, {
      method: "PUT", body: buf,
      headers: { "User-Agent": UA, "Content-Type": "video/mp4", "Content-Length": String(buf.length) },
    });
    return { status: r.status, out: (await r.text()).slice(0, 250) };
  },
};

(async () => {
  const buf = fs.readFileSync(FILE);
  const name = path.basename(FILE);
  console.log("file:", name, (buf.length / 1048576).toFixed(1), "MB");
  for (const [k, fn] of Object.entries(hosts)) {
    const t = Date.now();
    try {
      const res = await fn(buf, name);
      console.log(`[${k}] ${res.status} ${((Date.now() - t) / 1000).toFixed(1)}s -> ${res.out.replace(/\n/g, " ")}`);
    } catch (e) {
      console.log(`[${k}] ERROR ${((Date.now() - t) / 1000).toFixed(1)}s -> ${e.message}`);
    }
  }
  process.exit(0);
})().catch((e) => { console.error("ERR", e.message); process.exit(1); });