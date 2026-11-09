#!/usr/bin/env python3
"""Post stories to the MetaFlora Discord news channel through a channel webhook.

Automatic: after each edition deploys, the publish workflow posts its top 3 stories (the same ones as "Ready for X";
DISCORD_POSTS_PER_EDITION changes the count, DISCORD_AUTO=0 switches it off). By hand: .github/workflows/discord.yml,
or the "Post to Discord" button in the alerts admin.

Secret: DISCORD_WEBHOOK_URL (Discord: channel settings > Integrations > Webhooks > New Webhook > Copy Webhook URL).
Usage: post_to_discord.py --new <file>...  the top stories of the newest edition among these new article files
       post_to_discord.py top3            the latest edition's top 3 stories (same as "Ready for X")
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


def new_top(files):
    arts = [json.loads(Path(f).read_text(encoding="utf-8")) for f in files if f.endswith(".json") and Path(f).exists()]
    arts = [a for a in arts if not a.get("draft")]
    if not arts:
        return []
    ed = max(a["edition"] for a in arts)
    n = int(os.environ.get("DISCORD_POSTS_PER_EDITION") or 3)
    return sorted([a for a in arts if a["edition"] == ed], key=lambda a: a.get("rank", 99))[:n]


def wait_live(url, timeout=900):
    """Pages takes a minute or two to deploy: post only once the article and its card answer."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "MetaFloraNews"}), timeout=20) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(20)
    return False


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


def main(args):
    hook = os.environ.get("DISCORD_WEBHOOK_URL")
    auto = args[:1] == ["--new"]
    if auto and os.environ.get("DISCORD_AUTO") == "0":
        print("DISCORD_AUTO is 0; not posting.")
        return 0
    if not hook:
        if auto:
            print("DISCORD_WEBHOOK_URL is not set; skipping Discord.")
            return 0
        sys.exit("DISCORD_WEBHOOK_URL is not set (repo secret).")
    stories = new_top(args[1:]) if auto else pick(load(), args[0] if args else "top3")
    if not stories:
        print("No new stories to post.")
        return 0
    for a in stories:
        if auto and not (wait_live(L.article_url(a)) and wait_live(f"{SITE}/og/{a['id']}.png", 300)):
            print("page not live yet, skipped", a["id"])
            continue
        send(hook, {"username": "MetaFlora News", "avatar_url": f"{SITE}/assets/icons/icon-192.png",
                    "embeds": [embed(a)], "allowed_mentions": {"parse": []}})
        print("posted", a["id"])
        time.sleep(1.5)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
