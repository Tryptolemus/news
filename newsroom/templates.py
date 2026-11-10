"""Page templates for MetaFlora News (editorial design: Newsreader + Inter Tight, hairline rules, no boxes)."""
import json
import re
from datetime import datetime
import hashlib
from html import escape
from pathlib import Path
from urllib.parse import quote

from covers import plate_svg
import notify_site

# Content hash of the stylesheet: the link changes whenever the CSS does, so browsers never mix new pages with old styles.
CSS_VERSION = hashlib.sha256((Path(__file__).parent / "site.css").read_bytes()).hexdigest()[:10]

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
            '<span class="wm-top"><img src="/assets/metaflora-cube-mark-92.png" alt="" width="85" height="92">'
            '<span class="wm-text">METAFLORA</span></span><span class="wm-news">NEWS</span></a>')

LOGO = f"{SITE}/assets/metaflora-news-logo.png"
ORG = {"@type": "NewsMediaOrganization", "@id": f"{SITE}/#org", "name": NAME, "url": SITE + "/",
       "logo": {"@type": "ImageObject", "url": LOGO, "width": 512, "height": 512},
       "email": "support@metaflora.xyz",
       "parentOrganization": {"@type": "Organization", "name": "MetaFlora", "url": "https://metaflora.xyz"},
       "sameAs": [X_URL, "https://t.me/MetaFloraLabs", "https://www.youtube.com/@metafloralabs", "https://meta-flora.medium.com/"],
       "publishingPrinciples": f"{SITE}/how-we-report/", "correctionsPolicy": f"{SITE}/corrections/", "masthead": f"{SITE}/about/",
       "verificationFactCheckingPolicy": f"{SITE}/how-we-report/#checks",
       "ownershipFundingInfo": f"{SITE}/how-we-report/#ownership", "actionableFeedbackPolicy": f"{SITE}/how-we-report/#contact"}
PUBLISHER = {"@type": "NewsMediaOrganization", "@id": f"{SITE}/#org", "name": NAME,
             "logo": {"@type": "ImageObject", "url": LOGO, "width": 512, "height": 512}}
ROBOTS = "max-image-preview:large, max-snippet:-1, max-video-preview:-1"
# one entity = one tag: variants found in content map to the canonical hub name
TAG_ALIASES = {"Green Thumb Industries": "Green Thumb", "Verano Holdings": "Verano", "Tilray Brands": "Tilray",
               "Canopy": "Canopy Growth", "Aurora": "Aurora Cannabis", "Curaleaf Holdings": "Curaleaf",
               "Drug Enforcement Administration": "DEA", "280E": "Section 280E"}
SECTION_DESC = {
    "Policy": "Cannabis policy news: legalization votes, ballot measures, regulation and the politics of cannabis.",
    "Federal": "Federal cannabis news: DEA rescheduling, Congress, banking, Section 280E and federal enforcement.",
    "Hemp": "Hemp and hemp-derived THC news: federal and state rules, testing limits and the hemp market.",
    "Markets": "Cannabis business and markets news: earnings, deals, cannabis stocks and the companies behind them.",
    "Europe": "European cannabis news: Germany, the Czech Republic, medical cannabis markets and court rulings.",
    "States": "State cannabis news: licensing, new markets, rules and enforcement across the United States.",
    "Science": "Cannabis science news: clinical research, health studies and what the evidence says.",
    "Tech": "Cannabis technology news: software, payments, tracking and the tools the industry runs on.",
}

ctx = {"market": None, "photo_path": lambda a: None, "write": None, "out": None, "edition_label": None}

# Self-hosted WOFF2 subsets (newsroom/webfonts.py; @font-face at the top of site.css). Preload the faces every page
# paints above the fold: Newsreader (H1 + body text: the LCP element on articles), Inter Tight (nav) and the wordmark.
FONT_PRELOAD = "".join(f'<link rel="preload" href="/assets/fonts/{f}.woff2" as="font" type="font/woff2" crossorigin>'
                       for f in ("newsreader", "inter-tight", "casanova-scotia"))
# True Newsreader italic (pull quotes, glossary examples) from Google Fonts, loaded without blocking render:
# the roman, sans and wordmark faces are self-hosted above.
FONT_PRELOAD += ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@1,6..72,400&amp;display=swap" '
                 '''media="print" onload="this.media='all'">''')

_ABBR = re.compile(r"(?:\b(?:[A-Z]\.){1,3}|\b(?:Mr|Mrs|Ms|Dr|St|Jr|Sr|vs|No|Inc|Corp|Co|Ltd|Gov|Sen|Rep|approx|est|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.)$")


def meta_desc(text, limit=155):
    """Meta description that ends on a whole sentence: the longest run of full sentences within `limit` characters.
    If the first sentence alone is too long, cut at the last clause break (; – , → full stop), else at the last whole
    word (→ "…"); never mid-word."""
    text = " ".join(str(text).split())
    clipped = text.endswith(("…", "...")) and len(text) > 60   # arrived pre-cut by a caller: drop the broken tail
    if len(text) <= limit and not clipped:
        return text
    head = text.rstrip(".…") + " " if clipped else text[:limit + 1]
    best = 0
    for m in re.finditer(r"""[.!?]['"’”)]?(?=\s)""", head):
        end = m.end()
        if end <= limit and not _ABBR.search(text[:end]):
            best = end
    if best >= 70:   # under ~70 characters a snippet is too thin: prefer a longer clause cut
        return text[:best]
    if clipped and len(text) <= limit:
        return text
    cut = text[:limit]
    for brk in ("; ", " – ", " — ", ", "):
        i = cut.rfind(brk)
        if i >= 70:
            return cut[:i].rstrip(" ,;:–—-") + "."
    return cut[:limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:–—-(") + "…"

COPY_JS = ("<script>document.querySelectorAll('[data-copy]').forEach(function(b){b.addEventListener('click',function(){"
           "try{navigator.clipboard.writeText(b.dataset.copy).then(function(){b.textContent='Link copied'},function(){})}catch(e){}})});</script>")


def page(title, body, desc=TAGLINE, path="/", og_image=None, kind="website", extra_head="", active=None, dateline="", robots=ROBOTS,
         canonical=True, feeds=()):
    """canonical=False omits <link rel=canonical> (404 page). feeds: extra (title, url) RSS feeds to advertise, e.g. a section feed."""
    # brand suffix only where it fits in ~60 characters of search-result title
    full = "Cannabis News Today: Policy, Markets, Hemp & Laws · MetaFlora News" if title == NAME else (f"{title} · {NAME}" if len(title) <= 44 else title)
    # never cut the <title>: Google truncates by pixel width anyway, and a build-time cut only loses ranking words
    desc = meta_desc(desc)
    if "application/ld+json" not in extra_head and "noindex" not in robots:
        extra_head += '<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@type": "WebPage", "name": title, "description": desc,
                                                                          "url": SITE + path, "isPartOf": {"@type": "WebSite", "@id": f"{SITE}/#website", "name": NAME, "url": SITE + "/"},
                                                                          "publisher": PUBLISHER}) + "</script>"
    img = og_image or f"{SITE}/assets/og-default.png"
    nav = "".join(f'<a href="/section/{c.lower()}/"{" aria-current=page" if c == active else ""}>{c}</a>' for c in CATS)
    nav += f'<a href="/stocks/"{" aria-current=page" if active == "Stocks" else ""}>Stocks</a>'
    nav += f'<a href="/company/"{" aria-current=page" if active == "Companies" else ""}>Companies</a>'
    nav += f'<a href="/legal/"{" aria-current=page" if active == "Laws" else ""}>Laws</a>'
    social = "".join(f'<a href="{u}" target="_blank" rel="noopener" aria-label="{n}"><img src="/assets/{i}.png" alt="" width="47" height="44"></a>' for i, u, n in SOCIAL)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{escape(full)}</title>
<meta name="description" content="{escape(desc)}">
<meta name="robots" content="{robots}">
{f'<link rel="canonical" href="{SITE}{path}">' + chr(10) if canonical else ""}<meta property="og:site_name" content="{NAME}">
<meta property="og:locale" content="en_US">
<meta property="og:type" content="{kind}">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:url" content="{SITE}{path}">
<meta property="og:image" content="{img}">
<meta property="og:image:secure_url" content="{img}">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{escape(title)} · MetaFlora News">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@{X_HANDLE}">
<meta name="twitter:title" content="{escape(title)}">
<meta name="twitter:description" content="{escape(desc)}">
<meta name="twitter:image" content="{img}">
<meta name="twitter:image:alt" content="{escape(title)} · MetaFlora News">
<meta name="theme-color" content="#131313">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/assets/icons/icon-192.png" type="image/png" sizes="192x192">
<link rel="alternate" type="application/rss+xml" title="{NAME}" href="/feed.xml">
{"".join(f'<link rel="alternate" type="application/rss+xml" title="{escape(t)}" href="{u}">' + chr(10) for t, u in feeds)}{FONT_PRELOAD}
<link rel="stylesheet" href="/assets/site.css?v={CSS_VERSION}">
{notify_site.head_tags(CSS_VERSION)}
{extra_head}
</head>
<body>
<header class="masthead">
  <div class="wrap mast-row">
    <span class="mast-date">{dateline}</span>
    {WORDMARK}
    <span class="mast-cta">{notify_site.app_button()}{notify_site.bell()}<a class="btn-outline" href="{X_URL}" target="_blank" rel="noopener" aria-label="Follow MetaFlora News on X"><img src="/assets/x.png" alt="" width="47" height="44"><span>Follow</span></a></span>
  </div>
  <nav class="nav" aria-label="Sections"><div class="wrap nav-row">{nav}</div></nav>
</header>
<main class="wrap">
{body}
</main>
<footer class="foot"><div class="wrap">
  <section class="node-cta" aria-labelledby="node-cta-h">
    <img src="/assets/metaflora-cube-128.png" alt="" width="128" height="138" loading="lazy" decoding="async">
    <div class="node-copy">
      <p class="node-k">The MetaFlora node network</p>
      <h2 id="node-cta-h">Help decentralize MetaFlora.</h2>
      <p>Run a MetaFlora node and help power FloraChain, the network behind MetaFlora's data and transactions. Nodes for home growers, connoisseurs and industry.</p>
    </div>
    <div class="node-act">
      <a class="mfn-primary node-btn" href="https://metaflora.xyz/?pricing=true&amp;utm_source=metaflora-news&amp;utm_medium=footer&amp;utm_campaign=node" target="_blank" rel="noopener">Run a node</a>
      <a class="node-more" href="https://metaflora.xyz/?utm_source=metaflora-news&amp;utm_medium=footer&amp;utm_campaign=node#node" target="_blank" rel="noopener">Learn about the network &rarr;</a>
    </div>
  </section>
  <div class="foot-top">
    {WORDMARK}
    <nav class="foot-links" aria-label="About MetaFlora News">
      <a href="/about/">About</a><a href="/how-we-report/">How we report</a><a href="/corrections/">Corrections</a><a href="/advertise/">Advertise</a>
      <a href="/stocks/">Cannabis stocks</a><a href="/legal/us/">Cannabis laws by state</a><a href="/explainers/">Explainers</a><a href="/company/">Cannabis companies</a><a href="/data/">Cannabis sales data</a><a href="/legal/us/by-state/">Cannabis laws: state by state</a><a href="/glossary/">Cannabis glossary</a><button type="button" class="foot-app" data-app-open aria-haspopup="dialog" aria-expanded="false" aria-controls="mfa-panel">Get the app</button><a href="/archive/">Archive</a><a href="/topic/">Topics</a><a href="/feed.xml">RSS</a><a href="https://metaflora.xyz">MetaFlora</a>
    </nav>
  </div>
  <div class="foot-bottom">
    <p>MetaFlora News is published by MetaFlora and produced by an AI newsroom from named public sources. News and commentary only; not legal, medical or financial advice.</p>
    <div class="social">{social}</div>
  </div>
</div></footer>
{notify_site.app_ui()}
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
        return (f'<img src="/img/{a["id"]}.jpg" width="1600" height="900" alt="{escape(a.get("image_alt") or "")}"{lazy}>'
                '<span class="ph-mark" aria-hidden="true"></span>')
    return plate_svg(a) if plate else ""


# Key-figure plate lead images are OFF: Greg's design board rejected the plate look (6 Nov 2026, card A won 2-1)
# and he turned them down again on 8 Nov. Articles, JSON-LD and RSS use the editorial social card instead.
LEAD_IMAGES = False
LEAD_DIMS = {"16x9": (1600, 900), "4x3": (1200, 900), "1x1": (1200, 1200)}  # card.LEAD_SIZES


def lead(a):
    """The story's rendered lead images (card.render_lead, written by full builds into docs/img/) as {ratio: url},
    or None when they are not on disk (a fresh --no-media build), so no page ever points at a missing file."""
    if not LEAD_IMAGES:
        return None
    names = {r: f"{a['id']}-{r}.jpg" for r in list(LEAD_DIMS) + ["16x9-960"]}
    if not all((ctx["out"] / "img" / n).exists() for n in names.values()):
        return None
    return {r: f"/img/{n}" for r, n in names.items()}


def lead_figure(a):
    """16:9 lead graphic at the top of a story: the LCP element, so eager and fetchpriority=high, never lazy."""
    L = lead(a)
    if not L:
        return ""
    from card import lead_alt
    up = "../" * len(a["_path"].strip("/").split("/"))  # srcset is not rewritten by relativize(): write it page-relative
    v = a.get("visual") or {}
    return (f'<figure class="story-fig lead-fig"><img src="{L["16x9"]}" srcset="{up}{L["16x9-960"][1:]} 960w, {up}{L["16x9"][1:]} 1600w" '
            f'sizes="(max-width: 1080px) 100vw, 1040px" width="1600" height="900" fetchpriority="high" alt="{escape(lead_alt(a))}">'
            f'<figcaption>{escape(" ".join(x for x in (str(v.get("big") or ""), str(v.get("label") or "")) if x))} <span class="credit">MetaFlora News graphic</span></figcaption></figure>')


def lead_ld(a):
    """NewsArticle image: the 16:9, 4:3 and 1:1 lead images (Google's three ratios); the 1200x630 card when absent."""
    L = lead(a)
    if not L:
        return [{"@type": "ImageObject", "url": f"{SITE}/og/{a['id']}.png", "width": 1200, "height": 630}]
    return [{"@type": "ImageObject", "url": SITE + L[r], "width": w, "height": h} for r, (w, h) in LEAD_DIMS.items()]


def rss_image(a):
    """RSS media:content: the 16:9 lead image, else the social card."""
    L = lead(a)
    if L:
        return f'<media:content url="{SITE}{L["16x9"]}" medium="image" type="image/jpeg" width="1600" height="900"/>'
    return f'<media:content url="{SITE}/og/{a["id"]}.png" medium="image" type="image/png" width="1200" height="630"/>'


def caption(a):
    # credit only: the image prompt read as a low-quality description under the photo (Greg, 10 Nov 2026); it stays the alt text
    return '<span class="credit">Photo illustration: AI-generated · MetaFlora News</span>'


def kicker(cat):
    return f'<a class="kicker" href="/section/{cat.lower()}/">{escape(cat)}</a>'


def minutes(a):
    return max(2, round(sum(len(x.split()) for x in a["body"]) / 230))


def t_long(a):
    return f"{a['_dt'].day} {a['_dt']:%b %Y}, {a['_dt']:%H:%M} EET"


def card(a, kind="std", img=True):
    cls = "pic" if has_photo(a) else "pic plate"
    pic = f'<a class="{cls}" href="{a["_path"]}" tabindex="-1" aria-hidden="true">{image(a)}</a>' if img else ""
    return (f'<article class="card card-{kind}">{pic}<div class="card-txt">{kicker(a["cat"])}'
            f'<h3><a href="{a["_path"]}">{escape(a["headline"])}</a></h3>'
            f'<p class="dek">{escape(a["dek"])}</p><p class="meta">{minutes(a)} min read</p></div></article>')


def ed_short(a):
    return f'{a["_dt"].day} {a["_dt"]:%b} · {"Morning" if a["edition"].endswith("am") else "Evening"}'


def list_item(a, with_time=True):
    t = f'<time>{ed_short(a)}</time>' if with_time else ""
    return f'<li>{t}{kicker(a["cat"])}<a class="li-title" href="{a["_path"]}">{escape(a["headline"])}</a></li>'


def market_strip():
    m = ctx["market"]
    if not m:
        return ""
    def cells(hidden):
        tab = ' tabindex="-1"' if hidden else ""
        return "".join(
            f'<li><a href="/stocks/{r["sym"].lower()}/"{tab} title="{escape(r["full"])} stock: chart and news"><span class="sym">{r["sym"]}</span>'
            f'<span class="px">{r["price"]:.2f}</span><span class="chg {"up" if r["chg"] >= 0 else "down"}">{r["chg"]:+.1f}%</span></a></li>'
            for r in m["rows"])
    asof = f'{m["asof"].day} {m["asof"]:%b}'
    # endless tape: each run holds the list twice so it is always wider than the screen; the second run
    # is a visual copy (hidden from screen readers and the tab order) that makes the loop seamless
    run = cells(False) + cells(True)
    return (f'<section class="market" aria-label="Cannabis stocks"><a class="mk-label" href="/stocks/">Cannabis stocks · close {asof}</a>'
            f'<div class="mk-track"><ul class="mk-run">{run}</ul><ul class="mk-run" aria-hidden="true">{cells(True) + cells(True)}</ul></div></section>')


def watch_items(arts, today):
    seen, out = set(), []
    for a in arts:
        for w in a.get("watch", []):
            if w["date"] >= today and w["text"] not in seen:
                seen.add(w["text"])
                out.append((w["date"], w["text"], a))
    return sorted(out, key=lambda x: x[0])[:5]


def dl(top, sub=""):
    """Masthead dateline: a date line, and an optional small-caps line under it."""
    return f'<span class="dl-top">{escape(top)}</span><span class="dl-sub">{escape(sub)}</span>'


def dateline_for(ed, latest):
    d, half = ed.rsplit("-", 1)
    dt = datetime.fromisoformat(d)
    return dl(f"{dt:%A} {dt.day} {dt:%B %Y}", f'{"Morning" if half == "am" else "Evening"} edition')


# ---------- pages ----------

def front_ad():
    """The front page's single ad band: one slot that rotates through the house ads."""
    import ads
    return ads.slot("front" + datetime.now().strftime("%Y%m%d"), 0, "front")


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
    <h2 class="lead-h"><a href="{lead['_path']}">{escape(lead['headline'])}</a></h2>
    <p class="dek">{escape(lead['dek'])}</p>
    <p class="meta">By MetaFlora News Desk · {minutes(lead)} min read</p>
  </article>
  <aside class="col-right"><h2 class="rail-h">Latest</h2><ol class="rail">{''.join(list_item(a) for a in latest_rail)}</ol></aside>
</section>""")
    if watch:
        rows = "".join(f'<li><time>{datetime.fromisoformat(d).day} {datetime.fromisoformat(d):%b}</time><a href="{a["_path"]}">{escape(t)}</a></li>' for d, t, a in watch)
        parts.append(f'<section class="watch"><h2 class="sec-label">What to watch</h2><ol>{rows}</ol></section>')
    parts.append(front_ad())
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
    if has_reel:
        half = "morning" if latest_ed.endswith("am") else "evening"
        parts.append(f'''<section class="briefing"><h2 class="sec-label">Video briefing</h2>
<div class="brief-row"><video src="/{reel}" poster="/reels/{latest_ed}-poster.jpg" controls muted playsinline preload="none"></video>
<div><p class="brief-t">The {half} edition in {len(latest)} headlines.</p>
<p class="meta">Each edition is also posted to <a href="{X_URL}" target="_blank" rel="noopener">@{X_HANDLE}</a> on X.</p></div></div></section>''')
    parts.append(f'<section class="block"><h2 class="sec-label">All stories</h2><ol class="latest-list">{"".join(list_item(a) for a in arts[:15])}</ol>'
                 f'<p class="more-link"><a href="/archive/">Full archive</a></p></section>')
    org = {"@context": "https://schema.org", "@graph": [ORG, {"@type": "WebSite", "@id": f"{SITE}/#website", "name": NAME, "url": SITE + "/",
                                                            "description": TAGLINE, "publisher": {"@id": f"{SITE}/#org"}, "inLanguage": "en"}]}
    parts.insert(0, '<h1 class="sr-only">MetaFlora News: cannabis industry news, laws and markets</h1>')
    ctx["write"]("index.html", page(NAME, "".join(parts), og_image=f"{SITE}/og/{lead['id']}.png", dateline=dateline_for(latest_ed, latest),
                                    extra_head=f'<script type="application/ld+json">{json.dumps(org)}</script>'))


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
                out.append(ads.rotate(a["id"], slot, "article", a["cat"]))
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
    import hubs
    return "".join(hubs.autolink(out, a))


def build_article(a, arts):
    same = [x for x in arts if x["id"] != a["id"] and x["cat"] == a["cat"]][:3]
    latest = [x for x in arts if x["id"] != a["id"] and x not in same][:5]
    kp = ""
    if a.get("key_points"):
        v = a.get("visual") or {}
        # the lead graphic already shows the figure: no second copy of it right below
        stat = f'<p class="kp-stat"><b>{escape(str(v.get("big", "")))}</b><span>{escape(str(v.get("label", "")))}</span></p>' if v.get("big") and (has_photo(a) or not lead(a)) else ""
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
        updated = f' · Updated {datetime.fromisoformat(a["updated"]).day} {datetime.fromisoformat(a["updated"]):%b, %H:%M} EET'
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": a["headline"], "description": a["dek"],
          "datePublished": a["published"], "dateModified": a.get("updated", a["published"]),
          "image": ([f"{SITE}/img/{a['id']}.jpg"] if has_photo(a) else []) + lead_ld(a),
          "author": {"@type": "Organization", "name": "MetaFlora News Desk", "url": f"{SITE}/how-we-report/"},
          "publisher": PUBLISHER, "mainEntityOfPage": url, "isAccessibleForFree": True}
    tags_html = ""
    if a.get("tags"):
        tags_html = '<nav class="tags" aria-label="Topics">' + "".join(f'<a href="{tag_url(t)}">{escape(t)}</a>' for t in a["tags"]) + "</nav>"
    ticks = tickers_for(a.get("tags", []))
    if ticks:
        tags_html += ('<nav class="tags tickers" aria-label="Stocks in this story"><span class="tk-label">Stocks in this story</span>'
                      + "".join(f'<a href="/stocks/{r["sym"].lower()}/" title="Close {r["date"]}">{escape(r["name"])} <span class="tk">{r["sym"]}</span> '
                                f'<span class="{"up" if r["chg"] >= 0 else "down"}">{r["chg"]:+.1f}%</span></a>' for r in ticks) + "</nav>")
    fig = lead_figure(a)
    if has_photo(a):
        fig = f'<figure class="story-fig">{image(a, eager=True)}<figcaption>{caption(a)}</figcaption></figure>'
    import ads
    import hubs
    covered = hubs.covered_box(a)
    end_ad = ads.slot(a["id"], "end", "end", a["cat"])
    import archive as A
    crumb_trail, day_link = A.article_crumbs_html(a), A.day_path(a["_dt"])
    after_same = ""
    if len(same) >= 2:
        after_same = f'<div><h2 class="sec-label">More on {escape(a["cat"])}</h2><ol class="latest-list">{"".join(list_item(x) for x in same)}</ol></div>'
    body = f"""
<article class="story">
  <header class="story-head">
    {crumb_trail}
    {kicker(a['cat'])}
    <h1>{escape(a['headline'])}</h1>
    <p class="dek">{escape(a['dek'])}</p>
    <div class="byline">
      <p><span class="by">By <a href="/how-we-report/">MetaFlora News Desk</a></span> · <a class="dateline" href="{day_link}"><time datetime="{a['published']}">{t_long(a)}</time></a>{updated} · <span class="nowrap">{minutes(a)} min read</span></p>
      <p class="share">{share}</p>
    </div>
    <p class="disclosure">Produced by MetaFlora's AI newsroom from the sources listed at the end of this article. <a href="/how-we-report/">How we report</a></p>
  </header>
  {fig}
  <div class="story-col">
    {kp}
    <div class="story-body">{render_body(a)}</div>
    <section class="sources"><h2>Sources</h2><ol>{srcs}</ol>
      <p>This article summarises and links the original reporting. Spotted an error? Email <a href="mailto:support@metaflora.xyz">support@metaflora.xyz</a> or message <a href="{X_URL}" target="_blank" rel="noopener">@{X_HANDLE}</a> on X.</p></section>
    {covered}
    {tags_html}
    {corr}
    {end_ad}
  </div>
</article>
<section class="after{'' if after_same else ' after-one'}">
  {after_same}
  <div><h2 class="sec-label">Latest</h2><ol class="latest-list">{''.join(list_item(x) for x in latest)}</ol></div>
</section>
"""
    ld["keywords"] = a.get("tags", [])
    ld["articleSection"] = a["cat"]
    ld["wordCount"] = sum(len(x.split()) for x in a["body"])
    about, mentions = hubs.article_entities(a)  # after render_body: mentions are the hubs autolinked in the body
    if about:
        ld["about"] = about
    if mentions:
        ld["mentions"] = mentions
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": NAME, "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": a["cat"], "item": f"{SITE}/section/{a['cat'].lower()}/"},
        {"@type": "ListItem", "position": 3, "name": a["headline"], "item": url}]}
    og_art = (f'<meta property="article:published_time" content="{a["published"]}">'
              f'<meta property="article:modified_time" content="{a.get("updated", a["published"])}">'
              f'<meta property="article:section" content="{escape(a["cat"])}">'
              + "".join(f'<meta property="article:tag" content="{escape(t)}">' for t in a.get("tags", [])))
    extra = og_art + f'<script type="application/ld+json">{json.dumps(ld)}</script><script type="application/ld+json">{json.dumps(crumbs)}</script>'
    ctx["write"](a["_path"].strip("/") + "/index.html",
                 page(a["headline"], body, desc=a["dek"], path=a["_path"], og_image=f"{SITE}/og/{a['id']}.png", kind="article",
                      extra_head=extra, active=a["cat"], dateline=dl(f'{a["_dt"]:%A} {a["_dt"].day} {a["_dt"]:%B %Y}', f'{"Morning" if a["edition"].endswith("am") else "Evening"} edition')))


def build_sections(arts):
    """/section/<c>/ plus /section/<c>/page/N/ (archive.PER_PAGE stories per page, newest first)."""
    import archive as A
    for c in CATS:
        items = [a for a in arts if a["cat"] == c]
        base = f"/section/{c.lower()}/"
        pages = A.chunks(items)
        for n, chunk in enumerate(pages, 1):
            path = A.page_path(base, n)
            if not items:
                inner = '<p class="empty">No stories in this section yet. New editions publish every morning and evening.</p>'
            elif n == 1:
                import ads
                inner = (f'<div class="sec-lead">{card(chunk[0], "wide")}</div>{ads.slot("section-" + c, 0, "list", c)}'
                         f'<div class="grid4">{"".join(card(a) for a in chunk[1:13])}</div>')
                if len(chunk) > 13:
                    inner += f'<ol class="latest-list">{"".join(list_item(a) for a in chunk[13:])}</ol>'
            else:
                inner = f'<ol class="latest-list">{"".join(list_item(a) for a in chunk)}</ol>'
            if items:
                inner += A.pager_html(base, n, len(pages), extra='<a href="/archive/">Archive by date</a>')
            title = A.paged_title(f"{c} cannabis news", n)
            c_html, c_ld = A.crumbs([A.HOME, (c, base)] + ([(f"Page {n}", path)] if n > 1 else []))
            first = (n - 1) * A.PER_PAGE + 1
            meta = f"{len(items)} stories" if n == 1 else f"Stories {first}–{first + len(chunk) - 1} of {len(items)}"
            body = f'{c_html}<div class="page-h"><h1>{escape(A.paged_title(c, n))}</h1><p class="meta">{meta}</p></div>{inner}'
            desc = SECTION_DESC.get(c, TAGLINE) if n == 1 else f"Older {c} cannabis news from MetaFlora News, page {n}: stories {first} to {first + len(chunk) - 1} of {len(items)}, newest first."
            ctx["write"](path.strip("/") + "/index.html", page(title, body, desc=desc, path=path, active=c,
                                                                robots=ROBOTS if items else "noindex, follow",
                                                                feeds=[(f"{NAME}: {c}", f"{base}feed.xml")] if items else (),
                                                                extra_head=collection_ld(title, path, chunk) + c_ld))
            if n > 1:
                A.note(path, chunk)


def build_archive(eds):
    """/archive/ lists months; /archive/YYYY/MM/ lists every edition in that month. Pages stay small as the archive grows.
    Also writes the date-path pages /YYYY/MM/DD/, /YYYY/MM/ and /YYYY/ (archive.build_dates)."""
    import archive as A
    months = {}
    for ed, items in eds.items():
        months.setdefault(ed[:7], {})[ed] = items
    rows = []
    for ym, med in sorted(months.items(), reverse=True):
        dt = datetime.fromisoformat(ym + "-01")
        n = sum(len(v) for v in med.values())
        rows.append(f'<li><a class="li-title" href="/archive/{dt:%Y/%m}/">{dt:%B %Y}</a><span class="meta">{len(med)} editions · {n} stories</span></li>')
        blocks = "".join(f'<section class="block"><h2 class="sec-label"><a href="/{items[0]["_dt"]:%Y/%m/%d}/">{escape(ctx["edition_label"](ed))}</a></h2>'
                         f'<ol class="latest-list">{"".join(list_item(a) for a in items)}</ol></section>' for ed, items in sorted(med.items(), reverse=True))
        title = f"{dt:%B %Y} archive"
        c_html, c_ld = A.crumbs([A.HOME, ("Archive", "/archive/"), (f"{dt:%B %Y}", f"/archive/{dt:%Y/%m}/")])
        body = f'{c_html}<div class="page-h"><h1>{dt:%B %Y}</h1><p class="meta"><a href="/archive/">All months</a> · <a href="/{dt:%Y/%m}/">{dt:%B %Y} by day</a></p></div>{blocks}'
        ctx["write"](f"archive/{dt:%Y/%m}/index.html", page(title, body, desc=f"Every MetaFlora News story from {dt:%B %Y}: {n} cannabis news stories across {len(med)} morning and evening editions.", path=f"/archive/{dt:%Y/%m}/",
                                                            extra_head=collection_ld(title, f"/archive/{dt:%Y/%m}/", [a for _, v in sorted(med.items(), reverse=True) for a in v]) + c_ld))
    years = sorted({ed[:4] for ed in eds}, reverse=True)
    by_year = " · ".join(f'<a href="/{y}/">{y} by month and day</a>' for y in years)
    c_html, c_ld = A.crumbs([A.HOME, ("Archive", "/archive/")])
    body = f'{c_html}<div class="page-h"><h1>Archive</h1><p class="meta">{len(eds)} editions · {by_year}</p></div><ol class="month-list">{"".join(rows)}</ol>'
    ctx["write"]("archive/index.html", page("Archive", body, desc="Every MetaFlora News edition by month: morning and evening cannabis news since November 2026, each story with its sources.", path="/archive/",
                                            extra_head=c_ld))
    try:  # /YYYY/MM/DD/, /YYYY/MM/, /YYYY/: an error here must not stop an edition from publishing
        A.build_dates(eds)
    except Exception as e:  # noqa: BLE001
        print(f"WARNING date archive pages skipped: {e}")


def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def tag_url(t):
    import hubs
    return hubs.tag_url(t)


def collection_ld(name, path, items):
    """CollectionPage + ItemList for list pages (sections, topics, archive)."""
    return ('<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "CollectionPage", "name": name, "url": SITE + path, "isPartOf": {"@id": f"{SITE}/#org"},
        "mainEntity": {"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": SITE + a["_path"], "name": a["headline"]} for i, a in enumerate(items[:30])]}})
        + "</script>")


HUB_MIN = 3  # topic hubs index (and enter the sitemap) once they hold this many stories


def tickers_for(tags):
    """Market rows for tickers whose company matches any of these tags (only tickers with a stock page)."""
    m = ctx.get("market")
    if not m:
        return []
    aliases = {k.lower(): v for k, v in TAG_ALIASES.items()}
    want = {aliases.get(t.lower(), t).lower() for t in tags}
    return [r for r in m["rows"] if r["sym"] != "MSOS" and want & {x.lower() for x in r["tags"]}]


def build_topics(arts):
    """One evergreen hub page per topic tag (states, companies, regulators, themes).
    These are the pages that accumulate authority over time."""
    topics = {}
    for a in arts:
        for t in a.get("tags", []):
            topics.setdefault(t, []).append(a)
    import hubs
    for t, items in list(topics.items()):
        items = sorted(items, key=lambda a: a["_dt"], reverse=True)
        h = hubs.hub_for_tag(t)
        if h and hubs.complete(h):
            # the legal hub owns this entity: keep the old URL as a pointer, out of the index
            # minimal redirect stub (GitHub Pages can't 301): canonical + instant refresh, no noindex
            ctx["write"](f"topic/{slug(t)}/index.html",
                         f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{escape(h["name"])} · MetaFlora News</title>'
                         f'<link rel="canonical" href="{SITE}{h["_url"]}"><meta http-equiv="refresh" content="0; url={h["_url"]}">'
                         f'<meta name="viewport" content="width=device-width,initial-scale=1"></head><body>'
                         f'<p>Moved to <a href="{h["_url"]}">{escape(h["name"])}</a>.</p></body></html>')
            topics.pop(t)
            continue
        lead = items[0]
        import ads
        import archive as A
        n = len(items)
        base = f"/topic/{slug(t)}/"
        pages = A.chunks(items)
        for pn, chunk in enumerate(pages, 1):
            path = A.page_path(base, pn)
            if pn == 1:
                inner = f'<div class="sec-lead">{card(lead, "wide")}</div>{ads.slot("topic-" + t, 0, "list", lead["cat"])}'
                if len(chunk) > 1:
                    inner += f'<ol class="latest-list">{"".join(list_item(a) for a in chunk[1:])}</ol>'
                desc = f"{t} news from MetaFlora News: {n} {'story' if n == 1 else 'stories'}, newest first. Latest: {lead['headline']}"
                if len(desc) > 160:
                    desc = desc[:157].rsplit(" ", 1)[0] + "..."
                stock = "".join(f'<p class="hub-stock"><a href="/stocks/{r["sym"].lower()}/">{escape(r["full"])} stock ({r["sym"]}): price, chart and daily market note</a></p>'
                                for r in tickers_for([t]))
                intro = f'<p class="dek">Every MetaFlora News story about {escape(t)}, newest first, with links to the original reporting.</p>'
                meta = f'{n} {"story" if n == 1 else "stories"}'
            else:
                inner = f'<ol class="latest-list">{"".join(list_item(a) for a in chunk)}</ol>'
                first = (pn - 1) * A.PER_PAGE + 1
                desc = f"Older {t} news from MetaFlora News, page {pn}: stories {first} to {first + len(chunk) - 1} of {n}, newest first."
                stock = intro = ""
                meta = f"Stories {first}–{first + len(chunk) - 1} of {n}"
            inner += A.pager_html(base, pn, len(pages))
            title = A.paged_title(f"{t} news", pn)
            c_html, c_ld = A.crumbs([A.HOME, ("Topics", "/topic/"), (t, base)] + ([(f"Page {pn}", path)] if pn > 1 else []))
            body = f'{c_html}<div class="page-h"><h1>{escape(title)}</h1><p class="meta">{meta}</p>{intro}{stock}</div>{inner}'
            ctx["write"](path.strip("/") + "/index.html", page(title, body, desc=desc, path=path,
                                                                robots=ROBOTS if n >= HUB_MIN else "noindex, follow",
                                                                extra_head=collection_ld(title, path, chunk) + c_ld))
            if pn > 1 and n >= HUB_MIN:
                A.note(path, chunk)
    rows = "".join(f'<li><a class="li-title" href="/topic/{slug(t)}/">{escape(t)}</a><span class="meta">{len(v)}</span></li>'
                   for t, v in sorted(topics.items(), key=lambda kv: (-len(kv[1]), kv[0])))
    ctx["write"]("topic/index.html", page("Topics", f'<div class="page-h"><h1>Topics</h1></div><ol class="month-list">{rows}</ol>',
                                          desc="Every company, state, regulator and theme MetaFlora News covers, from Curaleaf and the DEA to Ohio and hemp, with each topic's stories newest first.", path="/topic/"))
    return topics


def build_how():
    body = f"""<article class="story static">
<header class="story-head"><h1>How we report</h1><p class="dek">MetaFlora News is produced by an AI newsroom. This page explains what that means and how we hold it to account.</p></header>
<div class="story-col"><div class="story-body">
<h2>How a story is made</h2>
<p>Twice a day our system reviews reporting from named outlets, regulators and public records. It writes original summaries in MetaFlora's own words and links every source it used at the end of each article.</p>
<h2 id="checks">How every story is checked</h2>
<p>Stories are written and checked by automated systems, not reviewed by a human editor before publication. Before anything goes live, the build rejects any story that is missing a linked source, and every figure, date and quote must come from a source the newsroom actually opened. Legal reference pages (state laws, country laws and federal explainers) show the source and the date each fact was last verified, and a change to whether cannabis is legal somewhere is only made on the strength of a primary source such as a statute, a regulator, a court or the Federal Register. Corrections are made openly and listed on our <a href="/corrections/">corrections page</a>.</p>
<h2>Our rules</h2>
<p>We do not publish anonymous claims, invent quotes or report a fact we cannot attribute to a source. Figures come from the sources we link. Images marked "Photo illustration: AI-generated" are created for illustration and never depict real, identifiable people.</p>
<h2 id="corrections">Corrections</h2>
<p>When we get something wrong we fix it, add a dated correction note to the article and list it on our <a href="/corrections/">corrections page</a>. To report an error, email <a href="mailto:support@metaflora.xyz">support@metaflora.xyz</a> or message <a href="{X_URL}" target="_blank" rel="noopener">@{X_HANDLE}</a> on X with the article link.</p>
<h2 id="ownership">Ownership and conflicts of interest</h2>
<p>MetaFlora News is owned and published by <a href="https://metaflora.xyz" target="_blank" rel="noopener">MetaFlora</a>, which builds a cannabis platform, a seller marketplace and dispensary loyalty tools. Many ads on this site are MetaFlora's own; they are always labelled "Advertisement · MetaFlora". When a story covers a company or market where MetaFlora does business, that commercial interest does not decide whether or how we cover it, and we say so in the story when it is directly relevant.</p>
<h2>Advertising</h2>
<p>Advertising is always labelled and kept separate from reporting. Advertisers, including MetaFlora, have no say over what we cover. See <a href="/advertise/">Advertise</a>.</p>
<h2 id="contact">Contact</h2>
<p>Email <a href="mailto:support@metaflora.xyz">support@metaflora.xyz</a> for corrections, tips, rights questions and anything else. You can also reach us at <a href="{X_URL}" target="_blank" rel="noopener">@{X_HANDLE}</a> on X.</p>
<h2 id="alerts">News alerts and your privacy</h2>
<p>News alerts are optional and free. Your browser asks for permission only after you choose to turn them on with the bell. To give each browser a private ID without an account, we use Firebase anonymous sign-in; we store that ID, the browser's push address, the topics and frequency you chose, when you subscribed, and which alerts were delivered or opened. We never store your name, email address or browsing history, and we don't sell or share this data.</p>
<p>Alerts are delivered through Google's Firebase Cloud Messaging, which processes the push address to deliver them. Turn alerts off with the bell (or block notifications in your browser) and we delete this browser's record and stop sending immediately; push addresses that stop working are deleted automatically. The legal basis is your consent, which you can withdraw at any time. Questions or deletion requests: <a href="mailto:support@metaflora.xyz">support@metaflora.xyz</a>.</p>
<h2>Not advice</h2>
<p>MetaFlora News is news and commentary. Nothing here is legal, medical or financial advice.</p>
</div></div></article>"""
    ctx["write"]("how-we-report/index.html", page("How we report", body, path="/how-we-report/",
                                                  desc="How MetaFlora News works: an AI newsroom with named sources, labelled ads, corrections, ownership disclosure and contact details."))


def build_about(arts):
    n = len(arts)
    import hubs
    gloss = 'a <a href="/glossary/">cannabis glossary</a> and ' if hubs.has_glossary() else "and "
    body = f"""<article class="story static">
<header class="story-head"><h1>About MetaFlora News</h1><p class="dek">Independent-minded cannabis industry news, laws and market data, published twice a day by MetaFlora.</p></header>
<div class="story-col"><div class="story-body">
<h2>What we cover</h2>
<p>MetaFlora News reports on the business, law and science of cannabis: federal policy such as rescheduling, Section 280E and the hemp THC rules; state markets, licensing and ballot measures; Europe and other international markets; cannabis stocks and company results; and research. A morning edition publishes around 06:00 and an evening edition around 18:00 (Bucharest time), and the newsroom has published {n} stories so far.</p>
<h2>Reference you can rely on</h2>
<p>Alongside the news we maintain the <a href="/legal/us/">MetaFlora Legalization Tracker</a> for every US state, <a href="/legal/world/">country cannabis laws</a>, <a href="/explainers/">federal explainers</a>, {gloss}<a href="/stocks/">cannabis stock pages</a>. Each fact shows its source and the date it was last verified, and the pages update as the newsroom reports changes.</p>
<h2>Who we are</h2>
<p>Stories are bylined to the MetaFlora News Desk, our AI newsroom. It works from named public sources and links every one of them; <a href="/how-we-report/">How we report</a> explains exactly how stories are made and checked, and what we do when we get something wrong.</p>
<h2>Publisher</h2>
<p>MetaFlora News is owned and published by <a href="https://metaflora.xyz" target="_blank" rel="noopener">MetaFlora</a>. MetaFlora's commercial interests are disclosed on <a href="/how-we-report/#ownership">How we report</a>, and its ads on this site are always labelled.</p>
<h2>Contact</h2>
<p>Corrections, tips and questions: <a href="mailto:support@metaflora.xyz">support@metaflora.xyz</a> · <a href="{X_URL}" target="_blank" rel="noopener">@{X_HANDLE}</a> on X. Advertising: see <a href="/advertise/">Advertise</a>.</p>
</div></div></article>"""
    ld = {"@context": "https://schema.org", "@type": "AboutPage", "name": "About MetaFlora News", "url": SITE + "/about/", "mainEntity": ORG, "publisher": {"@id": f"{SITE}/#org"}}
    ctx["write"]("about/index.html", page("About MetaFlora News", body, path="/about/",
                 desc="About MetaFlora News: cannabis industry news, laws and market data published twice a day by MetaFlora, with every source linked.",
                 extra_head=f'<script type="application/ld+json">{json.dumps(ld)}</script>'))


def build_corrections(arts):
    rows = []
    for a in sorted(arts, key=lambda a: a.get("updated") or a["published"], reverse=True):
        for c in a.get("corrections") or []:
            rows.append(f'<li><time>{escape(c["date"])}</time><a class="li-title" href="{a["_path"]}">{escape(a["headline"])}</a><p>{escape(c["text"])}</p></li>')
    inner = f'<ol class="corr-log">{"".join(rows)}</ol>' if rows else '<p class="empty">No corrections yet.</p>'
    body = f"""<div class="page-h"><h1>Corrections</h1><p class="meta">{len(rows)} {"correction" if len(rows) == 1 else "corrections"}</p></div>
<p class="dek corr-intro">When we get something wrong, we fix the story, add a dated note to it and list it here. To report an error, email <a href="mailto:support@metaflora.xyz">support@metaflora.xyz</a> with the article link.</p>
{inner}"""
    ctx["write"]("corrections/index.html", page("Corrections", body, path="/corrections/",
                 desc="Every correction MetaFlora News has made, newest first, with a link to the corrected story and what changed."))


def build_advertise():
    import ads
    inv = ads.load()
    contact = inv.get("advertise_contact", "https://metaflora.xyz")
    sample = ads.render(next((x for x in inv["ads"] if x["id"] == "sell"), None), "article")
    body = f"""<article class="story static">
<header class="story-head"><h1>Advertise</h1><p class="dek">MetaFlora News publishes a morning and an evening edition every day for cannabis operators, investors and connoisseurs, and posts every lead story to X.</p></header>
<div class="story-col"><div class="story-body">
<h2>Placements</h2>
<p><b>Article break.</b> One clearly labelled unit inside long-form stories, placed between sections. Can target a section such as Markets or Science.</p>
<p><b>End of article.</b> A card-sized unit after the sources, where readers finish the story.</p>
<p><b>Front page.</b> The labelled band on the front page, seen by every homepage visitor. House ads rotate in each slot; a partner booking takes the slot on its own.</p>
<p><b>Sections, topics and stocks.</b> One unit on each section, topic and cannabis stock page. Stock pages update every trading day.</p>
<p><b>Sponsored edition.</b> The front page unit plus every article break in one morning or evening edition.</p>
<h2>What it looks like</h2></div>
{sample}
<p class="adv-cta"><a class="btn" href="{escape(contact)}" target="_blank" rel="noopener">Become a partner</a></p>
<p class="meta">Tell us your brand, dates and target sections. We will come back with availability and rates.</p>
</div></article>"""
    ctx["write"]("advertise/index.html", page("Advertise", body, path="/advertise/",
                                              desc="Advertise on MetaFlora News: labelled ad breaks in long-form cannabis news, end-of-article cards, front-page bands and daily cannabis stock pages."))
