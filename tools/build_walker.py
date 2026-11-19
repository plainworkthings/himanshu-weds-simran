"""Builds assets/art/couple-walk.webp: the couple walking hand in hand, for the date page.

  python3 -I tools/build_walker.py

A clean, gently painted figure with no sticker outline: the photo is cut out with its mask
(source/masks/walk-fg.png), the edge is feathered, the colours are warmed toward the date page's
rose-and-marigold palette, and a soft shadow is laid under their feet so they stand on the ground.
Standalone on purpose: running tools/build_art.py would also overwrite the scene art that has faces.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source"
TARGET_H, PAD, FOOT = 900, 18, 46


def kuwahara(im, r):
    """Edge-preserving 'painted' filter (same as build_art.py)."""
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    H, W = a.shape[:2]
    pad = np.pad(a, ((r, r), (r, r), (0, 0)), mode="edge")
    lum = pad.mean(axis=2)
    k = r + 1

    def box(x):
        c = np.cumsum(np.cumsum(x, axis=0), axis=1)
        c = np.pad(c, ((1, 0), (1, 0)) + ((0, 0),) * (x.ndim - 2))
        return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)

    mean = box(pad)
    var = box(lum ** 2) - box(lum) ** 2
    offs = [(0, 0), (0, r), (r, 0), (r, r)]
    v = np.stack([var[dy:dy + H, dx:dx + W] for dy, dx in offs])
    m = np.stack([mean[dy:dy + H, dx:dx + W] for dy, dx in offs])
    idx = np.argmin(v, axis=0)
    out = np.take_along_axis(m, idx[None, ..., None], axis=0)[0]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


im = Image.open(SRC / "walk.jpg").convert("RGB")
m = Image.open(SRC / "masks" / "walk-fg.png").convert("L").resize(im.size, Image.LANCZOS)
box = m.point(lambda v: 255 if v > 40 else 0).getbbox()
box = (max(box[0] - PAD, 0), max(box[1] - PAD, 0), min(box[2] + PAD, im.width), min(box[3] + 4, im.height))
im, m = im.crop(box), m.crop(box)
k = TARGET_H / im.height
size = (round(im.width * k), TARGET_H)
im, m = im.resize(size, Image.LANCZOS), m.resize(size, Image.LANCZOS)

# a light painted finish: one gentle pass, then a touch of sharpening so faces stay crisp
fig = kuwahara(im, 2).filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
a = np.asarray(fig).astype(np.float32) / 255
a = a * np.array([1.0, .965, .955]) + np.array([.03, .012, .02])     # warm the light, rose the shadows
a = np.clip((a - .5) * 1.04 + .5, 0, 1)
fig = ImageEnhance.Color(Image.fromarray((a * 255).astype(np.uint8))).enhance(1.06)

# feathered edge, no outline
alpha = m.filter(ImageFilter.GaussianBlur(1.1)).point(lambda v: min(255, int(max(0, v - 110) * 2.4)))
alpha = alpha.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(1.0))  # pull in past the photo's dark fringe

W, H = size[0], size[1] + FOOT
canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
# a soft contact shadow under each pair of feet, nudged right as if lit from the left
from PIL import ImageDraw
al = np.asarray(alpha)
sh = Image.new("L", (W, H), 0)
d = ImageDraw.Draw(sh)
for lo, hi in ((0, W // 2), (W // 2, W)):
    part = al[:, lo:hi] > 120
    ys = np.where(part.any(axis=1))[0]
    if not len(ys):
        continue
    foot = ys.max()
    xs = np.where(part[foot - 40:foot + 1].any(axis=0))[0] + lo
    d.ellipse((xs.min() - 6, foot - 9, xs.max() + 26, foot + 13), fill=160)
sh = sh.filter(ImageFilter.GaussianBlur(10))
canvas = Image.composite(Image.new("RGBA", (W, H), (70, 28, 40, 255)), canvas, sh.point(lambda v: int(v * .55)))
layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
f = fig.convert("RGBA"); f.putalpha(alpha)
layer.paste(f, (0, 0))
canvas = Image.alpha_composite(canvas, layer)
out = ROOT / "assets" / "art" / "couple-walk.webp"
canvas.save(out, "WEBP", quality=86, method=6, alpha_quality=92)
print(out.name, canvas.size, out.stat().st_size, "bytes")
