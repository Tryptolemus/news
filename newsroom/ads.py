"""Ad selection and rendering for MetaFlora News.

Inventory lives in content/ads.json. Slots:
  article  ad breaks between sections of an article (wide or feature creatives)
  end      after the sources at the end of an article (card creatives)
  front    bands on the front page
  list     section, topic and stock-index pages
  stock    individual stock pages
Selection is deterministic per page and slot (no flicker between builds), weighted, filtered by
shape, section and start/end dates. Paid ads (any advertiser other than MetaFlora) win first.
"""
import hashlib
import json
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INVENTORY = ROOT / "content" / "ads.json"
HOUSE = ("MetaFlora", "MetaFlora News")
# which slots each creative shape fits
SHAPE_SLOTS = {"wide": {"article", "front", "list"},
               "feature": {"article", "front", "list"},
               "card": {"end", "stock"}}


def load():
    if not INVENTORY.exists():
        return {"ads": []}
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def fits(ad, placement):
    if not placement:
        return True
    if ad.get("placements") and placement not in ad["placements"]:
        return False
    return placement in SHAPE_SLOTS.get(ad.get("shape", "wide"), SHAPE_SLOTS["wide"])


def active(inv, cat=None, today=None, placement=None):
    today = today or date.today().isoformat()
    out = []
    for ad in inv.get("ads", []):
        if ad.get("start") and today < ad["start"]:
            continue
        if ad.get("end") and today > ad["end"]:
            continue
        if cat and ad.get("categories") and cat not in ad["categories"]:
            continue
        if not fits(ad, placement):
            continue
        out.append(ad)
    return out


def pick(inv, key, slot, cat=None, exclude=(), placement=None):
    pool = ([a for a in active(inv, cat, placement=placement) if a["id"] not in exclude]
            or [a for a in active(inv, placement=placement) if a["id"] not in exclude]
            or active(inv, cat, placement=placement))
    if not pool:
        return None
    paid = [a for a in pool if a.get("advertiser") not in HOUSE]
    pool = paid or pool
    total = sum(max(1, int(a.get("weight", 1))) for a in pool)
    h = int(hashlib.sha1(f"{key}:{slot}".encode()).hexdigest(), 16) % total
    for a in pool:
        h -= max(1, int(a.get("weight", 1)))
        if h < 0:
            return a
    return pool[-1]


def _rel(ad):
    if not ad["url"].startswith("http"):
        return ""
    house = ad.get("advertiser") in HOUSE
    return ' target="_blank" rel="noopener' + ("" if house else " sponsored") + '"'


def render(ad, placement="article"):
    """Flat, clearly labelled ad unit: hairline rules, ADVERTISEMENT label, one creative block."""
    if not ad:
        return ""
    house = ad.get("advertiser") in HOUSE
    who = "MetaFlora" if house else escape(ad["advertiser"])
    shape = ad.get("shape", "wide")
    head = (f'<aside class="ad ad-{placement} ad-{shape}" aria-label="Advertisement" data-ad="{escape(ad["id"])}">'
            f'<div class="ad-label">Advertisement · {who}</div>')
    if ad.get("format") == "creative":
        size = f' width="{int(ad["width"])}" height="{int(ad["height"])}"' if ad.get("width") and ad.get("height") else ""
        return (f'{head}<a class="ad-creative" href="{escape(ad["url"])}"{_rel(ad)} data-ad-click="{escape(ad["id"])}">'
                f'<img src="/assets/{escape(ad["image"])}" alt="{escape(ad.get("alt", ""))}"{size} loading="lazy" decoding="async"></a></aside>')
    img = f'<img src="/assets/{escape(ad["image"])}" alt="" loading="lazy">' if ad.get("image") else ""
    return f"""{head}
  <a class="ad-unit" href="{escape(ad['url'])}"{_rel(ad)} data-ad-click="{escape(ad['id'])}">
    <span class="ad-copy"><span class="ad-title">{escape(ad['title'])}</span><span class="ad-text">{escape(ad['body'])}</span><span class="ad-cta">{escape(ad['cta'])}</span></span>
    <span class="ad-art">{img}</span>
  </a>
</aside>"""


def slot(key, n, placement, cat=None, exclude=()):
    """Pick and render in one go (for list, front, end and stock slots)."""
    inv = load()
    return render(pick(inv, key, n, cat, exclude=exclude, placement=placement), placement)
