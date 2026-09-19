"""Character cut-out + polish, shared by both assembly engines.

Fixes the "little blue box" problem: the old loader only zeroed *near-black*
pixels, so anti-aliased background pixels (dark blue/grey, e.g. RGB 40,40,60)
stayed opaque and formed a visible halo/box around each character.

Pipeline per character:
  1. estimate the background colour from the image corners
  2. soft chroma-key: alpha = smoothstep(distance from bg colour)
  3. de-fringe: unmix the background tint out of semi-transparent edge pixels
     (this is what actually removes the blue cast)
  4. feather the mask slightly (kills jaggies)
  5. scale with LANCZOS to the configured height
  6. add a thin dark border + a subtle drop shadow for a clean, "stickers"
     look on the background
"""
import os

import numpy as np
from PIL import Image, ImageFilter

CHAR_HEIGHT_BASE = 750
CHAR_SCALES = {'peter': 1.10, 'stewie': 0.95}

# keying thresholds (0-255 colour distance from the background colour)
BG_SOFT_IN = 26      # below this = fully background
BG_SOFT_OUT = 64     # above this = fully character
BORDER_PX = 3        # "very small" border, as requested
BORDER_COLOR = (14, 16, 26)
SHADOW_OPACITY = 90  # 0-255, subtle


def _bg_color(rgb):
    """Median colour of the four corner patches = the flat background colour."""
    h, w, _ = rgb.shape
    p = max(4, min(h, w) // 24)
    corners = np.concatenate([
        rgb[:p, :p].reshape(-1, 3), rgb[:p, -p:].reshape(-1, 3),
        rgb[-p:, :p].reshape(-1, 3), rgb[-p:, -p:].reshape(-1, 3),
    ])
    return np.median(corners, axis=0)


def cut_out(img, soft_in=BG_SOFT_IN, soft_out=BG_SOFT_OUT):
    """Return an RGBA numpy array with a clean alpha channel and no bg fringe."""
    arr = np.array(img.convert("RGB")).astype(np.float32)
    bg = _bg_color(arr)

    # 2. soft key on colour distance from the background colour
    dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))
    alpha = np.clip((dist - soft_in) / max(1.0, soft_out - soft_in), 0.0, 1.0)

    # keep any genuine transparency the source already had
    src_alpha = np.array(img.convert("RGBA"))[:, :, 3].astype(np.float32) / 255.0
    alpha = np.minimum(alpha, np.where(src_alpha < 0.99, src_alpha, 1.0))

    # 3. de-fringe: F = (C - B*(1-a)) / a  (removes the leftover background tint)
    a3 = alpha[:, :, None]
    safe = np.clip(a3, 0.15, 1.0)
    unMixed = (arr - bg[None, None, :] * (1.0 - a3)) / safe
    rgb = np.where(a3 > 0.02, np.clip(unMixed, 0, 255), arr)

    rgba = np.dstack([rgb, alpha * 255.0]).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def add_border_and_shadow(img, border_px=BORDER_PX):
    """Thin dark border + soft shadow -> sticker-like, attractive look."""
    alpha = img.getchannel("A")

    # border: dilate the alpha silhouette, then draw it behind the character
    grown = alpha.filter(ImageFilter.MaxFilter(border_px * 2 + 1))
    border_layer = Image.new("RGBA", img.size, BORDER_COLOR + (0,))
    border_layer.putalpha(grown)

    out = Image.alpha_composite(border_layer, img)

    # shadow: offset + blurred copy of the grown silhouette, behind everything
    shadow_alpha = grown.filter(ImageFilter.GaussianBlur(6))
    shadow_alpha = shadow_alpha.point(lambda v: int(v * SHADOW_OPACITY / 255))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha)
    canvas = Image.new("RGBA", (img.width + 24, img.height + 24), (0, 0, 0, 0))
    canvas.paste(shadow, (14, 14), shadow)
    canvas.paste(out, (4, 4), out)
    return canvas


def load_character(name, assets_dir="assets", polish=True):
    """Load assets/{name}.png|jpg, cut it out cleanly, scale, border, shadow.

    Returns (PIL RGBA image, width, height) or None when no asset exists.
    """
    for ext in ("png", "jpg", "jpeg"):
        src = os.path.join(assets_dir, f"{name}.{ext}")
        if not os.path.exists(src):
            continue
        img = Image.open(src).convert("RGBA")

        # if the source already carries a real alpha channel, trust it
        a = np.array(img)[:, :, 3]
        if (a == 0).mean() > 0.05:
            cut = img
        else:
            cut = cut_out(img)

        target_h = int(CHAR_HEIGHT_BASE * CHAR_SCALES.get(name, 1.0))
        scale = target_h / cut.height
        new_w = max(1, int(cut.width * scale))
        resized = cut.resize((new_w, target_h), Image.LANCZOS)

        if polish:
            resized = add_border_and_shadow(resized)
        return resized, resized.width, resized.height
    return None