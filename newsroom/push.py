"""MetaFlora News push dispatcher (runs in GitHub Actions; never in the browser).

  python3 newsroom/push.py articles content/articles/<new>.json ...   automatic, after each deploy
  python3 newsroom/push.py preview <key>                              payload + audience size, nothing sent
  python3 newsroom/push.py test <key|latest>                          send only to admin devices, marked [TEST]
  python3 newsroom/push.py send <key> --confirm <key>                 manual send (still once per article)
  python3 newsroom/push.py status [<key>]                             delivery log
  python3 newsroom/push.py digest                                     daily digest for digest subscribers

<key> is the article file stem, e.g. 2026-11-06-aurora-deal.

Safety:
  * Credentials come from the FIREBASE_SERVICE_ACCOUNT secret only.
  * Nothing reaches readers unless PUSH_LIVE=1 (a repo variable). Otherwise every send is an FCM
    dry run: validated end to end, delivered to no one.
  * Each article (and each day's digest) is sent at most once: sends/<key> is created atomically first.
  * `test` only ever targets devices owned by admins.
  * Any failure is logged and the script exits 0, so it can never block publishing.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import notify_logic as L  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
ICON = f"{L.SITE}/assets/icons/icon-192.png"
BADGE = f"{L.SITE}/assets/icons/badge-96.png"
LIVE = os.environ.get("PUSH_LIVE") == "1"


def log(*a):
    print("[push]", *a, flush=True)


def load_article(key_or_path):
    p = Path(key_or_path)
    if not p.suffix:
        p = ARTICLES / f"{key_or_path}.json"
    a = json.loads(p.read_text(encoding="utf-8"))
    a["_key"] = p.stem
    return a


def latest_article():
    return load_article(sorted(ARTICLES.glob("*.json"))[-1])


def connect():
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if not raw:
        log("FIREBASE_SERVICE_ACCOUNT is not set: push alerts are not configured. Skipping.")
        return None
    import firebase_admin
    from firebase_admin import credentials, firestore, messaging
    from google.api_core.exceptions import AlreadyExists
    app = firebase_admin.initialize_app(credentials.Certificate(json.loads(raw)))
    return {"db": firestore.client(app), "fs": firestore, "msg": messaging, "app": app, "AlreadyExists": AlreadyExists}


def devices(fb, admin_only=False):
    db = fb["db"]
    if admin_only:  # test devices registered by admins from the dashboard
        ids = {i for a in db.collection("admins").stream() for i in (a.to_dict().get("devices") or [])}
        docs = [db.collection("devices").document(i).get() for i in sorted(ids)]
        return [d.to_dict() | {"_id": d.id} for d in docs if d.exists]
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        q = db.collection("devices").where(filter=FieldFilter("enabled", "==", True))
    except ImportError:  # tests use an in-memory fake
        q = db.collection("devices").where("enabled", "==", True)
    return [d.to_dict() | {"_id": d.id} for d in q.stream()]


def wait_live(url, timeout=600):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=15) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(20)
    return False


def deliver(fb, targets, p, dry):
    """Send one notification to many devices in batches of 500. Removes dead subscriptions."""
    m, db = fb["msg"], fb["db"]
    sent = failed = removed = 0
    errors = {}
    for batch in L.chunks(targets):
        msg = m.MulticastMessage(
            tokens=[d["token"] for d in batch],
            data={"key": p["key"], "link": p["link"]},
            webpush=m.WebpushConfig(
                headers={"Urgency": "high", "TTL": "86400"},
                notification=m.WebpushNotification(
                    title=p["title"], body=p["body"], icon=ICON, badge=BADGE, image=p.get("image"),
                    tag=p["tag"], renotify=False,
                    actions=[m.WebpushNotificationAction("read", "Read story"),
                             m.WebpushNotificationAction("settings", "Alert settings")]),
                fcm_options=m.WebpushFCMOptions(link=p["link"])))
        res = m.send_each_for_multicast(msg, dry_run=dry)
        for d, r in zip(batch, res.responses):
            if r.success:
                sent += 1
                continue
            failed += 1
            name = type(r.exception).__name__
            errors[name] = errors.get(name, 0) + 1
            if L.is_dead_token(name) and not dry:
                db.collection("devices").document(d["_id"]).delete()
                removed += 1
    return {"sent": sent, "failed": failed, "removed": removed, "errors": errors}


def claim(fb, key, meta):
    """Atomically reserve sends/<key>. False if this article was already sent (or is being sent)."""
    try:
        fb["db"].collection("sends").document(key).create(meta | {"status": "sending", "created": fb["fs"].SERVER_TIMESTAMP})
        return True
    except fb["AlreadyExists"]:
        return False


def send_article(fb, a, manual=False):
    """Manual send of one article to everyone whose preferences match it (still once per article)."""
    key = L.send_key(a)
    if a.get("draft"):
        log(f"{key}: draft, never sent")
        return
    ok, why = L.eligible(a)
    if not ok and not manual:
        log(f"{key}: not sent ({why})")
        return
    send_one(fb, a, L.audience(devices(fb), a), not LIVE, manual=manual)


def cmd_articles(fb, files):
    """Automatic alerts after a publish. Breaking stories go out one by one to everyone they match.
    Ordinary stories: up to 2 matches arrive as separate alerts; 3+ become one bundled alert per device."""
    arts = []
    for f in files:
        try:
            a = load_article(f)
        except Exception as e:  # noqa: BLE001
            log("skip", f, e)
            continue
        ok, why = L.eligible(a)
        if ok:
            arts.append(a)
        else:
            log(f"{L.send_key(a)}: not sent ({why})")
    devs = devices(fb)
    dry = not LIVE
    for a in sorted([a for a in arts if a.get("breaking")], key=lambda a: a.get("rank", 99)):
        send_one(fb, a, L.audience(devs, a), dry)
    normal = sorted([a for a in arts if not a.get("breaking")], key=lambda a: a.get("rank", 99))
    plan = L.plan_edition(devs, normal)
    if not plan:
        for a in normal:
            log(f"{L.send_key(a)}: no matching subscribers")
        return
    claimed = {}
    for a in normal:
        k = L.send_key(a)
        n = sum(1 for _, items in plan if any(x is a for x in items))
        if n:
            claimed[k] = claim(fb, k, {"kind": "article", "title": a["headline"], "link": L.article_url(a), "audience": n, "live": not dry, "manual": False})
            if not claimed[k]:
                log(f"{k}: already sent, skipping (no duplicates)")
    if not any(claimed.values()):
        return
    if not wait_live(L.article_url(normal[0])):
        for k, ok in claimed.items():
            if ok:
                fb["db"].collection("sends").document(k).update({"status": "page-not-live"})
        log("edition pages not live; ordinary alerts not sent")
        return
    groups = {}
    for d, items in plan:
        items = [x for x in items if claimed.get(L.send_key(x))]
        for p in L.edition_payloads(items):
            groups.setdefault((p["key"], p["title"], p["body"]), (p, []))[1].append(d)
    totals = {k: {"sent": 0, "failed": 0, "removed": 0} for k, ok in claimed.items() if ok}
    for p, targets in groups.values():
        out = deliver(fb, targets, p, dry)
        for k in p["keys"]:
            for f in totals[k]:
                totals[k][f] += out[f]
        log(f"{p['key']}: {'DRY RUN, ' if dry else ''}{len(targets)} devices: {out}")
    for k, t in totals.items():
        fb["db"].collection("sends").document(k).update(t | {"status": "dry-run" if dry else "sent", "finished": fb["fs"].SERVER_TIMESTAMP})


def send_one(fb, a, targets, dry, manual=False):
    key = L.send_key(a)
    p = L.payload(a, key)
    if not claim(fb, key, {"kind": "breaking" if a.get("breaking") else "article", "title": p["title"], "link": p["link"],
                           "audience": len(targets), "live": not dry, "manual": manual}):
        log(f"{key}: already sent, skipping (no duplicates)")
        return False
    if not wait_live(L.article_url(a)):
        fb["db"].collection("sends").document(key).update({"status": "page-not-live"})
        log(f"{key}: article page not live, nothing sent")
        return False
    out = deliver(fb, targets, p, dry) if targets else {"sent": 0, "failed": 0, "removed": 0, "errors": {}}
    fb["db"].collection("sends").document(key).update(out | {"status": "dry-run" if dry else "sent", "finished": fb["fs"].SERVER_TIMESTAMP})
    log(f"{key}: {'DRY RUN, ' if dry else ''}audience {len(targets)}, sent {out['sent']}, failed {out['failed']}, removed {out['removed']}")
    return True


def cmd_preview(fb, key):
    a = load_article(key)
    p = L.payload(a)
    ok, why = L.eligible(a)
    log("eligible:", ok, why)
    log("payload:", json.dumps(p, indent=1))
    if fb:
        t = L.audience(devices(fb), a)
        log("audience now:", len(t))
        if t:
            out = deliver(fb, t[:500], p, dry=True)
            log("FCM dry run on first", min(500, len(t)), "devices:", out)


def cmd_test(fb, key):
    a = latest_article() if key in (None, "", "latest") else load_article(key)
    p = L.payload(a, test=True)
    p["tag"] = p["key"] = f"test-{int(time.time())}"
    targets = [d for d in devices(fb, admin_only=True) if d.get("token")]
    if not targets:
        log("No admin devices. Turn alerts on in your own browser, then add your device ID to Firestore admins/ (see NOTIFICATIONS.md).")
        return
    out = deliver(fb, targets, p, dry=False)  # tests are real, but only to admin devices
    fb["db"].collection("tests").add(out | {"article": L.send_key(a), "at": fb["fs"].SERVER_TIMESTAMP, "devices": len(targets)})
    log(f"test sent to {len(targets)} admin device(s):", out)


def cmd_send(fb, key, confirm):
    if confirm != key:
        log("Refused: to send manually, set confirm to exactly the article key:", key)
        return
    send_article(fb, load_article(key), manual=True)


def cmd_status(fb, key):
    col = fb["db"].collection("sends")
    docs = [col.document(key).get()] if key else list(col.order_by("created", direction="DESCENDING").limit(20).stream())
    for d in docs:
        if d.exists:
            v = d.to_dict()
            log(d.id, {k: v.get(k) for k in ("status", "kind", "audience", "sent", "failed", "removed", "live", "manual", "errors")})


def cmd_digest(fb):
    now = datetime.now(timezone.utc)
    day = now.date().isoformat()
    arts = [load_article(p) for p in sorted(ARTICLES.glob("*.json"))[-60:]]
    todays = L.digest_articles(arts, now)
    devs = devices(fb)
    by_payload = {}
    for d in devs:
        p = L.digest_for(d, todays, day)
        if p:
            by_payload.setdefault((p["title"], p["body"]), (p, []))[1].append(d)
    total = sum(len(v[1]) for v in by_payload.values())
    key = f"digest-{day}"
    dry = not LIVE
    if not claim(fb, key, {"kind": "digest", "title": f"Daily digest {day}", "audience": total, "live": not dry, "manual": False}):
        log(f"{key}: already sent")
        return
    agg = {"sent": 0, "failed": 0, "removed": 0, "errors": {}}
    for p, targets in by_payload.values():
        out = deliver(fb, targets, p, dry)
        for k in ("sent", "failed", "removed"):
            agg[k] += out[k]
    fb["db"].collection("sends").document(key).update(agg | {"status": "dry-run" if dry else "sent", "finished": fb["fs"].SERVER_TIMESTAMP})
    log(f"{key}: {'DRY RUN, ' if dry else ''}{len(todays)} stories, {total} devices:", agg)


def main(argv):
    if not argv:
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    log("mode:", cmd, "| LIVE" if LIVE else "| dry run (set PUSH_LIVE=1 to reach readers)")
    try:
        fb = connect()
        if cmd == "preview":
            cmd_preview(fb, rest[0])
            return
        if not fb:
            return
        if cmd == "articles":
            cmd_articles(fb, rest)
        elif cmd == "test":
            cmd_test(fb, rest[0] if rest else "latest")
        elif cmd == "send":
            cmd_send(fb, rest[0], rest[2] if len(rest) > 2 and rest[1] == "--confirm" else "")
        elif cmd == "status":
            cmd_status(fb, rest[0] if rest else None)
        elif cmd == "digest":
            cmd_digest(fb)
        else:
            log("unknown command", cmd)
    except Exception as e:  # noqa: BLE001  never block publishing
        log("ERROR (ignored, publishing is unaffected):", type(e).__name__, e)


if __name__ == "__main__":
    main(sys.argv[1:])
