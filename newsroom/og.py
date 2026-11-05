"""Social card (1200x630) from an AI banner photo: brand gradient, MetaFlora logo, key figure."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from covers import color_for

ASSETS = Path(__file__).parent / "assets"


def _font(name, size, fallback="/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"):
    for p in (ASSETS / "fonts" / name, Path(fallback)):
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def photo_card(a, photo, out):
    W, H = 1200, 630
    im = Image.open(photo).convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((x, y, x + W, y + H)).convert("RGBA")
    shade = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(shade)
    for yy in range(H):
        t = max(0.0, (yy - H * 0.4) / (H * 0.6))
        d.line([(0, yy), (W, yy)], fill=(19, 19, 19, int(235 * t ** 1.3)))
    for xx in range(W):
        t = max(0.0, 1 - xx / (W * 0.6))
        d.line([(xx, 0), (xx, H)], fill=(34, 24, 44, int(150 * t)))
    im = Image.alpha_composite(im, shade)
    d = ImageDraw.Draw(im)
    logo = ASSETS / "metaflora-white-logo-no-icon.png"
    if logo.exists():
        lg = Image.open(logo).convert("RGBA")
        lg = lg.resize((round(lg.width * 44 / lg.height), 44), Image.LANCZOS)
        im.alpha_composite(lg, (54, 48))
        d.text((54 + lg.width + 14, 56), "NEWS", font=_font("CasanovaScotia.otf", 30), fill=(163, 230, 53))
    v = a.get("visual") or {}
    c = color_for(a["cat"]).lstrip("#")
    col = tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    big = (v.get("big") or "").upper()
    if big:
        f = _font("CasanovaScotia.otf", 150)
        while d.textlength(big, font=f) > W * 0.6 and f.size > 60:
            f = _font("CasanovaScotia.otf", f.size - 10)
        y0 = H - 70 - f.size - (40 if v.get("label") else 0)
        d.text((54, y0), big, font=f, fill=(255, 255, 255))
        d.rectangle([54, y0 + f.size + 14, 54 + min(d.textlength(big, font=f), 360), y0 + f.size + 19], fill=col)
        if v.get("label"):
            d.text((56, y0 + f.size + 32), v["label"], font=_font("x", 30), fill=(208, 208, 208))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(out, "PNG", optimize=True)
