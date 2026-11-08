"""Self-hosted web fonts: subset the full source fonts in assets/fonts/ to small Latin WOFF2 files.

The site serves only the .woff2 files this writes (build.py does not publish the .ttf/.otf sources, which
card.py, og.py, banner.py and reel.py read directly). Run it again only when a source font changes:

    python -I -X utf8 newsroom/webfonts.py          # writes assets/fonts/*.woff2, prints fallback metrics

Needs fontTools + brotli (pip install fonttools brotli). The printed size-adjust / ascent-override values are
the ones in the "Fallback" @font-face rules at the top of site.css: they make Georgia/Arial take the same
space as Newsreader/Inter Tight, so the swap to the web font does not move the page.
"""
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

FONTS = Path(__file__).resolve().parent / "assets" / "fonts"
# Latin + Latin-1, plus the punctuation a news page uses: dashes, curly quotes, bullet, ellipsis, euro, minus, arrows, trademark
UNICODE_RANGE = ("U+0000-00FF,U+0131,U+0152-0153,U+02C6,U+02DA,U+02DC,U+2013-2014,U+2018-201A,U+201C-201E,"
                 "U+2022,U+2026,U+20AC,U+2122,U+2190-2193,U+2212")
FEATURES = ["kern", "liga", "calt", "ccmp", "locl", "mark", "mkmk", "lnum", "tnum", "pnum", "onum", "case"]

# out name: (source, axis limits). Ranges keep the axis variable; a number pins it.
JOBS = {
    "newsreader.woff2": ("Newsreader.ttf", {"wght": (400, 600), "opsz": (12, 72)}),   # body 400, headlines 500/600, optical sizes 12-72px
    "inter-tight.woff2": ("InterTight.ttf", {"wght": (500, 700)}),                      # UI: 500, 600, 700
    "jetbrains-mono-500.woff2": ("JetBrainsMono.ttf", {"wght": 500}),                  # times and figures, one weight
    "casanova-scotia.woff2": ("CasanovaScotia.otf", None),                             # wordmark
}


def codepoints():
    out = []
    for part in UNICODE_RANGE.split(","):
        a, _, b = part[2:].partition("-")
        out.extend(range(int(a, 16), int(b or a, 16) + 1))
    return out


def build():
    for name, (src, limits) in JOBS.items():
        f = TTFont(FONTS / src)
        if limits and "fvar" in f:
            f = instancer.instantiateVariableFont(f, limits)
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = FEATURES
        opts.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14]   # keep copyright + licence (OFL requires it to travel with the font)
        s = subset.Subsetter(opts)
        s.populate(unicodes=codepoints())
        s.subset(f)
        f.flavor = "woff2"
        f.save(FONTS / name)
        print(f"{name}: {(FONTS / name).stat().st_size:,} B")


# English letter frequencies (approx.) for an average glyph width that matches running text
FREQ = {"a": 8.2, "b": 1.5, "c": 2.8, "d": 4.3, "e": 12.7, "f": 2.2, "g": 2.0, "h": 6.1, "i": 7.0, "j": .15, "k": .77, "l": 4.0,
        "m": 2.4, "n": 6.7, "o": 7.5, "p": 1.9, "q": .1, "r": 6.0, "s": 6.3, "t": 9.1, "u": 2.8, "v": .98, "w": 2.4, "x": .15,
        "y": 2.0, "z": .07, " ": 18.0}


def avg_width(font):
    cmap, hmtx, upm = font.getBestCmap(), font["hmtx"], font["head"].unitsPerEm
    tot = sum(hmtx[cmap[ord(c)]][0] * w for c, w in FREQ.items())
    return tot / sum(FREQ.values()) / upm


def fallback_metrics():
    win = Path("C:/Windows/Fonts")
    pairs = [("Newsreader.ttf", {"wght": 400, "opsz": 18}, "georgia.ttf"), ("InterTight.ttf", {"wght": 600}, "arial.ttf")]
    for src, pin, fb in pairs:
        if not (win / fb).exists():
            print(f"skip {src}: {fb} not found")
            continue
        f = instancer.instantiateVariableFont(TTFont(FONTS / src), pin)
        g = TTFont(win / fb)
        adj = avg_width(f) / avg_width(g)
        upm = f["head"].unitsPerEm
        asc, desc, gap = f["hhea"].ascent / upm, -f["hhea"].descent / upm, f["hhea"].lineGap / upm
        print(f"{src} vs {fb}: size-adjust:{adj * 100:.2f}%;ascent-override:{asc / adj * 100:.2f}%;"
              f"descent-override:{desc / adj * 100:.2f}%;line-gap-override:{gap / adj * 100:.2f}%")


if __name__ == "__main__":
    if "--metrics" not in sys.argv:
        build()
    fallback_metrics()
