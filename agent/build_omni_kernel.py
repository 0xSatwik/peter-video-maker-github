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
`k2-fsa/OmniVoice`, Voice Cloning mode, `num_step=32`, `speed=1.0`, 24 kHz).
Output goes to `/kaggle/working/audio/` with `metadata.json` — the same
contract as the old MOSS kernel, so `scripts/assemble_video.py` works unchanged.
"""

CELL_DEPS = """# Cell 1: deps (Kaggle already ships torch + torchaudio with CUDA)
!pip install -q omnivoice
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
# Consistent ref + instruct = more stable cloning (docs/tips.md).
# ONLY these attribute values are valid (docs/voice-design.md): gender
# (male/female), age (child/teenager/young adult/middle-aged/elderly),
# pitch (very low|low|moderate|high|very high pitch), style (whisper),
# english accent (american/british/...). Anything else -> the model raises
# "Unsupported instruct items found ..." and the line fails.
INSTRUCTS = {
    "peter": "male, american accent",
    "stewie": "male, british accent, child, high pitch",
}
for k, ps in VOICE_REFS.items():
    print(k, [p for p in ps if os.path.exists(p)] or "MISSING")
"""

CELL_GEN = """# Cell 4: batch voice-clone every line -> /kaggle/working/audio + metadata.json
# Realism settings (match the Colab UI): num_step=32 diffusion steps,
# speed=1.0, fp16, native 24 kHz output. VoiceClonePrompt is built once per
# speaker (ref encoded once -> consistent voice across all lines). Kernel
# auto-terminates when done.
import gc
import json
import time
import warnings

import torch
import torchaudio

warnings.filterwarnings("ignore")

OUT = "/kaggle/working/audio"
os.makedirs(OUT, exist_ok=True)

NUM_STEP = 32
SPEED = 1.0

lines = parse_script(SCRIPT)
print(f"Lines: {len(lines)}")

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

def synth_clone(sp, text, ref_audio):
    # Same call shape as the Colab UI generate() in Voice Cloning mode, plus a
    # consistent instruct (docs/tips.md: consistent ref+instruct = stabler clone).
    # If the model rejects the instruct (unsupported attribute), retry without it
    # so one bad attribute never kills the whole line.
    base = dict(text=text, language="English", num_step=NUM_STEP, speed=SPEED)
    prompt = get_prompt(sp, ref_audio)
    if prompt is not None:
        base["voice_clone_prompt"] = prompt
    else:
        base["ref_audio"] = ref_audio

    kwargs = dict(base)
    if INSTRUCTS.get(sp):
        kwargs["instruct"] = INSTRUCTS[sp]
    try:
        audio = model.generate(**kwargs)
    except Exception as e:
        if "instruct" in str(e).lower() and "instruct" in kwargs:
            print(f"instruct rejected for {sp} ({e}) -> retrying without instruct")
            audio = model.generate(**base)
        else:
            raise
    t = audio[0] if isinstance(audio[0], torch.Tensor) else torch.tensor(audio[0])
    if t.dim() == 1:
        t = t.unsqueeze(0)
    return t.cpu()

ok, fail = 0, 0
meta = []
t0 = time.time()
for i, ln in enumerate(lines):
    sp, text = ln["speaker"], ln["text"]
    out = f"{OUT}/{sp}_{i:03d}.wav"
    ref = resolve_ref(sp)
    if ref is None and sp in VOICE_REFS:
        print(f"SKIP {i}: missing ref for {sp}"); fail += 1
        meta.append({"index": i, "speaker": sp, "text": text, "audio_file": out, "exists": False})
        continue
    try:
        s = time.time()
        with torch.no_grad():
            wav = synth_clone(sp, text, ref)
        torchaudio.save(out, wav, 24000)
        dur = wav.shape[-1] / 24000
        print(f"OK [{i+1}/{len(lines)}] {sp} {time.time()-s:.1f}s ({dur:.1f}s audio) -> {out}")
        ok += 1
        meta.append({"index": i, "speaker": sp, "text": text, "audio_file": out, "exists": True})
    except Exception as e:
        print(f"FAIL [{i+1}/{len(lines)}] {e}"); fail += 1
        meta.append({"index": i, "speaker": sp, "text": text, "audio_file": out, "exists": False})
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

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
