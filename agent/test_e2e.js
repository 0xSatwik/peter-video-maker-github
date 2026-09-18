// download the audio-files artifact of a run and inspect the wavs
const fs = require("fs");
const { execSync } = require("child_process");
const env = Object.fromEntries(
  fs.readFileSync(process.env.USERPROFILE + "/.peter-deploy/deploy.env", "utf8")
    .split("\n").filter((l) => l.includes("="))
    .map((l) => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
);
const GH = { Authorization: "Bearer " + env.GH_PAT, Accept: "application/vnd.github+json", "User-Agent": "pvm" };
const repo = "0xSatwik/peter-video-maker-github";
const runNumber = Number(process.argv[2] || 27);

(async () => {
  const runs = await (await fetch(`https://api.github.com/repos/${repo}/actions/workflows/generate-kaggle.yml/runs?per_page=10`, { headers: GH })).json();
  const r = runs.workflow_runs.find((x) => x.run_number === runNumber);
  const arts = await (await fetch(`https://api.github.com/repos/${repo}/actions/runs/${r.id}/artifacts`, { headers: GH })).json();
  const a = (arts.artifacts || []).find((x) => x.name.startsWith("audio-files"));
  if (!a) { console.log("no audio artifact"); process.exit(1); }
  console.log("artifact:", a.name, (a.size_in_bytes / 1048576).toFixed(1), "MB");

  const dl = await fetch(a.archive_download_url, { headers: GH });
  const zip = "output/audio27.zip";
  fs.writeFileSync(zip, Buffer.from(await dl.arrayBuffer()));
  fs.rmSync("output/audio27", { recursive: true, force: true });
  execSync(`powershell -Command "Expand-Archive -Path '${zip.replace(/\//g, "\\")}' -DestinationPath 'output\\audio27' -Force"`);

  const ff = execSync('python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"', { encoding: "utf8" }).trim();
  const dir = "output/audio27";
  const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(d + "/" + e.name) : [d + "/" + e.name]);
  for (const f of walk(dir).filter((f) => f.endsWith(".wav")).slice(0, 12)) {
    try { execSync(`"${ff}" -hide_banner -i "${f}"`, { stdio: "pipe" }); }
    catch (e) {
      const o = (e.stdout || "") + (e.stderr || "");
      const dur = (o.match(/Duration: (\d+:\d+:[\d.]+)/) || [])[1];
      const au = (o.match(/Audio: (.*)/) || [])[1] || "";
      console.log(f.split(/[\\/]/).pop(), "|", dur, "|", au.slice(0, 60));
    }
  }
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });



