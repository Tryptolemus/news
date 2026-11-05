#!/usr/bin/env python3
"""Build news.metaflora.xyz from content/articles/*.json into docs/ (served by GitHub Pages).

Usage:  python3 newsroom/build.py [--no-media]
  --no-media  skip PNG social cards and the video reel (fast HTML-only rebuild)
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from covers import cover_svg, color_for, MOTIFS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content" / "articles"
OUT = ROOT / "docs"
SITE = "https://news.metaflora.xyz"
NAME = "MetaFlora News"
TAGLINE = "Cannabis news, every morning and every evening. Written by the MetaFlora AI newsroom."
CATS = ["Policy", "Federal", "Hemp", "Markets", "Europe", "States", "Science", "Tech"]
REQUIRED = ["id", "edition", "published", "cat", "headline", "dek", "body", "sources", "visual"]


# ---------- content ----------

def load_articles():
    arts, errors = [], []
    for p in sorted(CONTENT.glob("*.json")):
        try:
            a = json.loads(p.read_text())
        except Exception as e:  # noqa: BLE001
            errors.append(f"{p.name}: invalid JSON ({e})")
            continue
        missing = [k for k in REQUIRED if not a.get(k)]
        if missing:
            errors.append(f"{p.name}: missing {missing}")
            continue
        if a["cat"] not in CATS:
            errors.append(f"{p.name}: unknown cat {a['cat']}")
        if a["visual"].get("motif") not in MOTIFS:
            errors.append(f"{p.name}: unknown motif {a['visual'].get('motif')}")
        if not all(s.get("url", "").startswith("http") for s in a["sources"]):
            errors.append(f"{p.name}: every source needs a url")
        a["_dt"] = datetime.fromisoformat(a["published"])
        a["_path"] = f"/{a['_dt']:%Y/%m/%d}/{a['id']}/"
        arts.append(a)
    if errors:
        raise SystemExit("Content errors:\n  " + "\n  ".join(errors))
    ids = [a["id"] for a in arts]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise SystemExit(f"Duplicate ids: {dupes}")
    # newest first; within an edition keep the editor's order (rank)
    arts.sort(key=lambda a: (a["edition"], -a.get("rank", 99)), reverse=True)
    return arts


def editions(arts):
    eds = {}
    for a in arts:
        eds.setdefault(a["edition"], []).append(a)
    for k in eds:
        eds[k].sort(key=lambda a: a.get("rank", 99))
    return dict(sorted(eds.items(), reverse=True))


def edition_label(ed):
    d, half = ed.rsplit("-", 1)
    dt = datetime.fromisoformat(d)
    return f"{dt:%A} {dt.day} {dt:%B %Y} · {'Morning' if half == 'am' else 'Evening'} edition"


# ---------- layout ----------

CUBE = ('<svg class="cube" viewBox="0 0 40 40" aria-hidden="true"><path d="M20 3 36 12 20 21 4 12Z" fill="var(--accent)"/>'
        '<path d="M4 12 20 21V38L4 29Z" fill="var(--violet)"/><path d="M36 12 20 21V38L36 29Z" fill="var(--sage)"/></svg>')


def page(title, body, desc=TAGLINE, path="/", og_image=None, kind="website", extra_head=""):
    full = f"{title} · {NAME}" if title != NAME else NAME
    img = og_image or f"{SITE}/assets/og-default.png"
    nav = "".join(f'<a href="/section/{c.lower()}/">{c}</a>' for c in CATS)
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
<meta name="twitter:image" content="{img}">
<meta name="theme-color" content="#15121c">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="alternate" type="application/rss+xml" title="{NAME}" href="/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Unbounded:wght@500;600;800&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="/assets/site.css">
{extra_head}
</head>
<body>
<header class="top"><div class="wrap">
  <a class="brand" href="/">{CUBE}<span>METAFLORA <b>NEWS</b></span></a>
  <nav class="sections" aria-label="Sections">{nav}</nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="foot"><div class="wrap">
  <div class="foot-brand">{CUBE}<span>METAFLORA <b>NEWS</b></span></div>
  <p>Original reporting summaries written by the MetaFlora AI newsroom from public sources. Every story links the reporting it draws on.</p>
  <p>News and commentary only. Not legal, medical or financial advice.</p>
  <p class="mono"><a href="/archive/">Archive</a> · <a href="/feed.xml">RSS</a> · <a href="https://metaflora.xyz">metaflora.xyz</a></p>
  <p class="mono dim">Your world. Your genetics. Your taste. Your AI.</p>
</div></footer>
</body>
</html>
"""


def chip(cat):
    return f'<a class="chip" href="/section/{cat.lower()}/" style="--c:{color_for(cat)}">{escape(cat)}</a>'


def stamp(a):
    return f"{a['_dt']:%-d %b %Y · %H:%M}"


def card(a, size="m"):
    return f"""<article class="card {' '.join('card-' + x for x in size.split())}">
  <a class="cover" href="{a['_path']}" tabindex="-1" aria-hidden="true">{cover_svg(a)}</a>
  <div class="card-meta">{chip(a['cat'])}<span class="mono dim">{stamp(a)}</span></div>
  <h3><a href="{a['_path']}">{escape(a['headline'])}</a></h3>
  <p class="dek">{escape(a['dek'])}</p>
</article>"""


def grid_cards(items, cols=3):
    """Widen card(s) so every row of the 3-column grid is full: a wide card plus a normal one fills a row."""
    gap = (-len(items)) % cols
    wide = set()
    if len(items) > cols and gap >= 1:
        wide.add(0)
    if len(items) > cols and gap == 2:
        wide.add(len(items) - 2)
    return "".join(card(a, "m wide" if i in wide else "m") for i, a in enumerate(items))


def wire_row(a):
    return f"""<li><span class="mono dim">{a['_dt']:%d %b %H:%M}</span>{chip(a['cat'])}<a href="{a['_path']}">{escape(a['headline'])}</a></li>"""


# ---------- pages ----------

def build_front(arts, eds):
    latest_ed, latest = next(iter(eds.items()))
    lead, rest = latest[0], latest[1:]
    top = rest[:4]
    updated = max(a["_dt"] for a in latest)
    reel = f"/reels/{latest_ed}.mp4"
    has_reel = (OUT / reel.lstrip("/")).exists()
    reel_html = ""
    if has_reel:
        reel_html = f"""<section class="reel" aria-label="Edition reel">
  <video src="{reel}" poster="/og/{lead['id']}.png" controls muted autoplay loop playsinline preload="metadata"></video>
  <div class="reel-copy">
    <span class="kicker">The edition in motion</span>
    <h2>Every headline from the {('morning' if latest_ed.endswith('am') else 'evening')} edition, cut as a briefing reel.</h2>
    <p class="dim">Rendered by the newsroom with each edition.</p>
  </div>
</section>"""
    body = f"""
<div class="edbar">
  <span class="live"><i></i>Live newsroom</span>
  <span class="mono">{escape(edition_label(latest_ed))}</span>
  <span class="mono dim">Updated {updated:%H:%M} EET</span>
</div>
<section class="lead">
  <article class="lead-story">
    <a class="cover" href="{lead['_path']}" tabindex="-1" aria-hidden="true">{cover_svg(lead)}</a>
    <div class="lead-copy">
      <div class="card-meta">{chip(lead['cat'])}<span class="mono dim">{stamp(lead)}</span></div>
      <h1><a href="{lead['_path']}">{escape(lead['headline'])}</a></h1>
      <p class="dek big">{escape(lead['dek'])}</p>
      <a class="readmore" href="{lead['_path']}">Read the story →</a>
    </div>
  </article>
  <aside class="topstories" aria-label="Top stories">
    <span class="kicker">Top stories</span>
    <ol>{''.join(f'<li>{chip(a["cat"])}<a href="{a["_path"]}">{escape(a["headline"])}</a></li>' for a in top)}</ol>
  </aside>
</section>
{reel_html}
<div class="sec-h"><h2>This edition</h2><span class="mono dim">{len(latest)} stories</span></div>
<section class="grid">{grid_cards(rest)}</section>
<div class="sec-h"><h2>The wire</h2><a class="mono" href="/archive/">Full archive →</a></div>
<ul class="wire">{''.join(wire_row(a) for a in arts[:40])}</ul>
"""
    write("index.html", page(NAME, body, og_image=f"{SITE}/og/{lead['id']}.png"))


def build_article(a, arts):
    related = [x for x in arts if x["id"] != a["id"] and x["cat"] == a["cat"]][:2]
    related += [x for x in arts if x["id"] != a["id"] and x not in related][: 4 - len(related)]
    paras = "".join(f"<p>{escape(p)}</p>" for p in a["body"])
    srcs = "".join(f'<li><a href="{escape(s["url"])}" rel="noopener" target="_blank">{escape(s["name"])}</a></li>' for s in a["sources"])
    ld = {
        "@context": "https://schema.org", "@type": "NewsArticle", "headline": a["headline"],
        "description": a["dek"], "datePublished": a["published"], "image": [f"{SITE}/og/{a['id']}.png"],
        "author": {"@type": "Organization", "name": "MetaFlora AI Newsroom"},
        "publisher": {"@type": "Organization", "name": NAME},
        "mainEntityOfPage": f"{SITE}{a['_path']}",
    }
    body = f"""
<article class="story">
  <div class="story-head">
    <div class="card-meta">{chip(a['cat'])}<span class="mono dim">{escape(edition_label(a['edition']))}</span></div>
    <h1>{escape(a['headline'])}</h1>
    <p class="dek big">{escape(a['dek'])}</p>
    <p class="byline mono">MetaFlora AI Newsroom · {stamp(a)}</p>
  </div>
  <figure class="story-cover">{cover_svg(a)}</figure>
  <div class="story-body">{paras}</div>
  <aside class="sources">
    <span class="kicker">Sources</span>
    <ul>{srcs}</ul>
    <p class="dim">This story is MetaFlora's own summary of the reporting above. Read the originals for full detail.</p>
  </aside>
</article>
<div class="sec-h"><h2>More from the wire</h2></div>
<section class="grid grid-4">{''.join(card(x, 's') for x in related)}</section>
"""
    extra = f'<script type="application/ld+json">{json.dumps(ld)}</script>'
    write(a["_path"].strip("/") + "/index.html",
          page(a["headline"], body, desc=a["dek"], path=a["_path"], og_image=f"{SITE}/og/{a['id']}.png", kind="article", extra_head=extra))


def build_sections(arts):
    for c in CATS:
        items = [a for a in arts if a["cat"] == c]
        if items:
            inner = f'<section class="grid">{grid_cards(items[:30])}</section>'
        else:
            inner = '<p class="empty">No stories in this section yet. The newsroom files new stories every morning and evening.</p>'
        body = f'<div class="sec-h page-h"><h1>{c}</h1><span class="mono dim">{len(items)} stories</span></div>{inner}'
        write(f"section/{c.lower()}/index.html", page(c, body, path=f"/section/{c.lower()}/"))


def build_archive(eds):
    blocks = []
    for ed, items in eds.items():
        blocks.append(f'<div class="arch-ed"><h2 class="mono">{escape(edition_label(ed))}</h2><ul class="wire">{"".join(wire_row(a) for a in items)}</ul></div>')
    body = f'<div class="sec-h page-h"><h1>Archive</h1><span class="mono dim">{len(eds)} editions</span></div>{"".join(blocks)}'
    write("archive/index.html", page("Archive", body, path="/archive/"))


def build_feeds(arts):
    items = []
    for a in arts[:60]:
        items.append(f"""<item><title>{escape(a['headline'])}</title><link>{SITE}{a['_path']}</link><guid>{SITE}{a['_path']}</guid>
<pubDate>{format_datetime(a['_dt'])}</pubDate><category>{a['cat']}</category><description>{escape(a['dek'])}</description></item>""")
    now = format_datetime(datetime.now(timezone.utc))
    write("feed.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>{NAME}</title><link>{SITE}/</link><description>{escape(TAGLINE)}</description>
<lastBuildDate>{now}</lastBuildDate>{''.join(items)}</channel></rss>""")
    urls = [f"{SITE}/", f"{SITE}/archive/"] + [f"{SITE}/section/{c.lower()}/" for c in CATS] + [f"{SITE}{a['_path']}" for a in arts]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    write("CNAME", "news.metaflora.xyz\n")
    write(".nojekyll", "")
    write("404.html", page("Page not found", '<div class="page-h"><h1>That page moved or never existed.</h1><p><a href="/">Back to the front page →</a></p></div>', path="/404.html"))


def write(rel, text):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


# ---------- media ----------

def render_png(svg_text, out_path, width=1200):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".svg.tmp")
    tmp.write_text(svg_text)
    subprocess.run(["rsvg-convert", "-w", str(width), "-o", str(out_path), str(tmp)], check=True)
    tmp.unlink()


def build_media(arts, eds):
    for a in arts:
        png = OUT / "og" / f"{a['id']}.png"
        if not png.exists():
            render_png(cover_svg(a), png)
    default = OUT / "assets" / "og-default.png"
    if not default.exists():
        render_png(cover_svg({"id": "default", "cat": "Policy", "visual": {"motif": "leaf", "big": "NEWS", "label": "Cannabis news every morning and evening"}}), default)
    latest_ed = next(iter(eds))
    reel = OUT / "reels" / f"{latest_ed}.mp4"
    if not reel.exists():
        from reel import render_reel
        render_reel(latest_ed, edition_label(latest_ed), eds[latest_ed], OUT / "og", reel)


def main():
    media = "--no-media" not in sys.argv
    arts = load_articles()
    if not arts:
        raise SystemExit("No articles in content/articles")
    eds = editions(arts)
    OUT.mkdir(exist_ok=True)
    for sub in ("section", "archive"):
        shutil.rmtree(OUT / sub, ignore_errors=True)
    for d in OUT.glob("[0-9][0-9][0-9][0-9]"):
        shutil.rmtree(d)
    assets = OUT / "assets"
    assets.mkdir(exist_ok=True)
    shutil.copy(ROOT / "newsroom" / "site.css", assets / "site.css")
    (assets / "favicon.svg").write_text(CUBE.replace('class="cube" ', 'xmlns="http://www.w3.org/2000/svg" ')
                                        .replace("var(--accent)", "#f0a64a").replace("var(--violet)", "#a78bfa").replace("var(--sage)", "#8fc4a4"))
    if media:
        build_media(arts, eds)
    build_front(arts, eds)
    for a in arts:
        build_article(a, arts)
    build_sections(arts)
    build_archive(eds)
    build_feeds(arts)
    print(f"Built {len(arts)} articles across {len(eds)} editions -> {OUT}")


if __name__ == "__main__":
    main()
