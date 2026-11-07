#!/usr/bin/env python3
"""SEO scorecard for the built site (docs/).

Crawls every HTML page, measures the things search engines reward, prints a scorecard and
appends a dated entry to content/seo/history.json so progress can be graphed round by round.

Usage: python3 newsroom/seo_audit.py [--label "Round 1"] [--no-save]
"""
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
HIST = ROOT / "content" / "seo" / "history.json"
SITE = "https://news.metaflora.xyz"


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.desc = None
        self.canonical = None
        self.robots = ""
        self.h1 = 0
        self.links = []
        self.imgs = 0
        self.imgs_alt = 0
        self.jsonld = []
        self.og_image = None
        self.max_preview = False
        self.redirect = False
        self._in = None
        self._buf = []
        self.text_words = 0
        self._in_main = 0
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "svg":
            self._svg = getattr(self, "_svg", 0) + 1
        if tag == "title" and not getattr(self, "_svg", 0) and not self.title:
            self._in = "title"
        elif tag == "meta":
            n = (a.get("name") or a.get("property") or "").lower()
            if n == "description":
                self.desc = a.get("content", "")
            elif n == "robots":
                self.robots = a.get("content", "").lower()
                if "max-image-preview:large" in self.robots:
                    self.max_preview = True
            elif (a.get("http-equiv") or "").lower() == "refresh":
                self.redirect = True
            elif n == "og:image":
                self.og_image = a.get("content")
        elif tag == "link" and (a.get("rel") or "").lower() == "canonical":
            self.canonical = a.get("href")
        elif tag == "h1":
            self.h1 += 1
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "img":
            self.imgs += 1
            if a.get("alt") is not None:
                self.imgs_alt += 1
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._in = "ld"
            self._buf = []
        elif tag in ("main",):
            self._in_main += 1
        if tag in ("script", "style", "nav", "header", "footer"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag == "svg":
            self._svg = max(0, getattr(self, "_svg", 0) - 1)
        if tag == "title" and self._in == "title":
            self._in = None
        elif tag == "script" and self._in == "ld":
            try:
                self.jsonld.append(json.loads("".join(self._buf)))
            except Exception:  # noqa: BLE001
                self.jsonld.append({"_invalid": True})
            self._in = None
        elif tag == "main":
            self._in_main -= 1
        if tag in ("script", "style", "nav", "header", "footer"):
            self._skip = max(0, self._skip - 1)

    def handle_data(self, d):
        if self._in == "title":
            self.title += d
        elif self._in == "ld":
            self._buf.append(d)
        elif self._in_main and not self._skip:
            self.text_words += len(d.split())


def url_of(path):
    rel = path.relative_to(DOCS).as_posix()
    if rel.endswith("index.html"):
        rel = rel[: -len("index.html")]
    return "/" + rel


def norm(base, href):
    if href.startswith(("http://", "https://")):
        u = urlparse(href)
        if u.netloc != urlparse(SITE).netloc:
            return None
        p = u.path
    elif href.startswith(("mailto:", "tel:", "#", "javascript:")):
        return None
    else:
        p = urlparse(urljoin("https://x" + base, href)).path
    if p.endswith("index.html"):
        p = p[: -len("index.html")]
    if not p.endswith("/") and "." not in p.rsplit("/", 1)[-1]:
        p += "/"
    return p


def kind(url):
    if url == "/":
        return "home"
    if re.match(r"^/\d{4}/\d{2}/\d{2}/", url):
        return "article"
    for k in ("topic", "section", "stocks", "archive", "legal", "explainers", "glossary", "company", "guide", "data"):
        if url.startswith(f"/{k}/"):
            return k
    return "other"


def ld_types(objs):
    out = set()
    for o in objs:
        for x in (o.get("@graph") or [o]) if isinstance(o, dict) else []:
            t = x.get("@type")
            for v in ([t] if isinstance(t, str) else (t or [])):
                out.add(v)
    return out


def news_ok(objs):
    for o in objs:
        for x in (o.get("@graph") or [o]) if isinstance(o, dict) else []:
            if x.get("@type") in ("NewsArticle", "Article", "ReportageNewsArticle", "AnalysisNewsArticle"):
                need = ["headline", "image", "datePublished", "dateModified", "author", "publisher"]
                return all(x.get(k) for k in need)
    return False


def audit():
    pages = {}
    for f in sorted(DOCS.rglob("*.html")):
        if f.name == "404.html":
            continue
        p = Page()
        p.feed(f.read_text(errors="replace"))
        pages[url_of(f)] = p
    # redirect stubs (meta refresh + canonical elsewhere) are redirects, not indexable pages
    indexable = {u: p for u, p in pages.items() if "noindex" not in p.robots and not p.redirect}
    sm_urls = set()
    for sm in DOCS.glob("sitemap*.xml"):
        for loc in re.findall(r"<loc>([^<]+)</loc>", sm.read_text()):
            if not loc.endswith(".xml"):
                sm_urls.add(urlparse(loc).path)
    inbound = defaultdict(set)
    for u, p in indexable.items():
        for h in p.links:
            t = norm(u, h)
            if t and t != u:
                inbound[t].add(u)
    titles = Counter(p.title.strip() for p in indexable.values())
    arts = {u: p for u, p in indexable.items() if kind(u) == "article"}
    hubs = {u: p for u, p in indexable.items() if kind(u) in ("topic", "legal", "explainers", "glossary", "company", "guide", "stocks", "data")}
    n = len(indexable) or 1
    pct = lambda k: round(100 * k / n, 1)  # noqa: E731
    title_ok = sum(1 for p in indexable.values() if 25 <= len(p.title.strip()) <= 70)
    desc_ok = sum(1 for p in indexable.values() if p.desc and 70 <= len(p.desc) <= 170)
    h1_ok = sum(1 for p in indexable.values() if p.h1 == 1)
    canon_ok = sum(1 for u, p in indexable.items() if p.canonical and urlparse(p.canonical).path == u)
    ld_valid = sum(1 for p in indexable.values() if p.jsonld and not any(isinstance(o, dict) and o.get("_invalid") for o in p.jsonld))
    preview = sum(1 for p in indexable.values() if p.max_preview)
    unique_titles = sum(1 for p in indexable.values() if titles[p.title.strip()] == 1)
    orphans = [u for u in indexable if u != "/" and not inbound.get(u)]
    imgs = sum(p.imgs for p in indexable.values())
    imgs_alt = sum(p.imgs_alt for p in indexable.values())
    art_n = len(arts) or 1
    m = {
        "pages_indexable": len(indexable),
        "articles": len(arts),
        "hub_pages": len(hubs),
        "evergreen_ratio_pct": round(100 * len(hubs) / n, 1),
        "sitemap_coverage_pct": round(100 * len(set(indexable) & sm_urls) / n, 1),
        "title_ok_pct": pct(title_ok),
        "unique_title_pct": pct(unique_titles),
        "meta_desc_ok_pct": pct(desc_ok),
        "single_h1_pct": pct(h1_ok),
        "self_canonical_pct": pct(canon_ok),
        "jsonld_pct": pct(ld_valid),
        "newsarticle_complete_pct": round(100 * sum(1 for p in arts.values() if news_ok(p.jsonld)) / art_n, 1),
        "max_image_preview_pct": pct(preview),
        "img_alt_pct": round(100 * imgs_alt / imgs, 1) if imgs else 100.0,
        "orphan_pages": len(orphans),
        "avg_internal_links_per_article": round(sum(len({norm(u, h) for h in p.links} - {None, u}) for u, p in arts.items()) / art_n, 1),
        "avg_inbound_links_per_article": round(sum(len(inbound.get(u, ())) for u in arts) / art_n, 1),
        "avg_inbound_links_per_hub": round(sum(len(inbound.get(u, ())) for u in hubs) / (len(hubs) or 1), 1),
        "avg_words_per_article": round(sum(p.text_words for p in arts.values()) / art_n),
    }
    # composite 0-100: technical hygiene (50) + structure/authority (50)
    tech = (m["sitemap_coverage_pct"] + m["title_ok_pct"] + m["meta_desc_ok_pct"] + m["single_h1_pct"] + m["self_canonical_pct"]
            + m["jsonld_pct"] + m["newsarticle_complete_pct"] + m["max_image_preview_pct"] + m["img_alt_pct"] + m["unique_title_pct"]) / 10
    struct = (min(100, m["evergreen_ratio_pct"] * 2.5)  # target ≥40% evergreen pages
              + max(0, 100 - m["orphan_pages"] * 5)
              + min(100, m["avg_internal_links_per_article"] * 2.5)  # target ≥40 internal links incl. nav
              + min(100, m["avg_inbound_links_per_article"] * 20)  # target ≥5 inbound per article
              + min(100, m["avg_words_per_article"] / 8)) / 5  # target ≥800 words
    # scale & topical authority: how much durable, query-matching surface the site owns
    # targets: 300 evergreen hub pages (states, countries, companies, laws, glossary, topics), 1,000 indexable pages
    scale = (min(100, 100 * len(hubs) / 300) + min(100, 100 * len(indexable) / 1000)) / 2
    m["score_technical"] = round(tech, 1)
    m["score_structure"] = round(struct, 1)
    m["score_scale"] = round(scale, 1)
    m["score_total"] = round(tech * .35 + struct * .30 + scale * .35, 1)
    return m, orphans


def main():
    label = None
    if "--label" in sys.argv:
        label = sys.argv[sys.argv.index("--label") + 1]
    m, orphans = audit()
    w = max(len(k) for k in m)
    for k, v in m.items():
        print(f"{k:<{w}}  {v}")
    if orphans:
        print("orphans:", ", ".join(orphans[:10]) + (" …" if len(orphans) > 10 else ""))
    if "--no-save" not in sys.argv:
        HIST.parent.mkdir(parents=True, exist_ok=True)
        hist = json.loads(HIST.read_text()) if HIST.exists() else []
        hist.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "label": label or f"Audit {len(hist) + 1}", **m})
        HIST.write_text(json.dumps(hist, indent=1) + "\n")


if __name__ == "__main__":
    main()
