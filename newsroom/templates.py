"""Page templates for MetaFlora News (editorial design: Newsreader + Inter Tight, hairline rules, no boxes)."""
import json
from datetime import datetime
from html import escape
from urllib.parse import quote

from covers import plate_svg

SITE = "https://news.metaflora.xyz"
NAME = "MetaFlora News"
TAGLINE = "Cannabis industry news: policy, markets, science and the business of cannabis. Morning and evening editions."
CATS = ["Policy", "Federal", "Hemp", "Markets", "Europe", "States", "Science", "Tech"]
X_HANDLE = "MetaFloraLabs"
X_URL = "https://x.com/MetaFloraLabs"
SOCIAL = [("x", X_URL, "X"), ("telegram", "https://t.me/MetaFloraLabs", "Telegram"),
          ("discord", "https://discord.com/invite/BvsTfQZNzn", "Discord"), ("medium", "https://meta-flora.medium.com/", "Medium"),
          ("youtube", "https://www.youtube.com/@metafloralabs", "YouTube")]
WORDMARK = ('<a class="wordmark" href="/" aria-label="MetaFlora News home">'
            '<img src="/assets/metaflora-white-logo-no-icon.png" alt="MetaFlora" width="218" height="65"><span>NEWS</span></a>')

ctx = {"market": None, "photo_path": lambda a: None, "write": None, "out": None, "edition_label": None}

FONTS = ("https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400"
         "&family=Inter+Tight:wght@500;600;700&family=JetBrains+Mono:wght@500&display=swap")

COPY_JS = ("<script>document.querySelectorAll('[data-copy]').forEach(function(b){b.addEventListener('click',function(){"
           "try{navigator.clipboard.writeText(b.dataset.copy).then(function(){b.textContent='Link copied'},function(){})}catch(e){}})});</script>")


def page(title, body, desc=TAGLINE, path="/", og_image=None, kind="website", extra_head="", active=None, dateline=""):
    full = f"{title} · {NAME}" if title != NAME else f"{NAME} · Cannabis industry news"
    img = og_image or f"{SITE}/assets/og-default.png"
    nav = "".join(f'<a href="/section/{c.lower()}/"{" aria-current=page" if c == active else ""}>{c}</a>' for c in CATS)
    social = "".join(f'<a href="{u}" target="_blank" rel="noopener" aria-label="{n}"><img src="/assets/{i}.png" alt=""></a>' for i, u, n in SOCIAL)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{escape(full)}</title>
<meta name="description" content="{escape(desc)}">
<link rel="canonical" href="{SITE}{path}">
<meta property="og:site_name" content="{NAME}">
<meta property="og:type" content="{kind}">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:url" content="{SITE}{path}">
<meta property="og:image" content="{img}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@{X_HANDLE}">
<meta name="twitter:title" content="{escape(title)}">
<meta name="twitter:description" content="{escape(desc)}">
<meta name="twitter:image" content="{img}">
<meta name="theme-color" content="#131313">
<link rel="icon" href="/assets/metaflora-white-logo-just-icon.png" type="image/png">
<link rel="alternate" type="application/rss+xml" title="{NAME}" href="/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="/assets/site.css">
{extra_head}
</head>
<body>
<header class="masthead">
  <div class="wrap mast-row">
    <span class="mast-date">{dateline}</span>
    {WORDMARK}
    <span class="mast-cta"><a class="btn-outline" href="{X_URL}" target="_blank" rel="noopener" aria-label="Follow MetaFlora News on X"><img src="/assets/x.png" alt=""><span>Follow</span></a></span>
  </div>
  <nav class="nav" aria-label="Sections"><div class="wrap nav-row">{nav}</div></nav>
</header>
<main class="wrap">
{body}
</main>
<footer class="foot"><div class="wrap">
  <div class="foot-top">
    {WORDMARK}
    <nav class="foot-links" aria-label="About MetaFlora News">
      <a href="/how-we-report/">How we report</a><a href="/how-we-report/#corrections">Corrections</a><a href="/advertise/">Advertise</a>
      <a href="/archive/">Archive</a><a href="/feed.xml">RSS</a><a href="https://metaflora.xyz">MetaFlora</a>
    </nav>
  </div>
  <div class="foot-bottom">
    <p>MetaFlora News is published by MetaFlora and produced by an AI newsroom from named public sources. News and commentary only; not legal, medical or financial advice.</p>
    <div class="social">{social}</div>
  </div>
</div></footer>
{COPY_JS}
</body>
</html>
"""


# ---------- pieces ----------

def has_photo(a):
    return bool(ctx["photo_path"](a))


def image(a, eager=False, plate=True):
    """Clean lead image, never with text: the AI photo when there is one, else (optionally) the typographic plate."""
    if has_photo(a):
        lazy = "" if eager else ' loading="lazy"'
        return f'<img src="/img/{a["id"]}.jpg" width="1600" height="1067" alt="{escape(a.get("image_alt") or "")}"{lazy}>'
    return plate_svg(a) if plate else ""


def caption(a):
    return f'{escape(a.get("image_alt") or "")} <span class="credit">Photo illustration: AI-generated</span>'


def kicker(cat):
    return f'<a class="kicker" href="/section/{cat.lower()}/">{escape(cat)}</a>'


def minutes(a):
    return max(2, round(sum(len(x.split()) for x in a["body"]) / 230))


def t_long(a):
    return f"{a['_dt']:%-d %b %Y}, {a['_dt']:%H:%M} EET"


def card(a, kind="std", img=True):
    cls = "pic" if has_photo(a) else "pic plate"
    pic = f'<a class="{cls}" href="{a["_path"]}" tabindex="-1" aria-hidden="true">{image(a)}</a>' if img else ""
    return (f'<article class="card card-{kind}">{pic}<div class="card-txt">{kicker(a["cat"])}'
            f'<h3><a href="{a["_path"]}">{escape(a["headline"])}</a></h3>'
            f'<p class="dek">{escape(a["dek"])}</p><p class="meta">{minutes(a)} min read</p></div></article>')


def ed_short(a):
    return f'{a["_dt"]:%-d %b} · {"Morning" if a["edition"].endswith("am") else "Evening"}'


def list_item(a, with_time=True):
    t = f'<time>{ed_short(a)}</time>' if with_time else ""
    return f'<li>{t}{kicker(a["cat"])}<a class="li-title" href="{a["_path"]}">{escape(a["headline"])}</a></li>'


def market_strip():
    m = ctx["market"]
    if not m:
        return ""
    cells = "".join(
        f'<li><span class="sym">{r["sym"]}</span><span class="px">{r["price"]:.2f}</span>'
        f'<span class="chg {"up" if r["chg"] >= 0 else "down"}">{r["chg"]:+.1f}%</span></li>' for r in m["rows"])
    asof = f'{m["asof"]:%-d %b}'
    return (f'<section class="market" aria-label="Cannabis stocks"><span class="mk-label">Cannabis stocks · close {asof} · delayed</span>'
            f'<ul>{cells}</ul></section>')


def watch_items(arts, today):
    seen, out = set(), []
    for a in arts:
        for w in a.get("watch", []):
            if w["date"] >= today and w["text"] not in seen:
                seen.add(w["text"])
                out.append((w["date"], w["text"], a))
    return sorted(out, key=lambda x: x[0])[:5]


def dateline_for(ed, latest):
    d, half = ed.rsplit("-", 1)
    dt = datetime.fromisoformat(d)
    pub = max(a["_dt"] for a in latest)
    return f'{dt:%A} {dt.day} {dt:%B %Y} · {"Morning" if half == "am" else "Evening"} Edition · {pub:%H:%M} EET'


# ---------- pages ----------

def front_ad():
    import ads
    inv = ads.load()
    return ads.render(ads.pick(inv, "front", datetime.now().strftime("%Y%m%d"), placement="front"), "band")


def build_front(arts, eds):
    latest_ed, latest = next(iter(eds.items()))
    lead = latest[0]
    left = latest[1:4]
    shown = {a["id"] for a in [lead, *left]}
    latest_rail = [a for a in arts if a["id"] not in shown][:6]
    shown |= {a["id"] for a in latest_rail}
    more = [a for a in arts if a["id"] not in shown]
    watch = watch_items(arts[:24], datetime.now().date().isoformat())
    reel = f"reels/{latest_ed}.mp4"
    has_reel = (ctx["out"] / reel).exists()

    parts = [market_strip()]
    parts.append(f"""<section class="front-top">
  <div class="col-left">{''.join(card(a, 'side', img=False) for a in left)}</div>
  <article class="lead">
    <a class="{'pic' if has_photo(lead) else 'pic plate'}" href="{lead['_path']}" tabindex="-1" aria-hidden="true">{image(lead, eager=True)}</a>
    {kicker(lead['cat'])}
    <h1><a href="{lead['_path']}">{escape(lead['headline'])}</a></h1>
    <p class="dek">{escape(lead['dek'])}</p>
    <p class="meta">By MetaFlora News Desk · {minutes(lead)} min read</p>
  </article>
  <aside class="col-right"><h2 class="rail-h">Latest</h2><ol class="rail">{''.join(list_item(a) for a in latest_rail)}</ol></aside>
</section>""")
    if watch:
        rows = "".join(f'<li><time>{datetime.fromisoformat(d):%-d %b}</time><a href="{a["_path"]}">{escape(t)}</a></li>' for d, t, a in watch)
        parts.append(f'<section class="watch"><h2 class="sec-label">What to watch</h2><ol>{rows}</ol></section>')
    now = datetime.now(arts[0]["_dt"].tzinfo)
    week = [a for a in arts if (now - a["_dt"]).days < 7 and a["id"] not in shown]
    for c in ["Markets", "Policy", "Federal", "States", "Science", "Europe", "Hemp", "Tech"]:
        items = [a for a in week if a["cat"] == c]
        if len(items) >= 3:
            shown |= {a["id"] for a in items[:5]}
            parts.append(f'<section class="desk"><h2 class="sec-label"><a href="/section/{c.lower()}/">{c}</a></h2>'
                         f'<div class="desk-row">{card(items[0], "wide")}<ol class="desk-list">{"".join(list_item(a, False) for a in items[1:5])}</ol></div></section>')
    more = [a for a in more if a["id"] not in shown]
    if more:
        parts.append(f'<section class="block"><h2 class="sec-label">More news</h2><div class="grid4">{"".join(card(a) for a in more[:8])}</div></section>')
    parts.append(front_ad())
    if has_reel:
        half = "morning" if latest_ed.endswith("am") else "evening"
        parts.append(f'''<section class="briefing"><h2 class="sec-label">Video briefing</h2>
<div class="brief-row"><video src="/{reel}" poster="/reels/{latest_ed}-poster.jpg" controls muted playsinline preload="none"></video>
<div><p class="brief-t">The {half} edition in {len(latest)} headlines.</p>
<p class="meta">Each edition is also posted to <a href="{X_URL}" target="_blank" rel="noopener">@{X_HANDLE}</a> on X.</p></div></div></section>''')
    parts.append(f'<section class="block"><h2 class="sec-label">All stories</h2><ol class="latest-list">{"".join(list_item(a) for a in arts[:15])}</ol>'
                 f'<p class="more-link"><a href="/archive/">Full archive</a></p></section>')
    ctx["write"]("index.html", page(NAME, "".join(parts), og_image=f"{SITE}/og/{lead['id']}.png", dateline=dateline_for(latest_ed, latest)))


AD_INV = None


def render_body(a):
    """Paragraphs, '## ' subheads, '> ' pull quotes. At most one ad per ~600 words, never before
    paragraph 4, always just before a subhead, never in the final sections."""
    import ads
    global AD_INV
    if AD_INV is None:
        AD_INV = ads.load()
    blocks = a["body"]
    words = sum(len(b.split()) for b in blocks)
    budget = max(1, words // 600) if words >= 450 else 0
    out, paras, since, used, slot = [], 0, 0, [], 0
    for i, b in enumerate(blocks):
        is_head = b.startswith("## ")
        if budget and is_head and paras >= 4 and since >= 280 and i < len(blocks) - 3:
            ad = ads.pick(AD_INV, a["id"], slot, a["cat"], exclude=used, placement="article")
            if ad:
                out.append(ads.render(ad))
                used.append(ad["id"])
                slot += 1
                budget -= 1
                since = 0
        if is_head:
            out.append(f"<h2>{escape(b[3:])}</h2>")
        elif b.startswith("> "):
            out.append(f'<blockquote class="pull">{escape(b[2:])}</blockquote>')
        else:
            out.append(f"<p>{escape(b)}</p>")
            paras += 1
            since += len(b.split())
    return "".join(out)


def build_article(a, arts):
    same = [x for x in arts if x["id"] != a["id"] and x["cat"] == a["cat"]][:3]
    latest = [x for x in arts if x["id"] != a["id"] and x not in same][:5]
    kp = ""
    if a.get("key_points"):
        v = a.get("visual") or {}
        stat = f'<p class="kp-stat"><b>{escape(str(v.get("big", "")))}</b><span>{escape(str(v.get("label", "")))}</span></p>' if v.get("big") else ""
        kp = '<aside class="keypoints"><h2>Key points</h2>' + stat + '<ul>' + "".join(f"<li>{escape(k)}</li>" for k in a["key_points"]) + "</ul></aside>"
    srcs = "".join(f'<li><a href="{escape(s["url"])}" rel="noopener" target="_blank">{escape(s["name"])}</a>'
                   f'{(" · " + escape(s["title"])) if s.get("title") else ""}{(" · " + escape(s["date"])) if s.get("date") else ""}</li>'
                   for s in a["sources"])
    corr = ""
    if a.get("corrections"):
        corr = '<aside class="corrections">' + "".join(f'<p><b>Correction, {escape(c["date"])}:</b> {escape(c["text"])}</p>' for c in a["corrections"]) + "</aside>"
    url = SITE + a["_path"]
    share = (f'<a href="https://x.com/intent/post?text={quote(a["headline"])}&url={quote(url)}&via={X_HANDLE}" target="_blank" rel="noopener">Post on X</a>'
             f'<a href="https://www.linkedin.com/sharing/share-offsite/?url={quote(url)}" target="_blank" rel="noopener">LinkedIn</a>'
             f'<button type="button" data-copy="{escape(url)}">Copy link</button>')
    updated = ""
    if a.get("updated"):
        updated = f' · Updated {datetime.fromisoformat(a["updated"]):%-d %b, %H:%M} EET'
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": a["headline"], "description": a["dek"],
          "datePublished": a["published"], "dateModified": a.get("updated", a["published"]), "image": [f"{SITE}/og/{a['id']}.png"],
          "author": {"@type": "Organization", "name": "MetaFlora News Desk", "url": f"{SITE}/how-we-report/"},
          "publisher": {"@type": "Organization", "name": NAME}, "mainEntityOfPage": url}
    fig = ""
    if has_photo(a):
        fig = f'<figure class="story-fig">{image(a, eager=True)}<figcaption>{caption(a)}</figcaption></figure>'
    after_same = ""
    if len(same) >= 2:
        after_same = f'<div><h2 class="sec-label">More on {escape(a["cat"])}</h2><ol class="latest-list">{"".join(list_item(x) for x in same)}</ol></div>'
    body = f"""
<article class="story">
  <header class="story-head">
    {kicker(a['cat'])}
    <h1>{escape(a['headline'])}</h1>
    <p class="dek">{escape(a['dek'])}</p>
    <div class="byline">
      <p><span class="by">By <a href="/how-we-report/">MetaFlora News Desk</a></span> · <time datetime="{a['published']}">{t_long(a)}</time>{updated} · <span class="nowrap">{minutes(a)} min read</span></p>
      <p class="share">{share}</p>
    </div>
    <p class="disclosure">Produced by MetaFlora's AI newsroom from the sources listed at the end of this article. <a href="/how-we-report/">How we report</a></p>
  </header>
  {fig}
  <div class="story-col">
    {kp}
    <div class="story-body">{render_body(a)}</div>
    <section class="sources"><h2>Sources</h2><ol>{srcs}</ol>
      <p>This article summarises and links the original reporting. Spotted an error? Message <a href="{X_URL}" target="_blank" rel="noopener">@{X_HANDLE}</a> on X.</p></section>
    {corr}
  </div>
</article>
<section class="after{'' if after_same else ' after-one'}">
  {after_same}
  <div><h2 class="sec-label">Latest</h2><ol class="latest-list">{''.join(list_item(x) for x in latest)}</ol></div>
</section>
"""
    extra = f'<script type="application/ld+json">{json.dumps(ld)}</script>'
    ctx["write"](a["_path"].strip("/") + "/index.html",
                 page(a["headline"], body, desc=a["dek"], path=a["_path"], og_image=f"{SITE}/og/{a['id']}.png", kind="article",
                      extra_head=extra, active=a["cat"], dateline=f'{a["_dt"]:%A} {a["_dt"].day} {a["_dt"]:%B %Y}'))


def build_sections(arts):
    for c in CATS:
        items = [a for a in arts if a["cat"] == c]
        if items:
            inner = f'<div class="sec-lead">{card(items[0], "wide")}</div><div class="grid4">{"".join(card(a) for a in items[1:13])}</div>'
            if len(items) > 13:
                inner += f'<ol class="latest-list">{"".join(list_item(a) for a in items[13:40])}</ol>'
        else:
            inner = '<p class="empty">No stories in this section yet. New editions publish every morning and evening.</p>'
        body = f'<div class="page-h"><h1>{c}</h1><p class="meta">{len(items)} stories</p></div>{inner}'
        ctx["write"](f"section/{c.lower()}/index.html", page(c, body, path=f"/section/{c.lower()}/", active=c))


def build_archive(eds):
    blocks = "".join(f'<section class="block"><h2 class="sec-label">{escape(ctx["edition_label"](ed))}</h2>'
                     f'<ol class="latest-list">{"".join(list_item(a) for a in items)}</ol></section>' for ed, items in eds.items())
    body = f'<div class="page-h"><h1>Archive</h1><p class="meta">{len(eds)} editions</p></div>{blocks}'
    ctx["write"]("archive/index.html", page("Archive", body, path="/archive/"))


def build_how():
    body = f"""<article class="story static">
<header class="story-head"><h1>How we report</h1><p class="dek">MetaFlora News is produced by an AI newsroom. This page explains what that means and how we hold it to account.</p></header>
<div class="story-col"><div class="story-body">
<h2>How a story is made</h2>
<p>Twice a day our system reviews reporting from named outlets, regulators and public records. It writes original summaries in MetaFlora's own words and links every source it used at the end of each article.</p>
<h2>Our rules</h2>
<p>We do not publish anonymous claims, invent quotes or report a fact we cannot attribute to a source. Figures come from the sources we link. Images marked "Photo illustration: AI-generated" are created for illustration and never depict real, identifiable people.</p>
<h2 id="corrections">Corrections</h2>
<p>When we get something wrong we fix it and add a dated correction note to the article. To report an error, message <a href="{X_URL}" target="_blank" rel="noopener">@{X_HANDLE}</a> on X with the article link.</p>
<h2>Advertising</h2>
<p>Advertising is always labelled and kept separate from reporting. Advertisers have no say over what we cover. See <a href="/advertise/">Advertise</a>.</p>
<h2>Not advice</h2>
<p>MetaFlora News is news and commentary. Nothing here is legal, medical or financial advice.</p>
</div></div></article>"""
    ctx["write"]("how-we-report/index.html", page("How we report", body, path="/how-we-report/"))


def build_advertise():
    import ads
    inv = ads.load()
    contact = inv.get("advertise_contact", "https://metaflora.xyz")
    sample = ads.render(next((x for x in inv["ads"] if x["id"] == "home-grow-node"), None), "article")
    body = f"""<article class="story static">
<header class="story-head"><h1>Advertise</h1><p class="dek">MetaFlora News publishes a morning and an evening edition every day for cannabis operators, investors and connoisseurs, and posts every lead story to X.</p></header>
<div class="story-col"><div class="story-body">
<h2>Placements</h2>
<p><b>Article break.</b> One clearly labelled unit inside long-form stories, placed between sections. Can target a section such as Markets or Science.</p>
<p><b>Front page.</b> The labelled unit on the front page, seen by every homepage visitor.</p>
<p><b>Sponsored edition.</b> The front page unit plus every article break in one morning or evening edition.</p>
<h2>What it looks like</h2></div>
{sample}
<p class="adv-cta"><a class="btn" href="{escape(contact)}" target="_blank" rel="noopener">Become a partner</a></p>
<p class="meta">Tell us your brand, dates and target sections. We will come back with availability and rates.</p>
</div></article>"""
    ctx["write"]("advertise/index.html", page("Advertise", body, path="/advertise/"))
