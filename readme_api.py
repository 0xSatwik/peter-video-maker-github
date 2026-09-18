// check WHERE the PSNR difference comes from: per-frame psnr on a few frames
const { execSync } = require("child_process");
const os = require("os");
const path = require("path");
const root = "C:/Users/akasa/Desktop/MYPROJECTS/peter video maker github/output/parity";
const ff = path.join(root, "bin", "ffmpeg.exe");
process.chdir(root);

// extract frame 200 (mid-caption) from both and compare
for (const f of ["ws_old/output/final_reel.mp4", "ws_fast/output/final_reel.mp4"]) {
  execSync(`"${ff}" -y -ss 8.3 -i ${f} -frames:v 1 frame_8s_${f.includes("old") ? "old" : "fast"}.png`, { stdio: "pipe" });
}
const r = execSync(`"${ff}" -i frame_8s_old.png -i frame_8s_fast.png -lavfi psnr -f null - 2>&1`, { encoding: "utf8" });
const m = r.match(/PSNR.*average:([\d.]+)/);
console.log("frame@8.3s PSNR avg:", m ? m[1] : "n/a");

// also compare a caption-transition frame (word change)
for (const f of ["ws_old/output/final_reel.mp4", "ws_fast/output/final_reel.mp4"]) {
  execSync(`"${ff}" -y -ss 2.5 -i ${f} -frames:v 1 frame_2s_${f.includes("old") ? "old" : "fast"}.png`, { stdio: "pipe" });
}
const r2 = execSync(`"${ff}" -i frame_2s_old.png -i frame_2s_fast.png -lavfi psnr -f null - 2>&1`, { encoding: "utf8" });
const m2 = r2.match(/PSNR.*average:([\d.]+)/);
console.log("frame@2.5s PSNR avg:", m2 ? m2[1] : "n/a");
