"""Tell IndexNow (Bing, Yandex, Seznam, Naver and the AI search tools built on them) which URLs changed.

Usage: python3 newsroom/indexnow.py [content/articles/<new>.json ...]
Always submits the front page, section hubs and the stock pages (they change every run); adds any new
articles passed on the command line. Never fails the workflow: errors are printed and ignored.
"""
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build import INDEXNOW_KEY, SITE, CATS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main(files):
    urls = [f"{SITE}/", f"{SITE}/stocks/"] + [f"{SITE}/section/{c.lower()}/" for c in CATS]
    cache = ROOT / "content" / "market.json"
    if cache.exists():
        urls += [f"{SITE}/stocks/{s.lower()}/" for s in json.loads(cache.read_text())["series"]]
    for f in files:
        try:
            a = json.loads(Path(f).read_text())
            urls.append(f"{SITE}/{datetime.fromisoformat(a['published']):%Y/%m/%d}/{a['id']}/")
        except Exception as e:  # noqa: BLE001
            print("skip", f, e)
    body = json.dumps({"host": SITE.split("//")[1], "key": INDEXNOW_KEY, "keyLocation": f"{SITE}/{INDEXNOW_KEY}.txt",
                       "urlList": list(dict.fromkeys(urls))}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print("IndexNow", r.status, len(urls), "URLs")
    except Exception as e:  # noqa: BLE001
        print("IndexNow failed (ignored):", e)


if __name__ == "__main__":
    main(sys.argv[1:])
