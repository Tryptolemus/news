#!/usr/bin/env python3
"""Render design-board photo candidates (see .github/workflows/photo-test.yml). Writes tools/photo_tests/out/<name>.jpg."""
import io
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "newsroom"))
import gen_images  # noqa: E402
from PIL import Image  # noqa: E402

spec = json.loads((HERE / "prompts.json").read_text(encoding="utf-8"))
if spec.get("style"):
    gen_images.STYLE = spec["style"]
name, gen = gen_images.provider()
if not gen:
    sys.exit("no provider configured")
out = HERE / "out"
out.mkdir(exist_ok=True)
ok = 0
for it in spec["items"][: int(os.environ.get("MAX_IMAGES") or 24)]:
    try:
        im = Image.open(io.BytesIO(gen(it["prompt"]))).convert("RGB")
        im.save(out / f"{it['name']}.jpg", "JPEG", quality=90)
        ok += 1
        print("ok", it["name"])
    except Exception as e:  # noqa: BLE001
        print("FAILED", it["name"], e)
print(f"{ok}/{len(spec['items'])} rendered with {name}")
