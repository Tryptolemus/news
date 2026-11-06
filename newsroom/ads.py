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
               "card": {"end", "stock"},
               "native": {"article", "front", "list", "end", "stock"}}  # native ads lay out wide or as a card per slot
CARD_SLOTS = {"end", "stock"}
CUBE = '<span class="nad-brand"><img src="/assets/metaflora-cube-mark.png" alt="" width="111" height="120"><span>METAFLORA</span></span>'


def native_art(ad, card):
    """The drawn illustration for each native ad kind (HTML, no raster)."""
    kind = ad.get("kind")
    if kind == "sell":
        return ('<span class="fig2"><span><b>0%</b><span class="nad-k">to list</span></span>'
                f'<span><b>5%</b><span class="nad-k">{"when you sell" if card else "only when you sell"}</span></span></span>')
    if kind == "platform":
        rows = [("Lineage", "Sunset × Girl Scout"), ("Lab report", "Linked"), ("Top terpene", "Limonene")]
        rows = ([rows[1]] if card else rows)
        dl = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in rows) + '<div><dt>Genetics</dt><dd class="ok">Verified</dd></div>'
        return ('<span class="rec"><span class="nad-k">Example strain record</span>'
                f'<span class="rec-name">Lemon Cherry Gelato</span><dl>{dl}</dl></span>')
    if kind == "loyalty":
        return ('<span class="pts"><span class="nad-k">Example rewards card</span><span class="pts-store">Green Leaf Dispensary</span>'
                '<span class="pts-bal"><b>250</b><span class="nad-mono">points</span></span><span class="pts-bar"><i></i></span>'
                + ("" if card else '<span class="nad-mono">50 points to your next reward</span>') + "</span>")
    return ""


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
    if ad.get("format") == "native":
        card = placement in CARD_SLOTS
        body = ad.get("card_body") if card and ad.get("card_body") else ad["body"]
        copy = (f'<span class="nad-copy">{CUBE}<span class="nad-h">{escape(ad["headline"])}</span>'
                f'<span class="nad-b">{escape(body)}</span><span class="nad-cta">{escape(ad["cta"])}</span></span>')
        art = f'<span class="nad-art" aria-hidden="true">{native_art(ad, card)}</span>'
        return (f'{head}<a class="nad {"nad-card" if card else "nad-wide"}" href="{escape(ad["url"])}"{_rel(ad)} '
                f'data-ad-click="{escape(ad["id"])}">{copy}{art}</a></aside>')
    if ad.get("format") == "creative":
        size = f' width="{int(ad["width"])}" height="{int(ad["height"])}"' if ad.get("width") and ad.get("height") else ""
        return (f'{head}<a class="ad-creative" href="{escape(ad["url"])}"{_rel(ad)} data-ad-click="{escape(ad["id"])}">'
                f'<img src="/assets/{escape(ad["image"])}" alt="{escape(ad.get("alt", ""))}"{size} loading="lazy" decoding="async"></a></aside>')
    img = f'<img src="/assets/{escape(ad["image"])}" alt="" width="440" height="340" loading="lazy">' if ad.get("image") else ""
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
