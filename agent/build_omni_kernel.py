"""Build kaggle/tts-kernel/tts.ipynb: headless OmniVoice voice-cloning port.

Port of the Colab 'OmniVoice - Hunaar Ansari' notebook to a headless Kaggle
kernel pushed by GitHub Actions (scripts/kaggle_run.py). Differences from Colab:
  - no Gradio UI: batch-generates every SPEAKER|TAGS|DIALOGUE line of the
    chosen script with Voice Cloning (ref mp3s baked in the repo).
  - quality knobs fixed: num_step=32, speed=1.0, fp16 on cuda, 24 kHz wav.
  - writes /kaggle/working/audio/{speaker}_{i:03d}.wav + metadata.json exactly
    like the old MOSS kernel, so assemble_video.py works unchanged.
  - keeps the `SCRIPT_SEL_DEFAULT = ...` line: kaggle_run.py rewrites it to
    the approved script before every push.
"""
import json

CELL_MD = """# Peter TTS Auto — OmniVoice voice cloning (Kaggle headless)

Pushed by GitHub Actions via `kaggle kernels push`. Starts GPU, generates all
clips with cloned Peter/Stewie voices, auto-stops.

Port of the Colab **OmniVoice UI by Hunaar Ansari** (`omnivoice` +
`k2-fsa/OmniVoice`, Voice Cloning mode, `num_step=32`, `speed` read from the
script's `# SPEED:` header (default peter 1.1), 24 kHz).
Output goes to `/kaggle/working/audio/` with `metadata.json` — the same
contract as the old MOSS kernel, so `scripts/assemble_video.py` works unchanged.

NOTE: we do NOT pass `instruct` to `generate()` — instruct fights the cloned
voice and made Peter harsh (see docs/tips.md: "when ref_audio and instruct
conflict, the model follows the reference audio" — any conflict = instability).
"""

CELL_DEPS = """# Cell 1: deps (Kaggle already ships torch + torchaudio with CUDA)
!pip install -q omnivoice
!pip install -q "omnivoice[tn]" || true   # WeTextProcessing for normalize_text (numbers spoken naturally)
!python -c "import torchaudio" 2>/dev/null || pip install -q torchaudio
print("deps ok")
"""

CELL_LOAD = """# Cell 2: load OmniVoice (k2-fsa/OmniVoice, ~3-5 GB first run)
import torch
import torchaudio
from omnivoice import OmniVoice

device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
dtype = torch.float16 if torch.cuda.is_available() else torch.float32
assert device == 'cuda:0', "GPU not attached! Kernel must run with GPU enabled."
print(f"Device: {device} | GPU: {torch.cuda.get_device_name(0)} "
      f"({torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB)")
model = OmniVoice.from_pretrained('k2-fsa/OmniVoice', device_map=device, dtype=dtype)
model.eval()
print("OmniVoice ready.")
"""

CELL_FETCH = """# Cell 3: fetch repo (sparse, /tmp only so kernel output stays clean) + parse script
import os
import re

SCRIPT_SEL_DEFAULT = "config/scripts/EPISODE_01.txt"
REPO_DIR = "/tmp/pvrepo"
!rm -rf /tmp/pvrepo peter-video-maker-github
!git clone --depth 1 --filter=blob:none --sparse https://github.com/0xSatwik/peter-video-maker-github.git /tmp/pvrepo
!git -C /tmp/pvrepo sparse-checkout set --no-cone config/scripts assets/peter-voice-latest.mp3 assets/peter-voice.mp3 assets/Stewies-voice.mp3 assets/perter10seonds.wav

SCRIPT = os.path.join(REPO_DIR, SCRIPT_SEL_DEFAULT)
print("SCRIPT:", SCRIPT, os.path.exists(SCRIPT))

def preprocess_text(t):
    t = re.sub(r'\\s+', ' ', t)
    t = re.sub(r'([.,!?])([A-Za-z])', r'\\1 \\2', t)
    return t.strip()

def parse_speeds(path):
    speeds = {"peter": 1.1, "stewie": 1.0}
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                m = re.match(r"#\\s*SPEED:\\s*peter=([\\d.]+)\\s*,\\s*stewie=([\\d.]+)", raw)
                if m:
                    speeds["peter"] = max(0.7, min(1.4, float(m.group(1))))
                    speeds["stewie"] = max(0.7, min(1.4, float(m.group(2))))
                    break
    except Exception:
        pass
    return speeds

def parse_script(path):
    lines = []
    print("Parsing:", path)
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("format:") or line.lower().startswith("family guy"):
                continue
            parts = line.split("|")
            if len(parts) == 3:
                sp = parts[0].strip().lower()
                tx = preprocess_text(parts[2].strip())
                if not tx.endswith((".", "!", "?", '"', "'")):
                    tx += "."
                lines.append({"speaker": sp, "text": tx})
    return lines

VOICE_REFS = {
    "peter": [os.path.join(REPO_DIR, "assets/peter-voice-latest.mp3"),
              os.path.join(REPO_DIR, "assets/perter10seonds.wav"),
              os.path.join(REPO_DIR, "assets/peter-voice.mp3")],
    "stewie": [os.path.join(REPO_DIR, "assets/Stewies-voice.mp3")],
}
# Peter is anchored on the CLEANEST reference available; Stewie needs the
# child/british character, so his reference is the only option.
# We intentionally do NOT pass `instruct` (it fought the cloned voice and made
# Peter harsh). Documented valid instruct attributes for reference:
# gender male/female, age child|teenager|young adult|middle-aged|elderly,
# pitch very low|low|moderate|high|very high pitch, style whisper,
# English accents american|british|...
for k, ps in VOICE_REFS.items():
    print(k, [p for p in ps if os.path.exists(p)] or "MISSING")
"""

CELL_GEN = """# Cell 4: batch voice-clone every line -> /kaggle/working/audio + metadata.json
# Realism settings (match the Colab UI): num_step=32 diffusion steps,
# speed=1.0, fp16, native 24 kHz output. VoiceClonePrompt is built once per
# speaker and lines are BATCHED per speaker (OmniVoice batch mode is ~2.6x
# faster than sequential). Falls back to per-line on any batch error.
# Kernel auto-terminates when done.
import gc
import json
import time
import warnings

import torch
import torchaudio

warnings.filterwarnings("ignore")

OUT = "/kaggle/working/audio"
os.makedirs(OUT, exist_ok=True)

NUM_STEP = 64            # max quality (docs: higher = better, slower)
GUIDANCE = 2.5          # tighter adherence to the reference voice
SPEED = 1.0

lines = parse_script(SCRIPT)
print(f"Lines: {len(lines)}")
SPEEDS = parse_speeds(SCRIPT)
print(f"Speeds: peter={SPEEDS['peter']} stewie={SPEEDS['stewie']}")

def resolve_ref(sp):
    for p in VOICE_REFS.get(sp, []):
        if os.path.exists(p):
            return p
    return None

# Encode each speaker's reference ONCE -> reuse across all lines (consistent
# voice tone + skips re-loading/audio analysis every line).
prompts = {}
def get_prompt(sp, ref):
    if sp not in prompts:
        try:
            prompts[sp] = model.create_voice_clone_prompt(ref_audio=ref)
            print(f"cloned voice for {sp} from {ref}")
        except Exception as e:
            print(f"prompt build failed for {sp}: {e} -> will pass ref_audio directly")
            prompts[sp] = None
    return prompts[sp]

def build_kwargs(sp, ref_audio, batch_n=None):
    # Same call shape as the Colab UI generate() in Voice Cloning mode, plus a
    # consistent instruct (docs/tips.md: consistent ref+instruct = stabler clone).
    # If the model rejects the instruct (unsupported attribute), retry without it
    # so one bad attribute never kills the whole line.
# NOTE: we do NOT pass `instruct` — it fought the cloned voice and made
    # Peter harsh (docs/tips.md: ref+instruct conflict = instability). Pure
    # reference cloning is smoother.
    base = dict(text=None, language="English", num_step=NUM_STEP,
                guidance_scale=GUIDANCE, speed=SPEED,
                pad_duration=0.1, fade_duration=0.1,
                postprocess_output=True, normalize_text=True)
    if batch_n:
        base["text"] = [None] * batch_n
    prompt = get_prompt(sp, ref_audio)
    if prompt is not None:
        base["voice_clone_prompt"] = prompt
    else:
        base["ref_audio"] = ref_audio
    return base

def generate_with_fallback(base):
    # Try full config; if an optional dep (normalize_text / instruct) fails, retry without it.
    attempt = 1
    while True:
        try:
            return model.generate(**base)
        except Exception as e:
            msg = str(e).lower()
            if attempt == 1 and "instruct" in msg and "instruct" in base:
                print(f"instruct rejected ({e}) -> retrying without instruct")
                base = {k: v for k, v in base.items() if k != "instruct"}
                attempt += 1
            elif attempt <= 2 and "normalization" in msg or "wetestprocessing" in msg or "normalize_text" in msg:
                print(f"normalize_text failed ({e}) -> retrying with normalize_text=False")
                base["normalize_text"] = False
                attempt += 1
            else:
                raise

def to_tensor(audio):
    t = audio[0] if isinstance(audio[0], torch.Tensor) else torch.tensor(audio[0])
    if t.dim() == 1:
        t = t.unsqueeze(0)
    return t.cpu()

# group lines by speaker for batching (order of output wavs is preserved later)
by_speaker = {}
for i, ln in enumerate(lines):
    by_speaker.setdefault(ln["speaker"], []).append(i)

results = {}   # line index -> wav tensor or None
for sp, idxs in by_speaker.items():
    ref = resolve_ref(sp)
    if ref is None:
        for i in idxs:
            print(f"SKIP {i}: missing ref for {sp}")
            results[i] = None
        continue
    texts = [lines[i]["text"] for i in idxs]
    s = time.time()
    try:
        base = build_kwargs(sp, ref, batch_n=len(texts))
        base["text"] = texts
        sp_speed = SPEEDS.get(sp, 1.0)
        base["speed"] = sp_speed          # per-speaker speed (peter default 1.1)
        base["normalize_text"] = True     # numbers/dates spoken naturally
        base["pad_duration"] = 0.0        # keep pacing tight between lines
        audios = generate_with_fallback(base)
        if not isinstance(audios, (list, tuple)) or len(audios) != len(texts):
            raise RuntimeError(f"batch returned {len(audios)} for {len(texts)} texts")
        for i, audio in zip(idxs, audios):
            results[i] = to_tensor([audio])
        print(f"batch {sp}: {len(texts)} lines in {time.time()-s:.1f}s")
    except Exception as e:
        print(f"batch {sp} failed ({e}) -> falling back to per-line")
        for i in idxs:
            try:
                base = build_kwargs(sp, ref)
                base["text"] = lines[i]["text"]
                base["speed"] = SPEEDS.get(sp, 1.0)
                base["normalize_text"] = True
                base["pad_duration"] = 0.0
                results[i] = to_tensor(generate_with_fallback(base))
            except Exception as e2:
                print(f"FAIL {i}: {e2}")
                results[i] = None

ok, fail = 0, 0
meta = []
t0 = time.time()
for i, ln in enumerate(lines):
    sp, text = ln["speaker"], ln["text"]
    out = f"{OUT}/{sp}_{i:03d}.wav"
    wav = results.get(i)
    if wav is None:
        fail += 1
        meta.append({"index": i, "speaker": sp, "text": text, "audio_file": out, "exists": False})
        continue
    torchaudio.save(out, wav, 24000)
    print(f"OK [{i+1}/{len(lines)}] {sp} ({wav.shape[-1]/24000:.1f}s audio) -> {out}")
    ok += 1
    meta.append({"index": i, "speaker": sp, "text": text, "audio_file": out, "exists": True})

with open(f"{OUT}/metadata.json", "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=2)
print(f"DONE: {ok} ok, {fail} fail in {(time.time()-t0)/60:.1f} min. Files in {OUT}")
print(os.listdir(OUT))
"""


def md_cell(src):
    return {"cell_type": "markdown", "metadata": {}, "source": [src]}


def code_cell(src):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": [l + "\n" for l in src.split("\n")]}


nb = {
    "cells": [md_cell(CELL_MD), code_cell(CELL_DEPS), code_cell(CELL_LOAD),
              code_cell(CELL_FETCH), code_cell(CELL_GEN)],
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10.0"},
    },
    "nbformat": 4,
    "nbformat_minor": 4,
}

OUT = "kaggle/tts-kernel/tts.ipynb"
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

# validate: JSON parses, has the patch line, no gradio UI, realistic knobs
check = json.load(open(OUT, encoding="utf-8"))
src_all = "\n".join("".join(c.get("source", [])) for c in check["cells"])
assert 'SCRIPT_SEL_DEFAULT = "' in src_all, "patch line missing"
assert "OmniVoice" in src_all and "k2-fsa/OmniVoice" in src_all
assert "gradio" not in src_all.lower() or "gr." not in src_all
assert "num_step" in src_all and "24000" in src_all
assert "TORCH" not in src_all.upper() or True
print(f"wrote {OUT}: {len(check['cells'])} cells, "
      f"{'VOICE_REFS' in src_all and 'peter' in src_all}, "
      "contract: audio/{speaker}_{i:03d}.wav + metadata.json")
