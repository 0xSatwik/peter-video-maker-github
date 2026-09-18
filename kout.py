import json
import os
import shutil
import sys

from kaggle.api.kaggle_api_extended import KaggleApi

slug = sys.argv[1] if len(sys.argv) > 1 else "satwiksamanta/peter-tts-auto"
out = "output/omni_out"
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
for l in log.splitlines():
    if any(k in l for k in ["cloned voice", "prompt build failed", "retrying without", "OK [", "FAIL [", "DONE:", "Lines:"]):
        print(l.strip()[:220])

adir = os.path.join(out, "audio")
meta = os.path.join(adir, "metadata.json")
if os.path.exists(meta):
    m = json.load(open(meta, encoding="utf-8"))
    ok = sum(1 for x in m if x["exists"])
    print(f"metadata: {ok}/{len(m)} clips present")
    print("wavs:", sorted(f for f in os.listdir(adir) if f.endswith(".wav")))
else:
    print("no metadata.json ->", sorted(os.listdir(out)))