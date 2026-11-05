"""Cannabis stocks strip: last close and % change, fetched at build time.

Omitted entirely if the fetch fails (never shows stale data).
"""
import json
import urllib.request
from datetime import datetime, timezone

TICKERS = [("MSOS", "MSOS"), ("CURLF", "Curaleaf"), ("GTBIF", "Green Thumb"), ("TCNNF", "Trulieve"), ("VRNOF", "Verano"),
           ("TLRY", "Tilray"), ("CGC", "Canopy"), ("SNDL", "SNDL"), ("OGI", "Organigram"), ("ACB", "Aurora")]


def _one(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MetaFlora News build)"})
    with urllib.request.urlopen(req, timeout=8) as r:
        res = json.loads(r.read())["chart"]["result"][0]
    closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
    if len(closes) < 2:
        raise ValueError("not enough data")
    ts = res["timestamp"][-1]
    return closes[-1], (closes[-1] / closes[-2] - 1) * 100, datetime.fromtimestamp(ts, timezone.utc)


def fetch():
    rows, last = [], None
    for sym, name in TICKERS:
        try:
            price, chg, when = _one(sym)
        except Exception:  # noqa: BLE001
            continue
        rows.append({"sym": sym, "name": name, "price": price, "chg": chg})
        last = max(last, when) if last else when
    if len(rows) < 6:
        return None
    return {"rows": rows, "asof": last}
