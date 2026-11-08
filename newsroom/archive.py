"""Archive that scales: pagination helpers, breadcrumbs and the date-path index pages.

URL families written here (all self-canonical, indexable, listed in sitemap-archive.xml):
  /YYYY/MM/DD/   daily edition page: that day's morning and evening stories (the parent of every article URL)
  /YYYY/MM/      month index: one row per day, linking down to the day pages
  /YYYY/         year index: one row per month
Section and topic pages are paginated by templates.py with the helpers below:
  /section/<s>/ , /section/<s>/page/2/ , ...   and   /topic/<t>/ , /topic/<t>/page/2/ , ...
Pagination uses plain "Newer stories" / "Older stories" links (no rel=prev/next); page 2+ is titled "... – page N".

ARCHIVE_URLS collects (path, lastmod) for every page 2+ and every date page; build.py writes them to
sitemap-archive.xml.
"""
import json
from datetime import datetime
from html import escape

import templates as T

PER_PAGE = 30
ARCHIVE_URLS = []   # [(path, lastmod iso)] for sitemap-archive.xml: date pages and pagination pages 2+
HOME = ("MetaFlora News", "/")


# ---------- pagination ----------

def page_path(base, n):
    """base is the page-1 path ('/section/federal/'); page n>1 lives at base + 'page/n/'."""
    return base if n <= 1 else f"{base}page/{n}/"


def chunks(items, per=None):
    per = per or PER_PAGE
    return [items[i:i + per] for i in range(0, len(items), per)] or [[]]


def paged_title(title, n):
    return title if n <= 1 else f"{title} – page {n}"


def pager_html(base, n, total, extra=""):
    """Plain Newer/Older links between the pages of one list (page 1 is the newest)."""
    if total <= 1 and not extra:
        return ""
    parts = []
    if n > 1:
        parts.append(f'<a href="{page_path(base, n - 1)}">&larr; Newer stories</a>')
    if total > 1:
        parts.append(f'<span class="meta">Page {n} of {total}</span>')
    if n < total:
        parts.append(f'<a href="{page_path(base, n + 1)}">Older stories &rarr;</a>')
    if extra:
        parts.append(extra)
    return '<nav class="more-link pager" aria-label="More stories">' + " · ".join(parts) + "</nav>"


def note(path, items):
    """Record a paginated page 2+ (page 1 is already in sitemap-pages.xml) with the newest date of its items."""
    if items:
        ARCHIVE_URLS.append((path, max(a["_dt"] for a in items).isoformat()))


# ---------- breadcrumbs ----------

def crumbs(items):
    """Visible trail + BreadcrumbList JSON-LD for [(name, path), ...]. Returns (html, ld_script)."""
    import hubs
    return hubs.crumbs_html(items), f'<script type="application/ld+json">{json.dumps(hubs.crumbs_ld(items))}</script>'


def article_crumbs_html(a):
    """Visible Home › Section › headline trail for an article (its BreadcrumbList JSON-LD is already in the page)."""
    import hubs
    return hubs.crumbs_html([HOME, (a["cat"], f"/section/{a['cat'].lower()}/"), (a["headline"], a["_path"])])


def day_path(dt):
    return f"/{dt:%Y/%m/%d}/"


# ---------- date pages ----------

def _day_label(dt):
    return f"{dt:%A} {dt.day} {dt:%B %Y}"


def build_dates(eds):
    """Write /YYYY/MM/DD/, /YYYY/MM/ and /YYYY/ from the editions dict ({'2026-11-08-am': [articles], ...})."""
    days = {}
    for ed, items in eds.items():   # keyed by the article URL's date, so every /YYYY/MM/DD/<id>/ has its parent page
        for a in items:
            days.setdefault(f"{a['_dt']:%Y-%m-%d}", {}).setdefault(ed, []).append(a)
    order = sorted(days)  # oldest first
    months, years = {}, {}
    for i, d in enumerate(order):
        dt = datetime.fromisoformat(d)
        months.setdefault(d[:7], []).append(d)
        years.setdefault(d[:4], set()).add(d[:7])
        eds_day = days[d]
        n = sum(len(v) for v in eds_day.values())
        newest = max(a["_dt"] for v in eds_day.values() for a in v)
        blocks = "".join(f'<section class="block"><h2 class="sec-label">{"Morning" if ed.endswith("am") else "Evening"} edition</h2>'
                         f'<ol class="latest-list">{"".join(T.list_item(a, False) for a in items)}</ol></section>'
                         for ed, items in sorted(eds_day.items()))   # am before pm
        nav = []
        if i > 0:
            p = datetime.fromisoformat(order[i - 1])
            nav.append(f'<a href="{day_path(p)}">&larr; {p.day} {p:%B}</a>')
        nav.append(f'<a href="/{dt:%Y/%m}/">All of {dt:%B %Y}</a>')
        if i < len(order) - 1:
            q = datetime.fromisoformat(order[i + 1])
            nav.append(f'<a href="{day_path(q)}">{q.day} {q:%B} &rarr;</a>')
        trail = [HOME, ("Archive", "/archive/"), (f"{dt:%Y}", f"/{dt:%Y}/"), (f"{dt:%B %Y}", f"/{dt:%Y/%m}/"), (f"{dt.day} {dt:%B}", day_path(dt))]
        c_html, c_ld = crumbs(trail)
        all_items = [a for _, v in sorted(eds_day.items()) for a in v]
        title = f"Cannabis news for {dt.day} {dt:%B %Y}"
        body = (f'{c_html}<div class="page-h"><h1>{escape(_day_label(dt))}</h1>'
                f'<p class="meta">{len(eds_day)} {"edition" if len(eds_day) == 1 else "editions"} · {n} {"story" if n == 1 else "stories"}</p></div>'
                f'{blocks}<nav class="more-link pager" aria-label="Other days">{" · ".join(nav)}</nav>')
        lead = all_items[0]["headline"] if all_items else ""
        desc = f"Every MetaFlora News cannabis story from {_day_label(dt)}: {n} stories from the {'morning and evening editions' if len(eds_day) > 1 else 'day’s edition'}. Lead: {lead}"
        T.ctx["write"](day_path(dt).strip("/") + "/index.html",
                       T.page(title, body, desc=desc, path=day_path(dt), dateline=T.dl(_day_label(dt), "Daily archive"),
                              extra_head=T.collection_ld(title, day_path(dt), all_items) + c_ld))
        ARCHIVE_URLS.append((day_path(dt), newest.isoformat()))
    for ym, ds in months.items():
        dt = datetime.fromisoformat(ym + "-01")
        rows, total, newest = [], 0, None
        for d in sorted(ds, reverse=True):
            items = [a for v in days[d].values() for a in v]
            total += len(items)
            top = max(a["_dt"] for a in items)
            newest = max(newest, top) if newest else top
            dd = datetime.fromisoformat(d)
            rows.append(f'<li><a class="li-title" href="{day_path(dd)}">{escape(_day_label(dd))}</a>'
                        f'<span class="meta">{len(days[d])} {"edition" if len(days[d]) == 1 else "editions"} · {len(items)} stories</span></li>')
        path = f"/{dt:%Y/%m}/"
        c_html, c_ld = crumbs([HOME, ("Archive", "/archive/"), (f"{dt:%Y}", f"/{dt:%Y}/"), (f"{dt:%B %Y}", path)])
        body = (f'{c_html}<div class="page-h"><h1>{dt:%B %Y}: cannabis news by day</h1><p class="meta">{len(ds)} days · {total} stories · '
                f'<a href="/archive/{dt:%Y/%m}/">Every story this month on one page</a></p></div><ol class="month-list">{"".join(rows)}</ol>')
        T.ctx["write"](path.strip("/") + "/index.html",
                       T.page(f"Cannabis news by day, {dt:%B %Y}", body, path=path,
                              desc=f"MetaFlora News by day for {dt:%B %Y}: {total} cannabis news stories across {len(ds)} days of morning and evening editions.",
                              extra_head=c_ld))
        ARCHIVE_URLS.append((path, newest.isoformat()))
    for y, yms in years.items():
        rows = []
        for ym in sorted(yms, reverse=True):
            dt = datetime.fromisoformat(ym + "-01")
            n = sum(len(v) for d in months[ym] for v in days[d].values())
            rows.append(f'<li><a class="li-title" href="/{dt:%Y/%m}/">{dt:%B %Y}</a><span class="meta">{len(months[ym])} days · {n} stories</span></li>')
        c_html, c_ld = crumbs([HOME, ("Archive", "/archive/"), (y, f"/{y}/")])
        body = f'{c_html}<div class="page-h"><h1>{y}: cannabis news by month</h1></div><ol class="month-list">{"".join(rows)}</ol>'
        T.ctx["write"](f"{y}/index.html", T.page(f"Cannabis news archive, {y}", body, path=f"/{y}/",
                                                 desc=f"Every month of MetaFlora News cannabis coverage in {y}, with each day's morning and evening editions.",
                                                 extra_head=c_ld))
        ARCHIVE_URLS.append((f"/{y}/", max(a["_dt"] for ym in yms for d in months[ym] for v in days[d].values() for a in v).isoformat()))
    return sorted(years)
