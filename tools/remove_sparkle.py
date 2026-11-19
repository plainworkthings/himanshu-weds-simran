"""Removes the four-point sparkle Gemini stamps near the bottom-right corner of its pictures.

  python3 -I tools/remove_sparkle.py <in.png|webp> <out.png>

Run it on the picture Gemini made, before tools/add_faces.py --use. Instead of blurring the mark
(which leaves a smudge), it finds the exact star and rebuilds it from the outside in, 13x13 pixels at a
time, each time copying the nearby patch whose known pixels match best (exemplar inpainting), so the
floor, path or fabric texture carries on through.
"""
import sys

import numpy as np
from PIL import Image, ImageFilter


def star_mask(a, box):
    """Pale, low-saturation pixels clearly brighter than their surroundings, largest blob only."""
    x0, y0, x1, y1 = box
    c = a[y0:y1, x0:x1].astype(np.float32)
    lum = c.mean(axis=2)
    sat = (c.max(axis=2) - c.min(axis=2)) / (c.max(axis=2) + 1)
    bg = np.asarray(Image.fromarray(lum.astype(np.uint8)).filter(ImageFilter.GaussianBlur(25))).astype(np.float32)
    m = (lum > 175) & (sat < .14) & (lum - bg > 12)
    # keep the blob nearest the box centre (simple flood fill from the brightest central pixel)
    h, w = m.shape
    cy, cx = h // 2, w // 2
    ys, xs = np.nonzero(m)
    if not len(ys):
        return None
    k = np.argmin((ys - cy) ** 2 + (xs - cx) ** 2)
    seen = np.zeros_like(m)
    stack = [(ys[k], xs[k])]
    while stack:
        y, x = stack.pop()
        if y < 0 or x < 0 or y >= h or x >= w or seen[y, x] or not m[y, x]:
            continue
        seen[y, x] = True
        stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    full = np.zeros(a.shape[:2], bool)
    full[y0:y1, x0:x1] = seen
    return full


def grow(mask, px):
    return np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(px * 2 + 1))) > 0


def clean(src, dst):
    im = Image.open(src).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    H, W = a.shape[:2]
    s = W / 2000
    box = (int(W - 190 * s), int(H - 190 * s), int(W - 10 * s), int(H - 10 * s))
    m = star_mask(a.astype(np.uint8), box)
    if m is None or m.sum() < 400 * s * s:
        print(f"  {src}: no sparkle found"); im.save(dst); return
    hole = grow(m, max(3, int(4 * s)))
    # work in a window around the star
    ys, xs = np.nonzero(hole)
    M = int(110 * s)
    y0, y1 = max(0, ys.min() - M), min(H, ys.max() + M)
    x0, x1 = max(0, xs.min() - M), min(W, xs.max() + M)
    win = a[y0:y1, x0:x1].copy()
    unk = hole[y0:y1, x0:x1].copy()
    P = 6  # patch radius: 13x13 patches keep strokes and folds coherent
    h, w = unk.shape
    # every fully-known 9x9 patch in the window is a candidate source
    from numpy.lib.stride_tricks import sliding_window_view as swv
    srcs = swv(win, (2 * P + 1, 2 * P + 1), axis=(0, 1))          # (h-2P, w-2P, 3, 9, 9)
    okm = swv(~unk, (2 * P + 1, 2 * P + 1)).all(axis=(2, 3))         # sources free of the hole
    cy, cx = np.nonzero(okm)
    cand = srcs[cy, cx].reshape(len(cy), -1)                         # (N, 3*81)
    # fill from the outside in: the hole pixels with the most known neighbours first
    while unk.any():
        known = (~unk).astype(np.float32)
        cnt = np.asarray(Image.fromarray((known * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(P))).astype(np.float32)
        front = unk & (cnt > 0)
        fy, fx = np.nonzero(front)
        order = np.argsort(-cnt[fy, fx])
        done_any = False
        for i in order[: max(1, len(order) // 6)]:
            y, x = fy[i], fx[i]
            if not unk[y, x] or y < P or x < P or y >= h - P or x >= w - P:
                continue
            t = win[y - P:y + P + 1, x - P:x + P + 1].transpose(2, 0, 1).reshape(-1)
            k = (~unk[y - P:y + P + 1, x - P:x + P + 1]).reshape(-1)
            k3 = np.tile(k, 3)
            if k3.sum() == 0:
                continue
            d = ((cand[:, k3] - t[k3]) ** 2).mean(axis=1)
            j = np.argmin(d)
            patch = cand[j].reshape(3, 2 * P + 1, 2 * P + 1).transpose(1, 2, 0)
            u = unk[y - P:y + P + 1, x - P:x + P + 1]
            win[y - P:y + P + 1, x - P:x + P + 1][u] = patch[u]
            unk[y - P:y + P + 1, x - P:x + P + 1] = False
            done_any = True
        if not done_any:  # edge pixels the patch could not reach: take the mean of known neighbours
            yy, xx = np.nonzero(unk)
            for y, x in zip(yy, xx):
                nb = win[max(0, y - 2):y + 3, max(0, x - 2):x + 3][~unk[max(0, y - 2):y + 3, max(0, x - 2):x + 3]]
                win[y, x] = nb.mean(axis=0) if len(nb) else win[y, x]
            unk[:] = False
    # a light median inside the rebuilt area only, to melt the patch seams
    med = np.asarray(Image.fromarray(np.clip(win, 0, 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(5))).astype(np.float32)
    soft = np.asarray(Image.fromarray(hole[y0:y1, x0:x1].astype(np.uint8) * 255).filter(ImageFilter.GaussianBlur(2))).astype(np.float32)[..., None] / 255
    win = win * (1 - soft) + med * soft
    out = a.copy()
    out[y0:y1, x0:x1] = win
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(dst)
    print(f"  {src.split('/')[-1]}: star {int(m.sum())} px rebuilt from {len(cy)} nearby patches")


if __name__ == "__main__":
    clean(sys.argv[1], sys.argv[2])
