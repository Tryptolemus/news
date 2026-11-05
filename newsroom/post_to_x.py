#!/usr/bin/env python3
"""Post a new edition's top stories to X (@MetaFloraLabs), each linking to its article.

Run by .github/workflows/post-to-x.yml after the newsroom pushes an edition.
Credentials come from GitHub repo secrets (OAuth 1.0a user context of the posting account):
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
Optional repo variable X_POSTS_PER_EDITION (default 3).

Usage: post_to_x.py <file> [<file> ...]   (the article JSON files added by the push)
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

SITE = "https://news.metaflora.xyz"
URL_LEN = 23  # X counts every link as 23 characters
LIMIT = 280


def article_url(a):
    dt = datetime.fromisoformat(a["published"])
    return f"{SITE}/{dt:%Y/%m/%d}/{a['id']}/"


def compose(a):
    url = article_url(a)
    text = (a.get("x_post") or "").strip() or f"{a['headline']}\n\n{a['dek']}"
    tags = " #cannabis"
    budget = LIMIT - URL_LEN - 2 - len(tags)
    if len(text) > budget:
        text = text[: budget - 1].rstrip() + "…"
    return f"{text}{tags}\n\n{url}", url


def wait_live(url, timeout=900):
    """GitHub Pages takes a minute or two to deploy; post only once the page (and its card) is live."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(20)
    return False


def main(files):
    keys = [os.environ.get(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")]
    if not all(keys):
        print("X credentials not set; skipping X posts.")
        return 0
    from requests_oauthlib import OAuth1Session

    arts = []
    for f in files:
        p = Path(f)
        if p.suffix == ".json" and p.exists():
            arts.append(json.loads(p.read_text()))
    if not arts:
        print("No new articles in this push.")
        return 0
    latest = max(a["edition"] for a in arts)
    arts = sorted([a for a in arts if a["edition"] == latest], key=lambda a: a.get("rank", 99))
    n = int(os.environ.get("X_POSTS_PER_EDITION") or 3)
    x = OAuth1Session(keys[0], client_secret=keys[1], resource_owner_key=keys[2], resource_owner_secret=keys[3])
    failures = 0
    for a in arts[:n]:
        text, url = compose(a)
        if not wait_live(url):
            print(f"Page not live, skipped: {url}")
            failures += 1
            continue
        r = x.post("https://api.x.com/2/tweets", json={"text": text})
        if r.status_code in (200, 201):
            print(f"Posted: {a['headline']} -> https://x.com/i/status/{r.json()['data']['id']}")
        else:
            print(f"X API error {r.status_code}: {r.text[:300]}")
            failures += 1
        time.sleep(90)  # space posts out
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
