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


def render_photo_card(a, photo, out_png, out_jpg=None):
    """Design board pick "A Cover" (8 Nov 2026): the story's photo full-bleed, a dark fade from the left and the
    bottom, the nameplate top-left, green section kicker and Newsreader headline bottom-left, and
    "AI illustration · date" bottom-right (X puts its own domain label bottom-left). Falls back to render_card
    when there is no photo."""
    if not photo:
        return render_card(a, out_png, out_jpg)
    from PIL import ImageChops
    src = Image.open(photo).convert("RGB")
    s = max(W / src.width, H / src.height)
    src = src.resize((round(src.width * s), round(src.height * s)), Image.LANCZOS)
    left, top = (src.width - W) // 2, (src.height - H) // 2
    img = src.crop((left, top, left + W, top + H))
    # fade to #131313: from the left (0.94 -> 0.80 at 38% -> 0.15 at 72% -> 0) and from the bottom (0.85 -> 0 at 45%)
    def ramp(n, xs, ys):  # piecewise-linear 0..1 ramp sampled at n points
        out = []
        for i in range(n):
            t = i / (n - 1)
            for k in range(len(xs) - 1):
                if xs[k] <= t <= xs[k + 1]:
                    out.append(ys[k] + (ys[k + 1] - ys[k]) * (t - xs[k]) / (xs[k + 1] - xs[k]))
                    break
        return out
    ax = Image.new("L", (W, 1)); ax.putdata([round(255 * (1 - v)) for v in ramp(W, [0, .38, .72, 1], [.94, .80, .15, 0])])
    ay = Image.new("L", (1, H)); ay.putdata([round(255 * (1 - v)) for v in ramp(H, [0, .55, 1], [0, 0, .85])])
    keep = ImageChops.multiply(ax.resize((W, H)), ay.resize((W, H)))  # share of the photo that shows through
    img = Image.composite(img, Image.new("RGB", (W, H), BG), keep)
    d = ImageDraw.Draw(img)
    nameplate(img, d, 64, 52)

    # headline: bottom-anchored in a 640 px column; 60 px up to 3 lines, then 54, then 48 px up to 4
    col = 640
    for size, max_lines in ((60, 3), (54, 3), (48, 4)):
        hf = serif(size)
        lines = balanced(d, a["headline"], hf, col)
        if len(lines) <= max_lines:
            break
    else:
        lines = clamp(d, a["headline"], hf, col, 4)
    step = round(hf.size * 1.08)
    y = H - 70 - step * len(lines)
    tracked(d, (64, y - 38), a["cat"].upper(), sans(17, 700), GREEN, 2.5)
    for ln in lines:
        d.text((64, y), ln, font=hf, fill=FG)
        y += step
    dt = datetime.fromisoformat(a["published"])
    d.text((W - 56, H - 28), f"AI ILLUSTRATION · {dt.day} {dt:%b %Y}".upper(), font=mono(15), fill=META, anchor="rs")

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png, optimize=True)
    if out_jpg:
        img.save(out_jpg, quality=86, optimize=True, progressive=True)
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


# ---------- lead images (Discover / Top Stories): the story's visual motif, no headline ----------
# The three ratios Google asks for (16:9, 4:3, 1:1), each >= 1200 px wide, drawn in the site's own system:
# #131313 ground with a faint violet wash, hatch and grain; the `visual` motif (the covers.py motifs,
# redrawn in PIL); the `big` figure in Newsreader with a short accent rule and its label; and a small
# header row (cube + METAFLORA NEWS, section). The only words are the figure, its label and the motif's own.

LEAD_SIZES = {"16x9": (1600, 900), "4x3": (1200, 900), "1x1": (1200, 1200)}
VIOLET, PAPER, INK = (167, 139, 250), (242, 242, 242), (19, 19, 19)
LEAD_ACCENT = {"Federal": VIOLET, "Europe": VIOLET, "Tech": VIOLET, "Hemp": GREEN, "Science": GREEN}  # else lime
ARROWS = set("→←↑↓↗↘")  # not in Newsreader: drawn in Inter Tight
K = 2  # supersampling: PIL shapes have no anti-aliasing, so draw at 2x and downsample

# per ratio: motif centre x, y and radius (fractions of W, H, H); text box x0, top, x1, bottom (fractions of W/H);
# figure size cap and label size (fractions of H)
LEAD_LAYOUT = {
    "16x9": {"motif": (.72, .52, .39), "text": (.06, .22, .50, .885), "fs": .34, "label": .042},
    "4x3": {"motif": (.69, .37, .27), "text": (.067, .66, .933, .905), "fs": .21, "label": .038},
    "1x1": {"motif": (.60, .38, .26), "text": (.073, .67, .927, .925), "fs": .20, "label": .033},
}


def lead_accent(cat):
    return LEAD_ACCENT.get(cat, LIME)


def _rgba(c, a=1.0):
    return tuple(c[:3]) + (round(255 * a),)


def _radial(size, color, alpha, center, radius):
    """RGBA layer: a soft radial glow of `color`, `alpha` at the centre fading to 0 at `radius`."""
    g = Image.radial_gradient("L").resize((round(radius * 2), round(radius * 2)), Image.BILINEAR)
    g = g.point(lambda v: round(max(0, 255 - v * 2) * alpha))  # radial_gradient: 0 at the centre, 128 at the inscribed edge
    mask = Image.new("L", size, 0)
    mask.paste(g, (round(center[0] - radius), round(center[1] - radius)))
    layer = Image.new("RGBA", size, tuple(color) + (0,))
    layer.putalpha(mask)
    return layer


def _fit(text, maker, size, max_w, d):
    while size > 12 and d.textlength(text, font=maker(size)) > max_w:
        size -= 2
    return maker(size)


def _spaced(d, x, y, text, font, fill, track):
    """Letter-spaced text, vertically centred on y; returns the end x."""
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill, anchor="lm")
        x += d.textlength(ch, font=font) + track
    return x - track


def _motif(img, v, cx, cy, R, c, seed):
    """Draw visual['motif'] onto the RGBA layer `img` (supersampled coordinates). Unknown motifs draw the leaf."""
    import math
    import random
    from PIL import ImageChops
    d = ImageDraw.Draw(img)
    m = v.get("motif") or "leaf"
    paper, ink, acc = _rgba(PAPER), _rgba(INK), _rgba(c)

    def layer():
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        return lay, ImageDraw.Draw(lay)

    def ctext(xy, text, font, fill=ink):
        d.text(xy, text, font=font, fill=fill, anchor="mm")

    if m == "ballot":
        lay, ld = layer()
        px, py = cx + R * .05, cy - R * .32
        ld.rounded_rectangle([px - R * .38, py - R * .5, px + R * .38, py + R * .28], R * .04, fill=paper)
        ld.line([(px - R * .18, py - R * .12), (px - R * .04, py + R * .04), (px + R * .22, py - R * .3)], fill=ink, width=round(R * .07), joint="curve")
        for i in range(3):
            ld.rectangle([px - R * .26, py + R * (.1 + i * .05), px - R * .26 + R * .52 * (1 - i * .2), py + R * (.12 + i * .05)], fill=_rgba(INK, .25))
        img.alpha_composite(lay.rotate(7, resample=Image.BICUBIC, center=(px, py)))
        d.rounded_rectangle([cx - R * .62, cy + R * .02, cx + R * .62, cy + R * .74], R * .06, fill=acc)
        d.rounded_rectangle([cx - R * .4, cy + R * .1, cx + R * .4, cy + R * .17], R * .03, fill=ink)
        band, bd = layer()
        bd.rectangle([cx - R * .62, cy + R * .6, cx + R * .62, cy + R * .68], fill=_rgba(INK, .3))
        img.alpha_composite(band)
    elif m == "seal":
        d.ellipse([cx - R * .86, cy - R * .86, cx + R * .86, cy + R * .86], outline=_rgba(c, .4), width=max(2, round(R * .012)))
        d.ellipse([cx - R * .72, cy - R * .72, cx + R * .72, cy + R * .72], fill=acc)
        for r in (.62, .44):
            d.ellipse([cx - R * r, cy - R * r, cx + R * r, cy + R * r], outline=ink, width=round(R * .025))
        for i in range(18):
            a = i / 18 * math.tau
            sx, sy, sr = cx + math.cos(a) * R * .53, cy + math.sin(a) * R * .53, R * .045
            d.polygon([(sx + math.cos(-math.pi / 2 + j * math.pi / 5) * (sr * .45 if j % 2 else sr),
                        sy + math.sin(-math.pi / 2 + j * math.pi / 5) * (sr * .45 if j % 2 else sr)) for j in range(10)], fill=ink)
        word = str(v.get("word") or "FEDERAL").upper()
        ctext((cx, cy - R * .05), word, _fit(word, lambda s: sans(s, 800), round(R * .17), R * .74, d))
        sub = str(v.get("sub") or "").upper()
        if sub:
            ctext((cx, cy + R * .14), sub, _fit(sub, lambda s: mono(s, 600), round(R * .075), R * .76, d))
    elif m == "calendar":
        w, h = R * 1.05, R * 1.15
        X, Y = cx - w / 2, cy - h / 2
        d.rounded_rectangle([X, Y, X + w, Y + h], R * .07, fill=paper)
        d.rounded_rectangle([X, Y, X + w, Y + h * .28], R * .07, fill=acc, corners=(True, True, False, False))
        mon = str(v.get("mon") or "").upper()
        if mon:
            ctext((cx, Y + h * .15), mon, _fit(mon, lambda s: sans(s, 800), round(R * .17), w * .8, d))
        day = str(v.get("day") or "")
        if day:
            ctext((cx, Y + h * .64), day, _fit(day, lambda s: serif(s, 600), round(R * .56), w * .8, d))
        for o in (-.25, .25):
            x = cx + o * w
            d.rounded_rectangle([x - R * .045, Y - R * .1, x + R * .045, Y + R * .11], R * .045, fill=ink, outline=paper, width=2 * K)
    elif m == "merge":
        other = GREEN if tuple(c) == VIOLET else VIOLET
        r = R * .5
        ax, bx = cx - R * .28, cx + R * .28
        for x, col, op in ((ax, c, .92), (bx, other, .8)):
            lay, ld = layer()
            ld.ellipse([x - r, cy - r, x + r, cy + r], fill=_rgba(col, op))
            img.alpha_composite(lay)
        ma, mb = Image.new("L", img.size, 0), Image.new("L", img.size, 0)
        ImageDraw.Draw(ma).ellipse([ax - r, cy - r, ax + r, cy + r], fill=255)
        ImageDraw.Draw(mb).ellipse([bx - r, cy - r, bx + r, cy + r], fill=140)
        lens = Image.new("RGBA", img.size, paper)
        lens.putalpha(ImageChops.multiply(ma, mb))
        img.alpha_composite(lens)
        for lbl, dx in ((v.get("a", ""), -.52), (v.get("b", ""), .52)):
            lbl = str(lbl)
            if lbl:
                ctext((cx + R * dx, cy), lbl, _fit(lbl, lambda s: sans(s, 800), round(R * .15), R * .4, d))
        ctext((cx, cy), "+", sans(round(R * .2), 800))
    elif m == "gavel":
        base, bd = layer()
        bd.rounded_rectangle([cx - R * .6, cy + R * .42, cx + R * .5, cy + R * .58], R * .04, fill=_rgba(PAPER, .15))
        img.alpha_composite(base)
        d.rounded_rectangle([cx - R * .42, cy + R * .3, cx + R * .32, cy + R * .44], R * .03, fill=acc)
        lay, ld = layer()
        gx, gy = cx, cy - R * .05
        ld.rounded_rectangle([gx - R * .05, gy - R * .02, gx + R * .9, gy + R * .08], R * .04, fill=paper)
        ld.rounded_rectangle([gx - R * .32, gy - R * .26, gx, gy + R * .32], R * .06, fill=acc)
        ld.rectangle([gx - R * .32, gy - R * .12, gx, gy - R * .08], fill=ink)
        ld.rectangle([gx - R * .32, gy + R * .14, gx, gy + R * .18], fill=ink)
        img.alpha_composite(lay.rotate(37, resample=Image.BICUBIC, center=(gx, gy)))
        for l in ((-.55, .2, -.75, .12), (-.5, .05, -.7, -.08), (.45, .25, .62, .18)):
            d.line([(cx + R * l[0], cy + R * l[1]), (cx + R * l[2], cy + R * l[3])], fill=acc, width=round(R * .025))
    elif m == "pins":
        rnd = random.Random("pins" + seed)
        dots, dd = layer()
        for i in range(11):
            for j in range(7):
                if rnd.random() < .82:
                    x, y, r = cx - R * .8 + i * R * .16, cy - R * .45 + j * R * .16, R * .025
                    dd.ellipse([x - r, y - r, x + r, y + r], fill=_rgba(PAPER, .25))
        img.alpha_composite(dots)
        for k, p in enumerate(((-.45, -.2), (.1, .15), (.5, -.3), (.3, .35))):
            px, py = cx + p[0] * R, cy + p[1] * R
            s = R * (.2 if k == 0 else .13)
            col = acc if k == 0 else paper
            d.polygon([(px, py), (px - s * .62, py - s * .75), (px + s * .62, py - s * .75)], fill=col)
            d.ellipse([px - s * .7, py - s * 1.075 - s * .7, px + s * .7, py - s * 1.075 + s * .7], fill=col)
            d.ellipse([px - s * .28, py - s * 1.05 - s * .28, px + s * .28, py - s * 1.05 + s * .28], fill=ink)
    elif m == "molecule":
        def hexp(x, y, r):
            return [(x + math.cos(math.pi / 6 + i * math.pi / 3) * r, y + math.sin(math.pi / 6 + i * math.pi / 3) * r) for i in range(6)]
        p1, p2 = hexp(cx - R * .15, cy, R * .38), hexp(cx + R * .5, cy - R * .4, R * .3)
        lw = round(R * .04)
        for P in (p1, p2):
            d.line(P + [P[0], P[1]], fill=paper, width=lw, joint="curve")
        d.line([p1[5], p2[2]], fill=paper, width=lw)
        tail = (p1[2][0] - R * .35, p1[2][1] + R * .15)
        d.line([p1[2], tail], fill=paper, width=lw)
        for i, (a, b) in enumerate(p1 + p2):
            r = R * (.07 if i % 4 == 0 else .045)
            d.ellipse([a - r, b - r, a + r, b + r], fill=acc if i % 4 == 0 else paper)
        r = R * .08
        d.ellipse([tail[0] - r, tail[1] - r, tail[0] + r, tail[1] + r], fill=acc)
    elif m == "chart":
        try:
            vals = [max(.05, min(1.0, float(x))) for x in (v.get("vals") or [])][:12]
        except (TypeError, ValueError):
            vals = []
        if len(vals) < 2:
            vals = [.35, .5, .42, .62, .58, .8, 1]
        n = len(vals)
        w, h = R * 1.5, R * 1.0
        X, Y = cx - w / 2, cy + h / 2
        grid, gd = layer()
        for g in range(4):
            gd.line([(X, Y - g * h / 3), (X + w, Y - g * h / 3)], fill=_rgba(PAPER, .15), width=K)
        bw = w / n * .6
        for i, val in enumerate(vals):
            x = X + i * w / n + (w / n - bw) / 2
            gd.rectangle([x, Y - val * h, x + bw, Y], fill=acc if i == n - 1 else _rgba(PAPER, .28))
        img.alpha_composite(grid)
        pts = [(X + i * w / n + w / n / 2, Y - val * h - R * .08) for i, val in enumerate(vals)]
        d.line(pts, fill=acc, width=round(R * .03), joint="curve")
        ex, ey = pts[-1]
        r = R * .05
        d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=paper)
    else:  # leaf
        by = cy + R * .45
        for a in (-1.25, -.8, -.4, 0, .4, .8, 1.25):
            L = R * (1 - abs(a) * .38) * .95
            ang = -math.pi / 2 + a
            ca, sa = math.cos(ang), math.sin(ang)
            half = [(u / 20 * L, math.sin(math.pi * u / 20) * L * .11 * (1 + (u % 2) * .35)) for u in range(21)]
            outline = [(p, -q) for p, q in half] + [(p, q) for p, q in reversed(half)]
            d.polygon([(cx + p * ca - q * sa, by + p * sa + q * ca) for p, q in outline], fill=acc)
            d.line([(cx, by), (cx + L * .95 * ca, by + L * .95 * sa)], fill=_rgba(INK, .4), width=max(2, round(R * .012)))
        d.line([(cx, by), (cx, by + R * .3)], fill=acc, width=round(R * .04))


def _big_fonts(size):
    return serif(size, 500), sans(round(size * .8), 500)


def _big_width(d, text, size):
    f, fb = _big_fonts(size)
    return sum(d.textlength(ch, font=fb if ch in ARROWS else f) for ch in text)


def _draw_big(d, x, y, text, size):
    """The big figure in Newsreader on baseline y; glyphs Newsreader lacks (arrows) fall back to Inter Tight."""
    f, fb = _big_fonts(size)
    for ch in text:
        font = fb if ch in ARROWS else f
        d.text((x, y), ch, font=font, fill=PAPER, anchor="ls")
        x += d.textlength(ch, font=font)


def lead_alt(a):
    """Plain description of the lead graphic (image_alt describes the AI photo scene, not this picture)."""
    v = a.get("visual") or {}
    big, label = str(v.get("big") or "").strip(), str(v.get("label") or "").strip()
    fig = f"{big}, {label}" if big and label else (big or label)
    return f"MetaFlora News graphic: {fig}" if fig else "MetaFlora News graphic"


def render_lead(a, size="16x9"):
    """Clean editorial lead image for an article: its visual motif and key figure, no headline. Returns an RGB Image."""
    from PIL import ImageChops, ImageFilter
    W_, H_ = LEAD_SIZES[size]
    L = LEAD_LAYOUT[size]
    v = a.get("visual") or {}
    c = lead_accent(a.get("cat", ""))
    seed = str(a.get("id", "x"))
    SW, SH = W_ * K, H_ * K
    img = Image.new("RGBA", (SW, SH), BG + (255,))

    # ground: violet wash from the top-left, accent glow behind the motif, faint diagonal hatch
    img.alpha_composite(_radial((SW, SH), (59, 42, 90), .6, (0, 0), SW * .7))
    mx, my, mr = L["motif"]
    cx, cy, R = SW * mx, SH * my, SH * mr
    big = str(v.get("big") or "").strip()
    if not big:  # no figure: the motif carries the picture alone, centred and larger
        cx, cy, R = SW * .5, SH * .54, SH * mr * 1.3
    img.alpha_composite(_radial((SW, SH), c, .2, (cx, cy), R * 2.1))
    hatch = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hatch)
    for i in range(-SH, SW, 26 * K):
        hd.line([(i, SH), (i + SH, 0)], fill=_rgba(PAPER, .03), width=K)
    img.alpha_composite(hatch)

    # motif, with the soft glow cover_svg uses (a blurred copy underneath)
    mot = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    _motif(mot, v, cx, cy, R, c, "".join(ch for ch in seed if ch.isalnum())[:24] or "x")
    glow = mot.filter(ImageFilter.GaussianBlur(R * .08))
    glow.putalpha(glow.getchannel("A").point(lambda x: round(x * .5)))
    img.alpha_composite(glow)
    img.alpha_composite(mot)

    d = ImageDraw.Draw(img)
    x0 = round(SW * L["text"][0])

    # header row: cube + METAFLORA NEWS | SECTION
    hy = round(SH * (.09 if size == "16x9" else .075))
    cube = Image.open(HERE / "assets" / "metaflora-cube.png").convert("RGBA")
    chh = 30 * K
    cube = cube.resize((round(chh * cube.width / cube.height), chh), Image.LANCZOS)
    img.alpha_composite(cube, (x0, hy - chh // 2))
    x = x0 + cube.width + 12 * K
    wf = ImageFont.truetype(str(FONTS / "CasanovaScotia.otf"), 25 * K)
    d.text((x, hy), "METAFLORA", font=wf, fill=PAPER, anchor="lm")
    x += d.textlength("METAFLORA", font=wf) + 10 * K
    x = _spaced(d, x, hy, "NEWS", sans(14 * K, 700), LIME, 4 * K) + 18 * K
    d.line([(x, hy - 11 * K), (x, hy + 11 * K)], fill=(74, 74, 74), width=K)
    _spaced(d, x + 18 * K, hy, str(a.get("cat", "")).upper(), sans(15 * K, 700), c, 3 * K)

    # figure block, bottom-aligned in the text box: big figure, accent rule, label (max 2 lines)
    if big:
        bx0, top, bx1, bottom = SW * L["text"][0], SH * L["text"][1], SW * L["text"][2], SH * L["text"][3]
        max_w = bx1 - bx0
        lf = sans(round(SH * L["label"]), 500)
        label = str(v.get("label") or "").strip()
        llines = balanced(d, label, lf, max_w) if label else []
        if len(llines) > 2:
            llines = clamp(d, label, lf, max_w, 2)
        lstep = round(lf.size * 1.3)
        gap1, rule_h, gap2 = round(SH * .032), 4 * K, round(SH * .03)
        below = gap1 + rule_h + gap2 + (round(lf.size * .78) + lstep * (len(llines) - 1) if llines else 0)
        size_px = round(SH * L["fs"])

        def cap(s):
            return -serif(s, 500).getbbox("0", anchor="ls")[1]
        while size_px > 40 and (_big_width(d, big, size_px) > max_w or cap(size_px) + below > bottom - top):
            size_px -= 4
        y = bottom - below  # baseline of the figure
        _draw_big(d, bx0 - size_px * .02, y, big, size_px)
        ry = y + gap1
        d.rectangle([bx0, ry, bx0 + 64 * K, ry + rule_h], fill=c)
        ly = ry + rule_h + gap2 + round(lf.size * .78)
        for ln in llines:
            d.text((bx0, ly), ln, font=lf, fill=(178, 178, 178), anchor="ls")
            ly += lstep

    out = img.convert("RGB").resize((W_, H_), Image.LANCZOS)
    # grain: fine noise of about +-2 levels so the flat ground doesn't band
    noise = Image.effect_noise((W_, H_), 18)
    pos = Image.merge("RGB", (noise.point(lambda n: max(0, n - 128) // 9),) * 3)
    neg = Image.merge("RGB", (noise.point(lambda n: max(0, 128 - n) // 9),) * 3)
    return ImageChops.subtract(ImageChops.add(out, pos), neg)


def lead_paths(out_dir, aid):
    """{ratio: Path} of an article's lead images in docs/img/, plus "16x9-960" (the phone-size 16:9)."""
    out_dir = Path(out_dir)
    p = {r: out_dir / f"{aid}-{r}.jpg" for r in LEAD_SIZES}
    p["16x9-960"] = out_dir / f"{aid}-16x9-960.jpg"
    return p


LEAD_MANIFEST = ".leads.json"  # in docs/img: {id: hash of the inputs}, so CI can restore docs/img from cache and skip unchanged stories


def write_leads(a, out_dir):
    """Render the three ratios (and the 960 px 16:9) as JPEG, unless the files exist and the story's id, section,
    visual and this module are unchanged since they were drawn. Returns {ratio: Path}."""
    import hashlib
    import json
    out_dir = Path(out_dir)
    paths = lead_paths(out_dir, a["id"])
    key = hashlib.sha1(json.dumps([a["id"], a.get("cat"), a.get("visual")], sort_keys=True).encode()
                       + Path(__file__).read_bytes()).hexdigest()[:16]
    man_path = out_dir / LEAD_MANIFEST
    try:
        man = json.loads(man_path.read_text())
    except (OSError, ValueError):
        man = {}
    if man.get(a["id"]) == key and all(p.exists() for p in paths.values()):
        return paths
    out_dir.mkdir(parents=True, exist_ok=True)
    for r in LEAD_SIZES:
        im = render_lead(a, r)
        im.save(paths[r], quality=82, optimize=True, progressive=True, subsampling=0)
        if r == "16x9":
            im.resize((960, 540), Image.LANCZOS).save(paths["16x9-960"], quality=80, optimize=True, progressive=True, subsampling=0)
    man[a["id"]] = key
    man_path.write_text(json.dumps(man, sort_keys=True, indent=0))
    return paths
