"""Renders the entrance artwork: two carved, lit door leaves, a marigold toran and a stone texture.

  python3 -I tools/build_door.py

Everything is drawn from a height map and lit like a 3D surface, so there are no source images.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent.parent / "assets" / "art"
rng = np.random.default_rng(7)
W, H = 520, 1766


def blur(a, r):
    """Gaussian blur of a float array (separable, edges clamped)."""
    k = int(r * 3) + 1
    x = np.arange(-k, k + 1, dtype=np.float32)
    g = np.exp(-(x / r) ** 2 / 2); g /= g.sum()
    a = a.astype(np.float32)
    p = np.pad(a, ((0, 0), (k, k)), mode="edge")
    out = np.zeros_like(a)
    for i, w in enumerate(g):
        out += w * p[:, i:i + a.shape[1]]
    p = np.pad(out, ((k, k), (0, 0)), mode="edge")
    res = np.zeros_like(a)
    for i, w in enumerate(g):
        res += w * p[i:i + a.shape[0], :]
    return res


def noise(h, w, cell_y, cell_x):
    small = rng.random((max(2, h // cell_y + 2), max(2, w // cell_x + 2))).astype(np.float32)
    return np.asarray(Image.fromarray(small, "F").resize((w, h), Image.BICUBIC), np.float32)


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def rect_sd(X, Y, x0, y0, x1, y1):
    """Distance inside a rectangle (positive inside, 0 at the edge)."""
    return np.minimum(np.minimum(X - x0, x1 - X), np.minimum(Y - y0, y1 - Y))


def light(height, albedo, brass, spec_paint=.12):
    gy, gx = np.gradient(height)
    n = np.stack([-gx, -gy, np.ones_like(height)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    L = np.array([-.46, -.62, .64]); L /= np.linalg.norm(L)
    Hh = L + np.array([0, 0, 1.0]); Hh /= np.linalg.norm(Hh)
    diff = np.clip((n @ L) / L[2], .2, 2.0)
    ndh = np.clip(n @ Hh, 0, 1)
    spec = np.where(brass > .5, ndh ** 26 * .95, ndh ** 9 * spec_paint)
    ao = np.clip((blur(height, 16) - height) * .04, 0, .42)                       # recesses sit in shade
    cast = np.clip((np.roll(height, (7, 5), (0, 1)) - height) * .07, 0, .4)        # short cast shadows
    shade = (.34 + .66 * diff) * (1 - ao) * (1 - blur(cast, 2.5))
    col = albedo * shade[..., None] + spec[..., None] * np.array([255, 240, 205], np.float32)
    return np.clip(col, 0, 255)


def door(letter, mirror):
    Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
    h = np.zeros((H, W), np.float32)
    brass = np.zeros((H, W), np.float32)
    gold = np.zeros((H, W), np.float32)

    # planks
    for px in (130, 262, 392):
        h -= 2.2 * np.exp(-((X - px) / 2.2) ** 2)

    # four recessed panels, each with a raised field and a carved rosette
    mx, top, ph, gap = 50, 138, 352, 60
    rails = []
    for i in range(4):
        y0 = top + i * (ph + gap); y1 = y0 + ph
        rails.append(y1 + gap / 2)
        d = rect_sd(X, Y, mx, y0, W - mx, y1)
        h -= 11 * smooth(0, 15, d)
        d2 = rect_sd(X, Y, mx + 40, y0 + 40, W - mx - 40, y1 - 40)
        h += 8 * smooth(0, 13, d2)
        h += 2.5 * smooth(-7, 0, d2) * (1 - smooth(0, 7, d2))                      # bead around the field
        cx, cy, R = W / 2, (y0 + y1) / 2, 104
        dx, dy = X - cx, Y - cy
        r = np.hypot(dx, dy); phi = np.arctan2(dy, dx)
        edge = R * (.6 + .4 * np.abs(np.cos(4 * phi)) ** .8)
        petal = np.clip(1 - (r / edge) ** 2, 0, 1)
        vein = .82 + .18 * np.cos(16 * phi)
        h += 10 * petal ** .7 * vein * (r > 22)
        inner = np.clip(1 - (r / (R * .46 * (.7 + .3 * np.abs(np.sin(4 * phi))))) ** 2, 0, 1)
        h += 5 * inner ** .7
        boss = np.sqrt(np.clip(22 ** 2 - r ** 2, 0, None)) * .55
        h += boss
        ring = np.clip(1 - ((r - (R + 20)) / 5.5) ** 2, 0, 1)
        h += 3.5 * ring
        gold = np.maximum(gold, np.maximum(petal > 0, ring > .05).astype(np.float32) * .78)
        brass = np.maximum(brass, (r < 22).astype(np.float32))
        # corner leaves
        for sx in (-1, 1):
            for sy in (-1, 1):
                lx, ly = cx + sx * 150, cy + sy * 122
                u = ((X - lx) * sx + (Y - ly) * sy) / 1.414; v = ((X - lx) * sx - (Y - ly) * sy) / 1.414
                leaf = np.clip(1 - (u / 30) ** 2 - (v / 13) ** 2, 0, 1)
                h += 5 * leaf ** .6
                gold = np.maximum(gold, (leaf > 0).astype(np.float32) * .6)

    # brass studs along the rails
    for ry in [top - gap / 2] + rails:
        for sx_ in (74, 204, 334, 452):
            if ry == rails[1] and sx_ > 300:
                continue  # the monogram plaque sits here
            r = np.hypot(X - sx_, Y - ry)
            h += np.sqrt(np.clip(13 ** 2 - r ** 2, 0, None)) * .9
            h += 2 * np.clip(1 - ((r - 17) / 3) ** 2, 0, 1)
            brass = np.maximum(brass, (r < 19.5).astype(np.float32))

    # brass strap down the meeting edge, with rivets
    strap = np.clip(1 - ((X - (W - 15)) / 15) ** 2, 0, 1)
    h += 8 * np.sqrt(strap)
    brass = np.maximum(brass, (X > W - 30).astype(np.float32))
    for ry in range(60, H, 118):
        r = np.hypot(X - (W - 15), Y - ry)
        h += np.sqrt(np.clip(6.5 ** 2 - r ** 2, 0, None))

    # monogram plaque and ring knocker near the meeting edge
    pcx, pcy = W - 122, rails[1]
    r = np.hypot(X - pcx, Y - pcy)
    h += 9 * smooth(66, 58, r) + 4 * np.clip(1 - ((r - 58) / 6) ** 2, 0, 1)
    brass = np.maximum(brass, (r < 66).astype(np.float32))
    kcx, kcy, KR, kt = pcx, pcy + 100, 33, 7.5
    r = np.hypot(X - kcx, Y - kcy)
    h += np.sqrt(np.clip(kt ** 2 - (r - KR) ** 2, 0, None)) * 1.5
    brass = np.maximum(brass, (np.abs(r - KR) < kt).astype(np.float32))
    rb = np.hypot(X - kcx, Y - (kcy - KR))
    h += np.sqrt(np.clip(13 ** 2 - rb ** 2, 0, None)) * .9
    brass = np.maximum(brass, (rb < 13).astype(np.float32))

    if mirror:
        h, brass, gold = h[:, ::-1].copy(), brass[:, ::-1].copy(), gold[:, ::-1].copy()
        pcx = W - 1 - pcx

    # the initial, raised on its plaque (never mirrored)
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Didot.ttc", 92)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).text((pcx, pcy - 4), letter, font=font, fill=255, anchor="mm")
    h += blur(np.asarray(mask, np.float32) / 255, 1.6) * 5.5

    # painted, weathered wood
    grain = .6 * noise(H, W, 110, 3) + .4 * noise(H, W, 34, 2)
    blotch = noise(H, W, 220, 150)
    paint = np.array([19, 88, 97], np.float32) * (.82 + .3 * grain)[..., None] * (.88 + .22 * blotch)[..., None]
    paint += np.array([-4, 6, 10], np.float32) * smooth(-9, -3, h)[..., None]       # deeper tone in the recesses
    curv = np.clip((blur(h, 1.5) - blur(h, 6)) * .22, 0, .55) * (noise(H, W, 26, 26) > .35)
    paint = paint * (1 - curv[..., None]) + np.array([168, 140, 98], np.float32) * curv[..., None]   # worn edges
    brass_col = np.array([206, 160, 62], np.float32) * (.9 + .2 * noise(H, W, 40, 40))[..., None]
    gold_col = np.array([190, 150, 66], np.float32) * (.85 + .3 * grain)[..., None]
    albedo = paint * (1 - gold[..., None]) + gold_col * gold[..., None]
    albedo = albedo * (1 - brass[..., None]) + brass_col * brass[..., None]

    col = light(h + (grain - .5) * 1.1, albedo, brass)
    vy = Y / H
    col *= (1 - .3 * smooth(.72, 1, vy) - .18 * smooth(.2, 0, vy))[..., None]       # falls into shadow top and bottom
    return Image.fromarray(col.astype(np.uint8))


def toran():
    """A marigold garland: pompoms strung in swags with short drops, on a transparent ground."""
    TW, TH = 1120, 330
    col = np.zeros((TH, TW, 3), np.float32)
    alpha = np.zeros((TH, TW), np.float32)
    Y, X = np.mgrid[0:TH, 0:TW].astype(np.float32)

    def pom(cx, cy, r, tone):
        x0, x1, y0, y1 = int(max(cx - r - 2, 0)), int(min(cx + r + 3, TW)), int(max(cy - r - 2, 0)), int(min(cy + r + 3, TH))
        if x1 <= x0 or y1 <= y0:
            return
        dx, dy = X[y0:y1, x0:x1] - cx, Y[y0:y1, x0:x1] - cy
        d = np.hypot(dx, dy) / r; phi = np.arctan2(dy, dx)
        ph = rng.random() * 6.28
        ruffle = .5 + .5 * np.cos(11 * phi + ph + d * 9) * np.cos(d * 13 + ph)
        body = np.clip(1 - d ** 2, 0, 1) ** .5
        shade = .5 + .62 * np.clip(body * .9 + (-dx * .46 - dy * .62) / r * .5, 0, 1.2)
        shade *= .8 + .28 * ruffle
        base = np.array([[246, 150, 22], [250, 190, 40], [232, 112, 20]][tone], np.float32)
        a = smooth(1.04, .9, d * (1 + .05 * np.cos(9 * phi + ph)))
        c = np.clip(base * shade[..., None], 0, 255)
        col[y0:y1, x0:x1] = col[y0:y1, x0:x1] * (1 - a[..., None]) + c * a[..., None]
        alpha[y0:y1, x0:x1] = np.maximum(alpha[y0:y1, x0:x1], a)

    spans, drop = 4, 5
    span = TW / spans
    # short drops first so the swags overlap them
    for j in range(spans + 1):
        x = j * span
        for k in range(drop):
            pom(x + rng.normal(0, 1.5), 46 + k * 34, 18 - k * .8, (k + j) % 2)
        pom(x, 46 + drop * 34 + 6, 11, 2)
    for row, (depth, r, y0) in enumerate([(118, 21, 30), (78, 17, 22)]):
        for j in range(spans):
            n = int(span / (r * 1.25))
            for i in range(n + 1):
                t = i / n
                x = j * span + t * span
                y = y0 + depth * (1 - (2 * t - 1) ** 2) ** .9
                pom(x + rng.normal(0, 1.2), y + rng.normal(0, 1.2), r * (1 + rng.normal(0, .05)), (i + row) % 2)
    out = np.dstack([col, alpha * 255]).astype(np.uint8)
    im = Image.fromarray(out, "RGBA")
    shadow = Image.new("RGBA", im.size, (60, 30, 5, 0))
    shadow.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * .45)))
    canvas = Image.new("RGBA", im.size, (0, 0, 0, 0))
    canvas.alpha_composite(shadow, (0, 9)); canvas.alpha_composite(im)
    return canvas


def stone():
    """A seamless sandstone grain, used over the arch walls."""
    S = 128
    a = rng.random((S, S)).astype(np.float32)
    tile = np.tile(a, (3, 3))
    fine = blur(tile, 1.1)[S:2 * S, S:2 * S]
    coarse = blur(tile, 9)[S:2 * S, S:2 * S]
    fine = (fine - fine.mean()) / fine.std(); coarse = (coarse - coarse.mean()) / coarse.std()
    v = fine * .55 + coarse * .45
    alpha = np.clip(np.abs(v) * 62, 0, 120) + (a > .988) * 70
    rgb = np.where(v[..., None] > 0, np.array([255, 246, 228]), np.array([84, 50, 20])).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, np.clip(alpha, 0, 255).astype(np.uint8)]), "RGBA")


door("H", False).save(OUT / "door-left.webp", "WEBP", quality=82, method=6)
door("S", True).save(OUT / "door-right.webp", "WEBP", quality=82, method=6)
toran().save(OUT / "toran.webp", "WEBP", quality=86, method=6, alpha_quality=92)
stone().save(OUT / "stone.webp", "WEBP", quality=55, method=6, alpha_quality=60)
for f in ("door-left", "door-right", "toran", "stone"):
    p = OUT / f"{f}.webp"
    print(f, Image.open(p).size, p.stat().st_size // 1024, "KB")
