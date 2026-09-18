"""Assemble-parity test: run both engines on the same 2 clips, write frame diff."""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARITY = os.path.join(ROOT, "output", "parity")
BIN = os.path.join(PARITY, "bin")
FFMPEG = os.path.join(BIN, "ffmpeg.exe")
SRC_AUDIO = os.path.join(ROOT, "output", "audio27")


def clean_line(s):
    return s.encode("ascii", errors="replace").decode("ascii")


def build_ws(name):
    ws = os.path.join(PARITY, name)
    shutil.rmtree(ws, ignore_errors=True)
    for sub in ["assets", "audio", "output"]:
        os.makedirs(os.path.join(ws, sub), exist_ok=True)

    shutil.copy2(os.path.join(ROOT, "assets", "minecraft_bg.mp4"), os.path.join(ws, "assets"))
    for a in ["peter.png", "stewie.png"]:
        shutil.copy2(os.path.join(ROOT, "assets", a), os.path.join(ws, "assets"))

    clips = [f for f in sorted(os.listdir(SRC_AUDIO))
             if f.endswith(".wav") and ("peter_000" in f or "stewie_001" in f)]
    meta = []
    for i, f in enumerate(clips):
        shutil.copy2(os.path.join(SRC_AUDIO, f), os.path.join(ws, "audio", f))
        sp = f.split("_")[0]
        text = ("Well Stewie, that is a fantastic question and here is the answer." if sp == "peter"
                else "Yes Peter, that is surprisingly accurate for once in your life.")
        meta.append({"index": i, "speaker": sp, "text": text,
                     "audio_file": f"audio/{f}", "exists": True})
    with open(os.path.join(ws, "audio", "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    return ws


def run(ws, script):
    env = dict(os.environ)
    env["PATH"] = BIN + os.pathsep + env["PATH"]
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["FFMPEG_BIN"] = FFMPEG
    env["FFPROBE_BIN"] = os.path.join(BIN, "ffprobe.exe")

    print(f"=== running {script} in {os.path.basename(ws)} ===", flush=True)
    r = subprocess.run([sys.executable, "-u", os.path.join(ROOT, "scripts", script)],
                       cwd=ws, env=env, capture_output=True, text=True, errors="replace")
    tail = [clean_line(l) for l in r.stdout.splitlines() if any(
        k in l for k in ["DONE", "Compositing", "Total duration", "unique caption",
                         "caption layer", "frames", "OK ", "Failed"])]
    print("\n".join(tail[-10:]) or clean_line(r.stdout[-800:]))
    if r.returncode != 0:
        print("STDERR:", clean_line(r.stderr[-2000:]))
        raise SystemExit(f"{script} failed rc={r.returncode}")
    return r.stdout


if __name__ == "__main__":
    ws_old = build_ws("ws_old")
    ws_fast = build_ws("ws_fast")
    run(ws_old, "assemble_video.py")
    run(ws_fast, "assemble_fast.py")
    print("both engines finished")

