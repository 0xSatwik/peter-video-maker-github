import os
import shutil
import sys

from kaggle.api.kaggle_api_extended import KaggleApi

slug = sys.argv[1] if len(sys.argv) > 1 else "satwiksamanta/peter-voice-test"
out = os.path.join("output", "vtest")
shutil.rmtree(out, ignore_errors=True)
os.makedirs(out, exist_ok=True)

a = KaggleApi()
a.authenticate()
buf = []


class Cap:
    def write(self, s):
        buf.append(s)

    def flush(self):
        pass


real = sys.stdout
sys.stdout = Cap()
try:
    a.kernels_output(slug, out, force=True, quiet=True)
finally:
    sys.stdout = real

log = "".join(buf)
keep = [l for l in log.splitlines() if any(k in l for k in ["OK ", "FAIL", "files:", "ref exists", "GPU:", "voice cloned"])]
print("\n".join(keep[-20:]) or "(no matching log lines)")

adir = os.path.join(out, "audio")
if os.path.isdir(adir):
    for f in sorted(os.listdir(adir)):
        p = os.path.join(adir, f)
        print(" ", f, os.path.getsize(p) // 1024, "KB")
else:
    print("no audio dir; top-level:", sorted(os.listdir(out)))
