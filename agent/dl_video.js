// download the family-guy-short artifact to output/e2e_video.mp4 (background-friendly)
const fs = require("fs");
const env = Object.fromEntries(
  fs.readFileSync(process.env.USERPROFILE + "/.peter-deploy/deploy.env", "utf8")
    .split("\n").filter((l) => l.includes("="))
    .map((l) => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
);
const H = { Authorization: "Bearer " + env.GH_PAT, Accept: "application/vnd.github+json", "User-Agent": "pvm" };
const OUT = "C:/Users/akasa/Desktop/MYPROJECTS/peter video maker github/output/e2e_video.zip";
(async () => {
  const arts = await (await fetch("https://api.github.com/repos/0xSatwik/peter-video-maker-github/actions/runs/35269594506/artifacts", { headers: H })).json();
  const a = (arts.artifacts || []).find((x) => x.name.startsWith("family-guy-short"));
  if (!a) { console.log("artifact gone"); process.exit(1); }
  console.log("size:", a.size_in_bytes);
  const r = await fetch(a.archive_download_url, { headers: H });
  if (!r.ok) { console.log("dl failed", r.status); process.exit(1); }
  const ab = await r.arrayBuffer();
  fs.writeFileSync(OUT, Buffer.from(ab));
  console.log("saved", OUT, fs.statSync(OUT).size);
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });
