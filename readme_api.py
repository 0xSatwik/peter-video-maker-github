import subprocess
import os
import json

os.chdir(r"C:\Users\akasa\Desktop\MYPROJECTS\peter video maker github\output\parity")
cmd = (
    r"..\..\output\parity\bin\ffmpeg.exe -y "
    r"-i ws_old\output\final_reel.mp4 -i ws_fast\output\final_reel.mp4 "
    r"-lavfi psnr -f null -"
)
r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
for line in (r.stderr or "").splitlines():
    if "psnr_avg" in line.lower():
        print(line.replace("\r", "").strip()[:300])

# measure caption y position in a fast frame (find the bright green text pixel rows)
cmd2 = (
    r"..\..\output\parity\bin\ffmpeg.exe -y -ss 8.3 -i ws_fast\output\final_reel.mp4 "
    r"-frames:v 1 caption_frame.png"
)
subprocess.run(cmd2, capture_output=True)
print("extracted caption frame")

