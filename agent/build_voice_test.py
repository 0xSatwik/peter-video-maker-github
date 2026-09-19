"""Build kaggle/voice-test/tts.ipynb — Peter voice A/B test across settings.

Generates the SAME Peter line with different num_step / guidance_scale combos so
the best-sounding setting can be picked by ear before committing to the main
kernel. Output: /kaggle/working/audio/step32_gs20.wav etc.
"""
import json

CELL_MD = """# Peter voice A/B test — OmniVoice settings

Clones Peter from `assets/peter-voice-latest.mp3` and renders the same sentence
with different `num_step` / `guidance_scale` values so the best one can be chose
by ear. No instruct (instruct conflicts with the cloned voice and sounds harsh).
"""

CELL_DEPS = """# Cell 1: deps
!pip install -q omnivoice
!python -c "import torchaudio" 2>/dev/null || pip install -q torchaudio
print("deps ok")
"""

CELL_LOAD = """# Cell 2: load OmniVoice + fetch the clean Peter reference
import os
import torch
import torchaudio
from omnivoice import OmniVoice

device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
dtype = torch.float16 if torch.cuda.is_available() else torch.float32
assert device == 'cuda:0', "GPU not attached!"
print(f"GPU: {torch.cuda.get_device_name(0)}")

REPO_DIR = "/tmp/pvrepo"
!rm -rf /tmp/pvrepo
!git clone --depth 1 --filter=blob:none --sparse https://github.com/0xSatwik/peter-video-maker-github.git /tmp/pvrepo
!git -C /tmp/pvrepo sparse-checkout set --no-cone assets/peter-voice-latest.mp3

REF = os.path.join(REPO_DIR, "assets/peter-voice-latest.mp3")
print("ref exists:", os.path.exists(REF))

model = OmniVoice.from_pretrained('k2-fsa/OmniVoice', device_map=device, dtype=dtype)
model.eval()
prompt = model.create_voice_clone_prompt(ref_audio=REF)
print("voice cloned from", REF)
"""

CELL_GEN = """# Cell 3: render the same line across settings
import os
import time

OUT = "/kaggle/working/audio"
os.makedirs(OUT, exist_ok=True)

LINE = ("Stewie, I read that over four hundred and thirty thousand live AWS keys "
        "were leaked into public repositories, and eighty-eight percent of them "
        "still work right now.")

COMBOS = [
    (32, 2.0),
    (64, 2.0),
    (32, 2.5),
    (64, 2.5),
]

# NOTE: the line is already spelled out in words, so normalize_text is not
# needed here (it requires the optional WeTextProcessing dependency).

for steps, gs in COMBOS:
    name = f"step{steps}_gs{str(gs).replace('.', '')}"
    t0 = time.time()
    try:
        audio = model.generate(
            text=LINE,
            language="English",
            voice_clone_prompt=prompt,
            num_step=steps,
            guidance_scale=gs,
            speed=1.1,
            pad_duration=0.0,
        )
        t = audio[0] if isinstance(audio[0], torch.Tensor) else torch.tensor(audio[0])
        if t.dim() == 1:
            t = t.unsqueeze(0)
        path = f"{OUT}/{name}.wav"
        torchaudio.save(path, t.cpu(), 24000)
        print(f"OK {name} ({t.shape[-1] / 24000:.1f}s, {time.time() - t0:.1f}s) -> {path}")
    except Exception as e:
        print(f"FAIL {name}: {e}")

print("files:", sorted(os.listdir(OUT)))
"""


def md_cell(src):
    return {"cell_type": "markdown", "metadata": {}, "source": [src]}


def code_cell(src):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": [l + "\n" for l in src.split("\n")]}


nb = {
    "cells": [md_cell(CELL_MD), code_cell(CELL_DEPS), code_cell(CELL_LOAD), code_cell(CELL_GEN)],
    "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                 "language_info": {"name": "python", "version": "3.10.0"}},
    "nbformat": 4,
    "nbformat_minor": 4,
}

import os

os.makedirs("kaggle/voice-test", exist_ok=True)

with open("kaggle/voice-test/tts.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

meta = {
    "code_file": "tts.ipynb",
    "dataset_data_sources": [],
    "enable_gpu": True,
    "enable_internet": True,
    "id": "satwiksamanta/peter-voice-test",
    "is_private": True,
    "kernel_type": "notebook",
    "language": "python",
    "title": "peter-voice-test",
}
with open("kaggle/voice-test/kernel-metadata.json", "w", encoding="utf-8") as f:
    json.dump(meta, f)

print("wrote kaggle/voice-test/{tts.ipynb,kernel-metadata.json}")
