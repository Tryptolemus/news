"""Ad selection and rendering for MetaFlora News.

Inventory lives in content/ads.json. Each article gets ad breaks between its sections; the
front page gets one band. Selection is deterministic per page and slot (no flicker between
builds), weighted, filtered by section and by start/end dates. Paid ads go in the same file.
"""
import hashlib
import json
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INVENTORY = ROOT / "content" / "ads.json"


def load():
    if not INVENTORY.exists():
        return {"ads": []}
    return json.loads(INVENTORY.read_text())


def active(inv, cat=None, today=None):
    today = today or date.today().isoformat()
    out = []
    for ad in inv.get("ads", []):
        if ad.get("start") and today < ad["start"]:
            continue
        if ad.get("end") and today > ad["end"]:
            continue
        if cat and ad.get("categories") and cat not in ad["categories"]:
            continue
        out.append(ad)
    return out


def pick(inv, key, slot, cat=None, exclude=()):
    pool = [a for a in active(inv, cat) if a["id"] not in exclude] or active(inv, cat) or active(inv)
    if not pool:
        return None
    # paid (non-MetaFlora) ads win their slots before house ads
    paid = [a for a in pool if a.get("advertiser") not in ("MetaFlora", "MetaFlora News")]
    pool = paid or pool
    total = sum(max(1, int(a.get("weight", 1))) for a in pool)
    h = int(hashlib.sha1(f"{key}:{slot}".encode()).hexdigest(), 16) % total
    for a in pool:
        h -= max(1, int(a.get("weight", 1)))
        if h < 0:
            return a
    return pool[-1]


def render(ad, placement="article"):
    if not ad:
        return ""
    house = ad.get("advertiser") in ("MetaFlora", "MetaFlora News")
    label = "From MetaFlora" if house else f"Advertisement · {escape(ad['advertiser'])}"
    ext = ad["url"].startswith("http")
    rel = ' target="_blank" rel="noopener sponsored"' if ext and not house else (' target="_blank" rel="noopener"' if ext else "")
    img = f'<img src="/assets/{escape(ad["image"])}" alt="" loading="lazy">' if ad.get("image") else ""
    return f"""<aside class="ad ad-{placement} ad-{escape(ad.get('theme', 'purple'))}" aria-label="Advertisement" data-ad="{escape(ad['id'])}">
  <span class="ad-label">{label}</span>
  <div class="ad-body">
    <div class="ad-copy">
      <h3>{escape(ad['title'])}</h3>
      <p>{escape(ad['body'])}</p>
      <a class="btn" href="{escape(ad['url'])}"{rel}>{escape(ad['cta'])}</a>
    </div>
    <div class="ad-art">{img}</div>
  </div>
</aside>"""
