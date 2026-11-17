"""Builds the site's artwork from the source media.

  python3 -I tools/build_art.py <plates_dir> <masks_dir>

plates_dir : PNG frames grabbed from the invitation video (f_<seconds>.png)
masks_dir  : subject masks for the photos (<name>-fg.png), made by tools/mask.swift
Outputs go to assets/art/. Prints the colours the stylesheet needs.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

ROOT = Path(__file__).resolve().parent.parent
PLATES, MASKS = Path(sys.argv[1]), Path(sys.argv[2])
OUT = ROOT / "assets" / "art"
OUT.mkdir(parents=True, exist_ok=True)
SRC = ROOT / "source"


# ── helpers ──────────────────────────────────────────────────────────────
def load(name):
    return Image.open(PLATES / name).convert("RGB")


def inpaint_text(im, rect, thr=9, grow=7, radius=9):
    """Remove lettering inside rect (x0,y0,x1,y1 px) by filling it from the surrounding wash."""
    x0, y0, x1, y1 = rect
    a = np.asarray(im).astype(np.float32)
    region = Image.fromarray(a[y0:y1, x0:x1].astype(np.uint8))
    smooth = np.asarray(region.filter(ImageFilter.GaussianBlur(14))).astype(np.float32)
    diff = np.abs(a[y0:y1, x0:x1] - smooth).max(axis=2)
    m = Image.fromarray(((diff > thr) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(grow))
    mf = np.asarray(m).astype(np.float32) / 255.0
    keep = 1.0 - mf
    fill, got = None, None
    for rad in (radius, 18, 36, 72):  # widen the search until every hole is filled
        num = np.asarray(Image.fromarray((a[y0:y1, x0:x1] * keep[..., None]).astype(np.uint8)).filter(ImageFilter.GaussianBlur(rad))).astype(np.float32)
        den = np.asarray(Image.fromarray((keep * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(rad))).astype(np.float32) / 255.0
        cand = num / np.maximum(den, 1e-3)[..., None]
        ok = den > 0.1
        if fill is None:
            fill, got = cand, ok
        else:
            fill = np.where(got[..., None], fill, cand)
            got = got | ok
    soft = np.asarray(m.filter(ImageFilter.GaussianBlur(1.5))).astype(np.float32)[..., None] / 255.0
    a[y0:y1, x0:x1] = a[y0:y1, x0:x1] * (1 - soft) + fill * soft
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def up2(im, k=3):
    """Enlarge a video frame and redraw its edges cleanly (the frames are only 464 px wide)."""
    big = im.resize((im.width * k, im.height * k), Image.BICUBIC)
    big = kuwahara(kuwahara(big, 2), 4)
    return big.filter(ImageFilter.UnsharpMask(radius=2, percent=90, threshold=2))


def row_colour(im, y):
    a = np.asarray(im).astype(np.float32)
    y = int(np.clip(y, 2, im.height - 3))
    band = a[y - 2:y + 3, int(im.width * .3):int(im.width * .7)]
    r, g, b = np.median(band.reshape(-1, 3), axis=0)
    return "#%02x%02x%02x" % (int(r), int(g), int(b))


def strip(im, y0, y1, fade_top=0.0, fade_bottom=0.0):
    """Crop rows y0..y1 (fractions) and fade the chosen edges to transparent."""
    H = im.height
    a, b = int(H * y0), int(H * y1)
    crop = im.crop((0, a, im.width, b)).convert("RGBA")
    h = crop.height
    alpha = np.ones((h, crop.width), np.float32)
    ft, fb = int(H * fade_top), int(H * fade_bottom)
    if ft:
        ramp = np.linspace(0, 1, ft) ** 1.4
        alpha[:ft] *= ramp[:, None]
    if fb:
        ramp = np.linspace(1, 0, fb) ** 1.4
        alpha[h - fb:] *= ramp[:, None]
    crop.putalpha(Image.fromarray((alpha * 255).astype(np.uint8)))
    return crop


def save(im, name, q=76):
    im.save(OUT / name, "WEBP", quality=q, method=6, alpha_quality=90)
    return name


def kuwahara(im, r):
    """Edge-preserving 'painted' filter."""
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


def paint(im, r=3, passes=2, sat=1.18, con=1.06):
    for _ in range(passes):
        im = kuwahara(im, r)
    im = ImageEnhance.Color(im).enhance(sat)
    return ImageEnhance.Contrast(im).enhance(con)


# ── 1. plates from the invitation film ──────────────────────────────────
colours = {}

hero = up2(inpaint_text(load("f_2.40.png"), (250, 0, 464, 60), thr=6))
save(hero, "hero.webp", 78)
colours["hero_top"] = row_colour(hero, 20)

date = inpaint_text(load("f_20.0.png"), (96, 340, 372, 627))
save(up2(date), "date.webp", 78)

scenes = {
    # name: (frame, text rect or None, top end, top fade, bottom start, bottom fade)
    "floral": ("g_15.0.png", None, .36, .10, .70, .08),
    "carnival": ("f_25.5.png", None, .17, .07, .40, .10),
    "sufi": ("f_33.2.png", None, .34, .09, .44, .10),
    "baraat": ("f_41.6.png", None, .42, .14, .60, .10),
    "reception": ("f_52.5.png", (40, 256, 430, 455), .31, .08, .52, .08),
    "closing": ("f_60.0.png", (16, 350, 450, 495), .26, .09, .60, .16),
}
for name, (frame, rect, t_end, t_fade, b_start, b_fade) in scenes.items():
    im = load(frame)
    if rect:
        im = inpaint_text(im, rect)
    big = up2(im)
    save(strip(big, 0, t_end, fade_bottom=t_fade), f"{name}-top.webp")
    save(strip(big, b_start, 1, fade_top=b_fade), f"{name}-bottom.webp")
    colours[name] = [row_colour(big, big.height * (t_end - t_fade * .2)), row_colour(big, big.height * (b_start + b_fade * .2))]
    colours[name + "_ratio"] = [round(t_end * 832 / 464, 4), round((1 - b_start) * 832 / 464, 4)]

# ── 2. the couple, cut out and repainted ────────────────────────────────
def cutout(name, target_h, outline=6, r=3, pad=14):
    im = Image.open(SRC / f"{name}.jpg").convert("RGB")
    m = Image.open(MASKS / f"{name}-fg.png").convert("L").resize(im.size, Image.LANCZOS)
    box = m.point(lambda v: 255 if v > 40 else 0).getbbox()
    box = (max(box[0] - pad, 0), max(box[1] - pad, 0), min(box[2] + pad, im.width), min(box[3] + pad, im.height))
    im, m = im.crop(box), m.crop(box)
    k = target_h / im.height
    size = (round(im.width * k), target_h)
    im, m = im.resize(size, Image.LANCZOS), m.resize(size, Image.LANCZOS)
    painted = paint(im, r=r)
    m = m.filter(ImageFilter.GaussianBlur(.8)).point(lambda v: min(255, int(max(0, v - 60) * 1.7)))
    if not outline:
        painted.putalpha(m)
        return painted
    # paper-doll edge and a soft baked shadow
    margin = outline + 16
    W, H = size[0] + margin * 2, size[1] + margin * 2
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mm = Image.new("L", (W, H), 0)
    mm.paste(m, (margin, margin))
    edge = mm.filter(ImageFilter.MaxFilter(outline * 2 + 1)).filter(ImageFilter.GaussianBlur(1.2))
    shadow = Image.new("L", (W, H), 0)
    shadow.paste(edge, (0, 7))
    shadow = shadow.filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * .34))
    canvas = Image.composite(Image.new("RGBA", (W, H), (40, 20, 10, 255)), canvas, shadow)
    canvas = Image.composite(Image.new("RGBA", (W, H), (255, 252, 244, 255)), canvas, edge)
    fig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fig.paste(painted, (margin, margin))
    canvas = Image.composite(fig, canvas, mm)
    return canvas


save(cutout("walk", 760), "couple-walk.webp", 84)
save(cutout("car-wide", 760), "couple-lean.webp", 84)

# ── 3. whole photos repainted, for the gallery ──────────────────────────
for name in ["beach", "car-wide", "carry", "walk", "car-close"]:
    im = Image.open(SRC / f"{name}.jpg").convert("RGB")
    im = im.resize((760, round(im.height * 760 / im.width)), Image.LANCZOS)
    save(paint(im, r=3, passes=2, sat=1.22, con=1.08), f"painting-{name}.webp", 80)

print(json.dumps(colours, indent=1))
