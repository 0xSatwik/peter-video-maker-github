"""CPU TTS fallback (edge-tts): generates audio/<speaker>_NNN.wav + audio/metadata.json
from a SPEAKER|TAGS|DIALOGUE script file. Used by the workflow when Kaggle GPU
quota is exhausted. Voices are stock neural voices (not cloned), good enough
for validation runs.

Usage: python scripts/tts_cpu.py config/scripts/AUTO_xxx.txt
"""
import asyncio
import json
import os
import sys

import edge_tts

VOICES = {
    "peter": "en-US-ChristopherNeural",   # deep-ish male
    "stewie": "en-GB-RyanNeural",          # british male
}
DEFAULT_VOICE = "en-US-GuyNeural"


def parse_script(path):
    lines = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) == 3:
                lines.append({"speaker": parts[0].strip().lower(), "text": parts[2].strip()})
    return lines


async def synth(text, voice, out):
    await edge_tts.Communicate(text, voice).save(out)


async def main(path):
    lines = parse_script(path)
    if not lines:
        print("FATAL: no dialogue lines in", path)
        sys.exit(1)
    os.makedirs("audio", exist_ok=True)
    meta = []
    for i, ln in enumerate(lines):
        sp, text = ln["speaker"], ln["text"]
        out = f"audio/{sp}_{i:03d}.wav"
        voice = VOICES.get(sp, DEFAULT_VOICE)
        try:
            await synth(text, voice, out)
            ok = os.path.exists(out)
        except Exception as e:
            print(f"FAIL [{i}] {e}")
            ok = False
        print(("OK" if ok else "FAIL"), f"[{i + 1}/{len(lines)}] {sp} -> {out}")
        meta.append({"index": i, "speaker": sp, "text": text, "audio_file": out, "exists": ok})
    with open("audio/metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    if not any(m["exists"] for m in meta):
        print("FATAL: no audio generated")
        sys.exit(1)
    print(f"DONE: {sum(m['exists'] for m in meta)}/{len(meta)} clips")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "config/scripts/EPISODE_01.txt"))
