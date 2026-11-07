"""MetaFlora News social card (1200x630): the image X, LinkedIn, Telegram and push alerts show.

Design board pick A, "front page" (6 Nov 2026, 2-1): the site's own editorial system. Flat #131313
ground, the nameplate (cube + METAFLORA, NEWS in lime on a ruled line), a green section kicker, a big
Newsreader headline sized by line count with balanced breaks, an Inter Tight dek, and a hairline
footer with the date. Lime appears only in NEWS. No web address in the bottom-left (X overlays its
own domain label there). Writes <id>.png (og:image) and <id>.jpg (push alert image).
"""
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
FONTS = HERE / "assets" / "fonts"
W, H = 1200, 630
X0, X1 = 72, W - 72
FOOT_RULE = 566
BG, RULE = (19, 19, 19), (42, 42, 42)
FG, DEK, META = (242, 242, 242), (201, 201, 201), (154, 154, 154)
LIME, GREEN = (163, 230, 53), (124, 212, 112)


def serif(size, wght=500):
    f = ImageFont.truetype(str(FONTS / "Newsreader.ttf"), size)
    f.set_variation_by_axes([wght, min(72, max(6, size * 0.75))])  # axes: weight, optical size
    return f


def sans(size, wght=600):
    f = ImageFont.truetype(str(FONTS / "InterTight.ttf"), size)
    f.set_variation_by_axes([wght])
    return f


def mono(size, wght=500):
    f = ImageFont.truetype(str(FONTS / "JetBrainsMono.ttf"), size)
    f.set_variation_by_axes([wght])
    return f


def _greedy(d, words, font, width):
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if not cur or d.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur]


def balanced(d, text, font, width):
    """Fewest lines that fit, then the narrowest width that keeps that count (balances the rag
    and avoids a lone short word on the last line)."""
    words = text.split()
    lines = _greedy(d, words, font, width)
    n, best, w = len(lines), lines, width
    while w > width * 0.55:
        w -= 8
        trial = _greedy(d, words, font, w)
        if len(trial) != n or any(d.textlength(t, font=font) > width for t in trial):
            break
        best = trial
    return best


def clamp(d, text, font, width, max_lines):
    lines = _greedy(d, text.split(), font, width)
    if len(lines) <= max_lines:
        return lines
    lines = lines[:max_lines]
    while lines[-1] and d.textlength(lines[-1] + "…", font=font) > width:
        lines[-1] = lines[-1].rsplit(" ", 1)[0] if " " in lines[-1] else lines[-1][:-1]
    lines[-1] = lines[-1].rstrip(",;:—-") + "…"
    return lines


def tracked(d, xy, text, font, fill, track):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + track
    return x


def nameplate(img, d, x, y):
    """Cube + METAFLORA (Casanova Scotia) and NEWS in lime between two rules; ~340px wide."""
    cube = Image.open(HERE / "assets" / "metaflora-cube.png").convert("RGBA")
    ch = 52
    cube = cube.resize((round(ch * cube.width / cube.height), ch), Image.LANCZOS)
    f = ImageFont.truetype(str(FONTS / "CasanovaScotia.otf"), 44)
    tw = d.textlength("METAFLORA", font=f)
    total = cube.width + 15 + tw
    img.paste(cube, (x, y), cube)
    d.text((x + cube.width + 15, y + 5), "METAFLORA", font=f, fill=FG)
    nf, track = sans(16, 700), 8
    news_w = d.textlength("NEWS", font=nf) + track * 3
    ny, cx = y + ch + 12, x + total / 2
    ry = ny + 9
    d.line([(x, ry), (cx - news_w / 2 - 16, ry)], fill=(58, 58, 58), width=1)
    d.line([(cx + news_w / 2 + 16, ry), (x + total, ry)], fill=(58, 58, 58), width=1)
    tracked(d, (cx - news_w / 2, ny), "NEWS", nf, LIME, track)
    return ny + 20


def render_card(a, out_png, out_jpg=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    y = nameplate(img, d, X0, 52) + 46

    tracked(d, (X0, y), a["cat"].upper(), sans(18, 700), GREEN, 2.5)
    y += 44

    # headline: 76 px when it fits in 2 lines, otherwise 62 px in 3; never 4
    for size, max_lines in ((76, 2), (62, 3), (56, 3)):
        hf = serif(size)
        lines = balanced(d, a["headline"], hf, X1 - X0)
        if len(lines) <= max_lines:
            break
    else:
        lines = clamp(d, a["headline"], hf, X1 - X0, 3)
    step = round(hf.size * 1.08)
    for ln in lines:
        d.text((X0, y), ln, font=hf, fill=FG)
        y += step
    y += 18

    # dek: 2 lines (1 when the headline takes 3), only if it leaves 32 px above the footer rule
    df, dstep = sans(27, 500), 36
    room = (FOOT_RULE - 32 - y) // dstep
    dek_lines = min(2 if len(lines) <= 2 else 1, room)
    if dek_lines > 0:
        for ln in clamp(d, a["dek"], df, X1 - X0, dek_lines):
            d.text((X0, y), ln, font=df, fill=DEK)
            y += dstep

    d.line([(X0, FOOT_RULE), (X1, FOOT_RULE)], fill=RULE, width=1)
    dt = datetime.fromisoformat(a["published"])
    d.text((X1, FOOT_RULE + 18), f"{dt.day} {dt:%b %Y}".upper(), font=mono(19), fill=META, anchor="ra")

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png, optimize=True)
    if out_jpg:
        img.save(out_jpg, quality=85, optimize=True, progressive=True)
    return img


UP, DOWN = (124, 212, 112), (239, 107, 107)


def render_stock_card(r, out_png, out_jpg=None, title=None, kicker="Cannabis stocks"):
    """Stock page card: nameplate, kicker, company + ticker, close and day move, one-year chart."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    y = nameplate(img, d, X0, 52) + 40
    tracked(d, (X0, y), kicker.upper(), sans(18, 700), GREEN, 2.5)
    y += 40
    name = title or r["full"]
    tick = r["sym"]
    tf = mono(26)
    room = X1 - X0 - d.textlength("  " + tick, font=tf) - 12
    size = 62
    while size > 40 and d.textlength(name, font=serif(size)) > room:
        size -= 2
    nf = serif(size)
    d.text((X0, y), name, font=nf, fill=FG)
    if not title:
        d.text((X0 + d.textlength(name, font=nf) + 18, y + size * 0.42), tick, font=tf, fill=META)
    y += round(size * 1.18)
    price = f"${r['price']:,.2f}" if r["price"] >= 1 else f"${r['price']:,.3f}"
    pf = mono(46, 600)
    d.text((X0, y), price, font=pf, fill=FG)
    chg = r["chg"]
    d.text((X0 + d.textlength(price, font=pf) + 22, y + 10), f"{chg:+.1f}%", font=mono(34, 600), fill=UP if chg >= 0 else DOWN)
    y += 74

    # one-year chart, full width above the footer rule
    pts = [p["c"] for p in r["points"]]
    top, bot = y + 6, FOOT_RULE - 18
    lo, hi = min(pts), max(pts)
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    xs = [X0 + i * (X1 - X0) / (len(pts) - 1) for i in range(len(pts))]
    ys = [bot - (c - lo) / (hi - lo) * (bot - top) for c in pts]
    col = UP if pts[-1] >= pts[0] else DOWN
    for k in (1, 2, 3):
        gy = top + (bot - top) * k / 4
        d.line([(X0, gy), (X1, gy)], fill=(34, 34, 34), width=1)
    fill = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(fill).polygon([(X0, bot)] + list(zip(xs, ys)) + [(X1, bot)], fill=col + (26,))
    img.paste(fill, (0, 0), fill)
    d.line(list(zip(xs, ys)), fill=col, width=3, joint="curve")

    d.line([(X0, FOOT_RULE), (X1, FOOT_RULE)], fill=RULE, width=1)
    d.text((X0, FOOT_RULE + 18), "1 YEAR · DAILY CLOSES", font=mono(17), fill=META)
    dt = datetime.fromisoformat(r["date"])
    d.text((X1, FOOT_RULE + 18), f"CLOSE {dt.day} {dt:%b %Y}".upper(), font=mono(19), fill=META, anchor="ra")
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png, optimize=True)
    if out_jpg:
        img.save(out_jpg, quality=85, optimize=True, progressive=True)
    return img
