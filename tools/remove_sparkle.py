"""Paints out the small four-point sparkle Gemini stamps in the bottom-right corner of its pictures.

  python3 tools/remove_sparkle.py sufi reception baraat carnival

Works on assets/art/<scene>-bottom.webp in place (the full-quality copy in source/faces/ is used as input
when it exists). The sparkle is found as pale, low-saturation pixels brighter than their surroundings in the
corner, then filled by diffusing the colours around it inwards.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent


def clean(scene):
    src = ROOT / "source" / "faces" / f"{scene}-bottom.png"
    dst = ROOT / "assets" / "art" / f"{scene}-bottom.webp"
    im = Image.open(src if src.exists() else dst).convert("RGBA")
    W, H = im.size
    box = (W - 135, H - 130, W - 25, H - 20)  # the sparkle sits about 80 px in from the corner
    rgb = np.asarray(im.convert("RGB").crop(box)).astype(float)
    lum = rgb.mean(axis=2)
    blur = np.asarray(Image.fromarray(lum.astype(np.uint8)).filter(ImageFilter.GaussianBlur(14))).astype(float)
    sat = (rgb.max(axis=2) - rgb.min(axis=2)) / (rgb.max(axis=2) + 1)
    mask = (lum - blur > 22) & (sat < .16) & (lum > 160)
    if mask.sum() < 40:
        print(f"  {scene}: no sparkle found"); return
    m = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))
    hole = np.asarray(m) > 0
    fill = rgb.copy(); known = ~hole
    fill[hole] = 0
    for _ in range(400):  # diffuse surrounding colour into the hole
        acc = np.zeros_like(fill); cnt = np.zeros(hole.shape)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            k = np.roll(known, (dy, dx), (0, 1)); v = np.roll(fill, (dy, dx), (0, 1))
            acc += v * k[..., None]; cnt += k
        upd = hole & (cnt > 0)
        fill[upd] = acc[upd] / cnt[upd][:, None]
        known = known | upd
    # a little grain so the patch does not look airbrushed
    noise = np.random.default_rng(1).normal(0, 3, fill.shape)
    fill[hole] = np.clip(fill[hole] + noise[hole], 0, 255)
    out = np.asarray(im).copy()
    out[box[1]:box[3], box[0]:box[2], :3] = fill.astype(np.uint8)
    res = Image.fromarray(out, "RGBA")
    if src.exists():
        res.save(src)
    res.save(dst, "WEBP", quality=82, method=6, alpha_quality=90)
    print(f"  {scene}: removed {int(hole.sum())} px")


for s in sys.argv[1:]:
    clean(s)
