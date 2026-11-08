"""Cannabis stock pages: /stocks/ and /stocks/<sym>/.

Each page carries a daily market note written from the closing data (no opinions, no forecasts),
a one-year chart, the key numbers, MetaFlora News coverage of the company and links to its peers.
Rebuilt on every publish and by the weekday after-close run, so the note is new each trading day.
"""
import json
from datetime import datetime
from html import escape

import ads
import templates as T


def money(x):
    return f"${x:,.2f}" if x >= 1 else f"${x:,.3f}"


def pct(x, signed=True):
    if x is None:
        return "n/a"
    return f"{x:+.1f}%" if signed else f"{abs(x):.1f}%"


def cls(x):
    return "" if x is None else ("up" if x >= 0 else "down")


def day(iso, year=False):
    d = datetime.fromisoformat(iso)
    return f"{d:%A} {d.day} {d:%B}" + (f" {d.year}" if year else "")


def short(iso):
    d = datetime.fromisoformat(iso)
    return f"{d.day} {d:%b %Y}"


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def moved(x):
    return f"rose {abs(x):.1f}%" if x > 0.05 else (f"fell {abs(x):.1f}%" if x < -0.05 else "was flat")


def trend(x):
    return "n/a" if x is None else (f"up {abs(x):.1f}%" if x >= 0 else f"down {abs(x):.1f}%")


def note(r, rows):
    """The daily market note: plain sentences built only from the numbers."""
    ranked = sorted(rows, key=lambda x: x["chg"], reverse=True)
    pos = next(i for i, x in enumerate(ranked, 1) if x["sym"] == r["sym"])
    etf = next((x for x in rows if x["sym"] == "MSOS"), None)
    p = [f'{escape(r["full"])} ({r["sym"]}) {moved(r["chg"])} to {money(r["price"])} on {day(r["date"])}, its latest close.']
    if r["sym"] == "MSOS":
        ups = sum(1 for x in rows if x["chg"] > 0 and x["sym"] != "MSOS")
        p.append(f'Of the {len(rows) - 1} cannabis companies we track, {ups} closed higher. '
                 f'The best move was {escape(ranked[0]["name"])} ({pct(ranked[0]["chg"])}); the weakest was {escape(ranked[-1]["name"])} ({pct(ranked[-1]["chg"])}).')
    else:
        rank = "the best" if pos == 1 else ("the weakest" if pos == len(rows) else f"the {ordinal(pos)}-best")
        line = f"That was {rank} move of the {len(rows)} cannabis stocks we track."
        if etf:
            line += f' MSOS, the US cannabis ETF, {moved(etf["chg"])}.'
        p.append(line)
    p.append(f'Over the past week the stock is {trend(r["w1"])}, over a month {trend(r["m1"])} and over three months {trend(r["m3"])}. '
             f'Since the start of {r["date"][:4]} it is {trend(r["ytd"])}.')
    below = (1 - r["price"] / r["hi"]["c"]) * 100
    above = (r["price"] / r["lo"]["c"] - 1) * 100
    p.append(f'It closed {below:.1f}% below its 52-week high of {money(r["hi"]["c"])} ({short(r["hi"]["t"])}) '
             f'and {above:.1f}% above its 52-week low of {money(r["lo"]["c"])} ({short(r["lo"]["t"])}).')
    if r.get("vol") and r.get("avgvol"):
        ratio = r["vol"] / r["avgvol"]
        word = "well above" if ratio >= 1.5 else ("below" if ratio < 0.75 else "close to")
        p.append(f'Volume was {r["vol"]:,.0f} shares, {word} its 20-day average of {r["avgvol"]:,.0f}.')
    return "".join(f"<p>{x}</p>" for x in p)


def chart(r, w=760, h=260):
    pts = r["points"]
    cs = [p["c"] for p in pts]
    lo, hi = min(cs), max(cs)
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    def x(i):
        return round(i * w / (len(pts) - 1), 1)
    def y(c):
        return round(h - (c - lo) / (hi - lo) * h, 1)
    line = " ".join(f"{x(i)},{y(c)}" for i, c in enumerate(cs))
    up = cs[-1] >= cs[0]
    col = "var(--up)" if up else "var(--down)"
    grid = "".join(f'<line x1="0" x2="{w}" y1="{h * k / 4}" y2="{h * k / 4}" class="g"/>' for k in (1, 2, 3))
    first, last = short(pts[0]["t"]), short(pts[-1]["t"])
    return (f'<figure class="stk-chart"><svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" role="img" '
            f'aria-label="{escape(r["full"])} one-year price chart, from {money(cs[0])} on {first} to {money(cs[-1])} on {last}">'
            f'{grid}<polyline points="0,{h} {line} {w},{h}" class="a" style="fill:{col}"/>'
            f'<polyline points="{line}" class="l" style="stroke:{col}"/></svg>'
            f'<figcaption><span>{first}</span><span>One year · daily closes · high {money(r["hi"]["c"])} · low {money(r["lo"]["c"])}</span><span>{last}</span></figcaption></figure>')


def spark(r, w=120, h=32):
    cs = [p["c"] for p in r["points"][-63:]]
    lo, hi = min(cs), max(cs)
    rng = (hi - lo) or 1
    line = " ".join(f"{round(i * w / (len(cs) - 1), 1)},{round(h - (c - lo) / rng * h, 1)}" for i, c in enumerate(cs))
    col = "var(--up)" if cs[-1] >= cs[0] else "var(--down)"
    return f'<svg class="spark" viewBox="0 0 {w} {h}" aria-hidden="true"><polyline points="{line}" style="stroke:{col}"/></svg>'


def coverage(r, arts):
    """Stories tagged with this company (tags are canonical names, so no loose word matching)."""
    keys = {t.lower() for t in r["tags"]}
    return [a for a in arts if keys & {t.lower() for t in a.get("tags", [])}]


def stats(r):
    cells = [("Close", money(r["price"]), ""), ("Day", pct(r["chg"]), cls(r["chg"])), ("1 week", pct(r["w1"]), cls(r["w1"])),
             ("1 month", pct(r["m1"]), cls(r["m1"])), ("3 months", pct(r["m3"]), cls(r["m3"])), ("Year to date", pct(r["ytd"]), cls(r["ytd"])),
             ("1 year", pct(r["y1"]), cls(r["y1"])), ("52-week high", money(r["hi"]["c"]), ""), ("52-week low", money(r["lo"]["c"]), "")]
    if r.get("ma50"):
        cells.append(("50-day average", money(r["ma50"]), ""))
    if r.get("ma200"):
        cells.append(("200-day average", money(r["ma200"]), ""))
    if r.get("mdd") is not None:
        cells.append(("Max drawdown (1y)", pct(r["mdd"]), "down" if r["mdd"] < 0 else ""))
    if r.get("vs_msos") is not None:
        cells.append(("1y vs MSOS", f'{r["vs_msos"]:+.1f} pts', cls(r["vs_msos"])))
    if r.get("avgvol"):
        cells.append(("Avg volume (20d)", f'{r["avgvol"]:,.0f}', ""))
    return '<dl class="stk-stats">' + "".join(f'<div><dt>{k}</dt><dd class="{c}">{v}</dd></div>' for k, v, c in cells) + "</dl>"


def table(rows, current=None):
    def prof(sym):
        return f' <a class="tk-prof" href="/company/{PROFILES[sym][0]}/">Profile</a>' if sym in PROFILES else ""
    body = "".join(
        f'<tr{" aria-current=true" if r["sym"] == current else ""}><th scope="row"><a href="/stocks/{r["sym"].lower()}/">{escape(r["name"])}</a>'
        f'<span class="tk">{r["sym"]}</span>{prof(r["sym"])}</th><td>{money(r["price"])}</td><td class="{cls(r["chg"])}">{pct(r["chg"])}</td>'
        f'<td class="{cls(r["m1"])}">{pct(r["m1"])}</td><td class="{cls(r["ytd"])}">{pct(r["ytd"])}</td><td class="sp">{spark(r)}</td></tr>'
        for r in rows)
    return ('<div class="stk-table-wrap"><table class="stk-table"><thead><tr><th scope="col">Company</th><th scope="col">Close</th><th scope="col">Day</th>'
            f'<th scope="col">1M</th><th scope="col">YTD</th><th scope="col" class="sp">3M</th></tr></thead><tbody>{body}</tbody></table></div>')


SOURCE = ('<p class="stk-src">End-of-day closing prices from Yahoo Finance, in US dollars. '
          'This page is generated automatically from market data every trading day. It is not investment advice. '
          '<a href="/how-we-report/">How we report</a></p>')


def profiles():
    """Ticker symbol -> (company hub slug, short name, full name) for every company profile."""
    import glob
    from pathlib import Path
    out, seen = {}, []
    root = Path(__file__).resolve().parent.parent / "content" / "hubs" / "companies"
    for f in sorted(root.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        slug = d["id"].split("/")[-1]
        seen.append((slug, d.get("short_name") or d["name"], d["name"], [t["symbol"] for t in d.get("tickers", [])]))
        for t in d.get("tickers", []):
            out.setdefault(t["symbol"], (slug, d.get("short_name") or d["name"], d["name"]))
    return out, seen


PROFILES, ALL_COMPANIES = profiles()


def profile_link(sym, cls="stk-profile"):
    p = PROFILES.get(sym)
    if not p:
        return ""
    return f'<p class="{cls}"><a href="/company/{p[0]}/">{escape(p[2])}: company profile &rarr;</a></p>'


def share_row(url, text):
    from urllib.parse import quote
    return (f'<p class="share stk-share"><a href="https://x.com/intent/post?text={quote(text)}&url={quote(url)}&via={T.X_HANDLE}" target="_blank" rel="noopener">Post on X</a>'
            f'<a href="https://www.linkedin.com/sharing/share-offsite/?url={quote(url)}" target="_blank" rel="noopener">LinkedIn</a>'
            f'<button type="button" data-copy="{escape(url)}">Copy link</button></p>')


def stock_post(r):
    return f'{r["full"]} ({r["sym"]}) {moved(r["chg"])} to {money(r["price"])} at the close on {day(r["date"])}.'


def x_posts(m):
    """Ready-for-X posts for the stocks desk: the daily wrap and the day's biggest mover (facts only)."""
    from urllib.parse import urlencode
    import notify_logic as L
    if not m:
        return []
    rows = m["rows"]
    asof = max(r["date"] for r in rows)
    ranked = sorted([x for x in rows if x["sym"] != "MSOS"], key=lambda x: x["chg"], reverse=True)
    etf = next((x for x in rows if x["sym"] == "MSOS"), None)
    ups = sum(1 for x in ranked if x["chg"] > 0)
    wrap = (f"Cannabis stocks at the close, {day(asof)}: {ups} of {len(ranked)} higher. "
            f"{ranked[0]['name']} {pct(ranked[0]['chg'])}, {ranked[-1]['name']} {pct(ranked[-1]['chg'])}"
            + (f"; MSOS {pct(etf['chg'])}" if etf else "") + ". Charts and news for every name:")
    mover = max(ranked, key=lambda x: abs(x["chg"]))
    mtext = stock_post(mover) + " The biggest move among the cannabis stocks we track."
    out = []
    for key, label, text, url in ((f"stocks-{asof}", "Stocks wrap", wrap, f"{T.SITE}/stocks/"),
                                  (f"mover-{asof}", f"Biggest mover · {mover['sym']}", mtext, f"{T.SITE}/stocks/{mover['sym'].lower()}/")):
        text = L.X_TAGS.join([text[: L.X_LIMIT - L.X_URL_LEN - 2 - len(L.X_TAGS)], ""]) if len(text) > 200 else text + L.X_TAGS
        out.append({"key": key, "edition": f"Close {short(asof)}", "label": label, "rank": 0, "headline": label, "text": text, "url": url,
                    "intent": "https://x.com/intent/post?" + urlencode({"text": text, "url": url})})
    return out


def companies_block():
    lis = "".join(f'<li><a href="/company/{slug}/">{escape(full)}</a><span class="tk">{" · ".join(dict.fromkeys(syms))}</span></li>'
                  for slug, short, full, syms in ALL_COMPANIES)
    return (f'<section class="block stk-companies"><h2 class="sec-label"><a href="/company/">Company profiles</a></h2>'
            f'<ul class="co-grid">{lis}</ul></section>')


def build_stocks(arts, m):
    """Returns [(path, lastmod)] for the sitemap."""
    if not m:
        return []
    rows = m["rows"]
    etf = next((x for x in rows if x["sym"] == "MSOS"), None)
    for r in rows:
        r["vs_msos"] = (r["y1"] - etf["y1"]) if etf and r["sym"] != "MSOS" else None
    out = []
    for r in rows:
        sym = r["sym"].lower()
        path = f"/stocks/{sym}/"
        cov = coverage(r, arts)
        if cov:
            cov_html = (f'<section class="block"><h2 class="sec-label">MetaFlora News on {escape(r["name"])}</h2>'
                        f'<ol class="latest-list">{"".join(T.list_item(a) for a in cov[:12])}</ol>'
                        f'<p class="more-link"><a href="/topic/{T.slug(r["tags"][0])}/">All {escape(r["tags"][0])} coverage</a></p></section>')
        else:
            mk = [a for a in arts if a["cat"] == "Markets"][:6] or arts[:6]
            cov_html = (f'<section class="block"><h2 class="sec-label">Latest cannabis markets news</h2>'
                        f'<ol class="latest-list">{"".join(T.list_item(a) for a in mk)}</ol></section>')
        peers = [x for x in rows if x["sym"] != r["sym"]]
        from card import render_stock_card
        og = T.ctx["out"] / "og" / "stocks" / f"{sym}.png"
        render_stock_card(r, og, og.with_suffix(".jpg"))
        title = f'{r["name"]} stock ({r["sym"]}) today: price, chart and news'
        desc = (f'{r["full"]} ({r["sym"]}) {moved(r["chg"])} to {money(r["price"])} on {short(r["date"])}. '
                f'One-year chart, 52-week range and cannabis industry news, updated every trading day.')
        body = f"""<article class="stock">
  <header class="stk-head">
    <p class="kicker"><a href="/stocks/">Cannabis stocks</a></p>
    <h1>{escape(r["full"])} <span class="tk">{r["sym"]}</span></h1>
    <p class="stk-price"><b>{money(r["price"])}</b> <span class="{cls(r["chg"])}">{pct(r["chg"])}</span>
      <span class="meta">Close, {day(r["date"], True)}</span></p>
    {share_row(T.SITE + path, stock_post(r))}
    {profile_link(r["sym"])}
  </header>
  {chart(r)}
  <div class="stk-cols">
    <div class="stk-main">
      <h2 class="sec-label">Market note · {day(r["date"])}</h2>
      <div class="story-body">{note(r, rows)}</div>
      <h2 class="sec-label">About</h2>
      <div class="story-body"><p>{escape(r["about"])}</p></div>
      {SOURCE}
    </div>
    <aside class="stk-side">{stats(r)}</aside>
  </div>
  {ads.slot("stock-" + sym, 0, "list")}
  {cov_html}
  <section class="block"><h2 class="sec-label">Other cannabis stocks</h2>{table(peers)}</section>
</article>"""
        ld = {"@context": "https://schema.org", "@type": "WebPage", "name": title, "description": desc, "url": T.SITE + path,
              "dateModified": r["date"], "isPartOf": {"@id": T.SITE + "/#website"}, "publisher": {"@id": T.SITE + "/#org"},
              "about": {"@type": "Corporation", "name": r["full"], "tickerSymbol": r["sym"]} if r["sym"] != "MSOS"
              else {"@type": "FinancialProduct", "name": r["full"], "category": "Exchange-traded fund"}}
        crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": T.NAME, "item": T.SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Cannabis stocks", "item": T.SITE + "/stocks/"},
            {"@type": "ListItem", "position": 3, "name": f'{r["name"]} ({r["sym"]})', "item": T.SITE + path}]}
        extra = f'<script type="application/ld+json">{json.dumps(ld)}</script><script type="application/ld+json">{json.dumps(crumbs)}</script>'
        T.ctx["write"](f"stocks/{sym}/index.html", T.page(title, body, desc=desc, path=path, extra_head=extra, active="Stocks",
                                                         og_image=f"{T.SITE}/og/stocks/{sym}.png",
                                                         dateline=T.dl("Cannabis stocks", f"Close {short(r['date'])}")))
        out.append((path, r["date"]))
    asof = max(r["date"] for r in rows)
    ranked = sorted([x for x in rows if x["sym"] != "MSOS"], key=lambda x: x["chg"], reverse=True)
    ups = sum(1 for x in ranked if x["chg"] > 0)
    etf = next((x for x in rows if x["sym"] == "MSOS"), None)
    lead = (f'<p>{ups} of {len(ranked)} cannabis stocks closed higher on {day(asof)}. '
            f'{escape(ranked[0]["name"])} led ({pct(ranked[0]["chg"])}) and {escape(ranked[-1]["name"])} lagged ({pct(ranked[-1]["chg"])}).'
            + (f' MSOS, the US cannabis ETF, {moved(etf["chg"])}.' if etf else "") + "</p>")
    if etf:
        from card import render_stock_card
        og = T.ctx["out"] / "og" / "stocks" / "index.png"
        render_stock_card(etf, og, og.with_suffix(".jpg"), title="Cannabis stocks today", kicker="MSOS · US cannabis ETF")
    body = (f'<div class="page-h"><h1>Cannabis stocks today</h1><p class="meta">Close {day(asof, True)} · updated every trading day</p>'
            f'{share_row(T.SITE + "/stocks/", "Cannabis stocks today: closing prices, charts and news.")}</div>'
            f'<div class="story-body stk-lead">{lead}</div>{table(rows)}{companies_block()}{ads.slot("stocks-index", 0, "list")}{SOURCE}')
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Cannabis stocks today", "url": T.SITE + "/stocks/", "dateModified": asof,
          "hasPart": [{"@type": "WebPage", "url": f'{T.SITE}/stocks/{r["sym"].lower()}/', "name": f'{r["name"]} ({r["sym"]})'} for r in rows]}
    T.ctx["write"]("stocks/index.html", T.page("Cannabis stocks today", body, path="/stocks/", active="Stocks",
                                               og_image=f"{T.SITE}/og/stocks/index.png" if etf else None,
                                               desc=f"Cannabis stocks today: closing prices, daily and year-to-date moves for {len(ranked)} cannabis companies and the MSOS ETF, with charts and news.",
                                               extra_head=f'<script type="application/ld+json">{json.dumps(ld)}</script>',
                                               dateline=T.dl("Cannabis stocks", f"Close {short(asof)}")))
    out.insert(0, ("/stocks/", asof))
    return out
