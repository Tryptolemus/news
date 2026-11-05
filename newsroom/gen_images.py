#!/usr/bin/env python3
"""Generate AI banner images for articles that have an "image_prompt" and no image yet.

Runs in GitHub Actions (publish workflow) with OPENAI_API_KEY from repo secrets.
Every image gets the same MetaFlora art direction so the site looks like one publication.
Output: content/images/<id>.jpg (1600x1067). Articles without an image keep their designed cover.

Env:
  OPENAI_API_KEY      required (skips cleanly when absent)
  IMAGE_MODEL         default gpt-image-1
  IMAGE_QUALITY       default high   (low | medium | high)
"""
import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
IMAGES = ROOT / "content" / "images"

STYLE = (
    "Documentary news photograph for a serious business publication, as if shot by a photojournalist on a 35mm lens "
    "with available light. Natural grain, slightly underexposed, muted desaturated grade, cool shadows, a faint green cast in the highlights. "
    "Subject off-centre to the right with calm negative space in the left third, shallow depth of field, real places and real materials. 3:2 landscape. "
    "Strictly no text, letters, numbers, signage, logos or watermarks. No neon, no smoke effects, no purple lighting, no glowing leaves, "
    "no holograms, no symmetry, no illustration or CGI look. No identifiable real people and no public figures: "
    "people only as hands, backs or out-of-focus figures. Scene: "
)


def generate(prompt, key, model, quality):
    body = json.dumps({"model": model, "prompt": STYLE + prompt, "size": "1536x1024", "quality": quality, "n": 1}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read())
            item = data["data"][0]
            if item.get("b64_json"):
                return base64.b64decode(item["b64_json"])
            with urllib.request.urlopen(item["url"], timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (400, 401, 403):
                raise RuntimeError(f"OpenAI {e.code}: {msg}") from None
            print(f"  retry after {e.code}: {msg}")
        except Exception as e:  # noqa: BLE001
            print(f"  retry after error: {e}")
        time.sleep(10 * (attempt + 1))
    raise RuntimeError("image generation failed after retries")


def main():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("OPENAI_API_KEY not set; articles keep their designed covers.")
        return 0
    model = os.environ.get("IMAGE_MODEL") or "gpt-image-1"
    quality = os.environ.get("IMAGE_QUALITY") or "high"
    IMAGES.mkdir(parents=True, exist_ok=True)
    made = failed = 0
    for p in sorted(ARTICLES.glob("*.json")):
        a = json.loads(p.read_text())
        out = IMAGES / f"{a['id']}.jpg"
        if out.exists() or not a.get("image_prompt"):
            continue
        print(f"Generating banner: {a['id']}")
        try:
            raw = generate(a["image_prompt"], key, model, quality)
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            im = im.resize((1600, round(1600 * im.height / im.width)), Image.LANCZOS)
            im.save(out, "JPEG", quality=86, optimize=True, progressive=True)
            made += 1
        except Exception as e:  # noqa: BLE001
            print(f"  failed ({e}); keeping designed cover")
            failed += 1
    print(f"Banners generated: {made}, failed: {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
