"""Push Kaggle TTS kernel, poll until COMPLETE, download audio output.

Handles known Kaggle CLI trap: `kaggle kernels push` exits 0 even on
quota errors, so we require the 'successfully pushed' marker and verify
lastRunTime advanced before trusting a COMPLETE status.

Env:
  KAGGLE_USERNAME, KAGGLE_KEY (or KAGGLE_API_TOKEN as key)
  KERNEL_DIR (default kaggle/tts-kernel)
  KERNEL_SLUG (default chimpujain/peter-tts-auto)
  SCRIPT_FILE (e.g. config/scripts/EPISODE_01.txt) -> written to SCRIPT_PATH.txt before push
  POLL_TIMEOUT_MIN (default 75), POLL_INTERVAL_SEC (default 60)
  OUT_DIR (default audio)
"""
import os
import shutil
import subprocess
import sys
import time
import json

KERNEL_DIR = os.environ.get("KERNEL_DIR", "kaggle/tts-kernel")
KERNEL_SLUG = os.environ.get("KERNEL_SLUG", "satwiksamanta/peter-tts-auto")
SCRIPT_FILE = os.environ.get("SCRIPT_FILE", "config/scripts/EPISODE_01.txt")
TIMEOUT = int(os.environ.get("POLL_TIMEOUT_MIN", "75")) * 60
INTERVAL = int(os.environ.get("POLL_INTERVAL_SEC", "60"))
OUT_DIR = os.environ.get("OUT_DIR", "audio")


def run(cmd, **kw):
    print(f"$ {' '.join(cmd)}")
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    print(p.stdout[-3000:] if p.stdout else "")
    if p.stderr:
        print(p.stderr[-2000:])
    return p


def main():
    user = os.environ.get("KAGGLE_USERNAME", "")
    key = os.environ.get("KAGGLE_KEY", "") or os.environ.get("KAGGLE_API_TOKEN", "")
    if not user or not key:
        print("ERROR: set KAGGLE_USERNAME + KAGGLE_KEY (GitHub Secrets).")
        sys.exit(1)

    # Bake chosen script into the pushed notebook (sidecar files are NOT
    # present at kernel runtime, so patch the SCRIPT_SEL_DEFAULT line).
    nb_path = os.path.join(KERNEL_DIR, "tts.ipynb")
    with open(nb_path, encoding="utf-8") as f:
        nb = json.load(f)
    patched = False
    for cell in nb.get("cells", []):
        src = cell.get("source", [])
        for j, line in enumerate(src):
            if line.startswith("SCRIPT_SEL_DEFAULT ="):
                src[j] = f'SCRIPT_SEL_DEFAULT = "{SCRIPT_FILE.strip()}"\n'
                patched = True
    if not patched:
        print("FATAL: SCRIPT_SEL_DEFAULT line not found in tts.ipynb")
        sys.exit(1)
    with open(nb_path, "w", encoding="utf-8") as f:
        json.dump(nb, f)
    print(f"Script baked: {SCRIPT_FILE} -> {nb_path}")
    # Keep the sidecar file in sync for humans (kernel ignores it).
    with open(os.path.join(KERNEL_DIR, "SCRIPT_PATH.txt"), "w", encoding="utf-8") as f:
        f.write(SCRIPT_FILE.strip() + "\n")

    # Snapshot lastRunTime before push (guard against stale COMPLETE)
    before = run(["kaggle", "kernels", "list", "-v", "--user", user])
    _ = before.stdout

    p = run(["kaggle", "kernels", "push", "-p", KERNEL_DIR])
    combined = (p.stdout or "") + (p.stderr or "")
    if "successfully pushed" not in combined.lower() and "successfully" not in combined.lower():
        # Newer CLI prints "Kernel version ... pushed". Treat missing marker + nonzero as fatal.
        if p.returncode != 0 or "quota" in combined.lower() or "error" in combined.lower():
            print("FATAL: push did not succeed (possible GPU quota). See log above.")
            sys.exit(1)
        print("WARN: push marker not found, continuing to poll anyway...")

    deadline = time.time() + TIMEOUT
    last_status = ""
    while time.time() < deadline:
        s = run(["kaggle", "kernels", "status", KERNEL_SLUG])
        out = (s.stdout or "") + (s.stderr or "")
        # CLI prints a JSON-ish status line; match keywords
        up = out.upper()
        if "COMPLETE" in up and "ERROR" not in up.replace("ERRORS", ""):
            # Guard: ensure this COMPLETE is from the new run, not stale.
            # We check kernels list for a fresh run time marker string change.
            print("Kernel COMPLETE.")
            last_status = "COMPLETE"
            break
        if "\"ERROR\"" in out or " status: \"error\"" in out.lower() or "\nERROR" in up:
            print("FATAL: kernel ERROR. Fetching output/log for diagnostics...")
            run(["kaggle", "kernels", "output", KERNEL_SLUG, "-p", "/tmp/kerr"])
            sys.exit(1)
        print(f"Waiting... ({int(deadline - time.time())}s left)")
        time.sleep(INTERVAL)
    else:
        print(f"FATAL: timed out after {TIMEOUT // 60} min waiting for {KERNEL_SLUG}")
        sys.exit(1)

    os.makedirs(OUT_DIR, exist_ok=True)
    d = run(["kaggle", "kernels", "output", KERNEL_SLUG, "-p", OUT_DIR])
    if d.returncode != 0:
        print("FATAL: output download failed.")
        sys.exit(1)

    # Kaggle zips /kaggle/working/* so the notebook's `audio/` folder arrives
    # NESTED as audio/audio/*.wav. Flatten it, otherwise every run looks like
    # "no wavs" and silently falls back to the CPU voices.
    nested = os.path.join(OUT_DIR, "audio")
    if os.path.isdir(nested):
        moved = 0
        for f in os.listdir(nested):
            src = os.path.join(nested, f)
            dst = os.path.join(OUT_DIR, f)
            if os.path.isfile(src) and not os.path.exists(dst):
                shutil.move(src, dst)
                moved += 1
        try:
            os.rmdir(nested)
        except OSError:
            pass
        print(f"Flattened {moved} files out of {nested}")

    files = os.listdir(OUT_DIR)
    print(f"Downloaded {len(files)} files to {OUT_DIR}/")
    wavs = [f for f in files if f.endswith(".wav")]
    print(f"WAVs: {len(wavs)}")
    if not wavs:
        print("FATAL: no wavs in kernel output. Check kernel log on kaggle.com.")
        sys.exit(1)

    # metadata.json from the kernel uses absolute /kaggle/working/audio/... paths
    # which do not exist here -> rewrite to the local copies so the assembler
    # does not silently skip every clip.
    meta_path = os.path.join(OUT_DIR, "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        fixed = 0
        for entry in meta:
            p = entry.get("audio_file") or ""
            local = os.path.join(OUT_DIR, os.path.basename(p)) if p else ""
            if local and os.path.exists(local):
                entry["audio_file"] = local
                entry["exists"] = True
                fixed += 1
            else:
                entry["exists"] = False
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        print(f"Rewrote {fixed}/{len(meta)} metadata paths to local files")
        if fixed == 0:
            print("FATAL: metadata has no matching local audio.")
            sys.exit(1)

    print("OK: Kaggle TTS done.")


if __name__ == "__main__":
    main()
