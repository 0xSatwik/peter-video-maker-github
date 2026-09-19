"""Verify char_art cut-out: measure background-colour pixels left around the edges."""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import char_art  # noqa: E402

for name in ("peter", "stewie"):
    src = None
    for ext in ("png", "jpg", "jpeg"):
        p = os.path.join("assets", f"{name}.{ext}")
        if os.path.exists(p):
            src = p
            break
    if not src:
        print(name, "no asset")
        continue

    raw = Image.open(src).convert("RGBA")
    arr = np.array(raw.convert("RGB")).astype(np.float32)
    bg = char_art._bg_color(arr)
    a0 = np.array(raw)[:, :, 3]
    print(f"\n=== {name} ({src}) ===")
    print("bg colour estimate:", bg.round(1), "| source has alpha:", bool((a0 == 0).mean() > 0.05))

    cut = char_art.cut_out(raw)
    ca = np.array(cut)[:, :, 3].astype(np.float32)
    opaque = ca > 20

    # how many *background-coloured* pixels survive as opaque?
    dist = np.sqrt(((np.array(cut.convert("RGB")).astype(np.float32) - bg) ** 2).sum(axis=2))
    leftovers = int(((dist < 40) & opaque).sum())
    total_opaque = int(opaque.sum())
    print(f"opaque px: {total_opaque}, of which near-bg-colour: {leftovers} "
          f"({100.0 * leftovers / max(1, total_opaque):.2f}%)")

    final, w, h = char_art.load_character(name)
    out = f"output/charcut_{name}.png"
    final.save(out)
    print(f"saved {out} ({w}x{h})")