// confirm the two winning hosts really serve the bytes back
(async () => {
  const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36";
  const targets = [
    ["sto.care", "https://dl.sto.care/4beeroy3m1"],
    ["gofile-page", "https://gofile.io/d/9Kvd5V4b"],
  ];
  for (const [name, url] of targets) {
    try {
      const h = await fetch(url, { headers: { "User-Agent": UA } });
      const ct = h.headers.get("content-type");
      const cl = h.headers.get("content-length");
      const cd = h.headers.get("content-disposition");
      let magic = "";
      if ((ct || "").includes("video") || (ct || "").includes("octet")) {
        const ab = await h.arrayBuffer();
        const b = Buffer.from(ab);
        magic = `${(b.length / 1048576).toFixed(1)}MB magic=${b.subarray(4, 12).toString("ascii")}`;
      }
      console.log(`[${name}] ${h.status} ct=${ct} len=${cl} cd=${(cd || "").slice(0, 40)} ${magic}`);
    } catch (e) {
      console.log(`[${name}] ERR ${e.message}`);
    }
  }
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });