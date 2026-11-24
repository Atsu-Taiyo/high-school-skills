"""Editable chemistry SVG fragments in screen coordinates (x right, y down).

Geometry inherits stroke, stroke-width and fill from the caller. Use a group
with stroke="black" fill="none". Filled marks and text set their own paint.
"""
from itertools import groupby, product
from math import cos, radians, sin
from xml.sax.saxutils import escape

from hsfig import add, lerp, mul, perp, sub, unit


def _point(p):
    return f"{p[0]:.4f},{p[1]:.4f}"


def _path(d, attrs=""):
    return f'<path d="{d}" {attrs}/>'


def _chain(points, close=False, attrs=""):
    return _path("M" + " L".join(map(_point, points)) + (" Z" if close else ""), attrs)


def _circle(p, radius, fill):
    return f'<circle cx="{p[0]:g}" cy="{p[1]:g}" r="{radius:g}" fill="{fill}"/>'


_SUB = "₀₁₂₃₄₅₆₇₈₉"
_SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻"
_TRANSLATE = str.maketrans(_SUB + _SUP, "01234567890123456789+−")


CHEM_FONT = "Times New Roman, Times, Noto Serif, serif"
# Visual centre of a capital sits about this far above the typographic baseline.
_CAP_CENTER = 0.36


def _formula_runs(value):
    runs = []
    for shift, chars in groupby(value, lambda c: "sub" if c in _SUB else "super" if c in _SUP else ""):
        content = escape("".join(chars).translate(_TRANSLATE))
        if shift:
            content = f'<tspan font-size="75%" baseline-shift="{shift}">{content}</tspan>'
        runs.append(content)
    return "".join(runs)


def _chem_text(x, y, value, size, anchor, role=""):
    if anchor not in ("start", "middle", "end"):
        raise ValueError("unknown text anchor")
    role_attr = f' data-role="{role}"' if role else ""
    return (f'<text x="{x:g}" y="{y:g}" font-family="{CHEM_FONT}" font-size="{size:g}" '
            f'text-anchor="{anchor}" font-style="normal" fill="black" stroke="none"'
            f'{role_attr} xml:space="preserve">{_formula_runs(value)}</text>')


def formula(x, baseline, value, size=18, anchor="start"):
    """Upright type. Use Unicode indices/charges, baseline digits for coefficients."""
    return _chem_text(x, baseline, value, size, anchor)


def atom_label(x, y, value, size=18, anchor="middle"):
    """Upright element or group (C, OH, CH₃, Cl⁻). (x, y) is the visual centre of the capitals.

    Never italic: atom names are chemical symbols, not math variables. Bonds should
    stop short of the glyph; use bond_to_atom or atom_clearance for the inset.
    """
    return _chem_text(x, y + _CAP_CENTER * size, value, size, anchor, role="atom-label")


def atom_clearance(value, size=18, direction=None):
    """Distance from the atom centre to where an incoming bond should stop."""
    letters = "".join(c for c in value if c not in _SUB and c not in _SUP and not c.isspace()) or "C"
    em = 0.0
    for c in letters:
        em += 0.55 if c == "I" else 0.62 if c in "Jf" else 0.70 if c in "EFHL" else 0.80 if c in "OQG" else 0.74
    half_w = 0.5 * em * size + 0.08 * size
    half_h = 0.42 * size + 0.08 * size
    if not direction or (direction[0] == 0 and direction[1] == 0):
        return max(half_w, half_h)
    ux, uy = unit(direction)
    return 1.0 / ((ux * ux) / (half_w * half_w) + (uy * uy) / (half_h * half_h)) ** 0.5


def bond_to_atom(outer, centre, value, size=18, order=1, gap=4):
    """Bond from a vertex or previous atom toward centre, stopping short of the glyph."""
    direction = sub(centre, outer)
    end = sub(centre, mul(unit(direction), atom_clearance(value, size, direction)))
    return bond(outer, end, order, gap)


def bond(a, b, order=1, gap=4):
    """Centred parallel strokes for a single, double or triple bond."""
    if order not in (1, 2, 3):
        raise ValueError("bond order must be 1, 2, or 3")
    normal = perp(unit(sub(b, a)))
    lines = []
    for i in range(order):
        offset = mul(normal, gap * (i - (order-1)/2))
        lines.append(_chain([add(a, offset), add(b, offset)]))
    return "".join(lines)


def wedge(tip, end, width=9, hashes=0):
    """Narrow at tip. Use hashes >= 2 for a receding bond."""
    normal = mul(perp(unit(sub(end, tip))), width/2)
    if hashes == 0:
        return _chain([tip, add(end, normal), sub(end, normal)], True, 'fill="black" stroke="none"')
    if hashes < 2:
        raise ValueError("a hashed wedge needs at least two strokes")
    strokes = []
    for i in range(1, hashes+1):
        t = i / hashes
        centre = lerp(tip, end, t)
        strokes.append(_chain([sub(centre, mul(normal, t)), add(centre, mul(normal, t))]))
    return "".join(strokes)


def lone_pair(centre, separation=5, radius=1.4, angle=90):
    half = mul((cos(radians(angle)), sin(radians(angle))), separation/2)
    return '<g stroke="none">' + "".join(_circle(p, radius, "black")
                                         for p in (sub(centre, half), add(centre, half))) + '</g>'


def benzene(centre, radius, style="kekule", angle=-90, vertices=None):
    """Use six measured cyclic vertices in B or a regular hexagon in A."""
    points = list(vertices) if vertices is not None else [
        add(centre, mul((cos(radians(angle+i*60)), sin(radians(angle+i*60))), radius))
        for i in range(6)]
    if len(points) != 6 or style not in ("circle", "kekule"):
        raise ValueError("expected six vertices and circle or kekule style")
    outline = _chain(points, close=True)
    if style == "circle":
        return outline + _circle(centre, radius*0.57, "none")
    inside = [lerp(centre, p, 0.78) for p in points]
    return outline + "".join(bond(inside[i], inside[i+1]) for i in (0, 2, 4))


def reaction_arrow(x1, x2, y, kind="→", above="", below="", size=18, head=7, gap=5):
    """Horizontal scheme arrow. Multiple calls can share a product between steps."""
    direction = 1 if x2 > x1 else -1
    if x1 == x2 or kind not in ("→", "⇌", "↔"):
        raise ValueError("expected a nonzero arrow of type →, ⇌ or ↔")
    h = direction*head
    if kind == "⇌":
        top, bottom = y-gap/2, y+gap/2
        lines = [_chain([(x1,top), (x2,top), (x2-h,top-head/2)]),
                 _chain([(x2,bottom), (x1,bottom), (x1+h,bottom+head/2)])]
    else:
        lines = [bond((x1,y), (x2,y)), _chain([(x2-h,y-head/2),(x2,y),(x2-h,y+head/2)])]
        if kind == "↔":
            lines.append(_chain([(x1+h,y-head/2),(x1,y),(x1+h,y+head/2)]))
    for label, baseline in ((above, y-0.55*size), (below, y+1.35*size)):
        if label:
            lines.append(formula((x1+x2)/2, baseline, label, size, "middle"))
    return "".join(lines)


def vessel(x, y, width, height, kind="beaker"):
    """Open mouth. x,y is top centre, width is the widest outside span."""
    outlines = {
        "beaker": "M-0.52,0 L-0.5,.07 V.86 Q-.5,1 -.37,1 H.37 Q.5,1 .5,.86 V0",
        "erlenmeyer": "M-.14,0 V.28 L-.49,.90 Q-.53,1 -.40,1 H.40 Q.53,1 .49,.90 L.14,.28 V0",
        "round": "M-.13,0 V.30 C-.68,.47 -.58,1 0,1 C.58,1 .68,.47 .13,.30 V0",
    }
    return _scaled_path(x, y, width, height, outlines[kind])


def _scaled_path(x, y, width, height, d):
    # Normalized outlines have independent width and height. Preserve pen width.
    return (f'<g transform="translate({x:g} {y:g}) scale({width:g} {height:g})">'
            + _path(d, 'vector-effect="non-scaling-stroke"') + '</g>')


def burette(x, y, width, height, divisions=10):
    """Tip is centred below the stopcock. Graduations descend from the top."""
    d = ("M-.5,0 V.72 L-.13,.76 V.81 M.5,0 V.72 L.13,.76 V.81 "
         "M-.65,.81 H.7 V.85 H-.65 Z M-.13,.85 V.92 L0,1 L.13,.92 V.85")
    for i in range(divisions):
        mark = .05 + .65*i/max(1, divisions-1)
        d += f" M-.5,{mark:g} h{.48 if i%5==0 else .28}"
    return _scaled_path(x, y, width, height, d)


def condenser(a, b, radius=12):
    """Liebig condenser along a→b. Jacket ports on opposite sides near the ends."""
    n = perp(unit(sub(b,a)))
    def p(t,r):
        return add(lerp(a,b,t), mul(n,r*radius))
    lines = []
    for side, port in ((1,.24), (-1,.76)):
        lines += [_chain([p(0,.25*side),p(1,.25*side)]),
                  _chain([p(.12,.25*side),p(.12,side),p(port-.025,side),p(port-.025,1.8*side)]),
                  _chain([p(port+.025,1.8*side),p(port+.025,side),p(.88,side),p(.88,.25*side)])]
    return "".join(lines)


def gas_collection(x, y, width, height):
    """Inverted jar, submerged mouth, water surface and delivery tube."""
    return _scaled_path(x,y,width,height,
        "M0,.42 V1 H1 V.42 M0,.53 H.13963 M.17111,.53 H.48 M.82,.53 H1 "
        "M.48,.84 V.04 Q.48,0 .52,0 H.78 Q.82,0 .82,.04 V.84 "
        "M-.08,.22 H.07 Q.12,.22 .14,.32 L.22,.86 Q.23,.91 .29,.91 H.60 Q.64,.91 .64,.85 V.70 "
        "M-.08,.25 H.06 Q.10,.25 .11,.33 L.19,.87 Q.20,.94 .29,.94 H.60 Q.67,.94 .67,.85 V.70")


def electrode(x, top, width, depth, bubbles=()):
    """Draw a plate and the bubbles present at the supplied (cx,cy,r) positions."""
    plate = f'<rect x="{x-width/2:g}" y="{top:g}" width="{width:g}" height="{depth:g}"/>'
    return plate + "".join(_circle((cx,cy),r,"white") for cx,cy,r in bubbles)


def graph_axes(origin, right, top):
    """Plain axes without invented scales or arrowheads. Add source ticks/units."""
    x, y = origin
    return _chain([(x,top), origin, (right,y)])


def energy_profile(levels):
    """Smooth horizontal tangents at reactants, peaks, minima and products."""
    if len(levels) < 3 or any(b[0] <= a[0] for a,b in zip(levels,levels[1:])):
        raise ValueError("expected at least three ordered reaction-coordinate points")
    d = "M" + _point(levels[0])
    for a,b in zip(levels,levels[1:]):
        m = (a[0]+b[0])/2
        d += f" C{_point((m,a[1]))} {_point((m,b[1]))} {_point(b)}"
    return _path(d)


def measured_curve(points):
    """Observed titration or solubility points, in plot order and screen units."""
    return _chain(points)


def unit_cell(origin, side, depth, kind="simple", atom_radius=5, hidden_dash="4 3"):
    """Front lower-left origin. Depth points up and right. All atoms use one projection."""
    if side <= 0 or depth[0] <= 0 or depth[1] >= 0 or kind not in ("simple","bcc","fcc"):
        raise ValueError("use a positive side, upper-right depth and simple/bcc/fcc")
    def project(p):
        x, y, z = p
        return add(origin, (side*x + depth[0]*z, -side*y + depth[1]*z))
    corners = list(product((0,1), repeat=3))
    back_lower_left = (0,0,1)
    edges = []
    for point in corners:
        for axis in range(3):
            if point[axis] == 0:
                end = list(point)
                end[axis] = 1
                dashed = back_lower_left in (point,tuple(end))
                attrs = f'stroke-dasharray="{escape(hidden_dash)}"' if dashed and hidden_dash else ''
                edges.append(_chain([project(point),project(end)], attrs=attrs))
    atoms = corners[:]
    if kind == "bcc":
        atoms.append((.5,.5,.5))
    if kind == "fcc":
        for axis in range(3):
            for side_coord in (0,1):
                p = [.5,.5,.5]
                p[axis] = side_coord
                atoms.append(tuple(p))
    return "".join(edges) + "".join(_circle(project(p),atom_radius,"white") for p in atoms)


def element_tile(x, y, width, height, number, symbol, size=20):
    """Atomic number at upper left, upright symbol below. Place by group and period."""
    frame = f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" fill="none"/>'
    return frame + formula(x+4,y+size, str(number),size*.8) + formula(
        x+width/2,y+height*.75,symbol,size,"middle")
