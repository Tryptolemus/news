"""Push notification rules for MetaFlora News: topics, audience matching, payloads.

Pure Python (no Firebase imports) so it is unit-tested in tests/test_notify.py and shared by the
site build (bell panel), the dispatcher (newsroom/push.py) and the admin page.

Topics map onto the site's existing sections; nothing here invents a second taxonomy.
"""
from datetime import datetime, timedelta, timezone

SITE = "https://news.metaflora.xyz"

# id, label shown in the bell panel, site sections (article "cat") that belong to it
TOPICS = [
    ("breaking", "Breaking news", []),
    ("policy", "US cannabis policy", ["Policy", "Federal", "States"]),
    ("hemp", "Federal hemp legislation", ["Hemp"]),
    ("markets", "Cannabis business, markets and stocks", ["Markets"]),
    ("science", "Science and medical research", ["Science"]),
    ("tech", "Technology and innovation", ["Tech"]),
    ("international", "International cannabis news", ["Europe"]),
]
TOPIC_IDS = [t[0] for t in TOPICS]
FREQUENCIES = [
    ("breaking", "Breaking news only"),
    ("all", "Every new story in my topics"),
    ("digest", "One daily digest"),
]
FREQ_IDS = [f[0] for f in FREQUENCIES]
DEFAULT_TOPICS = ["breaking", "policy", "hemp", "markets"]
DEFAULT_FREQ = "all"
CAT_TO_TOPIC = {cat: tid for tid, _, cats in TOPICS for cat in cats}
BATCH = 500  # FCM multicast limit


def topic_for(article):
    return CAT_TO_TOPIC.get(article.get("cat"))


def send_key(article):
    """One key per article for de-duplication: the content file stem (date + id), stable across edits."""
    return f'{article["published"][:10]}-{article["id"]}'


def article_url(article):
    d = datetime.fromisoformat(article["published"])
    return f"{SITE}/{d:%Y/%m/%d}/{article['id']}/"


def eligible(article, now=None):
    """(ok, reason). Never notify for drafts, future-dated (scheduled) stories or opted-out stories."""
    now = now or datetime.now(timezone.utc)
    if article.get("draft"):
        return False, "draft"
    if article.get("push") is False:
        return False, "push disabled on this article"
    pub = datetime.fromisoformat(article["published"])
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    # stories go live on commit; "published" is the nominal edition time, which can be a little ahead
    if pub > now + timedelta(hours=2):
        return False, "scheduled for later"
    if pub < now - timedelta(days=2):
        return False, "older than 48 hours"
    return True, ""


def wants(device, article):
    """Does this device get a push for this article?"""
    if not device.get("enabled") or not device.get("token"):
        return False
    topics = set(device.get("topics") or [])
    if article.get("breaking") and "breaking" in topics:
        return True
    t = topic_for(article)
    return device.get("freq") == "all" and t is not None and t in topics


def audience(devices, article):
    """Matching devices, one per push token (a token can't appear twice in one send)."""
    seen, out = set(), []
    for d in devices:
        if wants(d, article) and d["token"] not in seen:
            seen.add(d["token"])
            out.append(d)
    return out


def clip(text, n):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


def payload(article, key=None, test=False):
    """Title, body, link and tag for one article. Uses the real headline and dek; nothing generated."""
    key = key or send_key(article)
    title = ("Breaking: " if article.get("breaking") else "") + article["headline"]
    if test:
        title = "[TEST] " + title
    return {
        "title": clip(title, 110),
        "body": clip(article["dek"], 160),
        "image": f"{SITE}/og/{article['id']}.jpg",
        "link": f"{article_url(article)}?utm_source=push&utm_medium=web-push&utm_campaign={key}",
        "tag": key,  # same tag = the browser replaces rather than stacks a repeat
        "key": key,
    }


def digest_articles(articles, now=None, hours=24):
    now = now or datetime.now(timezone.utc)
    out = []
    for a in articles:
        pub = datetime.fromisoformat(a["published"])
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        if now - timedelta(hours=hours) <= pub <= now and not a.get("draft"):
            out.append(a)
    return sorted(out, key=lambda a: (a.get("breaking") is not True, a.get("rank", 99)))


def digest_for(device, articles, day):
    """The digest a device should get, or None. Only stories in its topics (breaking counts if chosen)."""
    if not device.get("enabled") or device.get("freq") != "digest" or not device.get("token"):
        return None
    topics = set(device.get("topics") or [])
    mine = [a for a in articles if topic_for(a) in topics or (a.get("breaking") and "breaking" in topics)]
    if not mine:
        return None
    heads = "; ".join(clip(a["headline"], 70) for a in mine[:2])
    more = f" and {len(mine) - 2} more" if len(mine) > 2 else ""
    key = f"digest-{day}"
    return {"title": f"Today in cannabis news: {len(mine)} {'story' if len(mine) == 1 else 'stories'}",
            "body": clip(heads + more, 160),
            "image": f"{SITE}/og/{mine[0]['id']}.jpg",
            "link": f"{SITE}/?utm_source=push&utm_medium=web-push&utm_campaign={key}",
            "tag": key, "key": key}


def chunks(items, n=BATCH):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def is_dead_token(error_name):
    """Only errors that definitively mean "this subscription is gone" remove a device. A generic
    invalid-argument error can be a bad message, and must never wipe valid subscribers."""
    return error_name in ("UnregisteredError", "SenderIdMismatchError")


def plan_edition(devices, articles):
    """[(device, [matching articles])] for one edition's ordinary (non-breaking) stories."""
    seen, out = set(), []
    for d in devices:
        if not d.get("token") or d["token"] in seen:
            continue
        items = [a for a in articles if not a.get("breaking") and wants(d, a)]
        if items:
            seen.add(d["token"])
            out.append((d, items))
    return out


def edition_payloads(items, max_single=2):
    """What one device receives for an edition: up to 2 individual alerts, or one bundle for 3+."""
    if not items:
        return []
    if len(items) <= max_single:
        return [payload(a) | {"keys": [send_key(a)]} for a in items]
    first = items[0]
    key = f"bundle-{first.get('edition') or send_key(first)}"
    heads = "; ".join(clip(a["headline"], 70) for a in items[:2])
    return [{"title": f"{len(items)} new stories in your topics",
             "body": clip(f"{heads} and {len(items) - 2} more", 160),
             "image": f"{SITE}/og/{first['id']}.jpg",
             "link": f"{SITE}/?utm_source=push&utm_medium=web-push&utm_campaign={key}",
             "tag": key, "key": key, "keys": [send_key(a) for a in items]}]
