"""Writes draft generation-area icons to the directory given as argv[1]."""
import sys, os
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath, QGuiApplication

_BG_PATH = QPainterPath()
_BG_PATH.addRoundedRect(QRectF(1.0924, 1.0924, 125.8153, 125.8153), 31.2081, 31.2081)


def _d(path: QPainterPath) -> str:
    """Converts a QPainterPath to SVG path data."""
    parts, i = [], 0
    while i < path.elementCount():
        e = path.elementAt(i)
        if e.isMoveTo():
            parts.append(('Z ' if parts else '') + f'M {e.x:.2f} {e.y:.2f}')
        elif e.isLineTo():
            parts.append(f'L {e.x:.2f} {e.y:.2f}')
        else:
            c2, end = path.elementAt(i + 1), path.elementAt(i + 2)
            parts.append(f'C {e.x:.2f} {e.y:.2f} {c2.x:.2f} {c2.y:.2f} {end.x:.2f} {end.y:.2f}')
            i += 2
        i += 1
    return ' '.join(parts) + ' Z'


def clipped(path: QPainterPath) -> str:
    """Returns SVG path data for a path clipped to the icon background, since QtSvg ignores clipPath."""
    return _d(path.intersected(_BG_PATH))


def _hill(y0, cx1, cy1, x1, y1, cx2=None, cy2=None, x2=None, y2=None):
    p = QPainterPath()
    p.moveTo(-4, y0)
    p.quadTo(cx1, cy1, x1, y1)
    if cx2 is not None:
        p.quadTo(cx2, cy2, x2, y2)
    p.lineTo(132, 132)
    p.lineTo(-4, 132)
    p.closeSubpath()
    return p
OUT = sys.argv[1]

HEAD = ('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<svg version="1.1" width="128" height="128" viewBox="0 0 128 128" '
        'xmlns="http://www.w3.org/2000/svg">\n')
BG_ATTRS = 'x="1.0924" y="1.0924" width="125.8153" height="125.8153" rx="31.2081" ry="31.2081"'
DEFS = f'''<defs>
  <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#4fb3ff"/><stop offset="1" stop-color="#bfe6ff"/></linearGradient>
  <linearGradient id="spark" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#fff06a"/><stop offset="0.55" stop-color="#ff8a3d"/>
    <stop offset="1" stop-color="#ff2fb4"/></linearGradient>
  <radialGradient id="beam" cx="0.5" cy="0" r="1">
    <stop offset="0" stop-color="#fffbd0" stop-opacity="0.95"/>
    <stop offset="1" stop-color="#fff3a0" stop-opacity="0.35"/></radialGradient>
</defs>
'''
BG = f'<rect {BG_ATTRS} fill="#f2f2f2"/>\n'
BG_STROKE = f'<rect {BG_ATTRS} fill="none" stroke="#000000" stroke-width="2.1847"/>\n'
TAIL = '</svg>\n'

SCENE = (f'<rect {BG_ATTRS} fill="url(#sky)"/>\n'
         '<circle cx="90" cy="38" r="14" fill="#ffd23f" stroke="#000" stroke-width="2.5"/>\n'
         f'<path d="{clipped(_hill(86, 30, 50, 66, 80, 96, 58, 132, 74))}" fill="#5cc24a" stroke="#000" '
         'stroke-width="2.5"/>\n'
         f'<path d="{clipped(_hill(106, 50, 86, 132, 102))}" fill="#2e8b3a" stroke="#000" stroke-width="2.5"/>\n')


def dim_outside(x, y, w, h, opacity=0.6):
    window = QPainterPath()
    window.addRect(QRectF(x, y, w, h))
    return f'<path fill-rule="evenodd" fill="#000" fill-opacity="{opacity}" d="{_d(_BG_PATH.subtracted(window))}"/>\n'


def handles(x, y, w, h, s=10, edges=False):
    pts = [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
    if edges:
        pts += [(x + w / 2, y), (x + w / 2, y + h), (x, y + h / 2), (x + w, y + h / 2)]
    return ''.join(f'<rect x="{px - s / 2}" y="{py - s / 2}" width="{s}" height="{s}" fill="#fff" '
                   f'stroke="#000" stroke-width="2.5"/>\n' for px, py in pts)


def brackets(x, y, w, h, arm, width, color='#000'):
    paths = [f'M {x} {y + arm} V {y} H {x + arm}',
             f'M {x + w - arm} {y} H {x + w} V {y + arm}',
             f'M {x + w} {y + h - arm} V {y + h} H {x + w - arm}',
             f'M {x + arm} {y + h} H {x} V {y + h - arm}']
    return ''.join(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
                   f'stroke-linecap="square" stroke-linejoin="miter"/>\n' for d in paths)


def sparkle(cx, cy, r, stroke=3.0, fill='url(#spark)'):
    k = r * 0.16
    d = (f'M {cx} {cy - r} C {cx + k} {cy - k} {cx + k} {cy - k} {cx + r} {cy} '
         f'C {cx + k} {cy + k} {cx + k} {cy + k} {cx} {cy + r} '
         f'C {cx - k} {cy + k} {cx - k} {cy + k} {cx - r} {cy} '
         f'C {cx - k} {cy - k} {cx - k} {cy - k} {cx} {cy - r} Z')
    return f'<path d="{d}" fill="{fill}" stroke="#000" stroke-width="{stroke}" stroke-linejoin="round"/>\n'


def write(name, body):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
        f.write(HEAD + DEFS + body + TAIL)


# A: lit window in a dimmed image, with corner resize handles (mirrors the on-canvas look).
X, Y, W, H = 26, 28, 76, 66
write('a_lit_window.svg', BG + SCENE + dim_outside(X, Y, W, H)
      + f'<rect x="{X}" y="{Y}" width="{W}" height="{H}" fill="none" stroke="#000" stroke-width="4"/>\n'
      + f'<rect x="{X}" y="{Y}" width="{W}" height="{H}" fill="none" stroke="#fff" stroke-width="1.5"/>\n'
      + handles(X, Y, W, H) + BG_STROKE)

# B: focus brackets around an AI sparkle, on the plain background.
write('b_brackets_sparkle.svg', BG + brackets(17, 17, 94, 94, 26, 9)
      + sparkle(60, 68, 32) + sparkle(91, 37, 13, stroke=2.5) + BG_STROKE)

# C: A and B combined: lit window marked by brackets, with a sparkle inside.
X, Y, W, H = 22, 24, 84, 74
write('c_lit_window_sparkle.svg', BG + SCENE + dim_outside(X, Y, W, H)
      + f'<rect x="{X}" y="{Y}" width="{W}" height="{H}" fill="none" stroke="#fff" stroke-width="1.5"/>\n'
      + brackets(X, Y, W, H, 20, 6)
      + sparkle(58, 64, 22) + BG_STROKE)

# D: camera lens (aperture) framed by brackets: the user's suggestion, for comparison.
blades = ''
import math
cx, cy, ro, ri = 64, 64, 34, 14
for i in range(6):
    a0 = math.radians(i * 60 - 90)
    a1 = math.radians(i * 60 - 30)
    p0 = (cx + ro * math.cos(a0), cy + ro * math.sin(a0))
    p1 = (cx + ro * math.cos(a1), cy + ro * math.sin(a1))
    q0 = (cx + ri * math.cos(a0 + math.radians(30)), cy + ri * math.sin(a0 + math.radians(30)))
    q1 = (cx + ri * math.cos(a1 + math.radians(30)), cy + ri * math.sin(a1 + math.radians(30)))
    shade = ['#3b3f46', '#4a4f57', '#565c66', '#3b3f46', '#4a4f57', '#565c66'][i]
    blades += (f'<path d="M {p0[0]:.2f} {p0[1]:.2f} L {p1[0]:.2f} {p1[1]:.2f} L {q1[0]:.2f} {q1[1]:.2f} '
               f'L {q0[0]:.2f} {q0[1]:.2f} Z" fill="{shade}" stroke="#000" stroke-width="1.5"/>\n')
write('d_lens.svg', BG + brackets(14, 14, 100, 100, 24, 8)
      + f'<circle cx="{cx}" cy="{cy}" r="{ro + 6}" fill="#222" stroke="#000" stroke-width="3"/>\n'
      + f'<circle cx="{cx}" cy="{cy}" r="{ri + 1}" fill="url(#sky)"/>\n' + blades
      + f'<circle cx="{cx}" cy="{cy}" r="{ro}" fill="none" stroke="#000" stroke-width="2.5"/>\n'
      + sparkle(cx, cy, 11, stroke=2) + BG_STROKE)

# E: spotlight beam falling on a lit rectangle in a dimmed image.
X, Y, W, H = 28, 62, 72, 46
write('e_spotlight.svg', BG + SCENE + dim_outside(X, Y, W, H, 0.62)
      + f'<path d="M 54 6 H 74 L {X + W} {Y} H {X} Z" fill="url(#beam)"/>\n'
      + f'<rect x="{X}" y="{Y}" width="{W}" height="{H}" fill="none" stroke="#000" stroke-width="4"/>\n'
      + sparkle(64, 18, 13, stroke=2.5) + BG_STROKE)
