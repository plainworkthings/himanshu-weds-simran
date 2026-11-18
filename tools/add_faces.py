"""Gives the faceless illustrated bride and groom real, recognisable faces using an image model.

  python3 tools/add_faces.py              # uses OPENAI_API_KEY or GEMINI_API_KEY
  python3 tools/add_faces.py --dry-run    # checks the pipeline without calling any model
  python3 tools/add_faces.py --only sufi  # one scene

The key is read from the environment or from a `.env` file in the project root
(`OPENAI_API_KEY=...` or `GEMINI_API_KEY=...`). `.env` is git-ignored; never commit it.

For each scene the current bottom artwork strip (assets/art/<scene>-bottom.webp) is sent with two
reference photos of the couple. The result replaces the strip, keeping its exact size and its faded top
edge, so nothing else on the page changes. The first run backs the originals up to source/art-before-faces/.
Re-running starts from those backups, so you can iterate on the prompt.
"""
import argparse
import base64
import io
import json
import os
import sys
import urllib.request
import uuid
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ART, SRC = ROOT / "assets" / "art", ROOT / "source"
BACKUP = SRC / "art-before-faces"
REFS = [SRC / "beach.jpg", SRC / "car-close.jpg"]  # both show the couple's faces clearly

STYLE = (
    "Keep everything else in the illustration exactly as it is: the same composition, poses, outfits, colours, "
    "background, lighting and soft flat digital-illustration style. Faces must match that style: clean, elegant, "
    "softly shaded semi-realistic illustration, like a premium Indian wedding invitation. Not anime, not chibi, not a "
    "caricature, not photorealistic. Keep the likeness strong enough that friends instantly recognise them: face "
    "shape, eyes, nose, smile, hairline, and his short beard. Warm, happy, graceful expressions. No text, no watermark."
)
WHO = (
    "Reference photos: the woman with long dark hair is the bride, Simran. The man with short black hair and a "
    "trimmed beard is the groom, Himanshu."
)
SCENES = {
    "sufi": "This illustration shows the bride in a red-and-pink lehenga and the groom in a dark sherwani, standing "
            "together, but their faces are blank. Paint Simran's face on the bride and Himanshu's face on the groom.",
    "reception": "This illustration shows the bride in a magenta lehenga with a pink dupatta and the groom in a black "
                 "tuxedo under spotlights, with blank faces. Paint Simran's face on the bride and Himanshu's face on "
                 "the groom.",
    "baraat": "This illustration shows a baraat: the groom in a turban and pink sherwani standing in a vintage car, with "
              "three dancing friends, all with blank faces. Paint Himanshu's face on the groom (keep his turban; his "
              "sunglasses may stay, pushed up or on, as long as he is recognisable). Give the three friends pleasant, "
              "generic faces in the same style that do not resemble the couple.",
}


def load_key():
    env = dict(os.environ)
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    if env.get("OPENAI_API_KEY"):
        return "openai", env["OPENAI_API_KEY"], env.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
    if env.get("GEMINI_API_KEY") or env.get("GOOGLE_API_KEY"):
        return "gemini", env.get("GEMINI_API_KEY") or env["GOOGLE_API_KEY"], env.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    return None, None, None


def png_bytes(im):
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()


def ref_bytes(p):
    im = Image.open(p).convert("RGB"); im.thumbnail((1024, 1024)); b = io.BytesIO(); im.save(b, "JPEG", quality=90); return b.getvalue()


def call_openai(key, model, scene_png, size, prompt):
    boundary = uuid.uuid4().hex
    parts = []
    def field(name, value):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    def file(name, fname, data, ctype):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{fname}"\r\nContent-Type: {ctype}\r\n\r\n'.encode() + data + b"\r\n")
    field("model", model); field("prompt", prompt); field("size", size); field("quality", "high"); field("input_fidelity", "high"); field("n", "1")
    file("image[]", "scene.png", scene_png, "image/png")
    for i, p in enumerate(REFS):
        file("image[]", f"ref{i}.jpg", ref_bytes(p), "image/jpeg")
    body = b"".join(parts) + f"--{boundary}--\r\n".encode()
    req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.load(r)
    return Image.open(io.BytesIO(base64.b64decode(data["data"][0]["b64_json"]))).convert("RGB")


def call_gemini(key, model, scene_png, size, prompt):
    parts = [{"text": prompt + f" Output a single image with aspect ratio {size.replace('x', ':')}."},
             {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(scene_png).decode()}}]
    for p in REFS:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(ref_bytes(p)).decode()}})
    body = json.dumps({"contents": [{"parts": parts}], "generationConfig": {"responseModalities": ["IMAGE"]}}).encode()
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                 data=body, method="POST", headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.load(r)
    for part in data["candidates"][0]["content"]["parts"]:
        blob = part.get("inline_data") or part.get("inlineData")
        if blob:
            return Image.open(io.BytesIO(base64.b64decode(blob["data"]))).convert("RGB")
    raise RuntimeError("Gemini returned no image: " + json.dumps(data)[:400])


def process(scene, provider, key, model, dry):
    src_path = ART / f"{scene}-bottom.webp"
    BACKUP.mkdir(parents=True, exist_ok=True)
    orig_path = BACKUP / src_path.name
    if not orig_path.exists():
        orig_path.write_bytes(src_path.read_bytes())
    orig = Image.open(orig_path).convert("RGBA")
    W, H = orig.size
    a = np.asarray(orig)
    solid = a[a[..., 3] == 255][..., :3]
    bg = tuple(int(x) for x in np.median(solid[: max(1, W * 8)], axis=0))  # colour the faded top blends into
    flat = Image.new("RGB", (W, H), bg); flat.paste(orig, (0, 0), orig)

    # fit to the nearest size the model can return, cropping or padding only at the faded top
    sizes = {"1024x1024": 1.0, "1536x1024": 1.5, "1024x1536": 2 / 3}
    size = min(sizes, key=lambda s: abs(sizes[s] - W / H))
    ratio = sizes[size]
    need_h = round(W / ratio)
    if need_h <= H:
        cut, pad = H - need_h, 0
        fitted = flat.crop((0, cut, W, H))
    else:
        cut, pad = 0, need_h - H
        fitted = Image.new("RGB", (W, need_h), bg); fitted.paste(flat, (0, pad))
    tw, th = (int(x) for x in size.split("x"))
    send = fitted.resize((tw, th), Image.LANCZOS)

    prompt = f"{SCENES[scene]} {WHO} {STYLE}"
    if dry:
        out = send
    else:
        print(f"  {scene}: asking {provider} ({model}) at {size}…", flush=True)
        out = (call_openai if provider == "openai" else call_gemini)(key, model, png_bytes(send), size, prompt)

    out = out.resize(fitted.size, Image.LANCZOS)
    if pad:
        out = out.crop((0, pad, W, pad + H))
    else:
        top = Image.new("RGB", (W, H), bg); top.paste(out, (0, cut)); out = top
    out = out.convert("RGBA"); out.putalpha(orig.getchannel("A"))
    (SRC / "faces").mkdir(exist_ok=True)
    if not dry:
        out.save(SRC / "faces" / f"{scene}-bottom.png")  # full-quality copy of what the model made
    out.save(src_path, "WEBP", quality=82, method=6, alpha_quality=90)
    print(f"  {scene}: wrote {src_path.relative_to(ROOT)} ({W}x{H})" + (" [dry run]" if dry else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", choices=sorted(SCENES))
    args = ap.parse_args()
    provider, key, model = load_key()
    if not args.dry_run and not key:
        sys.exit("No OPENAI_API_KEY or GEMINI_API_KEY found (environment or .env). See the docstring.")
    for scene in [args.only] if args.only else SCENES:
        try:
            process(scene, provider, key, model, args.dry_run)
        except urllib.error.HTTPError as e:
            sys.exit(f"{scene}: the image API refused the request ({e.code}): {e.read()[:400]!r}")


if __name__ == "__main__":
    main()
