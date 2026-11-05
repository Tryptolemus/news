"""Edition reel: a 1280x720 H.264 briefing video cut from the edition's covers and headlines.

Intro card -> one shot per story (slow push-in on the cover, headline slides up) -> outro card.
Frames are drawn with Pillow and piped straight into ffmpeg.
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import tempfile

from covers import color_for, cover_svg

VW, VH, FPS = 1280, 720, 30
INTRO, SHOT, OUTRO = 3.0, 4.2, 3.0
INK = (19, 19, 19)
PAPER = (255, 255, 255)
DIM = (208, 208, 208)

FONT_DIRS = [Path(__file__).parent / "assets" / "fonts", Path("/usr/share/fonts/opentype/inter"), Path("/usr/share/fonts/truetype/dejavu")]


def _font(names, size):
    for d in FONT_DIRS:
        for n in names:
            p = d / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def F_DISPLAY(s):
    return _font(["InterDisplay-ExtraBold.otf", "InterDisplay-Bold.otf", "Inter-ExtraBold.otf", "DejaVuSans-Bold.ttf"], s)


def F_BRAND(s):
    return _font(["CasanovaScotia.otf", "InterDisplay-ExtraBold.otf"], s)


def F_MONO(s):
    return _font(["DejaVuSansMono.ttf"], s)


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def wrap(draw, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def cube(draw, x, y, s):
    a, v, g = (240, 166, 74), (167, 139, 250), (143, 196, 164)
    k = s / 40
    P = lambda pts: [(x + px * k, y + py * k) for px, py in pts]  # noqa: E731
    draw.polygon(P([(20, 3), (36, 12), (20, 21), (4, 12)]), fill=a)
    draw.polygon(P([(4, 12), (20, 21), (20, 38), (4, 29)]), fill=v)
    draw.polygon(P([(36, 12), (20, 21), (20, 38), (36, 29)]), fill=g)


_LOGO = None


def _logo():
    global _LOGO
    if _LOGO is None:
        p = Path(__file__).parent / "assets" / "metaflora-white-logo-no-icon.png"
        if p.exists():
            im = Image.open(p).convert("RGBA")
            _LOGO = im.resize((int(im.width * 90 / im.height), 90), Image.LANCZOS)
    return _LOGO


def title_card(t, dur, top, bottom, sub):
    im = Image.new("RGB", (VW, VH), INK)
    d = ImageDraw.Draw(im)
    e = ease(t / 0.8)
    fade = min(1.0, (dur - t) / 0.5)
    alpha = max(0.0, min(e, fade))
    col = lambda c: tuple(int(INK[i] + (c[i] - INK[i]) * alpha) for i in range(3))  # noqa: E731
    logo = _logo()
    if logo is not None:
        lg = logo.copy()
        lg.putalpha(lg.getchannel("A").point(lambda v: int(v * alpha)))
        im.paste(lg, (96, int(200 - (1 - e) * 20)), lg)
    d.text((96, 330 + (1 - e) * 30), top, font=F_BRAND(84), fill=col((163, 230, 53)))
    d.text((96, 440 + (1 - e) * 30), bottom, font=F_DISPLAY(44), fill=col(PAPER))
    d.text((96, 520), sub, font=F_MONO(22), fill=col(DIM))
    d.rectangle([96, 600, 96 + int(500 * e), 604], fill=col((124, 212, 112)))
    return im


_SCRIM = None
_INKFRAME = Image.new("RGB", (VW, VH), INK)


def _scrim():
    global _SCRIM
    if _SCRIM is None:
        col = Image.new("L", (1, VH))
        for y in range(VH):
            col.putpixel((0, y), int(max(0, (y - VH * 0.38) / (VH * 0.62)) ** 1.4 * 245))
        _SCRIM = col.resize((VW, VH))
    return _SCRIM


def story_shot(t, cover, story, idx, total):
    # slow push-in on the cover
    z = 1.0 + 0.06 * (t / SHOT)
    cw, ch = int(VW * z), int(VW * z * cover.height / cover.width)
    big = cover.resize((cw, ch), Image.BILINEAR)
    ox, oy = (cw - VW) // 2, max(0, (ch - VH) // 2 - 40)
    frame = Image.new("RGB", (VW, VH), INK)
    frame.paste(big.crop((ox, oy, ox + VW, oy + min(VH, ch - oy))), (0, 0))
    frame.paste(_INKFRAME, (0, 0), _scrim())
    d = ImageDraw.Draw(frame)
    c = hex2rgb(color_for(story["cat"]))
    e = ease((t - 0.25) / 0.7)
    fade = min(1.0, (SHOT - t) / 0.35)
    a = max(0.0, min(e, fade))
    mix = lambda col: tuple(int(INK[i] + (col[i] - INK[i]) * a) for i in range(3))  # noqa: E731
    v = story.get("visual") or {}
    eb = ease((t - 0.05) / 0.6)
    ab = max(0.0, min(eb, fade))
    mixb = lambda col: tuple(int(INK[i] + (col[i] - INK[i]) * ab) for i in range(3))  # noqa: E731
    if v.get("big"):
        fb = F_BRAND(120)
        bigtxt = v["big"].upper()
        while d.textlength(bigtxt, font=fb) > VW * 0.5 and fb.size > 56:
            fb = F_BRAND(fb.size - 8)
        d.text((96 - (1 - eb) * 40, 70), bigtxt, font=fb, fill=mixb(PAPER))
        if v.get("label"):
            d.text((100, 80 + fb.size * 1.12), v["label"], font=F_MONO(24), fill=mixb(DIM))
    f = F_DISPLAY(44)
    lines = wrap(d, story["headline"], f, VW - 200)[:3]
    base = VH - 70 - len(lines) * 56
    d.text((96, base - 46 + (1 - e) * 30), f"{story['cat'].upper()}  /  {idx} OF {total}", font=F_BRAND(24), fill=mix(c))
    for i, ln in enumerate(lines):
        d.text((96, base + i * 56 + (1 - e) * 30), ln, font=f, fill=mix(PAPER))
    d.rectangle([96, VH - 34, 96 + int((VW - 192) * (t / SHOT)), VH - 30], fill=c)
    return frame


def render_reel(edition, label, stories, og_dir, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    covers = []
    with tempfile.TemporaryDirectory() as td:
        for s in stories:
            svg, png = Path(td) / "c.svg", Path(td) / f"{s['id']}.png"
            svg.write_text(cover_svg(s, with_text=False))
            subprocess.run(["rsvg-convert", "-w", "1280", "-o", str(png), str(svg)], check=True)
            covers.append(Image.open(png).convert("RGB"))
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)],
        stdin=subprocess.PIPE)
    day, half = label.split(" · ")
    for n in range(int(INTRO * FPS)):
        proc.stdin.write(title_card(n / FPS, INTRO, "NEWS", day, half.upper() + f"  /  {len(stories)} STORIES").tobytes())
    for i, (s, cv) in enumerate(zip(stories, covers), 1):
        for n in range(int(SHOT * FPS)):
            proc.stdin.write(story_shot(n / FPS, cv, s, i, len(stories)).tobytes())
    for n in range(int(OUTRO * FPS)):
        proc.stdin.write(title_card(n / FPS, OUTRO, "NEWS", "news.metaflora.xyz", "EVERY MORNING. EVERY EVENING.").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
