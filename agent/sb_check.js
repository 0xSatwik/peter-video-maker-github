// inspect downloaded Peter clips via imageio's ffmpeg path (python resolves it)
const { execFileSync } = require("child_process");
const { execSync } = require("child_process");
const fs = require("fs");

const ff = execSync('python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"', { encoding: "utf8" }).trim();
console.log("ffmpeg:", ff);

for (const f of fs.readdirSync("output").filter((x) => x.startsWith("sb_"))) {
  const p = "output/" + f;
  try {
    execSync(`"${ff}" -hide_banner -i "${p}"`, { encoding: "utf8", stdio: "pipe" });
  } catch (e) {
    const o = (e.stdout || "") + (e.stderr || "");
    const dur = (o.match(/Duration: (\d+:\d+:[\d.]+)/) || [])[1];
    const audio = (o.match(/Audio: (.*)/) || [])[1];
    console.log(f, "| dur:", dur, "|", (audio || "").slice(0, 90));
  }
}