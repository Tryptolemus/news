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

KIND_DIR = {"us_state": "states", "country": "countries", "explainer": "explainers", "glossary": "glossary"}
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

HUBS = []          # all hub dicts
BY_TAG = {}        # tag (lower) -> hub


def url_for(h):
    s = h["_slug"]
    return {"us_state": f"/legal/us/{s}/", "country": f"/legal/world/{s}/", "explainer": f"/explainers/{s}/",
            "glossary": f"/glossary/{s}/"}[h["type"]]


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
            if kind == "glossary":
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
    return h.get("last_verified") or date.today().isoformat()


def fmt_date(iso):
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
                m = pat.search(block)
                if m and "<a " not in block[max(0, m.start() - 200):m.start()].split("</a>")[-1]:
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
        kind = {"us_state": "State law", "country": "Country law", "explainer": "Explainer"}[h["type"]]
        items.append(f'<li><a href="{h["_url"]}"><span class="cv-k">{kind}</span><span class="cv-n">{escape(h["name"])}</span>'
                     f'<span class="cv-s">{escape(line)}</span></a></li>')
    return f'<aside class="covered"><h2>Covered in this story</h2><ul>{"".join(items)}</ul></aside>'


# ---------- page pieces ----------

def coverage(h, arts, n=8):
    tags = {t.lower() for t in {h["name"], *h.get("tags", [])}}
    items = [a for a in arts if tags & {t.lower() for t in a.get("tags", [])}]
    items.sort(key=lambda a: a["_dt"], reverse=True)
    return items[:n]


def facts_table(h):
    rows = []
    for k, label in FACT_LABELS:
        f = (h.get("facts") or {}).get(k)
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


def sib_html(h):
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
    if is_state:
        title = f"Is weed legal in {name}? {name} cannabis laws {date.today().year}"
        crumbs = [("MetaFlora News", "/"), ("Cannabis laws", "/legal/"), ("United States", "/legal/us/"), (name, h["_url"])]
    else:
        title = f"Is cannabis legal in {name}? {name} cannabis laws {date.today().year}"
        crumbs = [("MetaFlora News", "/"), ("Cannabis laws", "/legal/"), ("World", "/legal/world/"), (name, h["_url"])]
    desc = (h.get("headline_status", "") + " Possession limits, home grow, medical access and the latest changes, with official sources.")[:300]
    if len(desc) > 165:
        desc = desc[:162].rsplit(" ", 1)[0] + "..."
    chips = (f'<ul class="status-chips"><li class="t-{tone(h)}"><span>Adult use</span><b>{ADULT.get(s.get("adult_use"), "Unknown")}</b></li>'
             f'<li><span>Medical</span><b>{MED.get(s.get("medical"), "Unknown")}</b></li>'
             f'<li><span>Decriminalized</span><b>{DECRIM.get(s.get("decriminalized"), "Unknown")}</b></li></ul>')
    f_html, f_ld = faq(h)
    body = f"""
<article class="story hub">
  <header class="story-head">
    {crumbs_html(crumbs)}
    <h1>{escape(name)} cannabis laws</h1>
    <p class="dek hub-answer">{escape(h.get("headline_status", ""))}</p>
    {chips}
    <p class="hub-by"><span>By <a href="/how-we-report/">MetaFlora News Desk</a></span> · Last verified <time datetime="{verified(h)}">{fmt_date(verified(h))}</time></p>
  </header>
  <div class="story-col">
    <section class="hub-sec"><h2>The law today</h2><p class="hub-summary">{escape(h.get("summary", ""))}</p></section>
    <section class="hub-sec"><h2>Key facts</h2>{facts_table(h)}</section>
    {pending(h)}
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
    title = f"{name}: where it stands and what changes ({date.today().year})"
    if len(title) > 70:
        title = f"{name}, explained"
    desc = (h.get("where_it_stands") or h.get("summary") or "")
    if len(desc) > 165:
        desc = desc[:162].rsplit(" ", 1)[0] + "..."
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


def us_index(arts):
    states = sorted([h for h in HUBS if h["type"] == "us_state"], key=lambda h: h["name"])
    counts = {k: sum(1 for h in states if tone(h) == k) for k in TONE_LABEL}
    rows = "".join(
        f'<tr><td><a href="{h["_url"]}">{escape(h["name"])}</a></td><td class="t-{tone(h)}-txt">{ADULT.get(st(h).get("adult_use"), "–")}</td>'
        f'<td>{MED.get(st(h).get("medical"), "–")}</td><td>{DECRIM.get(st(h).get("decriminalized"), "–")}</td>'
        f'<td>{escape(str(((h.get("facts") or {}).get("possession_limit") or {}).get("value", "–")))}</td><td>{fmt_date(verified(h))}</td></tr>'
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
    title = f"Cannabis laws by state ({date.today().year}): legal status in all 50 states"
    desc = f"Where cannabis is legal in the US: {n_rec} states plus DC allow adult use in some form and {n_med} have medical programs. Map, table and sources, updated as laws change."
    if len(desc) > 165:
        desc = desc[:162].rsplit(" ", 1)[0] + "..."
    crumbs = [("MetaFlora News", "/"), ("Cannabis laws", "/legal/"), ("United States", "/legal/us/")]
    body = f"""
<article class="story hub hub-wide">
  <header class="story-head">
    {crumbs_html(crumbs)}
    <h1>Cannabis laws by state</h1>
    <p class="dek hub-answer">Adult-use cannabis is legal in {n_rec} of {len(states)} jurisdictions tracked here, and {n_med} run a full medical program. Every state links to its current law, sources and our latest coverage.</p>
    <p class="hub-by"><span>MetaFlora Legalization Tracker</span> · Updated <time datetime="{latest}">{fmt_date(latest)}</time> · <a href="/legal/us/cannabis-laws-by-state.csv" download>Download CSV</a></p>
  </header>
  {tile_map(states)}
  <div class="table-wrap"><table class="tracker"><thead><tr><th>State</th><th>Adult use</th><th>Medical</th><th>Decriminalized</th><th>Possession limit</th><th>Verified</th></tr></thead><tbody>{rows}</tbody></table></div>
  <div class="story-col">
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
        f'<tr><td><a href="{h["_url"]}">{escape(h["name"])}</a></td><td class="t-{tone(h)}-txt">{ADULT.get(st(h).get("adult_use"), "–")}</td>'
        f'<td>{MED.get(st(h).get("medical"), "–")}</td><td>{escape(str(((h.get("facts") or {}).get("tourists") or {}).get("value", "–")))}</td><td>{fmt_date(verified(h))}</td></tr>'
        for h in cs)
    latest = max(verified(h) for h in cs)
    crumbs = [("MetaFlora News", "/"), ("Cannabis laws", "/legal/"), ("World", "/legal/world/")]
    title = f"Cannabis laws around the world ({date.today().year})"
    desc = "Where cannabis is legal outside the US: adult-use, medical and tourist rules country by country, from Germany and Thailand to Canada and Uruguay, with sources."
    body = f"""
<article class="story hub hub-wide">
  <header class="story-head">{crumbs_html(crumbs)}<h1>Cannabis laws around the world</h1>
  <p class="dek hub-answer">Country-by-country cannabis rules for residents and visitors, checked against government sources.</p>
  <p class="hub-by"><span>MetaFlora Legalization Tracker</span> · Updated <time datetime="{latest}">{fmt_date(latest)}</time></p></header>
  <div class="table-wrap"><table class="tracker"><thead><tr><th>Country</th><th>Adult use</th><th>Medical</th><th>Tourists</th><th>Verified</th></tr></thead><tbody>{rows}</tbody></table></div>
</article>"""
    extra = f'<script type="application/ld+json">{json.dumps(crumbs_ld(crumbs))}</script>'
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
    body = f"""<div class="page-h"><h1>Cannabis laws</h1><p class="dek">The MetaFlora Legalization Tracker: current cannabis law for every US state, key countries and the federal rules that sit above them, checked against official sources and updated as the newsroom reports changes.</p></div>
<div class="legal-grid">
  <a class="legal-card" href="/legal/us/"><span class="lc-k">United States</span><b>Cannabis laws by state</b><span>{n_rec} states allow adult use · map, table and CSV</span></a>
  <a class="legal-card" href="/legal/world/"><span class="lc-k">World</span><b>Cannabis laws by country</b><span>Rules for residents and tourists</span></a>
  <a class="legal-card" href="/explainers/"><span class="lc-k">Federal</span><b>Explainers</b><span>Rescheduling, 280E, hemp, banking</span></a>
</div>
<p class="more-link"><a href="/glossary/">Cannabis glossary: industry and legal terms explained</a></p>
{tile_map(states)}
<section class="block"><h2 class="sec-label">Federal explainers</h2><ul class="sib">{exl}</ul></section>"""
    T.ctx["write"]("legal/index.html", T.page("Cannabis laws: US states, countries and federal rules", body,
                   desc="Is cannabis legal where you are? Current cannabis laws for all 50 US states, key countries and federal rules, with sources and the latest changes.",
                   path="/legal/", active="Laws"))


def term_page(h, arts):
    name = h["name"]
    crumbs = [("MetaFlora News", "/"), ("Glossary", "/glossary/"), (name, h["_url"])]
    title = f"What is {name}? Meaning in cannabis"
    desc = h.get("short", "")
    if len(desc) > 165:
        desc = desc[:162].rsplit(" ", 1)[0] + "..."
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
    g = glossary_index()
    if g:
        urls.append(("/glossary/", g))
    if HUBS:
        legal_index()
        urls.append(("/legal/", max(verified(h) for h in HUBS)))
    return urls
