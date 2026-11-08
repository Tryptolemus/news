"""'X by state' aggregate pages, built only from hub facts that are already in content/hubs/.

Every row is one state hub fact ({value, source, as_of}): the table shows the fact's own text, its own
source link and its own as-of date. A state without the fact shows "Not yet verified", never an
inferred value. A page indexes only when at least 80% of its rows carry a sourced fact.

Categories ("Adults 21+", "Zero tolerance", ...) are read from the opening words of the sourced value
itself (e.g. a DUI fact that starts "Zero tolerance:"); a value that doesn't open with a known phrase
gets "See rule", so nothing is guessed.

URLs
  /legal/us/by-state/                          index of every by-state table
  /legal/us/<topic>-by-state/  (+ data.csv)    one table per topic (see TOPICS)
  /legal/us/where-tourists-can-buy-cannabis/   US states + countries
  /data/cannabis-sales-by-state/ (+ data.csv)  states ranked by latest official full-year sales
"""
import csv
import io
import json
from html import escape

import hubs as H
import templates as T

SITE = T.SITE
INDEX_MIN = 0.8  # share of rows that need a sourced fact before a page may be indexed
NV = "Not yet verified"
INDEX_URL = "/legal/us/by-state/"
SALES_URL = "/data/cannabis-sales-by-state/"
Y = H.TITLE_YEAR


def _sourced(f):
    return isinstance(f, dict) and bool(f.get("value")) and bool(f.get("source")) and bool(f.get("as_of"))


def _starts(v, *prefixes):
    v = (v or "").strip().lower()
    return any(v.startswith(p.lower()) for p in prefixes)


# ---------- categories read from the opening words of each sourced value ----------

def cat_home_grow(v):
    if _starts(v, "Not allowed for adult-use", "Only registered medical patients", "Registered patients", "Licensed patients", "Patients whose"):
        return "Patients only"
    if _starts(v, "Not allowed", "Not permitted", "Prohibited"):
        return "Not allowed"
    if _starts(v, "Only for adults"):
        return "Adults, restricted"
    return "Adults"


def cat_dui(v):
    if _starts(v, "Zero tolerance"):
        return "Zero tolerance"
    if _starts(v, "Per se"):
        return "Per se THC limit"
    if _starts(v, "Permissible inference"):
        return "Permissible inference"
    if _starts(v, "Impairment-based", "Mostly impairment-based"):
        return "Impairment-based"
    return "See rule"


def cat_tourists(v):
    if _starts(v, "Yes."):
        return "Yes"
    if _starts(v, "Medical patients only"):
        return "Visiting patients only"
    if _starts(v, "Partly.", "Limited.", "Only on"):
        return "Limited"
    if _starts(v, "No"):
        return "No"
    return "See rule"


LOUNGE_WORDS = ("lounge", "on-site", "consumption area", "hospitality", "licensed business", "approved venue", "licensed area", "21+ locations")


def cat_public(v):
    low = (v or "").lower()
    return "Venues allowed" if any(w in low for w in LOUNGE_WORDS) else "See rule"


TOPICS = [
    {"slug": "possession-limits-by-state", "fact": "possession_limit", "col": "Possession limit", "cat": None,
     "h1": "How much weed can you carry? Possession limits by state",
     "title": f"Marijuana possession limits by state ({Y})",
     "short": "Possession limits", "blurb": "How much cannabis adults and patients may carry in every state.",
     "explainers": ["medical-marijuana-card", "traveling-with-cannabis"]},
    {"slug": "home-grow-by-state", "fact": "home_grow", "col": "Home grow rule", "cat": cat_home_grow, "cat_col": "Who may grow",
     "h1": "Can you grow weed at home? Home grow laws by state",
     "title": f"Can you grow weed at home? Laws by state ({Y})",
     "short": "Home grow", "blurb": "Who may grow cannabis at home, and how many plants.",
     "explainers": ["home-grow-laws"]},
    {"slug": "hemp-thc-by-state", "fact": "hemp_thc", "col": "State hemp THC rule", "cat": None,
     "h1": "Is THCA or delta-8 legal in my state? Hemp THC laws by state",
     "title": f"THCA and delta-8 laws by state ({Y})",
     "short": "Hemp THC, THCA and delta-8", "blurb": "State rules on intoxicating hemp products, plus the federal deadlines.",
     "explainers": ["hemp-thc-ban", "thca-flower", "delta-8-thc", "total-thc", "farm-bill"]},
    {"slug": "public-consumption-by-state", "fact": "public_use", "col": "Public use rule", "cat": cat_public, "cat_col": "Consumption venues",
     "h1": "Where can you smoke weed? Public consumption laws by state",
     "title": f"Public cannabis consumption laws by state ({Y})",
     "short": "Public consumption", "blurb": "Where cannabis use is banned, and which states allow lounges.",
     "explainers": ["cannabis-lounges"]},
    {"slug": "marijuana-dui-laws-by-state", "fact": "dui", "col": "Driving rule", "cat": cat_dui, "cat_col": "Standard",
     "h1": "Marijuana DUI laws by state: per se limits and zero tolerance",
     "title": f"Marijuana DUI laws by state ({Y})",
     "short": "Marijuana DUI laws", "blurb": "Per se THC limits, zero tolerance and impairment-based states.",
     "explainers": ["cannabis-dui-laws"]},
    {"slug": "where-tourists-can-buy-cannabis", "fact": "tourists", "col": "Visitor rule", "cat": cat_tourists, "cat_col": "Can visitors buy?",
     "h1": "Where can tourists buy weed? US states and countries",
     "title": f"Where can tourists buy weed? States and countries ({Y})",
     "short": "Where tourists can buy", "blurb": "Can visitors buy cannabis legally? Every state, plus 22 countries.",
     "explainers": ["traveling-with-cannabis"], "world": True},
]


# ---------- helpers ----------

def _states():
    return sorted([h for h in H.HUBS if h["type"] == "us_state"], key=lambda h: h["name"])


def _countries():
    return sorted([h for h in H.HUBS if h["type"] == "country"], key=lambda h: h["name"])


def _fact(h, key):
    f = (h.get("facts") or {}).get(key)
    return f if _sourced(f) else None


def _count(hs):
    """'23 states plus DC' / '12 states' / '1 state'."""
    dc = any(h.get("abbr") == "DC" for h in hs)
    n = len(hs) - (1 if dc else 0)
    s = f"{n} state{'' if n == 1 else 's'}"
    return f"{s} plus DC" if dc else s


def _names(hs):
    names = [h["name"] for h in hs]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _ld(*objs):
    return "".join(f'<script type="application/ld+json">{json.dumps(x)}</script>' for x in objs if x)


def _faq(qs):
    qs = [(q, a) for q, a in qs if q and a]
    if not qs:
        return "", None
    html = "".join(f'<details class="faq"><summary>{escape(q)}</summary><p>{escape(a)}</p></details>' for q, a in qs)
    ld = {"@context": "https://schema.org", "@type": "FAQPage",
          "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qs]}
    return f'<section class="hub-sec"><h2>Questions people ask</h2>{html}</section>', ld


def _title_ok(title):
    full = f"{title} · {T.NAME}" if len(title) <= 44 else title
    assert len(full) <= 60, f"title too long ({len(full)}): {full}"
    return title


def _desc_ok(desc):
    assert len(desc) <= 155 and desc.endswith("."), f"bad description ({len(desc)}): {desc}"
    return desc


def _explainers(slugs):
    ex = {h["_slug"]: h for h in H.HUBS if h["type"] == "explainer" and H.complete(h)}
    items = [ex[s] for s in slugs if s in ex]
    if not items:
        return ""
    return ('<section class="hub-sec"><h2>Explainers</h2><ul class="sib">' + "".join(
        f'<li><a href="{h["_url"]}">{escape(h["name"])}</a><span>Explainer</span></li>' for h in items) + "</ul></section>")


def siblings_html(current):
    lis = [f'<li><a href="/legal/us/{t["slug"]}/">{escape(t["short"])}</a><span>By state</span></li>' for t in TOPICS if t["slug"] != current]
    if current != "sales":
        lis.append(f'<li><a href="{SALES_URL}">Cannabis sales ranking</a><span>Data</span></li>')
    lis.append(f'<li><a href="/legal/us/">Legal status in every state</a><span>Tracker</span></li>')
    return (f'<section class="hub-sec"><h2>More by-state tables</h2><ul class="sib">{"".join(lis)}</ul>'
            f'<p class="more-link"><a href="{INDEX_URL}">All by-state tables</a></p></section>')


def _status_cell(h):
    t = H.tone(h)
    return f'<td data-label="Status" class="t-{t}-txt">{escape(H.TONE_LABEL[t])}</td>'


def _table(hs, topic, label="State"):
    """Rows + CSV rows for one jurisdiction list. Returns (html_rows, csv_rows, sourced_count, latest_as_of)."""
    rows, out, n_ok, dates = [], [], 0, []
    for h in hs:
        f = _fact(h, topic["fact"])
        cat = topic["cat"](f["value"]) if f and topic.get("cat") else ""
        if f:
            n_ok += 1
            dates.append(f["as_of"])
            val = f'<td data-label="{escape(topic["col"])}" class="tr-long">{escape(f["value"])}</td>'
            src = f'<td data-label="Source">{H.src_link(f["source"])}</td>'
            asof = f'<td data-label="Verified" class="tr-date"><time datetime="{f["as_of"]}">{H.fmt_date(f["as_of"])}</time></td>'
        else:
            val = f'<td data-label="{escape(topic["col"])}" class="tr-long bys-nv">{NV}</td>'
            src = '<td data-label="Source">–</td>'
            asof = '<td data-label="Verified" class="tr-date">–</td>'
        catc = f'<td data-label="{escape(topic["cat_col"])}">{escape(cat) if f else "–"}</td>' if topic.get("cat") else ""
        rows.append(f'<tr><td class="tr-name" data-label="{label}"><a href="{h["_url"]}">{escape(h["name"])}</a><i class="tr-dot t-{H.tone(h)}" aria-hidden="true"></i></td>'
                    f'{_status_cell(h)}{catc}{val}{src}{asof}</tr>')
        out.append([h["name"], h.get("abbr", ""), H.TONE_LABEL[H.tone(h)], cat, f["value"] if f else NV,
                    f["source"] if f else "", f["as_of"] if f else "", SITE + h["_url"]])
    head = (f'<th>{label}</th><th>Status</th>' + (f'<th>{escape(topic["cat_col"])}</th>' if topic.get("cat") else "")
            + f'<th>{escape(topic["col"])}</th><th>Source</th><th>Verified</th>')
    html = f'<div class="table-wrap"><table class="tracker bys-t"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    return html, out, n_ok, (max(dates) if dates else None)


def _csv(rows, first_col="state"):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([first_col, "abbr", "status", "category", "value", "source", "as_of", "url"])
    w.writerows(rows)
    return buf.getvalue()


def _by_cat(states, topic):
    out = {}
    for h in states:
        f = _fact(h, topic["fact"])
        if f:
            out.setdefault(topic["cat"](f["value"]) if topic.get("cat") else "", []).append(h)
    return out


# ---------- per-topic copy: lead + FAQ, all computed from the rows ----------

def _copy(topic, states, n_ok):
    k = topic["fact"]
    adult = [h for h in states if H.st(h).get("adult_use") in ("legal", "legal_no_sales")]
    illegal = [h for h in states if H.st(h).get("adult_use") == "illegal"]
    cats = _by_cat(states, topic)
    total = len(states)
    if k == "possession_limit":
        lead = (f"Adults 21+ may legally possess cannabis in {_count(adult)}; in the other {_count(illegal)} there is no legal amount "
                f"for adults outside a medical program. The table gives each state's limit, word for word from our sourced state page.")
        desc = f"How much weed can you carry? Possession limits for all 50 states and DC: {_count(adult)} allow adults to possess cannabis, each with a source."
        faq = [("In which states can adults legally possess cannabis?", f"Adults 21+ may possess cannabis under state law in {_count(adult)}: {_names(adult)}. Limits differ by state; see the table."),
               ("Where is possessing cannabis still illegal for adults?", f"In {_count(illegal)}, state law sets no legal amount for adults outside a medical program: {_names(illegal)}.")]
    elif k == "home_grow":
        a, r, p, no = cats.get("Adults", []), cats.get("Adults, restricted", []), cats.get("Patients only", []), cats.get("Not allowed", [])
        lead = (f"Adults may grow cannabis at home in {_count(a + r)}{' (in ' + _names(r) + ' only far from a store)' if r else ''}; "
                f"{_count(p)} allow only registered patients to grow, and {_count(no)} allow no home cultivation.")
        desc = f"Can you grow weed at home? Home grow rules and plant limits for all 50 states and DC: {_count(a + r)} allow adults to grow, each with a source."
        faq = [("Which states allow home grow?", f"Adults may grow cannabis at home in {_count(a + r)}: {_names(sorted(a + r, key=lambda h: h['name']))}." + (f" In {_names(r)} it is limited to adults who live far from a store." if r else "")),
               ("Can medical patients grow cannabis at home?", f"Only registered patients may grow in {_count(p)}: {_names(p)}. Some adult-use states also give patients a higher plant count." if p else ""),
               ("Where is growing cannabis at home illegal?", f"Home cultivation is not allowed in {_count(no)}: {_names(no)}." if no else ""),
               ("Is home grow legal in every adult-use state?", "No. " + _names([h for h in adult if h in no or h in p]) + " allow adult use but not adult home grow." if any(h in no or h in p for h in adult) else "")]
    elif k == "hemp_thc":
        fed = _federal_hemp()
        verified = [h for h in states if _fact(h, k)]
        lead = (f"State rules for intoxicating hemp products such as THCA flower and delta-8 THC, sourced for {n_ok} of {total} jurisdictions so far. "
                + (fed["lead"] if fed else ""))
        desc = f"Is THCA or delta-8 legal in your state? Hemp THC rules for {n_ok} states, with sources, plus the federal hemp redefinition dates."
        faq = [("When does the federal hemp THC ban take effect?", fed["faq"] if fed else ""),
               ("Is THCA or delta-8 legal in my state?", f"It depends on state law and, from late 2026, the new federal hemp definition. We have a sourced state rule for {_count(verified)}; the rest are marked not yet verified.")]
    elif k == "public_use":
        v = cats.get("Venues allowed", [])
        lead = (f"Public cannabis use is restricted almost everywhere, including in adult-use states. The sourced rules for {_count(v)} mention licensed, local or "
                f"approved consumption venues such as lounges.")
        desc = f"Where can you smoke weed? Public cannabis use rules for all 50 states and DC, and the {_count(v)} whose rules allow consumption venues."
        faq = [("Which states allow cannabis lounges or consumption venues?", f"The rules we cite for {_count(v)} mention licensed, local or approved consumption venues: {_names(v)}. Many depend on local approval."),
               ("Can you smoke weed in public in a legal state?", "Usually not. Adult-use states generally ban use in public places and vehicles; a few allow it where tobacco smoking is allowed or in licensed venues. Check the state row."),
               ("Can you use cannabis in a car?", "Every state bans driving while impaired by cannabis, and many of the rules cited here also ban using it in a vehicle. See the marijuana DUI laws by state table.")]
    elif k == "dui":
        z, ps, pi, im, other = (cats.get(c, []) for c in ("Zero tolerance", "Per se THC limit", "Permissible inference", "Impairment-based", "See rule"))
        lead = (f"{_count(z)} have zero-tolerance drugged-driving laws that cover THC, {_count(ps)} set a per se THC blood limit, "
                f"and {_count(im)} require proof of impairment" + (f"; {_names(pi)} uses a permissible inference" if pi else "") + ".")
        desc = f"Marijuana DUI laws for all 50 states and DC: {_count(z)} are zero tolerance and {_count(ps)} set a per se THC limit, each with a source."
        faq = [("Which states have zero tolerance for THC while driving?", f"{_names(z)} ban driving with any amount of THC or a listed metabolite, according to the sources cited." if z else ""),
               ("Which states have a per se THC limit?", f"{_names(ps)} set a THC level in the blood at or above which a driver is legally impaired." if ps else ""),
               ("Is it legal to drive high in a state where weed is legal?", "No. Every state bans driving while impaired by cannabis. In impairment-based states, police and prosecutors must show impairment rather than a THC level."),
               ("What does permissible inference mean?", f"In {_names(pi)}, a THC level at or above the threshold lets a court infer impairment, but it is not automatic proof." if pi else "")]
    else:  # tourists
        y, lim, pat, no = cats.get("Yes", []), cats.get("Limited", []), cats.get("Visiting patients only", []), cats.get("No", [])
        lead = (f"Visitors 21+ can buy cannabis at licensed stores in {_count(y)}. {_count(pat).capitalize()} sell only to visiting medical patients, "
                f"{_count(lim)} offer limited access, and {_count(no)} offer no legal way for tourists to buy.")
        desc = f"Where can tourists buy weed? Visitor rules for all 50 states, DC and 22 countries: visitors 21+ can buy in {_count(y)}, with sources."
        faq = [("Which states let tourists buy weed?", f"Adults 21+ can buy at licensed stores without being residents in {_count(y)}: {_names(y)}."),
               ("Can I use my medical card in another state?", f"Some states sell to visiting patients: {_names(pat)}. Each has its own registration rules." if pat else ""),
               ("Can you take weed across state lines?", "No. Carrying cannabis across state lines or national borders is illegal under federal law, even between two legal states. Our traveling with cannabis explainer covers flights, airports and borders."),
               ("Which countries let tourists buy cannabis?", _world_answer())]
    return lead, desc, faq


def _federal_hemp():
    ex = next((h for h in H.HUBS if h["type"] == "explainer" and h["_slug"] == "hemp-thc-ban"), None)
    if not ex:
        return None
    keep = [e for e in ex.get("timeline") or [] if e.get("source") and e.get("date") in ("2025-11-12", "2026-09-02", "2026-11-12", "2026-12-11")]
    if not keep:
        return None
    lis = "".join(f'<li><time>{H.fmt_date(e["date"])}</time><span>{escape(e["event"])} {H.src_link(e["source"])}</span></li>' for e in keep)
    nxt = [e for e in keep if e["date"] >= "2026-11-12"]
    lead = ""
    faqa = ""
    if len(nxt) >= 2:
        lead = f"Federally, the new hemp definition starts in two steps: {H.fmt_date(nxt[0]['date'])} and {H.fmt_date(nxt[1]['date'])}."
        faqa = (f"In two steps under the current federal law: on {H.fmt_date(nxt[0]['date'])}, {nxt[0]['event'][0].lower() + nxt[0]['event'][1:]}; "
                f"on {H.fmt_date(nxt[1]['date'])}, {nxt[1]['event'][0].lower() + nxt[1]['event'][1:]}.")
    html = (f'<section class="hub-sec"><h2>Federal hemp deadlines</h2><ol class="timeline">{lis}</ol>'
            f'<p class="more-link"><a href="{ex["_url"]}">The federal hemp THC ban, explained</a></p></section>')
    return {"html": html, "lead": lead, "faq": faqa}


def _world_rows():
    cs = _countries()
    topic = next(t for t in TOPICS if t["fact"] == "tourists")
    t2 = dict(topic, cat=None)  # country texts don't open with a fixed Yes/No phrase: show the sourced text only
    return cs, t2


def _world_answer():
    cs = [h for h in _countries() if _fact(h, "tourists")]
    if not cs:
        return ""
    yes = [h for h in cs if _starts(_fact(h, "tourists")["value"], "Adult visitors may buy")]
    if yes:
        return (f"Of the {len(cs)} countries we track, {_names(yes)} lets adult visitors buy from licensed retailers. "
                "In most others visitors have no legal way to buy; see the countries table for each rule.")
    return f"See the countries table: we track visitor rules for {len(cs)} countries, each with a source."


# ---------- pages ----------

def topic_page(topic, arts):
    states = _states()
    url = f"/legal/us/{topic['slug']}/"
    html_rows, csv_rows, n_ok, latest = _table(states, topic)
    world_html = ""
    rows_total, ok_total = len(states), n_ok
    items = list(states)
    if topic.get("world"):
        cs, t2 = _world_rows()
        if cs:
            w_html, w_csv, w_ok, w_latest = _table(cs, t2, label="Country")
            csv_rows += w_csv
            rows_total += len(cs)
            ok_total += w_ok
            latest = max(x for x in (latest, w_latest) if x)
            items += cs
            world_html = (f'<h2 class="sec-label" id="countries">Countries</h2><p class="hub-note">Visitor rules in {len(cs)} countries, from each country page.</p>{w_html}')
    assert rows_total and html_rows, f"empty table for {topic['slug']}"
    pct = ok_total / rows_total
    indexable = pct >= INDEX_MIN
    lead, desc, faq = _copy(topic, states, n_ok)
    title = _title_ok(topic["title"])
    desc = _desc_ok(desc)
    T.ctx["write"](url.strip("/") + "/data.csv", _csv(csv_rows))
    crumbs = [("MetaFlora News", "/"), ("Cannabis laws", "/legal/"), ("United States", "/legal/us/"), ("By state", INDEX_URL), (topic["short"], url)]
    f_html, f_ld = _faq(faq)
    fed = _federal_hemp() if topic["fact"] == "hemp_thc" else None
    cover = f"{ok_total} of {rows_total} rows sourced ({round(100 * pct)}%)"
    body = f"""
<article class="story hub hub-wide">
  <header class="story-head">
    {H.crumbs_html(crumbs)}
    <h1>{escape(topic["h1"])}</h1>
    <p class="dek hub-answer">{escape(lead)}</p>
    <p class="hub-by"><span>MetaFlora Legalization Tracker</span> · Last verified <time datetime="{latest}">{H.fmt_date(latest)}</time> · {cover} · <a href="data.csv" download>Download CSV</a></p>
  </header>
  {fed["html"] if fed else ""}
  <h2 class="sec-label">{"US states" if topic.get("world") else "State-by-state table"}</h2>
  {html_rows}
  {world_html}
  <div class="story-col">
    {f_html}
    <section class="hub-sec"><h2>About this table</h2><p class="hub-note">Each row is the sourced fact from that state's page, with its own source and the date we last checked it. Rows marked "{NV}" have no sourced fact yet; we never fill them with a guess. {"The category column is read from the opening words of each sourced rule. " if topic.get("cat") else ""}Status is the state's adult-use and medical status from the <a href="/legal/us/">legalization tracker</a>.</p>
    <p class="hub-note">Use this data freely with a link to this page: <a href="data.csv" download>data.csv</a>. Laws change; check the linked official sources before acting. This is news and reference, not legal advice. Spotted something out of date? Email <a href="mailto:support@metaflora.xyz">support@metaflora.xyz</a>.</p></section>
    {_explainers(topic.get("explainers", []))}
    {siblings_html(topic["slug"])}
  </div>
</article>"""
    ds = {"@context": "https://schema.org", "@type": "Dataset", "name": f"{topic['short']} by state (MetaFlora Legalization Tracker)",
          "description": desc, "url": SITE + url, "dateModified": latest, "license": "https://creativecommons.org/licenses/by/4.0/",
          "creator": T.PUBLISHER, "isAccessibleForFree": True,
          "spatialCoverage": {"@type": "Country", "name": "United States"} if not topic.get("world") else "United States and selected countries",
          "variableMeasured": topic["col"],
          "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": SITE + url + "data.csv"}]}
    il = {"@context": "https://schema.org", "@type": "ItemList", "name": topic["h1"], "numberOfItems": len(items),
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": SITE + h["_url"], "name": h["name"]} for i, h in enumerate(items)]}
    T.ctx["write"](url.strip("/") + "/index.html", T.page(title, body, desc=desc, path=url, active="Laws",
                   extra_head=_ld(ds, il, H.crumbs_ld(crumbs), f_ld), robots=T.ROBOTS if indexable else "noindex, follow"))
    return {"url": url, "topic": topic, "rows": rows_total, "sourced": ok_total, "pct": pct, "indexable": indexable, "latest": latest}


# ---------- sales ranking ----------

def _full_year(r):
    p = str(r.get("period") or "").lower()
    return "year to date" not in p and r.get("total") not in (None, 0)


def _fy(r):
    return str(r.get("period") or "").startswith("FY")


def sales_rows():
    """[(hub, row, prev_row_or_None)] ranked by latest official full-year total; plus [(hub, reason)] not ranked."""
    ranked, skipped = [], []
    for h in H.sales_hubs():
        ann = [r for r in h.get("annual") or [] if _full_year(r)]
        if not ann:
            au = [r for r in h.get("annual") or [] if r.get("adult_use")]
            skipped.append((h, f"publishes adult-use sales only ({H.money(au[-1]['adult_use'], True)} in {au[-1]['year']})" if au else "has no official full-year total yet"))
            continue
        last = ann[-1]
        prev = next((r for r in ann if r.get("year") == last.get("year", 0) - 1 and _fy(r) == _fy(last)), None)
        ranked.append((h, last, prev))
    ranked.sort(key=lambda x: x[1]["total"], reverse=True)
    return ranked, skipped


def _yr(r):
    return r.get("period") or str(r.get("year"))


def sales_page():
    ranked, skipped = sales_rows()
    if not ranked:
        return None
    url = SALES_URL
    rows, csvr, dates = [], [], []
    for i, (h, r, p) in enumerate(ranked, 1):
        yoy = (r["total"] - p["total"]) / p["total"] * 100 if p else None
        dates.append(H.verified(h))
        rows.append(f'<tr><td data-label="Rank"><b>{i}</b></td><td class="tr-name" data-label="State"><a href="{h["_url"]}">{escape(h["state"])}</a></td>'
                    f'<td data-label="Sales">{H.money(r["total"], True)}</td><td data-label="Year">{escape(_yr(r))}</td>'
                    f'<td data-label="Change">{f"{yoy:+.1f}%" if yoy is not None else "–"}</td>'
                    f'<td data-label="Basis" class="tr-long">{escape(r.get("basis", ""))}</td>'
                    f'<td data-label="Source">{H.src_link(h["data_source"]["url"])}</td>'
                    f'<td data-label="Verified" class="tr-date">{H.fmt_date(H.verified(h))}</td></tr>')
        csvr.append([i, h["state"], r["total"], _yr(r), p["total"] if p else "", f"{yoy:.1f}" if yoy is not None else "",
                     r.get("basis", ""), h["data_source"]["url"], H.verified(h), SITE + h["_url"]])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rank", "state", "total_usd", "period", "prior_year_total_usd", "yoy_pct", "basis", "source", "last_verified", "url"])
    w.writerows(csvr)
    T.ctx["write"](url.strip("/") + "/data.csv", buf.getvalue())
    latest = max(dates)
    top, second = ranked[0], ranked[1] if len(ranked) > 1 else None
    lead = (f"{top[0]['state']} is the largest legal cannabis market with official data: {H.money(top[1]['total'], True)} in {_yr(top[1])}"
            + (f", ahead of {second[0]['state']} at {H.money(second[1]['total'], True)}" if second else "") + f". {len(ranked)} states ranked by their latest official full-year sales.")
    title = _title_ok(f"Largest cannabis markets by state: sales ranked ({Y})")
    desc = _desc_ok(f"Which state sells the most cannabis? {len(ranked)} states ranked by official full-year sales, with year-on-year change, sources and a CSV.")
    sk = "".join(f'<li><a href="{h["_url"]}">{escape(h["state"])}</a>: {escape(why)}</li>' for h, why in skipped)
    faq = [("Which state sells the most cannabis?", f"{top[0]['state']}, with {H.money(top[1]['total'], True)} in official sales in {_yr(top[1])}, according to {top[0]['data_source']['name']}."),
           ("Which states are the biggest cannabis markets?", "By latest official full-year sales: " + "; ".join(f"{i}. {h['state']} ({H.money(r['total'], True)}, {_yr(r)})" for i, (h, r, _) in enumerate(ranked[:5], 1)) + "."),
           ("Why are some states missing from the ranking?", "We rank only official full-year totals. " + " ".join(f"{h['state']} {why}." for h, why in skipped) if skipped else "")]
    f_html, f_ld = _faq(faq)
    crumbs = [("MetaFlora News", "/"), ("Cannabis data", "/data/"), ("Sales ranking", url)]
    body = f"""
<article class="story hub hub-wide">
  <header class="story-head">{H.crumbs_html(crumbs)}<h1>Cannabis sales by state: the biggest legal markets, ranked</h1>
  <p class="dek hub-answer">{escape(lead)}</p>
  <p class="hub-by"><span>MetaFlora Cannabis Data</span> · Last verified <time datetime="{latest}">{H.fmt_date(latest)}</time> · <a href="data.csv" download>Download CSV</a> · <a href="/data/">Monthly data by state</a></p></header>
  <div class="table-wrap"><table class="tracker bys-t"><thead><tr><th>Rank</th><th>State</th><th>Sales</th><th>Year</th><th>vs prior year</th><th>Basis</th><th>Source</th><th>Verified</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
  <div class="story-col">
    <section class="hub-sec"><h2>How to read this ranking</h2>
    <p class="hub-note">Each figure is the latest full-year total published by the state (or summed from its official monthly or quarterly reports), as shown on that state's sales page. Years differ: some states report fiscal years (July to June), Ohio reports 52-week periods, and a few have not yet published 2025 in full. Year-on-year change is shown only when the prior year comes from the same official basis. Some totals include medical sales or other items; the Basis column and each state page say exactly what is counted. Figures are not adjusted for inflation or population.</p>
    {f'<p class="hub-note">Not ranked:</p><ul class="hub-note">{sk}</ul>' if sk else ""}</section>
    {f_html}
    {siblings_html("sales")}
  </div>
</article>"""
    ds = {"@context": "https://schema.org", "@type": "Dataset", "name": "Cannabis sales by US state, ranked (MetaFlora Cannabis Data)", "description": desc,
          "url": SITE + url, "dateModified": latest, "license": "https://creativecommons.org/licenses/by/4.0/", "creator": T.PUBLISHER,
          "isAccessibleForFree": True, "spatialCoverage": {"@type": "Country", "name": "United States"}, "variableMeasured": "Annual legal cannabis sales (USD)",
          "isBasedOn": [h["data_source"]["url"] for h, _, _ in ranked],
          "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": SITE + url + "data.csv"}]}
    il = {"@context": "https://schema.org", "@type": "ItemList", "name": "Largest legal cannabis markets by state", "itemListOrder": "https://schema.org/ItemListOrderDescending",
          "numberOfItems": len(ranked), "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": SITE + h["_url"], "name": h["state"]} for i, (h, _, _) in enumerate(ranked)]}
    T.ctx["write"](url.strip("/") + "/index.html", T.page(title, body, desc=desc, path=url, active="Laws", extra_head=_ld(ds, il, H.crumbs_ld(crumbs), f_ld)))
    return {"url": url, "rows": len(ranked), "sourced": len(ranked), "pct": 1.0, "indexable": True, "latest": latest, "skipped": [h["state"] for h, _ in skipped]}


def index_page(results, sales):
    url = INDEX_URL
    cards = "".join(
        f'<a class="legal-card" href="{r["url"]}"><span class="lc-k">By state</span><b>{escape(r["topic"]["h1"])}</b>'
        f'<span>{escape(r["topic"]["blurb"])} {r["sourced"]} of {r["rows"]} rows sourced.</span></a>' for r in results)
    if sales:
        cards += (f'<a class="legal-card" href="{sales["url"]}"><span class="lc-k">Data</span><b>Cannabis sales by state, ranked</b>'
                  f'<span>{sales["rows"]} states by latest official full-year sales.</span></a>')
    latest = max([r["latest"] for r in results] + ([sales["latest"]] if sales else []))
    title = _title_ok(f"Cannabis laws by state: topic tables ({Y})")
    desc = _desc_ok("Cannabis laws by state, one topic at a time: possession limits, home grow, hemp THC, public use, DUI and tourist rules, each sourced.")
    crumbs = [("MetaFlora News", "/"), ("Cannabis laws", "/legal/"), ("United States", "/legal/us/"), ("By state", url)]
    body = f"""<article class="story hub hub-wide">
  <header class="story-head">{H.crumbs_html(crumbs)}<h1>Cannabis laws by state, topic by topic</h1>
  <p class="dek hub-answer">One table per question, built from the sourced facts on our {len(_states())} state pages: every row links to its state, its official source and the date we last checked it.</p>
  <p class="hub-by"><span>MetaFlora Legalization Tracker</span> · Last verified <time datetime="{latest}">{H.fmt_date(latest)}</time> · <a href="/legal/us/">Legal status in every state</a></p></header>
  <div class="legal-grid">{cards}</div>
</article>"""
    pages = [(r["topic"]["h1"], r["url"]) for r in results] + ([("Cannabis sales by state, ranked", sales["url"])] if sales else [])
    cp = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": SITE + url, "dateModified": latest,
          "mainEntity": {"@type": "ItemList", "numberOfItems": len(pages), "itemListElement": [
              {"@type": "ListItem", "position": i + 1, "url": SITE + u, "name": n} for i, (n, u) in enumerate(pages)]}}
    T.ctx["write"](url.strip("/") + "/index.html", T.page(title, body, desc=desc, path=url, active="Laws", extra_head=_ld(cp, H.crumbs_ld(crumbs))))
    return latest


REPORT = []


def build(arts):
    """Write every by-state page. Returns [(url, lastmod)] for indexable pages (for the sitemap)."""
    if not H.HUBS:
        H.load()
    if not _states():
        return []
    results = [topic_page(t, arts) for t in TOPICS]
    sales = sales_page()
    REPORT[:] = results + ([sales] if sales else [])
    urls = [(r["url"], r["latest"]) for r in REPORT if r["indexable"]]
    urls.append((INDEX_URL, index_page(results, sales)))
    for r in REPORT:
        flag = "" if r["indexable"] else "  NOINDEX (<80% sourced)"
        print(f"by-state: {r['url']}: {r['sourced']}/{r['rows']} rows sourced ({round(100 * r['pct'])}%){flag}")
    return urls
