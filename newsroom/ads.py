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


def creative(ad, placement):
    """The clickable creative alone (no label/wrapper), so one slot can hold several."""
    if ad.get("format") == "native":
        card = placement in CARD_SLOTS
        body = ad.get("card_body") if card and ad.get("card_body") else ad["body"]
        copy = (f'<span class="nad-copy">{CUBE}<span class="nad-h">{escape(ad["headline"])}</span>'
                f'<span class="nad-b">{escape(body)}</span><span class="nad-cta">{escape(ad["cta"])}</span></span>')
        art = f'<span class="nad-art" aria-hidden="true">{native_art(ad, card)}</span>'
        return (f'<a class="nad {"nad-card" if card else "nad-wide"}" href="{escape(ad["url"])}"{_rel(ad)} '
                f'data-mfp-id="{escape(ad["id"])}">{copy}{art}</a>')
    if ad.get("format") == "creative":
        size = f' width="{int(ad["width"])}" height="{int(ad["height"])}"' if ad.get("width") and ad.get("height") else ""
        return (f'<a class="mfp-creative" href="{escape(ad["url"])}"{_rel(ad)} data-mfp-id="{escape(ad["id"])}">'
                f'<img src="/assets/{escape(ad["image"])}" alt="{escape(ad.get("alt", ""))}"{size} loading="lazy" decoding="async"></a>')
    img = f'<img src="/assets/{escape(ad["image"])}" alt="" width="440" height="340" loading="lazy">' if ad.get("image") else ""
    return (f'<a class="mfp-unit" href="{escape(ad["url"])}"{_rel(ad)} data-mfp-id="{escape(ad["id"])}">'
            f'<span class="mfp-copy"><span class="mfp-title">{escape(ad["title"])}</span><span class="mfp-text">{escape(ad["body"])}</span>'
            f'<span class="mfp-cta">{escape(ad["cta"])}</span></span><span class="mfp-art">{img}</span></a>')


def _who(ads):
    paid = [a for a in ads if a.get("advertiser") not in HOUSE]
    return escape(paid[0]["advertiser"]) if len(paid) == 1 and len(ads) == 1 else "MetaFlora"


def render(ad, placement="article"):
    """Flat, clearly labelled ad unit: hairline rules, ADVERTISEMENT label, one creative block."""
    if not ad:
        return ""
    shape = ad.get("shape", "wide")
    return (f'<aside class="mfp mfp-{placement} mfp-{shape}" aria-label="MetaFlora promotion" data-mfp="{escape(ad["id"])}">'
            f'<div class="mfp-label">Advertisement · {_who([ad])}</div>{creative(ad, placement)}</aside>')


def rotate(key, n, placement, cat=None, exclude=()):
    """One slot that rotates through every ad that fits it. The build's pick goes first (so pages
    without JavaScript still show a sensible ad); the browser starts on a random one and crossfades
    every few seconds (static/assets/app.js). Paid ads, when present, take the slot on their own."""
    inv = load()
    first = pick(inv, key, n, cat, exclude=exclude, placement=placement)
    if not first:
        return ""
    pool = [a for a in active(inv, cat, placement=placement) if a["id"] not in exclude] or [first]
    paid = [a for a in pool if a.get("advertiser") not in HOUSE]
    if paid:
        return render(first, placement)
    ads = [first] + [a for a in pool if a["id"] != first["id"]]
    if len(ads) == 1:
        return render(first, placement)
    slides = "".join(f'<div class="mfp-slide{" is-on" if i == 0 else ""}"{"" if i == 0 else " aria-hidden=\"true\""}>{creative(a, placement)}</div>'
                     for i, a in enumerate(ads))
    dots = "".join(f'<button type="button" class="mfp-dot" aria-label="Show ad {i + 1} of {len(ads)}"{" aria-current=\"true\"" if i == 0 else ""}></button>'
                   for i in range(len(ads)))
    shape = first.get("shape", "wide")
    return (f'<aside class="mfp mfp-{placement} mfp-{shape} mfp-rot" aria-label="MetaFlora promotion" data-rotate>'
            f'<div class="mfp-label">Advertisement · MetaFlora</div><div class="mfp-slides">{slides}</div>'
            f'<div class="mfp-dots">{dots}</div></aside>')


def slot(key, n, placement, cat=None, exclude=()):
    """Rotating slot (list, front, end, stock and article placements)."""
    return rotate(key, n, placement, cat, exclude)
