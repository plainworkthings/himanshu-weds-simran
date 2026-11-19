"""Builds assets/art/edge.png: the hand-painted, uneven top edge each section fades in with.

  python3 -I tools/build_edge.py

Opaque is visible, transparent is see-through (CSS masks use the alpha channel). The edge wanders like a watercolour wash (a few octaves of
smooth noise), feathers softly, and has a little granulation so it reads as paint, not a gradient.
The image is wide so each section can show a different stretch of it (mask-position in styles.css).
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

W, H = 1400, 110
rng = np.random.default_rng(7)


def smooth_noise(n, scale):
    pts = rng.random(n // scale + 3)
    x = np.arange(n) / scale
    i = x.astype(int); t = x - i; t = t * t * (3 - 2 * t)
    return pts[i] * (1 - t) + pts[i + 1] * t


edge = sum(smooth_noise(W, s) * a for s, a in ((250, .55), (85, .3), (28, .12), (8, .05)))
edge = (edge - edge.min()) / (edge.max() - edge.min())
edge = H * (.28 + .44 * edge)                                  # the wash line wanders through the middle
soft = H * (.10 + .14 * smooth_noise(W, 150))                  # and is sharper in some places than others
y = np.arange(H)[:, None]
a = np.clip((y - (edge - soft)) / (2 * soft), 0, 1)
a = a * a * (3 - 2 * a)
grain = np.asarray(Image.fromarray((rng.random((H, W)) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.6))) / 255.0
a = np.clip(a + (grain - .5) * .35 * (a * (1 - a) * 4), 0, 1)    # granulation only along the wet edge
a[:4] = 0; a[-6:] = 1
out = Path(__file__).resolve().parent.parent / "assets" / "art" / "edge.png"
alpha = Image.fromarray((a * 255).astype(np.uint8), "L")
Image.merge("LA", (Image.new("L", alpha.size, 255), alpha)).save(out, optimize=True)  # masks read alpha
print(out, out.stat().st_size, "bytes")
