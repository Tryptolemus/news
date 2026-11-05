"""Editorial cover art for MetaFlora News.

Every story carries a "visual" spec: motif + big figure + label.
cover_svg() returns a self-contained 1200x630 SVG used inline on the site,
rendered to PNG for social cards, and composited into the video reel.
"""
import math
import random
from html import escape

W, H = 1200, 630
INK = "#120f19"
PAPER = "#f4eef8"
DIM = "#c9bfd6"
CAT_COLORS = {
    "Policy": "#f0a64a",
    "Federal": "#a78bfa",
    "Hemp": "#8fc4a4",
    "Markets": "#f08a8a",
    "Europe": "#a78bfa",
    "States": "#f0a64a",
    "Science": "#8fc4a4",
    "Tech": "#7cc7e8",
}
MOTIFS = ["ballot", "seal", "calendar", "merge", "gavel", "pins", "molecule", "chart", "leaf"]
DISPLAY = "Unbounded, 'Inter Display', 'Inter', sans-serif"
MONO = "'IBM Plex Mono', 'DejaVu Sans Mono', monospace"


def color_for(cat):
    return CAT_COLORS.get(cat, "#f0a64a")


def _f(n):
    return f"{n:.1f}"


def _star(cx, cy, r):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r * 0.45 if i % 2 else r
        pts.append(f"{_f(cx + math.cos(a) * rr)},{_f(cy + math.sin(a) * rr)}")
    return f'<polygon points="{" ".join(pts)}"/>'


def _hex(cx, cy, r):
    pts = []
    for i in range(6):
        a = math.pi / 6 + i * math.pi / 3
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def motif_svg(v, cx, cy, R, c, seed):
    m = v.get("motif", "leaf")
    out = []
    if m == "ballot":
        out.append(f'<g transform="translate({_f(cx + R*.05)},{_f(cy - R*.32)}) rotate(-7)">'
                   f'<rect x="{_f(-R*.38)}" y="{_f(-R*.5)}" width="{_f(R*.76)}" height="{_f(R*.78)}" rx="{_f(R*.04)}" fill="{PAPER}"/>'
                   f'<polyline points="{_f(-R*.18)},{_f(-R*.12)} {_f(-R*.04)},{_f(R*.04)} {_f(R*.22)},{_f(-R*.3)}" fill="none" stroke="{INK}" stroke-width="{_f(R*.07)}" stroke-linecap="round" stroke-linejoin="round"/>'
                   + "".join(f'<rect x="{_f(-R*.26)}" y="{_f(R*.1 + i*R*.05)}" width="{_f(R*.52*(1-i*.2))}" height="{_f(R*.02)}" fill="{INK}" opacity=".25"/>' for i in range(3))
                   + '</g>')
        out.append(f'<rect x="{_f(cx-R*.62)}" y="{_f(cy+R*.02)}" width="{_f(R*1.24)}" height="{_f(R*.72)}" rx="{_f(R*.06)}" fill="{c}"/>')
        out.append(f'<rect x="{_f(cx-R*.4)}" y="{_f(cy+R*.1)}" width="{_f(R*.8)}" height="{_f(R*.07)}" rx="{_f(R*.03)}" fill="{INK}"/>')
        out.append(f'<rect x="{_f(cx-R*.62)}" y="{_f(cy+R*.6)}" width="{_f(R*1.24)}" height="{_f(R*.14)}" fill="{INK}" opacity=".35"/>')
        out.append(f'<text x="{_f(cx)}" y="{_f(cy+R*.44)}" text-anchor="middle" font-family="{DISPLAY}" font-weight="800" font-size="{_f(R*.14)}" fill="{INK}">VOTE</text>')
    elif m == "seal":
        out.append(f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(R*.86)}" fill="none" stroke="{c}" stroke-width="{_f(R*.012)}" opacity=".4"/>')
        out.append(f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(R*.72)}" fill="{c}"/>')
        for r in (.62, .44):
            out.append(f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(R*r)}" fill="none" stroke="{INK}" stroke-width="{_f(R*.025)}"/>')
        out.append(f'<g fill="{INK}">' + "".join(_star(cx + math.cos(i/18*math.tau)*R*.53, cy + math.sin(i/18*math.tau)*R*.53, R*.045) for i in range(18)) + '</g>')
        word = escape(v.get("word", "FEDERAL"))
        out.append(f'<text x="{_f(cx)}" y="{_f(cy)}" text-anchor="middle" font-family="{DISPLAY}" font-weight="800" font-size="{_f(R*.11)}" fill="{INK}">{word}</text>')
        out.append(f'<text x="{_f(cx)}" y="{_f(cy+R*.14)}" text-anchor="middle" font-family="{MONO}" font-weight="500" font-size="{_f(R*.075)}" fill="{INK}">{escape(v.get("sub", "REGISTERED"))}</text>')
    elif m == "calendar":
        w, h = R*1.05, R*1.15
        X, Y = cx - w/2, cy - h/2
        out.append(f'<clipPath id="cal-{seed}"><rect x="{_f(X)}" y="{_f(Y)}" width="{_f(w)}" height="{_f(h)}" rx="{_f(R*.07)}"/></clipPath>')
        out.append(f'<rect x="{_f(X)}" y="{_f(Y)}" width="{_f(w)}" height="{_f(h)}" rx="{_f(R*.07)}" fill="{PAPER}"/>')
        out.append(f'<rect x="{_f(X)}" y="{_f(Y)}" width="{_f(w)}" height="{_f(h*.28)}" fill="{c}" clip-path="url(#cal-{seed})"/>')
        out.append(f'<text x="{_f(cx)}" y="{_f(Y+h*.2)}" text-anchor="middle" font-family="{DISPLAY}" font-weight="800" font-size="{_f(R*.16)}" fill="{INK}">{escape(str(v.get("mon", "")))}</text>')
        out.append(f'<text x="{_f(cx)}" y="{_f(Y+h*.82)}" text-anchor="middle" font-family="{DISPLAY}" font-weight="800" font-size="{_f(R*.52)}" fill="{INK}">{escape(str(v.get("day", "")))}</text>')
        for o in (-.25, .25):
            out.append(f'<rect x="{_f(cx+o*w-R*.04)}" y="{_f(Y-R*.09)}" width="{_f(R*.08)}" height="{_f(R*.2)}" rx="{_f(R*.04)}" fill="{INK}" stroke="{PAPER}" stroke-width="2"/>')
    elif m == "merge":
        out.append(f'<circle cx="{_f(cx-R*.28)}" cy="{_f(cy)}" r="{_f(R*.5)}" fill="{c}" opacity=".9"/>')
        out.append(f'<circle cx="{_f(cx+R*.28)}" cy="{_f(cy)}" r="{_f(R*.5)}" fill="#a78bfa" opacity=".75"/>')
        out.append(f'<path d="M{_f(cx)},{_f(cy-R*.41)} A{_f(R*.5)},{_f(R*.5)} 0 0 1 {_f(cx)},{_f(cy+R*.41)} A{_f(R*.5)},{_f(R*.5)} 0 0 1 {_f(cx)},{_f(cy-R*.41)}Z" fill="{PAPER}" opacity=".55"/>')
        for lbl, dx in ((v.get("a", ""), -.5), (v.get("b", ""), .5)):
            out.append(f'<text x="{_f(cx+R*dx)}" y="{_f(cy+R*.06)}" text-anchor="middle" font-family="{DISPLAY}" font-weight="800" font-size="{_f(R*.15)}" fill="{INK}">{escape(str(lbl))}</text>')
        out.append(f'<text x="{_f(cx)}" y="{_f(cy+R*.08)}" text-anchor="middle" font-family="{DISPLAY}" font-weight="800" font-size="{_f(R*.2)}" fill="{INK}">+</text>')
    elif m == "gavel":
        out.append(f'<rect x="{_f(cx-R*.6)}" y="{_f(cy+R*.42)}" width="{_f(R*1.1)}" height="{_f(R*.16)}" rx="{_f(R*.04)}" fill="{PAPER}" opacity=".15"/>')
        out.append(f'<rect x="{_f(cx-R*.42)}" y="{_f(cy+R*.3)}" width="{_f(R*.74)}" height="{_f(R*.14)}" rx="{_f(R*.03)}" fill="{c}"/>')
        out.append(f'<g transform="translate({_f(cx)},{_f(cy-R*.05)}) rotate(-37)">'
                   f'<rect x="{_f(-R*.05)}" y="{_f(-R*.02)}" width="{_f(R*.95)}" height="{_f(R*.1)}" rx="{_f(R*.04)}" fill="{PAPER}"/>'
                   f'<rect x="{_f(-R*.32)}" y="{_f(-R*.26)}" width="{_f(R*.32)}" height="{_f(R*.58)}" rx="{_f(R*.06)}" fill="{c}"/>'
                   f'<rect x="{_f(-R*.32)}" y="{_f(-R*.12)}" width="{_f(R*.32)}" height="{_f(R*.04)}" fill="{INK}"/>'
                   f'<rect x="{_f(-R*.32)}" y="{_f(R*.14)}" width="{_f(R*.32)}" height="{_f(R*.04)}" fill="{INK}"/></g>')
        for l in ((-.55, .2, -.75, .12), (-.5, .05, -.7, -.08), (.45, .25, .62, .18)):
            out.append(f'<line x1="{_f(cx+R*l[0])}" y1="{_f(cy+R*l[1])}" x2="{_f(cx+R*l[2])}" y2="{_f(cy+R*l[3])}" stroke="{c}" stroke-width="{_f(R*.025)}" stroke-linecap="round"/>')
    elif m == "pins":
        rnd = random.Random("pins" + seed)
        dots = []
        for i in range(11):
            for j in range(7):
                if rnd.random() < .82:
                    dots.append(f'<circle cx="{_f(cx-R*.8+i*R*.16)}" cy="{_f(cy-R*.45+j*R*.16)}" r="{_f(R*.025)}"/>')
        out.append(f'<g fill="{PAPER}" opacity=".25">' + "".join(dots) + '</g>')
        for k, p in enumerate(((-.45, -.2), (.1, .15), (.5, -.3), (.3, .35))):
            px, py = cx + p[0]*R, cy + p[1]*R
            s = R * (.2 if k == 0 else .13)
            out.append(f'<path d="M{_f(px)},{_f(py)} L{_f(px-s*.62)},{_f(py-s*.75)} A{_f(s*.7)},{_f(s*.7)} 0 1 1 {_f(px+s*.62)},{_f(py-s*.75)} Z" fill="{c if k == 0 else PAPER}"/>')
            out.append(f'<circle cx="{_f(px)}" cy="{_f(py-s)}" r="{_f(s*.28)}" fill="{INK}"/>')
    elif m == "molecule":
        p1 = _hex(cx - R*.15, cy, R*.38)
        p2 = _hex(cx + R*.5, cy - R*.4, R*.3)
        for P in (p1, p2):
            out.append(f'<polygon points="{" ".join(f"{_f(a)},{_f(b)}" for a, b in P)}" fill="none" stroke="{PAPER}" stroke-width="{_f(R*.04)}" stroke-linejoin="round"/>')
        out.append(f'<line x1="{_f(p1[5][0])}" y1="{_f(p1[5][1])}" x2="{_f(p2[2][0])}" y2="{_f(p2[2][1])}" stroke="{PAPER}" stroke-width="{_f(R*.04)}"/>')
        tail = (p1[2][0] - R*.35, p1[2][1] + R*.15)
        out.append(f'<line x1="{_f(p1[2][0])}" y1="{_f(p1[2][1])}" x2="{_f(tail[0])}" y2="{_f(tail[1])}" stroke="{PAPER}" stroke-width="{_f(R*.04)}"/>')
        for i, (a, b) in enumerate(p1 + p2):
            out.append(f'<circle cx="{_f(a)}" cy="{_f(b)}" r="{_f(R*(.07 if i % 4 == 0 else .045))}" fill="{c if i % 4 == 0 else PAPER}"/>')
        out.append(f'<circle cx="{_f(tail[0])}" cy="{_f(tail[1])}" r="{_f(R*.08)}" fill="{c}"/>')
    elif m == "chart":
        vals = v.get("vals") or [.35, .5, .42, .62, .58, .8, 1]
        vals = [max(0.05, min(1.0, float(x))) for x in vals][:12]
        n = len(vals)
        w, h = R*1.5, R*1.0
        X, Y = cx - w/2, cy + h/2
        for g in range(4):
            out.append(f'<line x1="{_f(X)}" y1="{_f(Y-g*h/3)}" x2="{_f(X+w)}" y2="{_f(Y-g*h/3)}" stroke="{PAPER}" stroke-opacity=".15"/>')
        bw = w/n*.6
        for i, val in enumerate(vals):
            fill = c if i == n-1 else PAPER
            op = 1 if i == n-1 else .28
            out.append(f'<rect x="{_f(X+i*w/n+(w/n-bw)/2)}" y="{_f(Y-val*h)}" width="{_f(bw)}" height="{_f(val*h)}" fill="{fill}" opacity="{op}"/>')
        pts = " ".join(f"{_f(X+i*w/n+w/n/2)},{_f(Y-val*h-R*.08)}" for i, val in enumerate(vals))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="{_f(R*.03)}" stroke-linejoin="round"/>')
        out.append(f'<circle cx="{_f(X+(n-1)*w/n+w/n/2)}" cy="{_f(Y-vals[-1]*h-R*.08)}" r="{_f(R*.05)}" fill="{PAPER}"/>')
    else:  # leaf
        by = cy + R*.45
        leaves = []
        for a in (-1.25, -.8, -.4, 0, .4, .8, 1.25):
            L = R*(1-abs(a)*.38)*.95
            pts = []
            for t in range(21):
                u = t/20
                wd = math.sin(math.pi*u)*L*.11*(1+(t % 2)*.35)
                pts.append((u*L, -wd))
            for t in range(20, -1, -1):
                u = t/20
                wd = math.sin(math.pi*u)*L*.11*(1+(t % 2)*.35)
                pts.append((u*L, wd))
            ang = math.degrees(-math.pi/2 + a)
            leaves.append(f'<g transform="translate({_f(cx)},{_f(by)}) rotate({_f(ang)})"><polygon points="{" ".join(f"{_f(p)},{_f(q)}" for p, q in pts)}" fill="{c}"/>'
                          f'<line x1="0" y1="0" x2="{_f(L*.95)}" y2="0" stroke="{INK}" stroke-opacity=".4" stroke-width="{_f(R*.012)}"/></g>')
        out.extend(leaves)
        out.append(f'<line x1="{_f(cx)}" y1="{_f(by)}" x2="{_f(cx)}" y2="{_f(by+R*.3)}" stroke="{c}" stroke-width="{_f(R*.04)}"/>')
    return "".join(out)


def _wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if len(t) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def cover_svg(story, with_text=True):
    v = story.get("visual") or {}
    cat = story.get("cat", "")
    c = color_for(cat)
    seed = story.get("id", "x")
    rnd = random.Random(seed)
    R = H * .42
    mx, my = W * .74, H * .5
    uid = "".join(ch for ch in seed if ch.isalnum())[:24] or "x"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{escape(v.get("big", "") + " " + v.get("label", ""))}">',
             '<defs>',
             f'<radialGradient id="g-{uid}" cx="{_f(mx)}" cy="{_f(my)}" r="{_f(R*2.2)}" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="{c}" stop-opacity=".35"/><stop offset=".6" stop-color="{c}" stop-opacity=".08"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>',
             f'<filter id="glow-{uid}" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur in="SourceGraphic" stdDeviation="{_f(R*.08)}" result="b"/><feColorMatrix in="b" type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 .55 0" result="b2"/><feMerge><feMergeNode in="b2"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
             f'<filter id="grain-{uid}"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="{rnd.randint(1, 999)}"/><feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .06 0"/></filter>',
             '</defs>',
             f'<rect width="{W}" height="{H}" fill="{INK}"/>',
             f'<rect width="{W}" height="{H}" fill="url(#g-{uid})"/>']
    lines = "".join(f'<line x1="{i}" y1="{H}" x2="{i+H}" y2="0"/>' for i in range(-H, W, 26))
    parts.append(f'<g stroke="{PAPER}" stroke-opacity=".045" stroke-width="1">{lines}</g>')
    parts.append(f'<rect width="{W}" height="{H}" filter="url(#grain-{uid})"/>')
    parts.append(f'<g filter="url(#glow-{uid})">{motif_svg(v, mx, my, R, c, uid)}</g>')
    if with_text:
        pad = W * .045
        parts.append(f'<text x="{_f(pad)}" y="{_f(pad + H*.045)}" font-family="{MONO}" font-weight="500" font-size="{_f(H*.042)}" letter-spacing="2" fill="{c}">{escape(("METAFLORA NEWS · " + cat).upper())}</text>')
        big = str(v.get("big", ""))
        if big:
            fs = H * .3
            max_w = W * .52
            est = len(big) * fs * .74
            if est > max_w:
                fs *= max_w / est
            label_lines = _wrap(str(v.get("label", "")), 30)[:2]
            ly = H - pad - (H*.1 + (len(label_lines)-1)*H*.065 if label_lines else 0)
            parts.append(f'<text x="{_f(pad)}" y="{_f(ly)}" font-family="{DISPLAY}" font-weight="800" font-size="{_f(fs)}" fill="{PAPER}">{escape(big)}</text>')
            parts.append(f'<rect x="{_f(pad)}" y="{_f(ly + H*.022)}" width="{_f(min(len(big)*fs*.7, W*.3))}" height="5" fill="{c}"/>')
            for i, l in enumerate(label_lines):
                parts.append(f'<text x="{_f(pad)}" y="{_f(ly + H*.1 + i*H*.065)}" font-family="{MONO}" font-weight="500" font-size="{_f(H*.05)}" fill="{DIM}">{escape(l)}</text>')
    parts.append('</svg>')
    return "".join(parts)
