#!/usr/bin/env python3
"""Post stories to the MetaFlora Discord news channel through a channel webhook (run by hand from
.github/workflows/discord.yml, or the "Post to Discord" button in the alerts admin). Nothing posts automatically.

Secret: DISCORD_WEBHOOK_URL (Discord: channel settings > Integrations > Webhooks > New Webhook > Copy Webhook URL).
Usage: post_to_discord.py top3            the latest edition's top 3 stories (same as "Ready for X")
       post_to_discord.py <id>[,<id>...]  specific stories by article id
Each post is an embed: headline linking to the article, the X text as the description, and the story's share card.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notify_logic as L  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://news.metaflora.xyz"
VIOLET = 0xA78BFA


def load():
    arts = [json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "content" / "articles").glob("*.json")]
    return [a for a in arts if not a.get("draft")]


def pick(arts, which):
    if which in ("", "top3"):
        ids = [x["id"] for x in L.x_ready(arts)]
    else:
        ids = [s.strip() for s in which.split(",") if s.strip()]
    by = {a["id"]: a for a in arts}
    missing = [i for i in ids if i not in by]
    if missing:
        sys.exit(f"Unknown story id(s): {', '.join(missing)}")
    return [by[i] for i in ids]


def embed(a):
    text = L.x_text(a).replace(L.X_TAGS, "").strip()
    return {"title": a["headline"][:256], "url": L.article_url(a), "description": text[:4000], "color": VIOLET,
            "image": {"url": f"{SITE}/og/{a['id']}.png"},
            "author": {"name": a.get("cat", "MetaFlora News").upper()},
            "footer": {"text": "MetaFlora News · news.metaflora.xyz", "icon_url": f"{SITE}/assets/icons/icon-192.png"},
            "timestamp": datetime.fromisoformat(a["published"]).isoformat()}


def send(hook, payload):
    body = json.dumps(payload).encode()
    for attempt in range(4):
        req = urllib.request.Request(hook + ("&" if "?" in hook else "?") + "wait=true", data=body,
                                     headers={"Content-Type": "application/json", "User-Agent": "MetaFloraNews (news.metaflora.xyz, 1.0)"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = float(json.loads(e.read() or b"{}").get("retry_after", 2))
                time.sleep(wait + 0.5)
                continue
            raise RuntimeError(f"Discord HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from None
    raise RuntimeError("Discord rate limit: gave up after retries")


def main(which):
    hook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not hook:
        sys.exit("DISCORD_WEBHOOK_URL is not set (repo secret).")
    for a in pick(load(), which):
        send(hook, {"username": "MetaFlora News", "avatar_url": f"{SITE}/assets/icons/icon-192.png",
                    "embeds": [embed(a)], "allowed_mentions": {"parse": []}})
        print("posted", a["id"])
        time.sleep(1.5)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "top3"))
