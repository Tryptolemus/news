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
from urllib.parse import quote
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from covers import cover_svg, color_for, MOTIFS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content" / "articles"
OUT = ROOT / "docs"
SITE = "https://news.metaflora.xyz"
NAME = "MetaFlora News"
TAGLINE = "Cannabis industry news: policy, markets, science and the business of cannabis. Morning and evening editions."
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
        if not a["visual"].get("big") or not a["visual"].get("label"):
            errors.append(f"{p.name}: visual needs big and label")
        bn = a.get("banner")
        if bn is not None and (not bn.get("title") or len(bn.get("points", [])) > 3):
            errors.append(f"{p.name}: banner needs a title and at most 3 points")
        if not (2 <= len(a.get("tags") or []) <= 8):
            errors.append(f"{p.name}: needs 2-8 tags")
        if len(a.get("x_post") or "") > 220:
            errors.append(f"{p.name}: x_post over 220 characters")
        if not all(s.get("url", "").startswith("http") for s in a["sources"]):
            errors.append(f"{p.name}: every source needs a url")
        a["_file"] = p.name
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


# ---------- pages (see templates.py) ----------

import templates as T  # noqa: E402

IMAGES = ROOT / "content" / "images"


def photo_path(a):
    p = IMAGES / f"{a['id']}.jpg"
    return p if p.exists() else None


page = T.page
TOPICS = {}
STOCKS = []


def build_feeds(arts):
    items = []
    for a in arts[:60]:
        items.append(f"""<item><title>{escape(a['headline'])}</title><link>{SITE}{a['_path']}</link><guid>{SITE}{a['_path']}</guid>
<pubDate>{format_datetime(a['_dt'])}</pubDate><category>{a['cat']}</category><description>{escape(a['dek'])}</description></item>""")
    now = format_datetime(datetime.now(timezone.utc))
    write("feed.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>{NAME}</title><link>{SITE}/</link><description>{escape(TAGLINE)}</description>
<lastBuildDate>{now}</lastBuildDate>{''.join(items)}</channel></rss>""")
    for c in CATS:
        its = [a for a in arts if a["cat"] == c][:40]
        write(f"section/{c.lower()}/feed.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>{NAME}: {c}</title><link>{SITE}/section/{c.lower()}/</link><description>{c} news from {NAME}</description>
<lastBuildDate>{now}</lastBuildDate>{''.join(f"<item><title>{escape(a['headline'])}</title><link>{SITE}{a['_path']}</link><guid>{SITE}{a['_path']}</guid><pubDate>{format_datetime(a['_dt'])}</pubDate><description>{escape(a['dek'])}</description></item>" for a in its)}</channel></rss>""")
    newest = arts[0]["_dt"].isoformat()
    def u(loc, mod):
        return f"<url><loc>{loc}</loc><lastmod>{mod}</lastmod></url>"
    pages = [u(f"{SITE}/", newest), u(f"{SITE}/archive/", newest), u(f"{SITE}/topic/", newest),
             u(f"{SITE}/how-we-report/", newest), u(f"{SITE}/advertise/", newest)]
    pages += [u(f"{SITE}/section/{c.lower()}/", newest) for c in CATS]
    pages += [u(f"{SITE}/topic/{T.slug(t)}/", max(a["_dt"] for a in v).isoformat()) for t, v in TOPICS.items()]
    pages += [u(f"{SITE}{p}", mod) for p, mod in STOCKS]
    months = sorted({a["edition"][:7] for a in arts})
    pages += [u(f"{SITE}/archive/{m.replace('-', '/')}/", newest) for m in months]
    ns = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
    write("sitemap-pages.xml", f'<?xml version="1.0" encoding="UTF-8"?><urlset {ns}>{"".join(pages)}</urlset>')
    # every article ever published, newest first (split at 40k URLs per file)
    allart = [u(f"{SITE}{a['_path']}", a.get("updated", a["published"])) for a in sorted(arts, key=lambda a: a["_dt"], reverse=True)]
    parts = [allart[i:i + 40000] for i in range(0, len(allart), 40000)] or [[]]
    for i, chunk in enumerate(parts, 1):
        write(f"sitemap-articles-{i}.xml", f'<?xml version="1.0" encoding="UTF-8"?><urlset {ns}>{"".join(chunk)}</urlset>')
    # Google News sitemap: articles from the last 48 hours
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    recent = [a for a in arts if a["_dt"] >= cutoff] or arts[:9]
    news = "".join(f'<url><loc>{SITE}{a["_path"]}</loc><news:news><news:publication><news:name>{NAME}</news:name><news:language>en</news:language>'
                   f'</news:publication><news:publication_date>{a["published"]}</news:publication_date><news:title>{escape(a["headline"])}</news:title>'
                   f'</news:news></url>' for a in recent)
    write("sitemap-news.xml", f'<?xml version="1.0" encoding="UTF-8"?><urlset {ns} xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">{news}</urlset>')
    maps = ["sitemap-pages.xml", "sitemap-news.xml"] + [f"sitemap-articles-{i}.xml" for i in range(1, len(parts) + 1)]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<sitemap><loc>{SITE}/{m}</loc><lastmod>{newest}</lastmod></sitemap>" for m in maps) + "</sitemapindex>")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    write("CNAME", "news.metaflora.xyz\n")
    write(".nojekyll", "")
    write("404.html", page("Page not found", '<div class="page-h"><h1>Page not found</h1><p class="dek">That page moved or never existed. <a href="/">Go to the front page</a>.</p></div>', path="/404.html"))


def relativize():
    """Rewrite root-absolute links ("/x/") to relative ones so the site works at any base path:
    news.metaflora.xyz, tryptolemus.github.io/news/, or opened from disk."""
    import re
    for f in OUT.rglob("*.html"):
        rel = f.relative_to(OUT)
        up = "../" * (len(rel.parts) - 1) or "./"
        def fix(m):
            t, frag = (m.group(2).split("#", 1) + [""])[:2]
            t, q = (t.split("?", 1) + [""])[:2]
            if t == "" or t.endswith("/"):
                t += "index.html"
            return f'{m.group(1)}="{up}{t}{"?" + q if q else ""}{"#" + frag if frag else ""}"'
        s = re.sub(r'(href|src|poster)="/(?!/)([^"]*)"', fix, f.read_text())
        s = s.replace('href="./index.html"', 'href="./"')
        f.write_text(s)
    css = OUT / "assets" / "site.css"
    css.write_text(css.read_text().replace("url(/assets/fonts/", "url(fonts/"))


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
    from banner import render_banner
    from PIL import Image
    for a in arts:
        src = CONTENT / a["_file"]
        ban = OUT / "banners" / f"{a['id']}.jpg"
        photo = photo_path(a)
        newest = max(src.stat().st_mtime, photo.stat().st_mtime if photo else 0, Path(__file__).with_name("banner.py").stat().st_mtime)
        if not ban.exists() or ban.stat().st_mtime < newest:
            render_banner(a, photo, ban, edition_label(a["edition"]).split(" · ")[1])
            og = OUT / "og" / f"{a['id']}.png"
            og.parent.mkdir(parents=True, exist_ok=True)
            im = Image.open(ban)
            im = im.resize((1200, round(1200 * im.height / im.width)), Image.LANCZOS)
            top = (im.height - 630) // 2
            im.crop((0, top, 1200, top + 630)).save(og, optimize=True)
    default = OUT / "assets" / "og-default.png"
    if not default.exists():
        render_png(cover_svg({"id": "default", "cat": "Policy", "visual": {"motif": "leaf", "big": "NEWS", "label": "Cannabis news every morning and evening"}}), default)
    latest_ed = next(iter(eds))
    reel = OUT / "reels" / f"{latest_ed}.mp4"
    if not reel.exists():
        from reel import render_reel
        render_reel(latest_ed, edition_label(latest_ed), eds[latest_ed], OUT / "og", reel,
                    lambda a: OUT / "banners" / f"{a['id']}.jpg", full_banner=True)
    poster = OUT / "reels" / f"{latest_ed}-poster.jpg"
    if not poster.exists():
        flat_poster(latest_ed, len(eds[latest_ed]), poster)


def flat_poster(ed, n, out):
    """Quiet video poster: flat ground, mono label, a white play glyph. No banner type."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1280, 720
    im = Image.new("RGB", (W, H), (26, 26, 27))
    d = ImageDraw.Draw(im)
    def f(names, size):
        for n_ in names:
            if Path(n_).exists():
                return ImageFont.truetype(n_, size)
        return ImageFont.load_default()
    mono = f(["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"], 26)
    serif = f(["/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"], 46)
    day, half = ed.rsplit("-", 1)
    dt = datetime.fromisoformat(day)
    d.text((80, 80), f"{'MORNING' if half == 'am' else 'EVENING'} BRIEFING  ·  {dt.day} {dt:%b %Y}".upper(), font=mono, fill=(154, 154, 154))
    d.text((80, H - 150), f"The {'morning' if half == 'am' else 'evening'} edition in {n} headlines", font=serif, fill=(242, 242, 242))
    d.rectangle([80, H - 80, 176, H - 77], fill=(163, 230, 53))
    cx, cy, r = W // 2, H // 2 - 20, 54
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(242, 242, 242), width=3)
    d.polygon([(cx - 16, cy - 24), (cx - 16, cy + 24), (cx + 26, cy)], fill=(242, 242, 242))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=88)


def install_fonts():
    """rsvg-convert and the reel need Casanova Scotia available to fontconfig."""
    dest = Path.home() / ".local/share/fonts"
    src = ROOT / "newsroom" / "assets" / "fonts" / "CasanovaScotia.otf"
    if not (dest / src.name).exists():
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dest / src.name)
        subprocess.run(["fc-cache", "-f"], check=False)


def main():
    media = "--no-media" not in sys.argv
    arts = load_articles()
    if not arts:
        raise SystemExit("No articles in content/articles")
    eds = editions(arts)
    OUT.mkdir(exist_ok=True)
    for sub in ("section", "archive", "img", "reels", "advertise", "how-we-report", "topic", "stocks"):
        shutil.rmtree(OUT / sub, ignore_errors=True)
    for d in OUT.glob("[0-9][0-9][0-9][0-9]"):
        shutil.rmtree(d)
    assets = OUT / "assets"
    assets.mkdir(exist_ok=True)
    shutil.copy(ROOT / "newsroom" / "site.css", assets / "site.css")
    shutil.copytree(ROOT / "newsroom" / "assets", assets, dirs_exist_ok=True)
    if IMAGES.exists():
        shutil.copytree(IMAGES, OUT / "img", dirs_exist_ok=True)
    install_fonts()
    T.ctx.update(photo_path=photo_path, write=write, out=OUT, edition_label=edition_label)
    import market
    if media:
        build_media(arts, eds)
    try:
        T.ctx["market"] = market.fetch() if media else market.cached()
    except Exception:  # noqa: BLE001
        T.ctx["market"] = None
    T.build_front(arts, eds)
    for a in arts:
        T.build_article(a, arts)
    T.build_sections(arts)
    T.build_archive(eds)
    global TOPICS
    TOPICS = T.build_topics(arts)
    import stocks
    STOCKS[:] = stocks.build_stocks(arts, T.ctx["market"])
    T.build_how()
    T.build_advertise()
    build_feeds(arts)
    relativize()
    print(f"Built {len(arts)} articles across {len(eds)} editions -> {OUT}")


if __name__ == "__main__":
    main()
