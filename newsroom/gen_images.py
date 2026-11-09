#!/usr/bin/env python3
"""Generate story photos for articles that have an "image_prompt" and no image yet.

Runs in GitHub Actions (publish workflow). Every image gets the same MetaFlora art direction (design board
pick "A Cover", 8 Nov 2026: premium editorial still life, lit like a high-end product commercial, subject in
the right half so the headline sits on the left). Output: content/images/<id>.jpg (1600 wide, 16:9), which the
site shows as the story photo and card.render_photo_card turns into the share card. Articles without a photo
keep their designed card.

Providers, first one configured wins:
  Cloudflare Workers AI (free daily allowance)  CF_ACCOUNT_ID + CF_AI_TOKEN; CF_IMAGE_MODEL
                                                 (default @cf/black-forest-labs/flux-2-klein-4b, Apache-2.0 weights)
  OpenAI (paid)                                  OPENAI_API_KEY; IMAGE_MODEL (gpt-image-1), IMAGE_QUALITY (high)
Skips cleanly when neither is set. MAX_IMAGES (default 50) caps one run so the free allowance is never exceeded.
"""
import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
IMAGES = ROOT / "content" / "images"

# Design board round 4 (9 Nov 2026, model test 4B / 9B / dev: Greg picked klein 4B, free): subject first, house style last
# (FLUX.2 weights the start of a prompt most), written positively (klein has no negative prompt). Keep prompts to one hero
# object and at most one supporting object: 4B drops extra elements.
STYLE = (
    "Premium product-commercial photograph in the style of an Apple advertisement: clean and minimal, one hero object, "
    "soft diffused studio light, crisp detail, subtle reflections, refined palette of deep charcoal and soft indigo with a "
    "faint violet edge light on the hero object, shallow depth of field, real materials. The hero subject sits in the right "
    "half of the frame; the left half is calm and darker. Every surface is plain and unprinted. 16:9 landscape photograph."
)


def _post(req, timeout=300):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (400, 401, 403, 404):
                raise RuntimeError(f"HTTP {e.code}: {msg}") from None
            print(f"  retry after {e.code}: {msg}")
        except Exception as e:  # noqa: BLE001
            print(f"  retry after error: {e}")
        time.sleep(10 * (attempt + 1))
    raise RuntimeError("image generation failed after retries")


def cloudflare(prompt, account, token, model):
    """Workers AI. FLUX.2 models take multipart/form-data; FLUX.1 schnell takes JSON. Both return base64 in result.image."""
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
    fields = {"prompt": prompt.strip() + " " + STYLE, "width": "1536", "height": "864"}
    if "flux-2" in model:
        b = uuid.uuid4().hex
        body = "".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in fields.items())
        body = (body + f"--{b}--\r\n").encode()
        ctype = f"multipart/form-data; boundary={b}"
    else:
        body = json.dumps({"prompt": (prompt.strip() + " " + STYLE)[:2048], "steps": 8}).encode()
        ctype = "application/json"
    req = urllib.request.Request(url, data=body, headers={"Authorization": f"Bearer {token}", "Content-Type": ctype})
    raw, rtype = _post(req)
    if rtype.startswith("image/"):
        return raw
    data = json.loads(raw)
    if not data.get("success", True):
        raise RuntimeError(f"Workers AI error: {data.get('errors')}")
    return base64.b64decode((data.get("result") or data)["image"])


def openai(prompt, key, model, quality):
    body = json.dumps({"model": model, "prompt": prompt.strip() + " " + STYLE, "size": "1536x1024", "quality": quality, "n": 1}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    item = json.loads(_post(req)[0])["data"][0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    with urllib.request.urlopen(item["url"], timeout=120) as r:
        return r.read()


def provider():
    if os.environ.get("CF_ACCOUNT_ID") and os.environ.get("CF_AI_TOKEN"):
        model = os.environ.get("CF_IMAGE_MODEL") or "@cf/black-forest-labs/flux-2-klein-4b"
        return f"Cloudflare {model}", lambda p: cloudflare(p, os.environ["CF_ACCOUNT_ID"], os.environ["CF_AI_TOKEN"], model)
    if os.environ.get("OPENAI_API_KEY"):
        model, quality = os.environ.get("IMAGE_MODEL") or "gpt-image-1", os.environ.get("IMAGE_QUALITY") or "high"
        return f"OpenAI {model}", lambda p: openai(p, os.environ["OPENAI_API_KEY"], model, quality)
    return None, None


def main():
    name, gen = provider()
    if not gen:
        print("No image provider configured (CF_ACCOUNT_ID + CF_AI_TOKEN, or OPENAI_API_KEY); stories keep their designed cards.")
        return 0
    cap = int(os.environ.get("MAX_IMAGES") or 50)
    IMAGES.mkdir(parents=True, exist_ok=True)
    made = failed = 0
    # newest stories first, so a capped run always covers the latest edition
    for p in sorted(ARTICLES.glob("*.json"), reverse=True):
        if made + failed >= cap:
            break
        a = json.loads(p.read_text(encoding="utf-8"))
        out = IMAGES / f"{a['id']}.jpg"
        if out.exists() or not a.get("image_prompt"):
            continue
        print(f"Generating photo ({name}): {a['id']}")
        try:
            im = Image.open(io.BytesIO(gen(a["image_prompt"]))).convert("RGB")
            im = im.resize((1600, round(1600 * im.height / im.width)), Image.LANCZOS)
            im.save(out, "JPEG", quality=86, optimize=True, progressive=True)
            made += 1
        except Exception as e:  # noqa: BLE001
            print(f"  failed ({e}); keeping the designed card")
            failed += 1
    print(f"Photos generated: {made}, failed: {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
