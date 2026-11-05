"""MetaFlora News banner compositor.

Builds the article banner in the house style (see Greg's "Mainnet Update" / "California
Cannabis Enforcement Bill Signed" examples): a cinematic scene on the right, and on the left the
MetaFlora cube logo, a "MetaFlora News" pill, a huge two-tone headline, a sub line, a divider with
spaced caps, a three-point icon strip, and spaced-caps corner text.

Scene = AI image (content/images/<id>.jpg) when present, otherwise the designed SVG motif.
Output 1672x941 (the size of the reference banners).
"""
import io
import random
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from covers import color_for, cover_svg

W, H = 1672, 941
HERE = Path(__file__).parent
ASSETS = HERE / "assets"
LIME = (163, 230, 53)
GREEN = (124, 212, 112)
EMERALD = (46, 230, 150)
VIOLET = (167, 123, 243)
WHITE = (255, 255, 255)
SILVER = (205, 205, 212)
INK = (8, 8, 12)

ICON_PATHS = {
    # 24x24 stroke icons, drawn for this banner set
    "shield": "M12 2.5 4 5.5v6c0 5 3.4 8.8 8 10 4.6-1.2 8-5 8-10v-6Z M8.5 12l2.4 2.4 4.6-4.8",
    "leaf": "M12 21V9 M12 13c-3.5 0-6-2.5-6-6.5 3.5 0 6 2.5 6 6.5Z M12 11c3.5 0 6-2.5 6-6.5-3.5 0-6 2.5-6 6.5Z M12 17c-2.5 0-4.5-1.6-4.5-4 2.5 0 4.5 1.6 4.5 4Z M12 16c2.5 0 4.5-1.6 4.5-4-2.5 0-4.5 1.6-4.5 4Z",
    "chart": "M3 21h18 M6 17v-4 M10.5 17V9 M15 17v-6 M19.5 17V5 M4 10l5-4 4 3 7-6",
    "gavel": "M14.5 3.5l6 6 M12 6l6 6 M13.2 4.8 7 11l3 3 6.2-6.2 M10 14 3.5 20.5 M3 22h9",
    "flask": "M9 2h6 M10 2v6L4.5 18.5A2 2 0 0 0 6.3 21.5h11.4a2 2 0 0 0 1.8-3L14 8V2 M7 15h10",
    "pin": "M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21Z M12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
    "ballot": "M4 11h16v10H4Z M8 15h8 M7 11V4h10v7 M9.5 7.5l1.5 1.5 3-3",
    "coin": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z M15 9.5c-.6-1-1.7-1.5-3-1.5-1.7 0-3 .9-3 2s1.3 1.7 3 2 3 .9 3 2-1.3 2-3 2c-1.3 0-2.4-.5-3-1.5 M12 6.5v11",
    "globe": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z M3 12h18 M12 3c2.5 2.7 3.8 5.7 3.8 9S14.5 18.3 12 21c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3Z",
    "doc": "M6 2h9l5 5v15H6Z M14 2v6h6 M9 13h8 M9 17h6",
    "handshake": "M2 12l4-4 4 2 4-3 4 1 4 4 M6 8v6l4 4c1 1 2.5 1 3.3 0L18 13 M10 10l3 3",
    "chip": "M7 7h10v10H7Z M10 10h4v4h-4Z M9 2v5 M15 2v5 M9 17v5 M15 17v5 M2 9h5 M2 15h5 M17 9h5 M17 15h5",
    "megaphone": "M3 10v4h4l7 5V5L7 10Z M17 9a4 4 0 0 1 0 6 M19.5 6.5a7.5 7.5 0 0 1 0 11",
    "drop": "M12 2.5S5.5 9.8 5.5 14.5a6.5 6.5 0 0 0 13 0C18.5 9.8 12 2.5 12 2.5Z",
    "cube": "M12 2.5 3.5 7v10L12 21.5 20.5 17V7Z M3.5 7 12 11.5 20.5 7 M12 11.5v10",
}
CAT_ICONS = {
    "Policy": ["ballot", "shield", "leaf"], "Federal": ["shield", "doc", "chart"], "Hemp": ["leaf", "doc", "shield"],
    "Markets": ["chart", "coin", "handshake"], "Europe": ["globe", "gavel", "leaf"], "States": ["pin", "doc", "chart"],
    "Science": ["flask", "leaf", "chart"], "Tech": ["chip", "cube", "shield"],
}
CAT_WORDS = {
    "Policy": ["PEOPLE", "PLANTS", "POLICY", "PROGRESS"], "Federal": ["FEDERAL", "MEDICAL", "ACCESS", "COMPLIANCE"],
    "Hemp": ["HEMP", "THC", "RULES", "MARKETS"], "Markets": ["CAPITAL", "DEALS", "GROWTH", "SCALE"],
    "Europe": ["EUROPE", "LAW", "CULTURE", "CHANGE"], "States": ["STATES", "LICENSES", "MARKETS", "ACCESS"],
    "Science": ["SCIENCE", "MEDICINE", "DATA", "HEALTH"], "Tech": ["CHAIN", "DATA", "AI", "TRUST"],
}


# ---------- fonts ----------

def _font(cands, size):
    for c in cands:
        p = Path(c)
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def F_HEAD(s):
    return _font([ASSETS / "fonts" / "CasanovaScotia.otf", "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"], s)


def F_BOLD(s):
    return _font(["/usr/share/fonts/opentype/inter/InterDisplay-SemiBold.otf", "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"], s)


def F_MED(s):
    return _font(["/usr/share/fonts/opentype/inter/InterDisplay-Medium.otf", "/usr/share/fonts/opentype/inter/Inter-Medium.otf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"], s)


# ---------- helpers ----------

def gradient(size, stops, horizontal=False):
    w, h = size
    n = w if horizontal else h
    line = Image.new("RGB", (n, 1))
    px = line.load()
    for i in range(n):
        t = i / max(1, n - 1)
        for j in range(len(stops) - 1):
            t0, c0 = stops[j]
            t1, c1 = stops[j + 1]
            if t0 <= t <= t1:
                u = (t - t0) / max(1e-6, t1 - t0)
                px[i, 0] = tuple(int(c0[k] + (c1[k] - c0[k]) * u) for k in range(3))
                break
    img = line.resize((n, 1))
    return img.resize((w, h)) if horizontal else img.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT).resize((w, h))


def spaced(d, xy, text, font, fill, track=6, anchor_right=False):
    x, y = xy
    widths = [d.textlength(ch, font=font) + track for ch in text]
    if anchor_right:
        x -= sum(widths) - track
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=font, fill=fill)
        x += w
    return x


def icon(name, size, color):
    path = ICON_PATHS.get(name, ICON_PATHS["cube"])
    c = "#%02x%02x%02x" % color
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" '
           f'stroke="{c}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="{path}"/></svg>')
    out = subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size)], input=svg.encode(), capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(out)).convert("RGBA")


def smoke(seed, color, strength=1.0):
    """Soft procedural smoke wisps tinted with color (RGBA, W x H)."""
    rnd = random.Random(seed)
    small = Image.new("L", (W // 8, H // 8))
    d = ImageDraw.Draw(small)
    for _ in range(26):
        x, y = rnd.uniform(0, W // 8), rnd.uniform(0, H // 8)
        r = rnd.uniform(6, 22)
        d.ellipse([x - r, y - r * .6, x + r, y + r * .6], fill=int(rnd.uniform(40, 120) * strength))
    mask = small.filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(12))
    layer = Image.new("RGBA", (W, H), color + (0,))
    layer.putalpha(mask)
    return layer


def sparkles(seed, n=140):
    rnd = random.Random(seed + "s")
    layer = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(layer)
    for _ in range(n):
        x, y = rnd.uniform(0, W * .55), rnd.uniform(0, H)
        r = rnd.choice([1, 1, 1.5, 2, 3])
        c = VIOLET if rnd.random() < .7 else GREEN
        d.ellipse([x - r, y - r, x + r, y + r], fill=c + (int(rnd.uniform(60, 200)),))
    pts = [(rnd.uniform(0, W * .3), rnd.uniform(0, H)) for _ in range(18)]
    for i, p in enumerate(pts):
        for q in pts[i + 1:i + 3]:
            d.line([p, q], fill=VIOLET + (45,), width=1)
    return layer.filter(ImageFilter.GaussianBlur(.6))


def scene_image(a, photo):
    if photo:
        im = Image.open(photo).convert("RGB")
    else:
        return Image.new("RGBA", (W, H), (14, 12, 20, 255))
    # cover-fit, biased so the subject sits right of centre
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x = (im.width - W) // 2
    y = (im.height - H) // 2
    im = im.crop((x, y, x + W, y + H))
    if not photo:  # push the designed motif to the right half
        canvas = Image.new("RGB", (W, H), (19, 19, 19))
        canvas.paste(im, (int(W * .12), 0))
        im = canvas
    return im.convert("RGBA")


def fit_lines(d, words, font_fn, max_w, max_lines, start, floor):
    size = start
    while size >= floor:
        f = font_fn(size)
        lines, cur = [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) > max_w and cur:
                lines.append(cur)
                cur = w
            else:
                cur = t
        lines.append(cur)
        if len(lines) <= max_lines and all(d.textlength(l, font=f) <= max_w for l in lines):
            return f, lines
        size -= 6
    return font_fn(floor), lines


def headline_layer(lines, font, highlight, x, y, gap):
    """Two-tone metallic headline: silver for normal lines, violet->green for highlighted words."""
    layer = Image.new("RGBA", (W, H))
    probe = ImageDraw.Draw(layer)
    hl = {w.upper() for w in highlight}
    yy = y
    for line in lines:
        cx = x
        for k, word in enumerate(line.split(" ")):
            token = word + (" " if k < len(line.split(" ")) - 1 else "")
            tw = probe.textlength(token, font=font)
            bbox = probe.textbbox((0, 0), word, font=font)
            wh = bbox[3] + 8
            mask = Image.new("L", (int(tw) + 4, int(wh)))
            ImageDraw.Draw(mask).text((0, 0), word, font=font, fill=255)
            if word.strip(",.:;!?").upper() in hl:
                fill = gradient(mask.size, [(0, VIOLET), (.55, (190, 190, 230)), (1, EMERALD)], horizontal=True)
            else:
                fill = gradient(mask.size, [(0, WHITE), (.55, SILVER), (1, (150, 150, 160))])
            # bevel: dark offset shadow + glow
            shadow = Image.merge("RGBA", (*Image.new("RGB", mask.size, (0, 0, 0)).split(), mask.point(lambda v: int(v * .8))))
            layer.alpha_composite(shadow, (int(cx) + 5, int(yy) + 6))
            glyph = fill.convert("RGBA")
            glyph.putalpha(mask)
            layer.alpha_composite(glyph, (int(cx), int(yy)))
            cx += tw
        yy += gap
    glow = layer.filter(ImageFilter.GaussianBlur(14))
    glow = Image.merge("RGBA", (*Image.new("RGB", (W, H), VIOLET).split(), glow.getchannel("A").point(lambda v: int(v * .35))))
    out = Image.new("RGBA", (W, H))
    out.alpha_composite(glow)
    out.alpha_composite(layer)
    return out, yy


def _wrap(d, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    if len(lines) > 2:
        lines = lines[:2]
        lines[1] = lines[1].rstrip(",.;:") + "…"
    return lines


def _short_title(h):
    import re
    t = re.split(r",| as | while | after | then ", h, maxsplit=1)[0]
    return " ".join(t.split()[:7])


def default_banner(a):
    v = a.get("visual") or {}
    title = _short_title(a["headline"]).upper()
    words = title.split()
    return {
        "title": title,
        "highlight": words[-1:],
        "sub": a["dek"],
        "points": [{"icon": i, "text": t} for i, t in zip(CAT_ICONS.get(a["cat"], ["cube"] * 3),
                   [v.get("big", "") + " " + v.get("label", ""), a["cat"] + " desk", "Sources linked"])],
    }


# ---------- compose ----------

def render_banner(a, photo, out_path, edition_label=""):
    b = a.get("banner") or default_banner(a)
    seed = a["id"]
    cat = a.get("cat", "Policy")
    accent = tuple(int(color_for(cat).lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))

    base = Image.new("RGBA", (W, H), INK + (255,))
    base.alpha_composite(scene_image(a, photo))
    # left darkness so type reads, purple/green atmosphere
    left = gradient((W, H), [(0, (6, 5, 10)), (.36, (8, 6, 14)), (.62, (12, 10, 20)), (1, (12, 10, 20))], horizontal=True).convert("RGBA")
    left.putalpha(gradient((W, H), [(0, (250, 250, 250)), (.38, (225, 225, 225)), (.62, (60, 60, 60)), (1, (0, 0, 0))], horizontal=True).convert("L"))
    base.alpha_composite(left)
    bottom = Image.new("RGBA", (W, H), (6, 5, 10, 0))
    bottom.putalpha(gradient((W, H), [(0, (0, 0, 0)), (.7, (0, 0, 0)), (1, (170, 170, 170))]).convert("L"))
    base.alpha_composite(bottom)
    base.alpha_composite(smoke(seed, VIOLET, 1.0))
    base.alpha_composite(smoke(seed + "g", EMERALD, .55))
    base.alpha_composite(sparkles(seed))
    d = ImageDraw.Draw(base)

    X = 92
    # logo: cube + white wordmark
    cube = Image.open(ASSETS / "metaflora-cube.png").convert("RGBA")
    cube = cube.resize((round(cube.width * 104 / cube.height), 104), Image.LANCZOS)
    base.alpha_composite(cube, (X, 62))
    word = Image.open(ASSETS / "metaflora-white-logo-no-icon.png").convert("RGBA")
    word = word.resize((round(word.width * 58 / word.height), 58), Image.LANCZOS)
    base.alpha_composite(word, (X + cube.width + 22, 86))

    # "MetaFlora News" pill
    py = 196
    f = F_BOLD(30)
    t1, t2 = "MetaFlora ", "News"
    pw = int(d.textlength(t1, font=f) + d.textlength(t2, font=f)) + 56
    ring = gradient((pw, 56), [(0, EMERALD), (1, VIOLET)], horizontal=True).convert("RGBA")
    rm = Image.new("L", (pw, 56))
    ImageDraw.Draw(rm).rounded_rectangle([0, 0, pw - 1, 55], radius=28, outline=255, width=3)
    ring.putalpha(rm)
    d.rounded_rectangle([X, py, X + pw, py + 55], radius=28, fill=(10, 10, 16, 230))
    base.alpha_composite(ring, (X, py))
    d.text((X + 28, py + 9), t1, font=f, fill=WHITE)
    d.text((X + 28 + d.textlength(t1, font=f), py + 9), t2, font=f, fill=GREEN)

    # headline + sub: shrink together until the whole left column fits above the bottom margin
    max_w = int(W * .54)
    sub = b.get("sub", "")
    has_pts = bool((b.get("points") or [])[:3])
    words = b["title"].upper().split()
    for size in range(132, 58, -6):
        font, lines = fit_lines(d, words, F_HEAD, max_w, 3, size, size)
        if len(lines) > 3:
            continue
        gap = int(font.size * 1.02)
        fs = F_MED(max(26, min(36, int(font.size * .3))))
        sub_lines = _wrap(d, sub, fs, max_w)[:2]
        hy = py + 92
        sy = hy + gap * len(lines) + 12
        dy = sy + len(sub_lines) * int(fs.size * 1.3) + 26
        bottom = dy + 46 + (128 if has_pts else 0)
        if bottom <= H - 48:
            break
    head, end_y = headline_layer(lines, font, b.get("highlight", []), X, hy, gap)
    base.alpha_composite(head)
    d = ImageDraw.Draw(base)
    for k, l in enumerate(sub_lines):
        d.text((X, sy + k * int(fs.size * 1.3)), l, font=fs, fill=(235, 235, 240))

    # divider with spaced caps
    cap = (b.get("divider") or edition_label or "MetaFlora News").upper()
    fcap = F_MED(19)
    capw = sum(d.textlength(ch, font=fcap) + 8 for ch in cap)
    mid = X + max_w // 2
    d.line([(X + 40, dy + 11), (mid - capw / 2 - 22, dy + 11)], fill=VIOLET + (200,), width=2)
    spaced(d, (mid - capw / 2, dy), cap, fcap, VIOLET, track=8)
    d.line([(mid + capw / 2 + 14, dy + 11), (X + max_w - 40, dy + 11)], fill=EMERALD + (200,), width=2)

    # icon strip
    pts = (b.get("points") or [])[:3]
    if pts:
        top = dy + 46
        ph = 128
        pw2 = max_w + 40
        frame = gradient((pw2, ph), [(0, VIOLET), (1, EMERALD)], horizontal=True).convert("RGBA")
        fm = Image.new("L", (pw2, ph))
        ImageDraw.Draw(fm).rounded_rectangle([0, 0, pw2 - 1, ph - 1], radius=16, outline=255, width=2)
        frame.putalpha(fm.point(lambda v: int(v * .8)))
        d.rounded_rectangle([X - 20, top, X - 20 + pw2, top + ph], radius=16, fill=(10, 9, 16, 170))
        base.alpha_composite(frame, (X - 20, top))
        cw = pw2 / len(pts)
        fpt = F_MED(25)
        for i, p in enumerate(pts):
            cx = X - 20 + cw * i
            col = VIOLET if i % 2 == 0 else EMERALD
            ic = icon(p.get("icon", "cube"), 58, col)
            base.alpha_composite(ic, (int(cx + 24), int(top + (ph - 58) / 2)))
            txt = p.get("text", "")
            words, lines2, cur = txt.split(), [], ""
            for w_ in words:
                t = (cur + " " + w_).strip()
                if d.textlength(t, font=fpt) > cw - 112 and cur:
                    lines2.append(cur)
                    cur = w_
                else:
                    cur = t
            lines2.append(cur)
            lines2 = lines2[:2]
            ty = top + ph / 2 - len(lines2) * 16
            for k, l in enumerate(lines2):
                d.text((cx + 98, ty + k * 32), l, font=fpt, fill=(240, 240, 245))
            if i:
                d.line([(cx, top + 22), (cx, top + ph - 22)], fill=(120, 110, 150, 140), width=2)

    # corner words
    fc = F_MED(17)
    words = b.get("corner") or CAT_WORDS.get(cat, CAT_WORDS["Policy"])
    for i, w_ in enumerate(words[:4]):
        spaced(d, (W - 60, H - 60 - (len(words[:4]) - 1 - i) * 30), w_, fc, (215, 215, 225), track=6, anchor_right=True)
    d.line([(W - 52, H - 160), (W - 52, H - 44)], fill=accent + (220,), width=2)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    rgb = base.convert("RGB")
    if out_path.suffix.lower() in (".jpg", ".jpeg"):
        rgb.save(out_path, "JPEG", quality=88, optimize=True, progressive=True)
    else:
        rgb.save(out_path, optimize=True)
    return out_path
