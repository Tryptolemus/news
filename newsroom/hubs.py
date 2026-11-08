"""Evergreen legal hubs: US state law pages, country law pages and federal explainers.

Data lives in content/hubs/{states,countries,explainers}/*.json (every fact carries a source and an
as-of date). The newsroom feeds them automatically: any story tagged with a hub's tag appears in that
hub's "Latest coverage", links to the hub on first mention in its body, and lists it under
"Covered in this story". Pages whose facts aren't complete stay noindex until they are.

URLs
  /legal/                     index: US tracker + world + federal explainers
  /legal/us/                  50-state tracker (tile map, table, CSV, Dataset schema)
  /legal/us/<state>/          "Is weed legal in <state>?" page
  /legal/world/               countries table
  /legal/world/<country>/     country page
  /explainers/                federal explainers index
  /explainers/<slug>/         explainer page
"""
import csv
import io
import json
import re
from datetime import date, datetime
from html import escape
from pathlib import Path

import templates as T

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "content" / "hubs"
SITE = T.SITE

KIND_DIR = {"us_state": "states", "country": "countries", "explainer": "explainers", "glossary": "glossary", "company": "companies", "sales": "sales"}
FACT_LABELS = [
    ("adult_use_since", "Adult-use legal since"), ("retail_sales", "Retail sales"), ("purchase_age", "Minimum age"),
    ("possession_limit", "Possession limit"), ("home_grow", "Home grow"), ("public_use", "Public use"),
    ("medical_since", "Medical program since"), ("medical_program", "Medical program"), ("taxes", "Taxes"),
    ("hemp_thc", "Hemp-derived THC"), ("penalties", "Penalties"), ("tourists", "Tourists"), ("regulator", "Regulator"),
]
ADULT = {"legal": "Legal", "legal_no_sales": "Legal, no stores yet", "illegal": "Illegal"}
MED = {"comprehensive": "Legal", "limited": "Limited", "cbd_only": "CBD / low-THC only", "none": "None"}
DECRIM = {"yes": "Yes", "partial": "Partial", "no": "No"}

# US tile map: (column, row) per state abbreviation
TILES = {
    "AK": (0, 0), "ME": (11, 0), "WI": (6, 1), "VT": (10, 1), "NH": (11, 1),
    "WA": (1, 2), "ID": (2, 2), "MT": (3, 2), "ND": (4, 2), "MN": (5, 2), "IL": (6, 2), "MI": (7, 2), "NY": (9, 2), "MA": (10, 2),
    "OR": (1, 3), "NV": (2, 3), "WY": (3, 3), "SD": (4, 3), "IA": (5, 3), "IN": (6, 3), "OH": (7, 3), "PA": (8, 3), "NJ": (9, 3), "CT": (10, 3), "RI": (11, 3),
    "CA": (1, 4), "UT": (2, 4), "CO": (3, 4), "NE": (4, 4), "MO": (5, 4), "KY": (6, 4), "WV": (7, 4), "VA": (8, 4), "MD": (9, 4), "DE": (10, 4),
    "AZ": (2, 5), "NM": (3, 5), "KS": (4, 5), "AR": (5, 5), "TN": (6, 5), "NC": (7, 5), "SC": (8, 5), "DC": (9, 5),
    "OK": (4, 6), "LA": (5, 6), "MS": (6, 6), "AL": (7, 6), "GA": (8, 6),
    "HI": (0, 7), "TX": (4, 7), "FL": (9, 7),
}

NEIGHBORS = {
    "AL": "FL GA MS TN", "AK": "WA", "AZ": "CA CO NV NM UT", "AR": "LA MS MO OK TN TX", "CA": "AZ NV OR",
    "CO": "AZ KS NE NM OK UT WY", "CT": "MA NY RI", "DE": "MD NJ PA", "DC": "MD VA", "FL": "AL GA",
    "GA": "AL FL NC SC TN", "HI": "CA", "ID": "MT NV OR UT WA WY", "IL": "IN IA KY MO WI MI", "IN": "IL KY MI OH",
    "IA": "IL MN MO NE SD WI", "KS": "CO MO NE OK", "KY": "IL IN MO OH TN VA WV", "LA": "AR MS TX", "ME": "NH",
    "MD": "DE PA VA WV DC", "MA": "CT NH NY RI VT", "MI": "IN OH WI IL", "MN": "IA ND SD WI", "MS": "AL AR LA TN",
    "MO": "AR IL IA KS KY NE OK TN", "MT": "ID ND SD WY", "NE": "CO IA KS MO SD WY", "NV": "AZ CA ID OR UT",
    "NH": "ME MA VT", "NJ": "DE NY PA", "NM": "AZ CO OK TX UT", "NY": "CT MA NJ PA VT", "NC": "GA SC TN VA",
    "ND": "MN MT SD", "OH": "IN KY MI PA WV", "OK": "AR CO KS MO NM TX", "OR": "CA ID NV WA",
    "PA": "DE MD NJ NY OH WV", "RI": "CT MA", "SC": "GA NC", "SD": "IA MN MT NE ND WY", "TN": "AL AR GA KY MS MO NC VA",
    "TX": "AR LA NM OK", "UT": "AZ CO ID NV NM WY", "VT": "MA NH NY", "VA": "KY MD NC TN WV DC",
    "WA": "ID OR", "WV": "KY MD OH PA VA", "WI": "IL IA MI MN", "WY": "CO ID MT NE SD UT",
}
QUICK = [("purchase_age", "Minimum age"), ("possession_limit", "How much can I carry?"), ("public_use", "Where can I use it?"),
         ("dui", "Driving"), ("tourists", "Visitors"), ("home_grow", "Home grow")]
TITLE_YEAR = 2026  # bump with a dated sweep, not per build

HUBS = []          # all hub dicts
BY_TAG = {}        # tag (lower) -> hub


def url_for(h):
    s = h["_slug"]
    return {"us_state": f"/legal/us/{s}/", "country": f"/legal/world/{s}/", "explainer": f"/explainers/{s}/",
            "glossary": f"/glossary/{s}/", "company": f"/company/{s}/", "sales": f"/data/{s}-cannabis-sales/"}[h["type"]]


def complete(h):
    return (h.get("page_status") or (h.get("status") if isinstance(h.get("status"), str) else None)) == "complete"


def load():
    HUBS.clear()
    BY_TAG.clear()
    for kind, d in KIND_DIR.items():
        for f in sorted((DATA / d).glob("*.json")):
            try:
                h = json.loads(f.read_text())
            except Exception as e:  # noqa: BLE001
                print(f"WARNING: skipping hub file {f.name}: invalid JSON ({e})")
                continue
            h.setdefault("type", kind)
            h["_slug"] = f.stem
            h["_url"] = url_for(h)
            HUBS.append(h)
            if kind in ("glossary", "sales"):
                continue  # glossary terms link from hubs and each other, not from story tags
            for t in {h["name"], *h.get("tags", [])}:
                BY_TAG.setdefault(t.lower(), h)
    return HUBS


def hub_for_tag(t):
    return BY_TAG.get(t.lower())


def tag_url(t):
    h = hub_for_tag(t)
    return h["_url"] if h and complete(h) else f"/topic/{T.slug(t)}/"


def status_class(h):
    st = h.get("status") if isinstance(h.get("status"), dict) else h.get("status_detail") or {}
    st = h.get("status_map") or (h["status"] if isinstance(h.get("status"), dict) else {})
    return st


def st(h):
    """The legal-status dict ('legal'; older files used 'status')."""
    s = h.get("legal") or h.get("status")
    return s if isinstance(s, dict) else {}


def tone(h):
    s = st(h)
    if s.get("adult_use") == "legal":
        return "rec"
    if s.get("adult_use") == "legal_no_sales":
        return "rec-ns"
    if s.get("medical") == "comprehensive":
        return "med"
    if s.get("medical") in ("limited", "cbd_only"):
        return "lim"
    return "none"


TONE_LABEL = {"rec": "Adult-use legal", "rec-ns": "Adult-use legal, no stores", "med": "Medical only",
              "lim": "Limited medical / CBD", "none": "No program"}


def verified(h):
    """Honest last-verified date: never 'today' by default, so rebuilds don't fake freshness."""
    if h.get("last_verified"):
        return h["last_verified"]
    dates = [f.get("as_of") for f in (h.get("facts") or {}).values() if isinstance(f, dict) and f.get("as_of")]
    dates += [e.get("date") for e in h.get("timeline") or [] if len(str(e.get("date", ""))) == 10]
    return max(dates) if dates else "2026-11-07"


def clip(text, n=155):
    text = " ".join(str(text).split())
    if len(text) <= n:
        return text
    return text[: n - 1].rsplit(" ", 1)[0].rstrip(",;:.") + "…"


def short_fact(v, n=110):
    """Table-sized version of a fact: first sentence, clipped. The full text lives on the state page."""
    if not v:
        return "–"
    v = " ".join(str(v).split())
    first = re.split(r"(?<=[.;])\s", v, 1)[0].rstrip(".;")
    return clip(first, n)


def has_glossary():
    return any(h["type"] == "glossary" and complete(h) for h in HUBS)


def fmt_date(iso):
    if isinstance(iso, str) and len(iso) == 7 and iso[4] == "-":
        try:
            return f"{datetime.fromisoformat(iso + '-01'):%B %Y}"
        except Exception:  # noqa: BLE001
            return iso
    if isinstance(iso, str) and len(iso) == 4 and iso.isdigit():
        return iso
    try:
        d = datetime.fromisoformat(iso[:10])
        return f"{d.day} {d:%b %Y}"
    except Exception:  # noqa: BLE001
        return iso


def src_link(url, label="Source"):
    return f'<a class="src" href="{escape(url)}" target="_blank" rel="noopener">{label}</a>' if url else ""


# ---------- article integration ----------

def article_hubs(a):
    out, seen = [], set()
    for t in a.get("tags", []):
        h = hub_for_tag(t)
        if h and complete(h) and h["_url"] not in seen:
            seen.add(h["_url"])
            out.append(h)
    return out


def autolink(html_paras, a, limit=8):
    """Link the first in-body mention of each hub the story is tagged with. Works on escaped HTML <p> blocks."""
    hubs = article_hubs(a)
    if not hubs:
        return html_paras
    done, n = set(), 0
    out = []
    for block in html_paras:
        if not block.startswith("<p>") or n >= limit:
            out.append(block)
            continue
        for h in hubs:
            if h["_url"] in done or n >= limit:
                continue
            for name in sorted({h["name"], *h.get("tags", [])}, key=len, reverse=True):
                pat = re.compile(r"(?<![\w>/-])(" + re.escape(escape(name)) + r")(?![\w<-])")
                m = None
                for cand in pat.finditer(block):
                    before, after = block[:cand.start()], block[cand.end():]
                    # skip matches inside proper names ("Texas Hemp Business Council"): a capitalised word right next to it
                    if re.search(r"\b[A-Z][a-z]+ $", before) and not re.search(r"(?:^|[.!?>] ?)[A-Z][a-z]+ $", before[-40:]):
                        continue
                    if re.match(r"^ [A-Z][a-z]", after):
                        continue
                    if "<a " in before[-200:].split("</a>")[-1]:
                        continue
                    m = cand
                    break
                if m:
                    block = block[:m.start()] + f'<a class="hub-link" href="{h["_url"]}">{m.group(1)}</a>' + block[m.end():]
                    done.add(h["_url"])
                    n += 1
                    break
        out.append(block)
    return out


def covered_box(a):
    hubs = article_hubs(a)
    if not hubs:
        return ""
    items = []
    for h in hubs:
        line = h.get("headline_status") or h.get("where_it_stands") or ""
        kind = {"us_state": "State law", "country": "Country law", "explainer": "Explainer", "company": "Company"}[h["type"]]
        items.append(f'<li><a href="{h["_url"]}"><span class="cv-k">{kind}</span><span class="cv-n">{escape(h["name"])}</span>'
                     f'<span class="cv-s">{escape(line)}</span></a></li>')
    return f'<aside class="covered"><h2>Covered in this story</h2><ul>{"".join(items)}</ul></aside>'


# ---------- page pieces ----------

def coverage(h, arts, n=8):
    tags = {t.lower() for t in {h["name"], *h.get("tags", [])}}
    items = [a for a in arts if tags & {t.lower() for t in a.get("tags", [])}]
    items.sort(key=lambda a: a["_dt"], reverse=True)
    return items[:n]


EXTRA_LABELS = {"medical_product_forms": "Medical product forms", "license_caps": "License caps", "ballot_history": "Ballot history",
                "employment": "Employment", "expungement": "Expungement", "unlicensed_shops": "Unlicensed shops", "dui": "Driving",
                "social_use": "Social use", "delivery": "Delivery", "clubs": "Cannabis clubs", "imports": "Imports and travel"}


def facts_table(h):
    rows = []
    facts = h.get("facts") or {}
    known = {k for k, _ in FACT_LABELS}
    order = list(FACT_LABELS) + [(k, EXTRA_LABELS.get(k, k.replace("_", " ").capitalize())) for k in facts if k not in known]
    for k, label in order:
        f = facts.get(k)
        if not isinstance(f, dict):
            continue
        if not f or not f.get("value"):
            continue
        rows.append(f'<tr><th scope="row">{label}</th><td>{escape(str(f["value"]))}'
                    f'<span class="fact-src">{src_link(f.get("source"))}{" · as of " + fmt_date(f["as_of"]) if f.get("as_of") else ""}</span></td></tr>')
    return f'<table class="facts">{"".join(rows)}</table>' if rows else ""


def timeline(h):
    tl = h.get("timeline") or []
    if not tl:
        return ""
    lis = "".join(f'<li><time>{fmt_date(e["date"])}</time><span>{escape(e["event"])} {src_link(e.get("source"))}</span></li>' for e in tl)
    return f'<section class="hub-sec"><h2>Timeline</h2><ol class="timeline">{lis}</ol></section>'


def pending(h):
    p = h.get("pending") or []
    if not p:
        return ""
    lis = "".join(f'<li><b>{escape(x["item"])}</b>{(" " + escape(x["status"])) if x.get("status") else ""} {src_link(x.get("source"))}</li>' for x in p)
    return f'<section class="hub-sec"><h2>Pending and proposed changes</h2><ul class="pending">{lis}</ul></section>'


def faq(h):
    qs = h.get("faq") or []
    if not qs:
        return "", None
    html = "".join(f'<details class="faq"><summary>{escape(q["q"])}</summary><p>{escape(q["a"])}</p></details>' for q in qs)
    ld = {"@context": "https://schema.org", "@type": "FAQPage",
          "mainEntity": [{"@type": "Question", "name": q["q"], "acceptedAnswer": {"@type": "Answer", "text": q["a"]}} for q in qs]}
    return f'<section class="hub-sec"><h2>Questions people ask</h2>{html}</section>', ld


def sources(h):
    s = h.get("sources") or []
    if not s:
        return ""
    lis = "".join(f'<li><a href="{escape(x["url"])}" target="_blank" rel="noopener">{escape(x["name"])}</a></li>' for x in s)
    return f'<section class="sources"><h2>Sources</h2><ol>{lis}</ol></section>'


def coverage_html(h, arts):
    items = coverage(h, arts)
    if not items:
        return ""
    return f'<section class="hub-sec"><h2>Latest MetaFlora coverage</h2><ol class="latest-list">{"".join(T.list_item(a) for a in items)}</ol></section>'


def disclaimer(h):
    return (f'<p class="hub-note">Last verified {fmt_date(verified(h))}. Laws change; check the linked official sources before acting. '
            f'This page is news and reference, not legal advice. Cannabis remains illegal under US federal law except where noted. '
            f'Spotted something out of date? Email <a href="mailto:support@metaflora.xyz">support@metaflora.xyz</a>.</p>')


def crumbs_ld(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": SITE + u} for i, (n, u) in enumerate(items)]}


def crumbs_html(items):
    return '<nav class="crumbs" aria-label="Breadcrumb">' + " › ".join(
        f'<a href="{u}">{escape(n)}</a>' for n, u in items[:-1]) + f' › <span>{escape(items[-1][0])}</span></nav>'


def siblings(h, n=8):
    same = [x for x in HUBS if x is not h and x["type"] == h["type"] and complete(x)]
    if h["type"] in ("us_state", "country"):
        same.sort(key=lambda x: (tone(x) != tone(h), x["name"]))
    return same[:n]


def neighbors(h):
    by_abbr = {x.get("abbr"): x for x in HUBS if x["type"] == "us_state" and complete(x)}
    return [by_abbr[a] for a in NEIGHBORS.get(h.get("abbr"), "").split() if a in by_abbr]


def neighbors_html(h):
    nb = neighbors(h)
    if not nb:
        return ""
    lis = "".join(f'<li><a href="{x["_url"]}">Is weed legal in {escape(x["name"])}?</a><span>{escape(TONE_LABEL[tone(x)])}</span></li>' for x in nb)
    return (f'<section class="hub-sec"><h2>Neighbouring states</h2><ul class="sib">{lis}</ul>'
            f'<p class="hub-note">Taking cannabis across a state line is a federal crime, even between two adult-use states.</p>'
            f'<p class="more-link"><a href="/legal/us/">All 50 states</a></p></section>')


def quick_answers(h):
    facts = h.get("facts") or {}
    cells = []
    for k, label in QUICK:
        v = (facts.get(k) or {}).get("value") if isinstance(facts.get(k), dict) else None
        if v:
            cells.append(f'<div class="qa"><dt>{label}</dt><dd>{escape(clip(v, 140))}</dd></div>')
    return f'<dl class="quick-answers">{"".join(cells)}</dl>' if len(cells) >= 2 else ""


def _year(v):
    m = re.search(r"(19|20)\d{2}", str(v or ""))
    return int(m.group(0)) if m else None


def comparisons(h):
    """Computed, page-unique context: where this state sits among the others."""
    if h["type"] != "us_state":
        return ""
    states = [x for x in HUBS if x["type"] == "us_state"]
    out = []
    if tone(h) in ("rec", "rec-ns"):
        rec = [(x, _year(((x.get("facts") or {}).get("adult_use_since") or {}).get("value"))) for x in states if tone(x) in ("rec", "rec-ns")]
        rec = sorted([r for r in rec if r[1]], key=lambda r: (r[1], r[0]["name"]))
        y = next((yy for x, yy in rec if x is h), None)
        if y:
            rank = 1 + sum(1 for _, yy in rec if yy < y)
            out.append(f"{h['name']} legalized adult use in {y}, making it one of the first {rank} of the {len(rec)} adult-use jurisdictions tracked here"
                       if rank <= 5 else f"{h['name']} legalized adult use in {y}; {rank - 1} of the {len(rec)} adult-use jurisdictions tracked here got there first")
    else:
        n_rec = sum(1 for x in states if tone(x) in ("rec", "rec-ns"))
        out.append(f"{h['name']} is one of {len(states) - n_rec} jurisdictions tracked here where adult use is still illegal")
    nb = neighbors(h)
    if nb:
        legal_nb = [x["name"] for x in nb if tone(x) in ("rec", "rec-ns")]
        if legal_nb:
            out.append(f"{len(legal_nb)} of its {len(nb)} neighbours {'allows' if len(legal_nb) == 1 else 'allow'} adult use ({', '.join(legal_nb)})")
        else:
            out.append(f"none of its {len(nb)} neighbours allow adult use")
    return f'<p class="hub-compare">{escape("; ".join(out))}.</p>' if out else ""


def related_explainers(h):
    text = " ".join([h.get("summary", ""), json.dumps(h.get("facts") or {}), json.dumps(h.get("pending") or [])]).lower()
    keys = {"hemp-thc-ban": ("hemp", "delta-8", "thca"), "schedule-iii-rescheduling": ("schedule iii", "reschedul"),
            "section-280e": ("280e",), "safer-banking": ("banking",), "delta-8-thc": ("delta-8",), "total-thc": ("total thc", "thca"),
            "cannabis-gun-rights": ("firearm", "gun"), "interstate-commerce": ("interstate",)}
    ex = {x["_slug"]: x for x in HUBS if x["type"] == "explainer" and complete(x)}
    picks = [ex[s] for s, words in keys.items() if s in ex and any(w in text for w in words)]
    for s in ("schedule-iii-rescheduling", "hemp-thc-ban"):
        if s in ex and ex[s] not in picks:
            picks.append(ex[s])
    lis = "".join(f'<li><a href="{x["_url"]}">{escape(x["name"])}</a><span>{escape(clip(x.get("where_it_stands", ""), 110))}</span></li>' for x in picks[:4])
    return f'<section class="hub-sec"><h2>Federal and hemp rules that apply here</h2><ul class="sib">{lis}</ul></section>' if lis else ""


def latest_change(h):
    tl = [e for e in h.get("timeline") or [] if e.get("date")]
    if not tl:
        return ""
    e = max(tl, key=lambda e: str(e["date"]))
    return f'<p class="hub-latest"><b>Latest change</b> · <time>{fmt_date(e["date"])}</time> · {escape(clip(e["event"], 140))}</p>'


def sib_html(h):
    if h["type"] == "us_state" and neighbors(h):
        return neighbors_html(h)
    sib = siblings(h)
    if not sib:
        return ""
    label = {"us_state": "Other states", "country": "Other countries", "explainer": "More explainers", "glossary": "More terms"}[h["type"]]
    lis = "".join(f'<li><a href="{x["_url"]}">{escape(x["name"])}</a><span>{escape(TONE_LABEL[tone(x)] if x["type"] != "explainer" else "")}</span></li>' for x in sib)
    up = {"us_state": ("All 50 states", "/legal/us/"), "country": ("All countries", "/legal/world/"), "explainer": ("All explainers", "/explainers/"),
          "glossary": ("Full glossary", "/glossary/")}[h["type"]]
    return f'<section class="hub-sec"><h2>{label}</h2><ul class="sib">{lis}</ul><p class="more-link"><a href="{up[1]}">{up[0]}</a></p></section>'


# ---------- pages ----------

def jurisdiction_page(h, arts):
    s = st(h)
    is_state = h["type"] == "us_state"
    name = h["name"]
    short = h.get("short_name") or ("DC" if name == "District of Columbia" else name)
    if is_state:
        title = f"Is weed legal in {name}? {short} cannabis laws ({TITLE_YEAR})"
        if len(title) > 60:
            title = f"Is weed legal in {short}? {short} cannabis laws ({TITLE_YEAR})"
        crumbs = [("MetaFlora News", "/"), ("Cannabis laws", "/legal/"), ("United States", "/legal/us/"), (name, h["_url"])]
    else:
        title = f"Is cannabis legal in {name}? {short} cannabis laws ({TITLE_YEAR})"
        if len(title) > 60:
            title = f"Is cannabis legal in {short}? Laws ({TITLE_YEAR})"
        crumbs = [("MetaFlora News", "/"), ("Cannabis laws", "/legal/"), ("World", "/legal/world/"), (name, h["_url"])]
    f0 = h.get("facts") or {}
    bits = [h.get("headline_status", "")]
    for k in ("possession_limit", "home_grow", "purchase_age"):
        v = (f0.get(k) or {}).get("value") if isinstance(f0.get(k), dict) else None
        if v:
            bits.append(f"{dict(QUICK + FACT_LABELS).get(k, k)}: {v}")
    desc = clip(" ".join(b.rstrip(".") + "." for b in bits if b), 155)
    chips = (f'<ul class="status-chips"><li class="t-{tone(h)}"><span>Adult use</span><b>{ADULT.get(s.get("adult_use"), "Unknown")}</b></li>'
             f'<li><span>Medical</span><b>{MED.get(s.get("medical"), "Unknown")}</b></li>'
             f'<li><span>Decriminalized</span><b>{DECRIM.get(s.get("decriminalized"), "Unknown")}</b></li></ul>')
    f_html, f_ld = faq(h)
    body = f"""
<article class="story hub">
  <header class="story-head">
    {crumbs_html(crumbs)}
    <h1>{"Is weed legal in" if is_state else "Is cannabis legal in"} {escape(name)}?</h1>
    <p class="dek hub-answer">{escape(h.get("headline_status", ""))}</p>
    {chips}
    {quick_answers(h)}
    {latest_change(h)}
    <p class="hub-by"><span>By <a href="/how-we-report/">MetaFlora News Desk</a></span> · Last verified <time datetime="{verified(h)}">{fmt_date(verified(h))}</time></p>
  </header>
  <div class="story-col">
    <section class="hub-sec"><h2>{escape(name)} cannabis laws today</h2><p class="hub-summary">{escape(h.get("summary", ""))}</p>{comparisons(h)}</section>
    <section class="hub-sec"><h2>Key facts</h2>{facts_table(h)}</section>
    {pending(h)}
    {related_explainers(h) if is_state else ""}
    {sales_link(h)}
    {operators_html(h)}
    {coverage_html(h, arts)}
    {timeline(h)}
    {f_html}
    {sib_html(h)}
    {sources(h)}
    {disclaimer(h)}
  </div>
</article>"""
    place = {"@type": "State" if is_state else "Country", "name": name}
    if is_state:
        place["containedInPlace"] = {"@type": "Country", "name": "United States"}
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": title, "headline": f"{name} cannabis laws",
          "description": desc, "url": SITE + h["_url"], "dateModified": verified(h), "about": place,
          "publisher": T.PUBLISHER, "isAccessibleForFree": True,
          "author": {"@type": "Organization", "name": "MetaFlora News Desk", "url": f"{SITE}/how-we-report/"},
          "citation": [x["url"] for x in h.get("sources", [])][:20]}
    extra = "".join(f'<script type="application/ld+json">{json.dumps(x)}</script>' for x in (ld, crumbs_ld(crumbs), f_ld) if x)
    T.ctx["write"](h["_url"].strip("/") + "/index.html",
                   T.page(title, body, desc=desc, path=h["_url"], extra_head=extra, active="Laws",
                          robots=T.ROBOTS if complete(h) else "noindex, follow"))


def explainer_page(h, arts):
    name = h["name"]
    crumbs = [("MetaFlora News", "/"), ("Explainers", "/explainers/"), (name, h["_url"])]
    title = f"{name}: where it stands and what changes ({TITLE_YEAR})"
    if len(title) > 70:
        title = f"{name}, explained"
    desc = (h.get("where_it_stands") or h.get("summary") or "")
    desc = clip(desc, 155)
    nm = h.get("next_milestone") or {}
    nm_html = ""
    if nm.get("text"):
        nm_html = (f'<p class="milestone"><span>Next milestone</span><b>{escape(nm["text"])}</b>'
                   f'{"<time>" + fmt_date(nm["date"]) + "</time>" if nm.get("date") else ""} {src_link(nm.get("source"))}</p>')
    wc = h.get("what_changes") or []
    wc_html = ""
    if wc:
        wc_html = '<section class="hub-sec"><h2>What changes, for whom</h2><dl class="wc">' + "".join(
            f'<dt>{escape(x["for"])}</dt><dd>{escape(x["text"])}</dd>' for x in wc) + "</dl></section>"
    f_html, f_ld = faq(h)
    body = f"""
<article class="story hub">
  <header class="story-head">
    {crumbs_html(crumbs)}
    <h1>{escape(name)}</h1>
    <p class="dek hub-answer">{escape(h.get("where_it_stands", ""))}</p>
    {nm_html}
    <p class="hub-by"><span>By <a href="/how-we-report/">MetaFlora News Desk</a></span> · Last verified <time datetime="{verified(h)}">{fmt_date(verified(h))}</time></p>
  </header>
  <div class="story-col">
    <section class="hub-sec"><h2>The short version</h2><p class="hub-summary">{escape(h.get("summary", ""))}</p></section>
    {wc_html}
    {coverage_html(h, arts)}
    {timeline(h)}
    {f_html}
    {sib_html(h)}
    {sources(h)}
    {disclaimer(h)}
  </div>
</article>"""
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": name, "description": desc, "url": SITE + h["_url"],
          "dateModified": verified(h), "datePublished": h.get("first_published", verified(h)), "publisher": T.PUBLISHER,
          "author": {"@type": "Organization", "name": "MetaFlora News Desk", "url": f"{SITE}/how-we-report/"},
          "image": [f"{SITE}/assets/og-default.png"], "about": {"@type": "Thing", "name": name}}
    extra = "".join(f'<script type="application/ld+json">{json.dumps(x)}</script>' for x in (ld, crumbs_ld(crumbs), f_ld) if x)
    T.ctx["write"](h["_url"].strip("/") + "/index.html",
                   T.page(title, body, desc=desc, path=h["_url"], extra_head=extra, active="Laws",
                          robots=T.ROBOTS if complete(h) else "noindex, follow"))


def tile_map(states):
    by_abbr = {h.get("abbr"): h for h in states}
    W, S, G = 12, 46, 4
    cells = []
    for ab, (c, r) in TILES.items():
        h = by_abbr.get(ab)
        cls = tone(h) if h else "none"
        x, y = c * (S + G), r * (S + G)
        inner = f'<rect x="{x}" y="{y}" width="{S}" height="{S}" rx="3" class="tile t-{cls}"/><text x="{x + S / 2}" y="{y + S / 2 + 5}" text-anchor="middle">{ab}</text>'
        if h and complete(h):
            inner = f'<a href="{h["_url"]}" aria-label="{escape(h["name"])}: {escape(TONE_LABEL[cls])}">{inner}</a>'
        cells.append(inner)
    w, hgt = W * (S + G), 8 * (S + G)
    legend = "".join(f'<li><i class="t-{k}"></i>{v}</li>' for k, v in TONE_LABEL.items())
    return (f'<figure class="tilemap"><svg viewBox="0 0 {w} {hgt}" role="img" aria-label="Map of cannabis legal status by US state">{"".join(cells)}</svg>'
            f'<figcaption><ul class="legend">{legend}</ul></figcaption></figure>')


def recent_changes(hubs, n=10):
    ev = []
    for h in hubs:
        for e in h.get("timeline") or []:
            if len(str(e.get("date", ""))) >= 7:
                ev.append((str(e["date"]), h, e))
    ev.sort(key=lambda x: x[0], reverse=True)
    if not ev:
        return ""
    lis = "".join(f'<li><time>{fmt_date(d)}</time><span><a href="{h["_url"]}">{escape(h["name"])}</a>: {escape(clip(e["event"], 160))}</span></li>' for d, h, e in ev[:n])
    return f'<h2 class="sec-label">What changed recently</h2><ol class="timeline">{lis}</ol>'


def us_index(arts):
    states = sorted([h for h in HUBS if h["type"] == "us_state"], key=lambda h: h["name"])
    counts = {k: sum(1 for h in states if tone(h) == k) for k in TONE_LABEL}
    rows = "".join(
        f'<tr><td class="tr-name" data-label="State"><a href="{h["_url"]}">{escape(h["name"])}</a><i class="tr-dot t-{tone(h)}" aria-hidden="true"></i></td>'
        f'<td data-label="Adult use" class="t-{tone(h)}-txt">{ADULT.get(st(h).get("adult_use"), "–")}</td>'
        f'<td data-label="Medical">{MED.get(st(h).get("medical"), "–")}</td><td data-label="Decriminalized">{DECRIM.get(st(h).get("decriminalized"), "–")}</td>'
        f'<td data-label="Possession" class="tr-long">{escape(short_fact(((h.get("facts") or {}).get("possession_limit") or {}).get("value")))}</td>'
        f'<td data-label="Verified" class="tr-date">{fmt_date(verified(h))}</td></tr>'
        for h in states)
    # CSV for journalists and researchers
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["state", "abbr", "adult_use", "medical", "decriminalized", "possession_limit", "home_grow", "purchase_age", "last_verified", "url"])
    for h in states:
        f = h.get("facts") or {}
        w.writerow([h["name"], h.get("abbr", ""), st(h).get("adult_use", ""), st(h).get("medical", ""), st(h).get("decriminalized", ""),
                    (f.get("possession_limit") or {}).get("value", ""), (f.get("home_grow") or {}).get("value", ""),
                    (f.get("purchase_age") or {}).get("value", ""), verified(h), SITE + h["_url"]])
    T.ctx["write"]("legal/us/cannabis-laws-by-state.csv", buf.getvalue())
    latest = max((verified(h) for h in states), default=date.today().isoformat())
    n_rec = counts["rec"] + counts["rec-ns"]
    n_med = n_rec + counts["med"]
    title = f"Cannabis laws by state ({TITLE_YEAR}): status in all 50 states"
    dc_rec = any(h.get("abbr") == "DC" and tone(h) in ("rec", "rec-ns") for h in states)
    n_rec_states = n_rec - (1 if dc_rec else 0)
    desc = f"Where cannabis is legal in the US: {n_rec_states} states{' plus DC' if dc_rec else ''} allow adult use and {n_med} jurisdictions have medical programs. Map, table, CSV and sources."
    desc = clip(desc, 155)
    crumbs = [("MetaFlora News", "/"), ("Cannabis laws", "/legal/"), ("United States", "/legal/us/")]
    body = f"""
<article class="story hub hub-wide">
  <header class="story-head">
    {crumbs_html(crumbs)}
    <h1>Cannabis laws by state</h1>
    <p class="dek hub-answer">Adult-use cannabis is legal in {n_rec} of {len(states)} jurisdictions tracked here, and {n_med} run a full medical program. Every state links to its current law, sources and our latest coverage.</p>
    <p class="hub-by"><span>MetaFlora Legalization Tracker</span> · Updated <time datetime="{latest}">{fmt_date(latest)}</time> · <a href="/legal/us/cannabis-laws-by-state.csv" download>Download CSV</a></p>
  </header>
  <h2 class="sec-label">Map</h2>
  {tile_map(states)}
  <h2 class="sec-label">State-by-state table</h2>
  <div class="table-wrap"><table class="tracker"><thead><tr><th>State</th><th>Adult use</th><th>Medical</th><th>Decriminalized</th><th>Possession limit</th><th>Verified</th></tr></thead><tbody>{rows}</tbody></table></div>
  <div class="story-col">
    {recent_changes(states)}
    <h2 class="sec-label">Download the data</h2>
    <p><a href="/legal/us/cannabis-laws-by-state.csv" download>cannabis-laws-by-state.csv</a>: status, possession, home grow, minimum age and last-verified date for every state.</p>
    <p class="hub-note">Use this data: you're free to cite or embed the tracker with a link to this page. Statuses are checked against each state's statute or regulator; see each state page for sources. Not legal advice.</p>
  </div>
</article>"""
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": "MetaFlora Legalization Tracker: cannabis laws by US state",
          "description": desc, "url": SITE + "/legal/us/", "dateModified": latest, "license": "https://creativecommons.org/licenses/by/4.0/",
          "creator": T.PUBLISHER, "isAccessibleForFree": True, "spatialCoverage": {"@type": "Country", "name": "United States"},
          "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": SITE + "/legal/us/cannabis-laws-by-state.csv"}]}
    extra = "".join(f'<script type="application/ld+json">{json.dumps(x)}</script>' for x in (ld, crumbs_ld(crumbs)))
    T.ctx["write"]("legal/us/index.html", T.page(title, body, desc=desc, path="/legal/us/", extra_head=extra, active="Laws"))
    return latest


def world_index():
    cs = sorted([h for h in HUBS if h["type"] == "country"], key=lambda h: h["name"])
    if not cs:
        return None
    rows = "".join(
        f'<tr><td class="tr-name" data-label="Country"><a href="{h["_url"]}">{escape(h["name"])}</a><i class="tr-dot t-{tone(h)}" aria-hidden="true"></i></td>'
        f'<td data-label="Adult use" class="t-{tone(h)}-txt">{ADULT.get(st(h).get("adult_use"), "–")}</td>'
        f'<td data-label="Medical">{MED.get(st(h).get("medical"), "–")}</td>'
        f'<td data-label="Tourists" class="tr-long">{escape(short_fact(((h.get("facts") or {}).get("tourists") or {}).get("value")))}</td>'
        f'<td data-label="Verified" class="tr-date">{fmt_date(verified(h))}</td></tr>'
        for h in cs)
    latest = max(verified(h) for h in cs)
    crumbs = [("MetaFlora News", "/"), ("Cannabis laws", "/legal/"), ("World", "/legal/world/")]
    title = f"Cannabis laws around the world ({TITLE_YEAR})"
    desc = "Where cannabis is legal outside the US: adult-use, medical and tourist rules country by country, from Germany and Thailand to Canada and Uruguay, with sources."
    body = f"""
<article class="story hub hub-wide">
  <header class="story-head">{crumbs_html(crumbs)}<h1>Cannabis laws around the world</h1>
  <p class="dek hub-answer">Country-by-country cannabis rules for residents and visitors, checked against government sources.</p>
  <p class="hub-by"><span>MetaFlora Legalization Tracker</span> · Updated <time datetime="{latest}">{fmt_date(latest)}</time></p></header>
  <div class="table-wrap"><table class="tracker"><thead><tr><th>Country</th><th>Adult use</th><th>Medical</th><th>Tourists</th><th>Verified</th></tr></thead><tbody>{rows}</tbody></table></div>
</article>"""
    wl = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": SITE + "/legal/world/",
          "mainEntity": {"@type": "ItemList", "numberOfItems": len(cs), "itemListElement": [
              {"@type": "ListItem", "position": i + 1, "url": SITE + h["_url"], "name": h["name"]} for i, h in enumerate(cs)]}}
    extra = "".join(f'<script type="application/ld+json">{json.dumps(x)}</script>' for x in (wl, crumbs_ld(crumbs)))
    T.ctx["write"]("legal/world/index.html", T.page(title, body, desc=desc, path="/legal/world/", extra_head=extra, active="Laws"))
    return latest


def explainers_index():
    ex = sorted([h for h in HUBS if h["type"] == "explainer" and complete(h)], key=lambda h: h["name"])
    if not ex:
        return None
    lis = "".join(f'<li><a class="li-title" href="{h["_url"]}">{escape(h["name"])}</a><p class="dek">{escape(h.get("where_it_stands", ""))}</p></li>' for h in ex)
    crumbs = [("MetaFlora News", "/"), ("Explainers", "/explainers/")]
    body = f'<div class="page-h"><h1>Cannabis explainers</h1><p class="meta">{len(ex)} explainers</p></div><ol class="explainer-list">{lis}</ol>'
    extra = f'<script type="application/ld+json">{json.dumps(crumbs_ld(crumbs))}</script>'
    T.ctx["write"]("explainers/index.html", T.page("Cannabis explainers: federal law, tax and hemp", body,
                   desc="Plain-English explainers on US federal cannabis law: rescheduling, Section 280E, SAFER Banking, the hemp THC ban and more, each with where it stands now.",
                   path="/explainers/", extra_head=extra, active="Laws"))
    return max(verified(h) for h in ex)


def legal_index():
    states = [h for h in HUBS if h["type"] == "us_state"]
    n_rec = sum(1 for h in states if tone(h) in ("rec", "rec-ns"))
    ex = [h for h in HUBS if h["type"] == "explainer" and complete(h)][:6]
    exl = "".join(f'<li><a href="{h["_url"]}">{escape(h["name"])}</a></li>' for h in ex)
    done = [h for h in HUBS if h["type"] in ("us_state", "country") and complete(h)]
    stl = "".join(f'<li><a href="{h["_url"]}">{escape(h["name"])}</a></li>' for h in sorted(done, key=lambda h: h["name"]) if h["type"] == "us_state")
    cl = "".join(f'<li><a href="{h["_url"]}">{escape(h["name"])}</a></li>' for h in sorted(done, key=lambda h: h["name"]) if h["type"] == "country")
    body = f"""<div class="page-h"><h1>Cannabis laws</h1><p class="dek">The MetaFlora Legalization Tracker: current cannabis law for every US state, key countries and the federal rules that sit above them, checked against official sources and updated as the newsroom reports changes.</p></div>
<div class="legal-grid">
  <a class="legal-card" href="/legal/us/"><span class="lc-k">United States</span><b>Cannabis laws by state</b><span>{n_rec} states allow adult use · map, table and CSV</span></a>
  <a class="legal-card" href="/legal/world/"><span class="lc-k">World</span><b>Cannabis laws by country</b><span>Rules for residents and tourists</span></a>
  <a class="legal-card" href="/explainers/"><span class="lc-k">Federal</span><b>Explainers</b><span>Rescheduling, 280E, hemp, banking</span></a>
</div>
{'<p class="more-link"><a href="/glossary/">Cannabis glossary: industry and legal terms explained</a></p>' if has_glossary() else ''}
<h2 class="sec-label">Map</h2>
{tile_map(states)}
<section class="block"><h2 class="sec-label">Every state</h2><ul class="az-list">{stl}</ul></section>
<section class="block"><h2 class="sec-label">Countries</h2><ul class="az-list">{cl}</ul></section>
<section class="block"><h2 class="sec-label">Federal explainers</h2><ul class="sib">{exl}</ul></section>"""
    items = [SITE + h["_url"] for h in sorted(done, key=lambda h: h["name"])]
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Cannabis laws: US states, countries and federal rules",
          "url": SITE + "/legal/", "mainEntity": {"@type": "ItemList", "numberOfItems": len(items),
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": u} for i, u in enumerate(items)]}}
    T.ctx["write"]("legal/index.html", T.page("Cannabis laws: US states, countries and federal rules", body,
                   desc="Is cannabis legal where you are? Current cannabis laws for all 50 US states, key countries and federal rules, with sources and the latest changes.",
                   path="/legal/", active="Laws", extra_head=f'<script type="application/ld+json">{json.dumps(ld)}</script>'))


def term_page(h, arts):
    name = h["name"]
    crumbs = [("MetaFlora News", "/"), ("Glossary", "/glossary/"), (name, h["_url"])]
    title = f"What is {name}? Meaning in cannabis"
    desc = h.get("short", "")
    desc = clip(desc, 155)
    by_name = {x["name"].lower(): x for x in HUBS if x["type"] == "glossary"}
    rel = [by_name[r.lower()] for r in h.get("related", []) if r.lower() in by_name]
    rel_html = ""
    if rel:
        rel_html = '<section class="hub-sec"><h2>Related terms</h2><ul class="sib">' + "".join(
            f'<li><a href="{x["_url"]}">{escape(x["name"])}</a></li>' for x in rel) + "</ul></section>"
    deeper = [x for t in h.get("tags", []) for x in [hub_for_tag(t)] if x and complete(x)]
    deep_html = ""
    if deeper:
        deep_html = '<section class="hub-sec"><h2>Go deeper</h2><ul class="sib">' + "".join(
            f'<li><a href="{x["_url"]}">{escape(x["name"])}</a><span>{"Explainer" if x["type"] == "explainer" else "Law"}</span></li>' for x in {d["_url"]: d for d in deeper}.values()) + "</ul></section>"
    paras = "".join(f"<p>{escape(x)}</p>" for x in (h.get("definition") or []))
    ex = f'<p class="term-ex"><span>In the news</span>{escape(h["example"])}</p>' if h.get("example") else ""
    body = f"""
<article class="story hub">
  <header class="story-head">
    {crumbs_html(crumbs)}
    <h1>{escape(name)}</h1>
    <p class="dek hub-answer">{escape(h.get("short", ""))}</p>
    <p class="hub-by"><span>MetaFlora cannabis glossary</span> · Last verified <time datetime="{verified(h)}">{fmt_date(verified(h))}</time></p>
  </header>
  <div class="story-col">
    <div class="story-body term-body">{paras}</div>
    {ex}
    {deep_html}
    {coverage_html(h, arts) if h.get("tags") else ""}
    {rel_html}
    {sources(h)}
  </div>
</article>"""
    ld = {"@context": "https://schema.org", "@type": "DefinedTerm", "name": name, "description": h.get("short", ""), "url": SITE + h["_url"],
          "inDefinedTermSet": {"@type": "DefinedTermSet", "name": "MetaFlora cannabis glossary", "url": SITE + "/glossary/"}}
    extra = "".join(f'<script type="application/ld+json">{json.dumps(x)}</script>' for x in (ld, crumbs_ld(crumbs)))
    T.ctx["write"](h["_url"].strip("/") + "/index.html",
                   T.page(title, body, desc=desc, path=h["_url"], extra_head=extra, active="Laws",
                          robots=T.ROBOTS if complete(h) else "noindex, follow"))


def glossary_index():
    terms = sorted([h for h in HUBS if h["type"] == "glossary" and complete(h)], key=lambda h: h["name"].lower())
    if not terms:
        return None
    groups = {}
    for h in terms:
        k = h["name"][0].upper() if h["name"][0].isalpha() else "#"
        groups.setdefault(k, []).append(h)
    blocks = "".join(f'<section class="block"><h2 class="sec-label">{k}</h2><dl class="gloss">' + "".join(
        f'<dt><a href="{h["_url"]}">{escape(h["name"])}</a></dt><dd>{escape(h.get("short", ""))}</dd>' for h in v) + "</dl></section>"
        for k, v in sorted(groups.items()))
    ld = {"@context": "https://schema.org", "@type": "DefinedTermSet", "name": "MetaFlora cannabis glossary", "url": SITE + "/glossary/",
          "hasDefinedTerm": [{"@type": "DefinedTerm", "name": h["name"], "url": SITE + h["_url"]} for h in terms]}
    body = f'<div class="page-h"><h1>Cannabis glossary</h1><p class="meta">{len(terms)} terms</p></div>{blocks}'
    T.ctx["write"]("glossary/index.html", T.page("Cannabis glossary: industry and legal terms explained", body,
                   desc="Plain-English definitions of cannabis industry, science and legal terms, from THCA and total THC to Section 280E, MSOs and Schedule III.",
                   path="/glossary/", extra_head=f'<script type="application/ld+json">{json.dumps(ld)}</script>', active="Laws"))
    return max(verified(h) for h in terms)


def build(arts):
    """Write every hub page. Returns [(url, lastmod)] for indexable hub URLs (for the sitemap)."""
    if not HUBS:
        load()
    urls = []
    for h in HUBS:
        if h["type"] == "explainer":
            explainer_page(h, arts)
        elif h["type"] == "glossary":
            term_page(h, arts)
        elif h["type"] == "company":
            company_page(h, arts)
        elif h["type"] == "sales":
            sales_page(h, arts)
        else:
            jurisdiction_page(h, arts)
        if complete(h):
            urls.append((h["_url"], verified(h)))
    if any(h["type"] == "us_state" for h in HUBS):
        urls.append(("/legal/us/", us_index(arts)))
    w = world_index()
    if w:
        urls.append(("/legal/world/", w))
    e = explainers_index()
    if e:
        urls.append(("/explainers/", e))
    d = sales_index()
    if d:
        urls.append(("/data/", d))
    c = companies_index()
    if c:
        urls.append(("/company/", c))
    g = glossary_index()
    if g:
        urls.append(("/glossary/", g))
    if HUBS:
        legal_index()
        urls.append(("/legal/", max(verified(h) for h in HUBS)))
    return urls


# ---------- companies ----------

STOCK_PAGES = {"MSOS", "CURLF", "GTBIF", "VRNO", "TLRY", "CGC", "SNDL", "OGI", "ACB"}


def companies():
    return sorted([h for h in HUBS if h["type"] == "company" and complete(h)], key=lambda h: h.get("short_name") or h["name"])


def operators_html(h):
    """On a state or country page: the tracked companies that operate there."""
    key = "us_states" if h["type"] == "us_state" else "countries"
    ops = [c for c in companies() if h["name"] in ((c.get("footprint") or {}).get(key) or [])]
    if not ops:
        return ""
    lis = "".join(f'<li><a href="{c["_url"]}">{escape(c.get("short_name") or c["name"])}</a><span>{escape(c.get("segment", ""))}</span></li>' for c in ops)
    return f'<section class="hub-sec"><h2>Cannabis companies operating in {escape(h["name"])}</h2><ul class="sib">{lis}</ul></section>'


def _tickers(h):
    out = []
    for t in h.get("tickers") or []:
        sym = t.get("symbol", "")
        label = f'{escape(t.get("exchange", ""))}: {escape(sym)}'
        out.append(f'<a href="/stocks/{sym.lower()}/">{label}</a>' if sym.upper() in STOCK_PAGES else label)
    return " · ".join(out)


def company_page(h, arts):
    name = h.get("short_name") or h["name"]
    crumbs = [("MetaFlora News", "/"), ("Cannabis companies", "/company/"), (name, h["_url"])]
    title = f"{name}: company profile, results and news ({TITLE_YEAR})"
    if len(title) > 60:
        title = f"{name}: profile, results and news"
    desc = clip(h.get("headline_status", ""), 155)
    lr = h.get("latest_results") or {}
    res_rows = "".join(f'<tr><th scope="row">{lbl}</th><td>{escape(str(lr[k]))}</td></tr>'
                       for k, lbl in (("period", "Period"), ("revenue", "Revenue"), ("net_income", "Net income"), ("adj_ebitda", "Adjusted EBITDA")) if lr.get(k))
    res = (f'<section class="hub-sec"><h2>Latest results</h2><table class="facts">{res_rows}</table>'
           f'<p class="fact-src">{src_link(lr.get("source"), "Company filing")}{" · reported " + fmt_date(lr["date"]) if lr.get("date") else ""}</p></section>') if res_rows else ""
    fp = h.get("footprint") or {}
    st_by = {x["name"]: x for x in HUBS if x["type"] in ("us_state", "country") and complete(x)}
    def chip(n):
        x = st_by.get(n)
        return f'<li><a href="{x["_url"]}">{escape(n)}</a></li>' if x else f"<li>{escape(n)}</li>"
    foot = ""
    if fp.get("us_states"):
        foot += f'<h3 class="sub-h">US states ({len(fp["us_states"])})</h3><ul class="az-list">{"".join(chip(n) for n in fp["us_states"])}</ul>'
    intl = [n for n in fp.get("countries") or [] if n != "United States"]
    if intl:
        foot += f'<h3 class="sub-h">Countries</h3><ul class="az-list">{"".join(chip(n) for n in intl)}</ul>'
    foot = f'<section class="hub-sec"><h2>Where {escape(name)} operates</h2>{foot}</section>' if foot else ""
    meta = [("Tickers", _tickers(h)), ("Headquarters", escape(h.get("hq", ""))), ("Founded", escape(str(h.get("founded", "")))),
            ("Chief executive", escape(h.get("ceo", ""))), ("Website", f'<a href="{escape(h["website"])}" target="_blank" rel="noopener">{escape(h["website"].split("//")[-1].rstrip("/"))}</a>' if h.get("website") else "")]
    meta_html = "".join(f'<div class="qa"><dt>{k}</dt><dd>{v}</dd></div>' for k, v in meta if v)
    f_html, f_ld = faq(h)
    body = f"""
<article class="story hub">
  <header class="story-head">
    {crumbs_html(crumbs)}
    <h1>{escape(name)}</h1>
    <p class="dek hub-answer">{escape(h.get("headline_status", ""))}</p>
    <dl class="quick-answers co-meta">{meta_html}</dl>
    <p class="hub-by"><span>By <a href="/how-we-report/">MetaFlora News Desk</a></span> · Last verified <time datetime="{verified(h)}">{fmt_date(verified(h))}</time></p>
  </header>
  <div class="story-col">
    <section class="hub-sec"><h2>About {escape(name)}</h2><p class="hub-summary">{escape(h.get("summary", ""))}</p></section>
    {res}
    {foot}
    <section class="hub-sec"><h2>Key facts</h2>{facts_table(h)}</section>
    {coverage_html(h, arts)}
    {timeline(h)}
    {f_html}
    {company_sibs(h)}
    {sources(h)}
    <p class="hub-note">Last verified {fmt_date(verified(h))}. Company profile for news and reference only; not investment advice. Figures come from company filings and releases linked above.</p>
  </div>
</article>"""
    org = {"@context": "https://schema.org", "@type": "Corporation", "name": h["name"], "alternateName": name, "url": h.get("website"),
           "foundingDate": str(h.get("founded", "")) or None, "address": h.get("hq"),
           "tickerSymbol": " ".join(f'{t.get("exchange")}: {t.get("symbol")}' for t in h.get("tickers") or []) or None}
    org = {k: v for k, v in org.items() if v}
    page_ld = {"@context": "https://schema.org", "@type": "ProfilePage", "name": title, "description": desc, "url": SITE + h["_url"],
               "dateModified": verified(h), "publisher": T.PUBLISHER, "mainEntity": {k: v for k, v in org.items() if k != "@context"}}
    extra = "".join(f'<script type="application/ld+json">{json.dumps(x)}</script>' for x in (page_ld, crumbs_ld(crumbs), f_ld) if x)
    T.ctx["write"](h["_url"].strip("/") + "/index.html",
                   T.page(title, body, desc=desc, path=h["_url"], extra_head=extra, active="Companies",
                          robots=T.ROBOTS if complete(h) else "noindex, follow"))


def company_sibs(h):
    seg = h.get("segment", "")
    others = [c for c in companies() if c is not h]
    others.sort(key=lambda c: (("US" in seg) != ("US" in c.get("segment", "")), c.get("short_name") or c["name"]))
    lis = "".join(f'<li><a href="{c["_url"]}">{escape(c.get("short_name") or c["name"])}</a><span>{escape(c.get("segment", ""))}</span></li>' for c in others[:8])
    return f'<section class="hub-sec"><h2>Other cannabis companies</h2><ul class="sib">{lis}</ul><p class="more-link"><a href="/company/">All companies</a></p></section>' if lis else ""


def companies_index():
    cs = companies()
    if not cs:
        return None
    rows = "".join(
        f'<tr><td class="tr-name" data-label="Company"><a href="{c["_url"]}">{escape(c.get("short_name") or c["name"])}</a></td>'
        f'<td data-label="Tickers">{_tickers(c)}</td><td data-label="Segment" class="tr-long">{escape(c.get("segment", ""))}</td>'
        f'<td data-label="US states">{len((c.get("footprint") or {}).get("us_states") or []) or "–"}</td>'
        f'<td data-label="Latest quarter" class="tr-long">{escape(clip((c.get("latest_results") or {}).get("period", "–"), 40))}</td></tr>'
        for c in cs)
    crumbs = [("MetaFlora News", "/"), ("Cannabis companies", "/company/")]
    title = f"Cannabis companies: profiles, results and footprints ({TITLE_YEAR})"
    desc = "Profiles of the major cannabis companies and US multi-state operators: tickers, latest results, the states they operate in and our latest coverage."
    body = f"""
<article class="story hub hub-wide">
  <header class="story-head">{crumbs_html(crumbs)}<h1>Cannabis companies</h1>
  <p class="dek hub-answer">The listed cannabis companies we cover most, with their latest results from filings and where they operate.</p>
  <p class="hub-by"><span>MetaFlora News Desk</span> · Updated <time>{fmt_date(max(verified(c) for c in cs))}</time> · <a href="/stocks/">Cannabis stock prices</a></p></header>
  <div class="table-wrap"><table class="tracker"><thead><tr><th>Company</th><th>Tickers</th><th>Segment</th><th>US states</th><th>Latest quarter</th></tr></thead><tbody>{rows}</tbody></table></div>
  <div class="story-col"><p class="hub-note">News and reference only; not investment advice.</p></div>
</article>"""
    il = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": SITE + "/company/",
          "mainEntity": {"@type": "ItemList", "numberOfItems": len(cs), "itemListElement": [
              {"@type": "ListItem", "position": i + 1, "url": SITE + c["_url"], "name": c["name"]} for i, c in enumerate(cs)]}}
    extra = "".join(f'<script type="application/ld+json">{json.dumps(x)}</script>' for x in (il, crumbs_ld(crumbs)))
    T.ctx["write"]("company/index.html", T.page(title, body, desc=desc, path="/company/", extra_head=extra, active="Companies"))
    return max(verified(c) for c in cs)


# ---------- state sales data ----------

def sales_hubs():
    return sorted([h for h in HUBS if h["type"] == "sales"], key=lambda h: h["state"])


def per(k):
    """'2026-07' -> 'Jul 2026'; quarters and years pass through."""
    k = str(k)
    if re.fullmatch(r"\d{4}-\d{2}", k):
        return f"{datetime.fromisoformat(k + '-01'):%b %Y}"
    return k.replace("-Q", " Q")


def money(v, short=False):
    if v is None:
        return "–"
    if short == "m":
        return f"${v / 1e6:,.2f}M"
    if short:
        return f"${v / 1e9:.2f}B" if v >= 1e9 else f"${v / 1e6:.1f}M"
    return f"${v:,.0f}"


def _series(h):
    """(label, value) points for the chart: monthly totals (or adult-use), else quarterly."""
    m = h.get("monthly") or []
    pts = [(r["month"], r.get("total") if r.get("total") is not None else r.get("adult_use", r.get("taxable_sales"))) for r in m]
    pts = [(k, v) for k, v in pts if v is not None]
    if pts:
        return pts, "month"
    q = h.get("quarterly") or []
    pts = [(r.get("quarter") or r.get("period"), r.get("total") if r.get("total") is not None else r.get("adult_use", r.get("taxable_sales"))) for r in q]
    return [(k, v) for k, v in pts if v is not None and k], "quarter"


def sales_chart(h):
    pts, unit = _series(h)
    pts = pts[-24:]
    if len(pts) < 3:
        return ""
    W, H, P = 720, 260, 64
    mx = max(v for _, v in pts) or 1
    bw = (W - P) / len(pts)
    bars, labels = [], []
    for i, (k, v) in enumerate(pts):
        bh = (H - 40) * v / mx
        x = P + i * bw
        bars.append(f'<rect x="{x + bw * .12:.1f}" y="{H - 20 - bh:.1f}" width="{bw * .76:.1f}" height="{bh:.1f}" rx="2" class="sb"><title>{escape(str(k))}: {money(v)}</title></rect>')
        if i % max(1, len(pts) // 6) == 0 or i == len(pts) - 1:
            anchor = "end" if i == len(pts) - 1 else ("start" if i == 0 else "middle")
            lx = x + bw if anchor == "end" else (x if anchor == "start" else x + bw / 2)
            labels.append(f'<text x="{lx:.1f}" y="{H - 4}" text-anchor="{anchor}">{escape(per(k))}</text>')
    grid = "".join(f'<text x="{P - 8}" y="{H - 20 - (H - 40) * f + 4:.1f}" text-anchor="end">{money(mx * f, True)}</text><line x1="{P}" x2="{W}" y1="{H - 20 - (H - 40) * f:.1f}" y2="{H - 20 - (H - 40) * f:.1f}" class="sg"/>' for f in (.5, 1))
    what = "total" if any(r.get("total") for r in (h.get("monthly") or h.get("quarterly") or [])) else "reported"
    return (f'<figure class="sales-chart"><svg viewBox="0 0 {W} {H}" role="img" aria-label="{escape(h["state"])} {what} cannabis sales by {unit}">{grid}{"".join(bars)}{"".join(labels)}</svg>'
            f'<figcaption>{escape(h["state"])} {what} cannabis sales by {unit}, last {len(pts)} {unit}s. Source: {escape(h["data_source"]["name"])}.</figcaption></figure>')


def _rows_table(rows, key, label):
    if not rows:
        return ""
    cols = [c for c in ("adult_use", "medical", "total", "taxable_sales") if any(r.get(c) is not None for r in rows)]
    names = {"adult_use": "Adult use", "medical": "Medical", "total": "Total", "taxable_sales": "Taxable sales"}
    head = f"<th>{label}</th>" + "".join(f"<th>{names[c]}</th>" for c in cols)
    body = "".join(f'<tr><td data-label="{label}"><b>{escape(per(r.get(key) or r.get("period", "")))}</b></td>'
                   + "".join(f'<td data-label="{names[c]}">{money(r.get(c), "m")}</td>' for c in cols) + "</tr>" for r in reversed(rows))
    return f'<div class="table-wrap"><table class="tracker sales-t"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def sales_page(h, arts):
    name = h["state"]
    url = h["_url"]
    crumbs = [("MetaFlora News", "/"), ("Cannabis data", "/data/"), (f"{name} sales", url)]
    pts, unit = _series(h)
    ann = [r for r in h.get("annual") or [] if r.get("total") or r.get("adult_use") or r.get("taxable_sales")]
    last_ann = ann[-1] if ann else None
    latest = pts[-1] if pts else None
    ans = []
    if latest:
        ans.append(f"{name} reported {money(latest[1], True)} in cannabis sales for {per(latest[0])}")
    if last_ann:
        v = last_ann.get("total") or last_ann.get("adult_use") or last_ann.get("taxable_sales")
        ans.append(f"{money(v, True)} for {last_ann.get('year') or last_ann.get('period')}")
    answer = (" and ".join(ans) + ".") if ans else h.get("summary", "")[:200]
    freq = "monthly" if unit == "month" else ("quarterly" if pts else "annual")
    title = f"{name} cannabis sales ({TITLE_YEAR}): {freq} data and trends"
    if len(title) > 62:
        title = f"{name} cannabis sales: {freq} data ({TITLE_YEAR})"
    desc = clip(answer + " Official figures from " + h.get("regulator", "the state") + ", with chart and CSV.", 155)
    # CSV
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["state", "period", "adult_use_usd", "medical_usd", "total_usd", "source"])
    for r in h.get("monthly") or []:
        w.writerow([name, r.get("month"), r.get("adult_use"), r.get("medical"), r.get("total", r.get("taxable_sales")), h["data_source"]["url"]])
    for r in h.get("quarterly") or []:
        w.writerow([name, r.get("quarter") or r.get("period"), r.get("adult_use"), r.get("medical"), r.get("total", r.get("taxable_sales")), h["data_source"]["url"]])
    csv_name = f"{h['_slug']}-cannabis-sales.csv"
    T.ctx["write"](url.strip("/") + "/" + csv_name, buf.getvalue())
    jur = next((x for x in HUBS if x["type"] == "us_state" and x["name"] == name and complete(x)), None)
    ops = [c for c in companies() if name in ((c.get("footprint") or {}).get("us_states") or [])]
    f_html, f_ld = faq(h)
    tables = ""
    if h.get("monthly"):
        tables += f'<section class="hub-sec"><h2>Monthly sales</h2>{_rows_table(h["monthly"], "month", "Month")}</section>'
    if h.get("quarterly"):
        tables += f'<section class="hub-sec"><h2>Quarterly sales</h2>{_rows_table(h["quarterly"], "quarter", "Quarter")}</section>'
    if ann:
        tables += f'<section class="hub-sec"><h2>Annual sales</h2>{_rows_table(ann, "year", "Year")}</section>'
    body = f"""
<article class="story hub">
  <header class="story-head">
    {crumbs_html(crumbs)}
    <h1>{escape(name)} cannabis sales</h1>
    <p class="dek hub-answer">{escape(answer)}</p>
    <p class="hub-by"><span>MetaFlora Cannabis Data</span> · Verified <time datetime="{verified(h)}">{fmt_date(verified(h))}</time> · <a href="{csv_name}" download>Download CSV</a></p>
  </header>
  {sales_chart(h)}
  <div class="story-col">
    <section class="hub-sec"><h2>The {escape(name)} market</h2><p class="hub-summary">{escape(h.get("summary", ""))}</p>
      <p class="hub-note"><b>Tax:</b> {escape(h.get("tax_note", ""))}</p>
      <p class="hub-note"><b>About this data:</b> {escape(h["data_source"].get("notes", ""))} {src_link(h["data_source"]["url"], "Official source")}</p></section>
    {tables}
    {f'<section class="hub-sec"><h2>Related</h2><ul class="sib"><li><a href="{jur["_url"]}">Is weed legal in {escape(name)}?</a><span>Current law, limits and sources</span></li>' + "".join(f'<li><a href="{c["_url"]}">{escape(c.get("short_name") or c["name"])}</a><span>Operates in {escape(name)}</span></li>' for c in ops[:6]) + '</ul></section>' if jur else ""}
    {f_html}
    {sources(h)}
    <p class="hub-note">Figures are as published by the source and are not adjusted for inflation. Use freely with a link to this page.</p>
  </div>
</article>"""
    ds = {"@context": "https://schema.org", "@type": "Dataset", "name": f"{name} cannabis sales", "description": desc, "url": SITE + url,
          "dateModified": verified(h), "license": "https://creativecommons.org/licenses/by/4.0/", "creator": T.PUBLISHER, "isAccessibleForFree": True,
          "spatialCoverage": {"@type": "State", "name": name}, "isBasedOn": h["data_source"]["url"],
          "temporalCoverage": f"{pts[0][0]}/{pts[-1][0]}" if pts else None,
          "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": SITE + url + csv_name}]}
    ds = {k: v for k, v in ds.items() if v}
    extra = "".join(f'<script type="application/ld+json">{json.dumps(x)}</script>' for x in (ds, crumbs_ld(crumbs), f_ld) if x)
    T.ctx["write"](url.strip("/") + "/index.html", T.page(title, body, desc=desc, path=url, extra_head=extra, active="Laws",
                   robots=T.ROBOTS if complete(h) else "noindex, follow"))


def sales_link(h):
    if h.get("type") != "us_state":
        return ""
    s = next((x for x in HUBS if x["type"] == "sales" and x["state"] == h["name"] and complete(x)), None)
    if not s:
        return ""
    return f'<p class="more-link"><a href="{s["_url"]}">{escape(h["name"])} cannabis sales: monthly data, chart and CSV</a></p>'


def sales_index():
    ss = [h for h in sales_hubs() if complete(h)]
    if not ss:
        return None
    rows = []
    for h in ss:
        pts, unit = _series(h)
        ann = [r for r in h.get("annual") or [] if r.get("total") or r.get("adult_use") or r.get("taxable_sales")]
        a = ann[-1] if ann else {}
        rows.append(f'<tr><td class="tr-name" data-label="State"><a href="{h["_url"]}">{escape(h["state"])}</a></td>'
                    f'<td data-label="Latest">{money(pts[-1][1], True) if pts else "–"} <span class="meta">{escape(per(pts[-1][0])) if pts else ""}</span></td>'
                    f'<td data-label="Last full year">{money(a.get("total") or a.get("adult_use") or a.get("taxable_sales"), True) if a else "–"} <span class="meta">{escape(str(a.get("year", "")))}</span></td></tr>')
    crumbs = [("MetaFlora News", "/"), ("Cannabis data", "/data/")]
    title = f"Cannabis sales by state ({TITLE_YEAR}): monthly data"
    desc = "Monthly legal cannabis sales by US state from official state data: latest month, annual totals, charts and free CSV downloads, updated as states publish."
    body = f"""
<article class="story hub hub-wide">
  <header class="story-head">{crumbs_html(crumbs)}<h1>Cannabis sales by state</h1>
  <p class="dek hub-answer">Legal cannabis sales in {len(ss)} US states, straight from each state's official reports, with a chart and CSV for every state.</p>
  <p class="hub-by"><span>MetaFlora Cannabis Data</span> · Updated <time>{fmt_date(max(verified(h) for h in ss))}</time> · <a href="/legal/us/">Cannabis laws by state</a></p></header>
  <div class="table-wrap"><table class="tracker"><thead><tr><th>State</th><th>Latest period</th><th>Last full year</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
  <div class="story-col"><p class="hub-note">States report differently: some include medical sales, some publish only adult-use, and some figures are taxable sales. Each state page explains exactly what its numbers cover.</p></div>
</article>"""
    il = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": SITE + "/data/",
          "mainEntity": {"@type": "ItemList", "numberOfItems": len(ss), "itemListElement": [
              {"@type": "ListItem", "position": i + 1, "url": SITE + h["_url"], "name": f'{h["state"]} cannabis sales'} for i, h in enumerate(ss)]}}
    extra = "".join(f'<script type="application/ld+json">{json.dumps(x)}</script>' for x in (il, crumbs_ld(crumbs)))
    T.ctx["write"]("data/index.html", T.page(title, body, desc=desc, path="/data/", extra_head=extra, active="Laws"))
    return max(verified(h) for h in ss)
