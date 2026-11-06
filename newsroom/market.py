"""Cannabis stocks: one year of daily closes per ticker, fetched at build time.

Feeds the market strip and the /stocks/ pages. Every successful fetch is cached to
content/market.json (committed by the publish workflow); if a fetch fails the cache is used,
labelled with its real as-of date. Nothing is ever shown without a date.
"""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / "content" / "market.json"

# sym, short name, full name, tags that link our coverage, one-line profile
TICKERS = [
    ("MSOS", "MSOS", "AdvisorShares Pure US Cannabis ETF", ["MSOS", "Cannabis stocks"],
     "An exchange-traded fund that holds US cannabis operators. Its daily move is the market's shorthand for how US cannabis stocks are trading."),
    ("CURLF", "Curaleaf", "Curaleaf Holdings", ["Curaleaf"],
     "A US multi-state cannabis operator with retail, cultivation and manufacturing across many states and international operations."),
    ("GTBIF", "Green Thumb", "Green Thumb Industries", ["Green Thumb", "Green Thumb Industries"],
     "A US multi-state cannabis operator that makes branded cannabis products and runs its own dispensaries."),
    ("VRNO", "Verano", "Verano Holdings", ["Verano", "Verano Holdings"],
     "A US multi-state cannabis operator with cultivation, consumer brands and its own dispensaries."),
    ("TLRY", "Tilray", "Tilray Brands", ["Tilray", "Tilray Brands"],
     "A cannabis and consumer-products company with medical cannabis operations in Europe and a beverage business."),
    ("CGC", "Canopy", "Canopy Growth", ["Canopy Growth", "Canopy"],
     "A Canadian cannabis producer with consumer brands sold in Canada and abroad."),
    ("SNDL", "SNDL", "SNDL Inc.", ["SNDL"],
     "A Canadian cannabis producer and retailer that also runs a large liquor retail business."),
    ("OGI", "Organigram", "Organigram Global", ["Organigram"],
     "A Canadian licensed producer of cannabis flower, vapes, pre-rolls and edibles."),
    ("ACB", "Aurora", "Aurora Cannabis", ["Aurora Cannabis", "Aurora"],
     "A Canadian cannabis company focused on medical cannabis in Canada and international markets."),
]
META = {t[0]: {"name": t[1], "full": t[2], "tags": t[3], "about": t[4]} for t in TICKERS}


def _one(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1y&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MetaFlora News build)"})
    with urllib.request.urlopen(req, timeout=10) as r:
        res = json.loads(r.read())["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    pts = [(t, c, v) for t, c, v in zip(res["timestamp"], q["close"], q.get("volume") or [None] * len(q["close"])) if c is not None]
    if len(pts) < 20:
        raise ValueError("not enough data")
    return [{"t": datetime.fromtimestamp(t, timezone.utc).date().isoformat(), "c": round(c, 4), "v": v} for t, c, v in pts]


def _shape(raw):
    """Turn {sym: [points]} into rows with the numbers the pages use."""
    rows = []
    for sym, *_ in TICKERS:
        pts = raw.get(sym)
        if not pts or len(pts) < 20:
            continue
        closes = [p["c"] for p in pts]
        last, prev = closes[-1], closes[-2]
        def back(n):
            return (last / closes[-1 - n] - 1) * 100 if len(closes) > n else None
        year = pts[-1]["t"][:4]
        ytd_base = next((p["c"] for p in reversed(pts) if p["t"][:4] < year), closes[0])
        hi = max(pts, key=lambda p: p["c"])
        lo = min(pts, key=lambda p: p["c"])
        vols = [p["v"] for p in pts[-20:] if p.get("v")]
        rows.append({"sym": sym, **META[sym], "price": last, "chg": (last / prev - 1) * 100,
                     "w1": back(5), "m1": back(21), "m3": back(63), "y1": (last / closes[0] - 1) * 100,
                     "ytd": (last / ytd_base - 1) * 100, "hi": hi, "lo": lo,
                     "vol": pts[-1].get("v"), "avgvol": sum(vols) / len(vols) if vols else None,
                     "date": pts[-1]["t"], "points": pts})
    return rows


def fetch():
    raw, fresh = {}, True
    for sym, *_ in TICKERS:
        try:
            raw[sym] = _one(sym)
        except Exception:  # noqa: BLE001
            continue
    if len(raw) >= 6:
        CACHE.write_text(json.dumps({"fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"), "series": raw}, separators=(",", ":")))
    elif CACHE.exists():
        raw, fresh = json.loads(CACHE.read_text())["series"], False
    else:
        return None
    rows = _shape(raw)
    if len(rows) < 6:
        return None
    asof = max(r["date"] for r in rows)
    return {"rows": rows, "asof": datetime.fromisoformat(asof), "fresh": fresh}


def cached():
    """Market data from the committed cache only (used by --no-media builds)."""
    if not CACHE.exists():
        return None
    rows = _shape(json.loads(CACHE.read_text())["series"])
    if len(rows) < 6:
        return None
    return {"rows": rows, "asof": datetime.fromisoformat(max(r["date"] for r in rows)), "fresh": False}
