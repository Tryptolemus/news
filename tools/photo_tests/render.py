#!/usr/bin/env python3
"""Render design-board photo candidates (see .github/workflows/photo-test.yml). Writes tools/photo_tests/out/<name>.jpg.

prompts.json: {"style": "...", "models": ["@cf/...", ...] (optional), "items": [{"name", "prompt", "model"?}]}
With "models", every item is rendered once per model (name suffixed with the model's short name), cheapest first.
"""
import io
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "newsroom"))
import gen_images  # noqa: E402
from PIL import Image  # noqa: E402

spec = json.loads((HERE / "prompts.json").read_text(encoding="utf-8"))
if spec.get("style"):
    gen_images.STYLE = spec["style"]
acct, token = os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_AI_TOKEN")
if not (acct and token):
    sys.exit("CF_ACCOUNT_ID / CF_AI_TOKEN not set")
jobs = []
for m in spec.get("models") or [os.environ.get("CF_IMAGE_MODEL") or "@cf/black-forest-labs/flux-2-klein-4b"]:
    for it in spec["items"]:
        short = m.rsplit("/", 1)[-1].replace("flux-2-", "")
        jobs.append((f"{it['name']}__{short}", it["prompt"], it.get("model") or m))
out = HERE / "out"
out.mkdir(exist_ok=True)
ok = 0
for name, prompt, model in jobs:
    t0 = time.time()
    try:
        im = Image.open(io.BytesIO(gen_images.cloudflare(prompt, acct, token, model))).convert("RGB")
        im.save(out / f"{name}.jpg", "JPEG", quality=92)
        ok += 1
        print(f"ok {name} {im.size} {time.time() - t0:.1f}s")
    except Exception as e:  # noqa: BLE001
        print(f"FAILED {name}: {str(e)[:300]}")
print(f"{ok}/{len(jobs)} rendered")
