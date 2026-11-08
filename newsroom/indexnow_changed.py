"""Tell IndexNow about the hub and aggregate pages whose content changed in a push.

indexnow.py already submits the front page, sections, stock pages and new articles on every run. This adds what
it misses: hub pages edited in content/hubs/ (law changes are the most valuable updates on the site), the index
and by-state tables built from them, edited articles, and the pages a new or edited story feeds (its tag hubs and
topic pages, its day/month/year archive pages).

Usage:
  python3 newsroom/indexnow_changed.py --before <sha> --after <sha> [--dry-run] [--max 200] [--docs docs]
    --dry-run  print the URLs, send nothing
    --docs     drop URLs with no built page in that directory (local check; the deploy job has no docs/)
Never fails the workflow: every error is printed and the script exits 0.
"""
import argparse
import json
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(__file__).resolve().parent.parent
MAX_URLS = 200


def changed_files(before, after):
    if not before or set(before) == {"0"}:
        print("indexnow_changed: no previous head (first push or manual run); nothing to diff")
        return []
    try:
        subprocess.run(["git", "cat-file", "-e", before], cwd=ROOT, check=True, capture_output=True)
    except Exception:  # noqa: BLE001
        print(f"indexnow_changed: previous head {before[:10]} not in this clone; nothing to diff")
        return []
    out = subprocess.run(["git", "diff", "--name-only", "--diff-filter=AM", before, after or "HEAD", "--", "content/hubs", "content/articles"],
                         cwd=ROOT, check=True, capture_output=True, text=True).stdout
    return [line.strip() for line in out.splitlines() if line.strip().endswith(".json")]


def urls_for(files):
    import build
    import hubs
    import templates as T
    hubs.load()
    try:
        import bystate
        by_state = [f"/legal/us/{t['slug']}/" for t in bystate.TOPICS] + [bystate.INDEX_URL]
        sales_by_state, tourists = bystate.SALES_URL, "/legal/us/where-tourists-can-buy-cannabis/"
    except Exception:  # noqa: BLE001
        by_state, sales_by_state, tourists = [], None, None
    index_for = {"us_state": ["/legal/us/", "/legal/"] + by_state + ([tourists] if tourists else []),
                 "country": ["/legal/world/", "/legal/"] + ([tourists] if tourists else []),
                 "explainer": ["/explainers/"], "glossary": ["/glossary/"], "company": ["/company/"],
                 "sales": ["/data/"] + ([sales_by_state] if sales_by_state else [])}
    dir_kind = {d: k for k, d in hubs.KIND_DIR.items()}
    urls = []
    arts = None
    for f in files:
        p = Path(f)
        try:
            if p.parts[:2] == ("content", "hubs") and len(p.parts) == 4:
                kind = dir_kind.get(p.parts[2])
                h = next((x for x in hubs.HUBS if x["_slug"] == p.stem and x["type"] == kind), None)
                if h and hubs.complete(h):
                    urls.append(h["_url"])
                    urls += index_for.get(kind, [])
                    if kind == "sales":  # the state page shows the sales figure
                        st = next((x for x in hubs.HUBS if x["type"] == "us_state" and x["_slug"] == p.stem), None)
                        if st and hubs.complete(st):
                            urls.append(st["_url"])
            elif p.parts[:2] == ("content", "articles"):
                if arts is None:
                    arts = build.load_articles()
                    topics = {}
                    for x in arts:
                        for t in x.get("tags", []):
                            topics[t] = topics.get(t, 0) + 1
                a = json.loads((ROOT / f).read_text(encoding="utf-8"))
                if a.get("draft"):
                    continue
                dt = datetime.fromisoformat(a["published"])
                urls.append(f"/{dt:%Y/%m/%d}/{a['id']}/")
                urls += [f"/{dt:%Y/%m/%d}/", f"/{dt:%Y/%m}/", f"/{dt:%Y}/", f"/archive/{dt:%Y/%m}/"]
                aliases = {k.lower(): v for k, v in T.TAG_ALIASES.items()}
                for t in a.get("tags") or []:
                    t = aliases.get(t.lower(), t)
                    h = hubs.hub_for_tag(t)
                    if h and hubs.complete(h):
                        urls.append(h["_url"])
                    elif topics.get(t, 0) >= T.HUB_MIN:
                        urls.append(f"/topic/{T.slug(t)}/")
        except Exception as e:  # noqa: BLE001
            print("indexnow_changed: skip", f, e)
    return list(dict.fromkeys(urls))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default="")
    ap.add_argument("--after", default="HEAD")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max", type=int, default=MAX_URLS)
    ap.add_argument("--docs", default="")
    args = ap.parse_args()
    files = changed_files(args.before, args.after)
    if not files:
        print("indexnow_changed: no hub or article JSON changed")
        return
    paths = urls_for(files)
    if args.docs:
        d = Path(args.docs)
        missing = [u for u in paths if not (d / u.strip("/") / "index.html").exists()]
        for u in missing:
            print("indexnow_changed: no built page, dropped", u)
        paths = [u for u in paths if u not in missing]
    from build import INDEXNOW_KEY, SITE
    urls = [SITE + u for u in paths][:args.max]
    print(f"indexnow_changed: {len(files)} changed files -> {len(paths)} URLs" + (f" (capped at {args.max})" if len(paths) > args.max else ""))
    if args.dry_run or not urls:
        for u in urls:
            print("  ", u)
        return
    body = json.dumps({"host": SITE.split("//")[1], "key": INDEXNOW_KEY, "keyLocation": f"{SITE}/{INDEXNOW_KEY}.txt",
                       "urlList": urls}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=20) as r:
        print("IndexNow (changed pages)", r.status, len(urls), "URLs")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print("indexnow_changed failed (ignored):", e)
    sys.exit(0)
