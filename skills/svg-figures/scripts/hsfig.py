#!/usr/bin/env python3
"""hsfig — 高校数学・物理の図を SVG で描くための小さなヘルパー（Python 標準ライブラリのみ）。

考え方
  * 図は「数学座標」（y 上向き）で組み立てる。SVG 座標（y 下向き，px）への変換は
    Figure.px() の1か所だけで行う。
  * 交点・接点・垂線の足・像の位置などは，このモジュールの幾何関数で計算する。
  * ラベルは最後にまとめて配置する。dir="auto" なら線・他のラベルを避け，
    図の重心から離れる側に置く。置き場が無いときは Figure.warnings に残る。
  * 出力は変換（transform）・外部参照・CSS を使わない素の SVG。lint_svg.py で検査できる。

最小の例
    from hsfig import Figure
    fig = Figure(-2, 3, -1, 5, unit=40, title="放物線", desc="y=x^2 のグラフ")
    fig.axes()
    fig.plot(lambda x: x * x, -2, 3)
    fig.label("$y=x^2$", (2, 4), dir="E")
    fig.save("parabola.svg")

ラベルの書き方（TeX 風の最小記法）
    "A"            立体（点の名前，O，数字，和文）
    "$x$" "$mg$"   $...$ の中の英字・ギリシャ小文字はイタリック，数字・記号は立体
    "$x_1$" "$x^2$" "$a_{n+1}$"   添字・指数
    "$\\theta$" "$\\sin x$" "$\\vec{a}$" "$\\sqrt{2}$" "$F'$" "$-1$"
    "$\\frac{5}{6}$" "$M=\\sin 1-\\frac{5}{6}$"   分数は縦組み（分子・括線・分母）
    "C$(0, 0, 2)$"   座標のカンマの後には空白が入る（"(0,0,2)" と書いても補う）
    "5/6" のような斜線の分数は使わない（save() が警告する）。
"""
from __future__ import annotations

import math
import re
import sys
import zlib
from xml.sax.saxutils import escape

__all__ = [
    "Figure", "add", "sub", "mul", "dot", "cross", "norm", "dist", "unit", "perp",
    "rotate", "polar", "lerp", "midpoint", "centroid", "angle_deg", "foot", "reflect",
    "intersect_lines", "intersect_line_circle", "intersect_circles", "tangent_points",
    "circumcenter", "incenter", "inradius", "orthocenter", "deriv", "solve",
    "tangent_at", "oblique", "lens_image", "circle_region", "region_between", "parse_label",
]

# ---------------------------------------------------------------- 幾何（数学座標）


def add(p, q):
    return (p[0] + q[0], p[1] + q[1])


def sub(p, q):
    return (p[0] - q[0], p[1] - q[1])


def mul(p, k):
    return (p[0] * k, p[1] * k)


def dot(p, q):
    return p[0] * q[0] + p[1] * q[1]


def cross(p, q):
    return p[0] * q[1] - p[1] * q[0]


def norm(p):
    return math.hypot(p[0], p[1])


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def unit(p):
    n = norm(p)
    if n == 0:
        raise ValueError("長さ 0 のベクトルは正規化できない")
    return (p[0] / n, p[1] / n)


def perp(p):
    """反時計回りに 90° 回したベクトル。"""
    return (-p[1], p[0])


def rotate(p, deg, center=(0.0, 0.0)):
    """center のまわりに反時計回りに deg 度回す。"""
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    x, y = p[0] - center[0], p[1] - center[1]
    return (center[0] + c * x - s * y, center[1] + s * x + c * y)


def polar(r, deg, center=(0.0, 0.0)):
    t = math.radians(deg)
    return (center[0] + r * math.cos(t), center[1] + r * math.sin(t))


def lerp(a, b, t):
    """a から b へ t:(1-t) に内分（t=0.5 が中点，t>1 で外分）。"""
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def midpoint(a, b):
    return lerp(a, b, 0.5)


def centroid(*pts):
    n = len(pts)
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)


def angle_deg(p, origin=(0.0, 0.0)):
    """origin から見た p の偏角（度，-180〜180）。"""
    return math.degrees(math.atan2(p[1] - origin[1], p[0] - origin[0]))


def foot(p, a, b):
    """点 p から直線 ab に下ろした垂線の足。"""
    d = sub(b, a)
    t = dot(sub(p, a), d) / dot(d, d)
    return lerp(a, b, t)


def reflect(p, a, b):
    """直線 ab に関する p の対称点。"""
    h = foot(p, a, b)
    return (2 * h[0] - p[0], 2 * h[1] - p[1])


def intersect_lines(a, b, c, d):
    """直線 ab と直線 cd の交点。平行なら ValueError。"""
    r, s = sub(b, a), sub(d, c)
    den = cross(r, s)
    if abs(den) < 1e-12:
        raise ValueError("2直線が平行で交点が無い")
    t = cross(sub(c, a), s) / den
    return lerp(a, b, t)


def intersect_line_circle(a, b, c, r):
    """直線 ab と中心 c 半径 r の円の交点（0〜2個。a→b の向きの順）。"""
    d = unit(sub(b, a))
    h = foot(c, a, b)
    k2 = r * r - dist(c, h) ** 2
    if k2 < -1e-12:
        return []
    if k2 < 1e-12:
        return [h]
    k = math.sqrt(k2)
    return [sub(h, mul(d, k)), add(h, mul(d, k))]


def intersect_circles(c1, r1, c2, r2):
    """2円の交点（0〜2個）。"""
    d = dist(c1, c2)
    if d == 0 or d > r1 + r2 + 1e-12 or d < abs(r1 - r2) - 1e-12:
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h2 = max(r1 * r1 - a * a, 0.0)
    u = unit(sub(c2, c1))
    m = add(c1, mul(u, a))
    if h2 < 1e-18:
        return [m]
    h = math.sqrt(h2)
    return [add(m, mul(perp(u), h)), sub(m, mul(perp(u), h))]


def tangent_points(p, c, r):
    """円外の点 p から中心 c 半径 r の円に引いた接線の接点（2個）。"""
    d = dist(p, c)
    if d <= r:
        raise ValueError("点が円の内部または円周上にあり接線が2本引けない")
    return intersect_circles(c, r, midpoint(p, c), d / 2)


def circumcenter(a, b, c):
    d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    if abs(d) < 1e-12:
        raise ValueError("3点が一直線上にある")
    sa, sb, sc = dot(a, a), dot(b, b), dot(c, c)
    return ((sa * (b[1] - c[1]) + sb * (c[1] - a[1]) + sc * (a[1] - b[1])) / d,
            (sa * (c[0] - b[0]) + sb * (a[0] - c[0]) + sc * (b[0] - a[0])) / d)


def incenter(a, b, c):
    la, lb, lc = dist(b, c), dist(c, a), dist(a, b)
    s = la + lb + lc
    return ((la * a[0] + lb * b[0] + lc * c[0]) / s, (la * a[1] + lb * b[1] + lc * c[1]) / s)


def inradius(a, b, c):
    return abs(cross(sub(b, a), sub(c, a))) / (dist(b, c) + dist(c, a) + dist(a, b))


def orthocenter(a, b, c):
    return intersect_lines(a, foot(a, b, c), b, foot(b, c, a))


def deriv(f, x, h=1e-5):
    """中心差分による微分係数。"""
    return (f(x + h) - f(x - h)) / (2 * h)


def solve(f, a, b, tol=1e-12):
    """区間 [a,b] で f(x)=0 の解を二分法で求める（両端で符号が異なること）。"""
    fa, fb = f(a), f(b)
    if fa == 0:
        return a
    if fb == 0:
        return b
    if fa * fb > 0:
        raise ValueError("区間の両端で符号が同じ。区間を取り直す")
    for _ in range(200):
        m = (a + b) / 2
        fm = f(m)
        if fm == 0 or (b - a) / 2 < tol:
            return m
        if fa * fm < 0:
            b = m
        else:
            a, fa = m, fm
    return (a + b) / 2


def tangent_at(f, a):
    """y=f(x) の x=a における接点と傾き ((a, f(a)), f'(a))。"""
    return (a, f(a)), deriv(f, a)


def oblique(p, angle=45, ratio=0.5):
    """斜投影（キャビネット図）。空間の点 (x, y, z) を平面の点に移す。

    y 軸が右，z 軸が上，x 軸が手前（左下 angle 度の向き）で，x 方向だけ ratio 倍に縮める。
    """
    x, y, z = p
    t = math.radians(angle)
    return (y - ratio * x * math.cos(t), z - ratio * x * math.sin(t))


def lens_image(a, f):
    """薄いレンズの写像公式 1/a + 1/b = 1/f。物体距離 a，焦点距離 f（凹レンズは f<0）。

    戻り値 (b, m)。b>0 は実像（レンズの後方），b<0 は虚像（前方）。m=-b/a は倍率（負は倒立）。
    """
    if abs(a - f) < 1e-12:
        raise ValueError("物体が焦点上にあり像ができない")
    b = a * f / (a - f)
    return b, -b / a


def circle_region(c, r, n=96):
    """ハッチング用に円を多角形（点の列）にする。"""
    return [polar(r, 360 * i / n, c) for i in range(n)]


def region_between(f, g, a, b, n=200):
    """x=a..b で y=f(x) と y=g(x) に挟まれた領域の多角形。"""
    xs = [a + (b - a) * i / n for i in range(n + 1)]
    return [(x, f(x)) for x in xs] + [(x, g(x)) for x in reversed(xs)]


# ---------------------------------------------------------------- ラベルの記法

_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "theta": "θ",
    "lambda": "λ", "mu": "μ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ",
    "phi": "φ", "varphi": "φ", "omega": "ω", "eta": "η", "kappa": "κ", "nu": "ν", "xi": "ξ",
    "varepsilon": "ε", "chi": "χ", "psi": "ψ", "zeta": "ζ", "ell": "ℓ",
}   # phi と varphi は同じ字形（φ）にする。本文は varphi で書く
_SYMBOL = {
    "Delta": "Δ", "Omega": "Ω", "Sigma": "Σ", "Phi": "Φ", "fallingdotseq": "≒", "ll": "≪",
    "gg": "≫", "otimes": "⊗", "odot": "⊙", "cdot": "·", "times": "×", "div": "÷",
    "le": "≦", "leq": "≦", "ge": "≧", "geq": "≧", "ne": "≠", "neq": "≠", "pm": "±",
    "angle": "∠", "triangle": "△", "circ": "°", "prime": "′", "infty": "∞", "perp": "⊥",
    "parallel": "∥", "cap": "∩", "cup": "∪", "to": "→", "quad": "\u2003", ",": "\u2009",
}
_FUNCS = {"sin", "cos", "tan", "log", "lim", "max", "min"}
_REL = "=<>≦≧≠≒≪≫"


class _Run:
    __slots__ = ("text", "italic", "script", "over")

    def __init__(self, text, italic=False, script=0, over=None):
        self.text, self.italic, self.script, self.over = text, italic, script, over


class _Frac:
    """縦組みの分数（分子・分母はそれぞれ _Run の列）。"""
    __slots__ = ("num", "den")

    def __init__(self, num, den):
        self.num, self.den = num, den


def _group(s, i):
    """s[i] から1トークン（{...} か \\name か1文字）を取り，(中身, 次の位置) を返す。"""
    if i >= len(s):
        return "", i
    if s[i] == "{":
        depth, j = 1, i + 1
        while j < len(s) and depth:
            depth += {"{": 1, "}": -1}.get(s[j], 0)
            j += 1
        return s[i + 1:j - 1], j
    if s[i] == "\\":
        j = i + 1
        while j < len(s) and s[j].isalpha():
            j += 1
        return s[i:j], j
    return s[i], i + 1


def _math_runs(s, script=0, over=None):
    runs, i = [], 0

    def put(text, italic=False):
        runs.append(_Run(text, italic, script, over))

    while i < len(s):
        c = s[i]
        if c == "\\":
            j = i + 1
            while j < len(s) and s[j].isalpha():
                j += 1
            name = s[i + 1:j] or s[j:j + 1]
            i = j if j > i + 1 else j + 1
            if name in ("vec", "sqrt", "overline"):
                body, i = _group(s, i)
                if name == "sqrt":
                    put("√")
                runs.extend(_math_runs(body, script, "vec" if name == "vec" else "bar"))
            elif name in ("frac", "dfrac", "tfrac"):
                num, i = _group(s, i)
                den, i = _group(s, i)
                if script:   # 添字・指数の中では縦に組めないので a/b にする
                    runs.extend(_math_runs(num + "/" + den, script, over))
                else:
                    runs.append(_Frac(_merge(_math_runs(num)), _merge(_math_runs(den))))
            elif name in _GREEK:
                put(_GREEK[name], True)
            elif name in _SYMBOL:
                put(_SYMBOL[name])
            elif name in _FUNCS:
                lead = ("\u2009" if runs and not isinstance(runs[-1], _Frac)
                        and runs[-1].text[-1:].isalnum() else "")
                put(lead + name + ("\u2009" if i < len(s) and s[i] not in "^_({" else ""))
                while i < len(s) and s[i] == " ":
                    i += 1
            elif name == "mathrm" or name == "text":
                body, i = _group(s, i)
                put(body)
            else:
                put(name)
        elif c in "_^":
            body, i = _group(s, i + 1)
            if c == "^" and body.strip() in ("\\circ", "°", "∘"):
                put("°")    # 角度の ° は指数にしない（小さく浮いて「˚」に見える）
            else:
                runs.extend(_math_runs(body, -1 if c == "_" else 1, over))
        elif c == " ":
            i += 1
        elif c == "~":
            put(" ")
            i += 1
        elif c == "'":
            put("′")
            i += 1
        elif c == ",":
            put(", ")   # 座標 (a, b) のカンマの後は空ける
            i += 1
        elif c == "-":
            prev = "" if not runs else "0" if isinstance(runs[-1], _Frac) else runs[-1].text[-1:]
            binary = prev not in ("", "(", ",", "\u2009") and prev not in _REL
            put("\u2009−\u2009" if binary and script == 0 else "−")
            i += 1
        elif c == "+":
            put("\u2009+\u2009" if runs and script == 0 else "+")
            i += 1
        elif c in _REL:
            put("\u2009" + c + "\u2009" if script == 0 else c)
            i += 1
        elif c.isalpha() and ord(c) < 0x250:
            put(c, True)
            i += 1
        else:
            put(c)
            i += 1
    return runs


def _merge(runs):
    merged = []
    for r in runs:
        m = merged[-1] if merged else None
        if (m is not None and not isinstance(m, _Frac) and not isinstance(r, _Frac)
                and (m.italic, m.script, m.over) == (r.italic, r.script, r.over)):
            m.text += r.text
        else:
            merged.append(r)
    return merged


def _coord_commas(text):
    """括弧の中のカンマの後に空白を補う： "(0,0,2)" → "(0, 0, 2)"。"""
    return re.sub(r"\([^()]*\)", lambda m: re.sub(r",(?=\S)", ", ", m.group(0)), text)


def parse_label(s):
    """ラベル文字列を _Run と _Frac の列にする。"""
    runs = []
    s = str(s).replace("\u02da", "°").replace("\u00ba", "°")   # ˚ º を度の記号 ° に直す
    for k, part in enumerate(s.split("$")):
        if not part:
            continue
        if k % 2:
            runs.extend(_math_runs(part))
        else:
            runs.append(_Run(_coord_commas(part)))
    return _merge(runs)


def _plain(items):
    out = ""
    for it in items:
        out += (_plain(it.num) + "/" + _plain(it.den)) if isinstance(it, _Frac) else it.text
    return out


def _char_em(c):
    o = ord(c)
    if o >= 0x2E80:
        return 1.0
    if c == " ":
        return 0.25
    if c == "\u2009":
        return 0.17
    if c == "\u2003":
        return 1.0
    if c in "MWmw":
        return 0.82
    if c in "ijlItfr":
        return 0.32
    if c.isupper():
        return 0.68
    if c.isdigit():
        return 0.5
    if c in "=+−<>≦≧≠≒≪≫±×÷→∥⊥∠△∩∪√∞⊗⊙":
        return 0.6
    if c in "()[],.′'·°:;":
        return 0.33
    return 0.48


def _run_width(run, fs):
    if isinstance(run, _Frac):
        return max(sum(_run_width(r, fs) for r in run.num),
                   sum(_run_width(r, fs) for r in run.den)) + 7
    k = 0.7 if run.script else 1.0
    return sum(_char_em(c) for c in run.text) * fs * k


# ---------------------------------------------------------------- 図本体

WIDTH = {"main": 1.5, "aux": 1.0, "axis": 1.0, "thin": 0.6, "force": 2.2, "circuit": 1.2,
         "dash": 1.0, "hidden": 1.0, "chain": 1.0, "dot": 1.0}
DASH = {"dash": "5 3", "hidden": "5 3", "chain": "9 3 1.5 3", "dot": "1.5 3.5"}
_ARROW = {  # 名前: (長さ, 半幅, くびれ, 線を縮める量)
    "arr": (9.0, 3.2, 2.2, 5.0),
    "frc": (12.0, 4.4, 3.0, 7.0),
    "dim": (7.0, 2.3, 1.6, 4.0),     # 寸法線用の小さい矢じり
}
DIM_OFFSET = 16   # 図形から1段目の寸法線までの距離（px）
DIM_STEP = 20     # 寸法線の段の間隔（px）
MIN_TEXT_PX = 12  # 最終表示での本文字の最小サイズ（px）。添字は 9px（約 7pt）


def _arrow_kind(width):
    """線幅に合う矢じりの種類。矢じりの幅は線幅の4倍以上にする（太線に埋もれない）。"""
    if width <= 1.6:
        return "arr"
    if width <= 2.3:
        return "frc"
    name = "w%d" % round(width * 10)
    if name not in _ARROW:
        k = width / 2.2
        _ARROW[name] = (12.0 * k, 4.4 * k, 3.0 * k, 7.0 * k)
    return name
_COMPASS = {"E": 0, "NE": 45, "N": 90, "NW": 135, "W": 180, "SW": 225, "S": 270, "SE": 315}
FONT = ("'Times New Roman', Times, 'Nimbus Roman', 'Liberation Serif', "
        "'Hiragino Mincho ProN', 'Yu Mincho', 'Noto Serif CJK JP', serif")


def _f(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _seg_hits_box(p, q, box):
    """線分 pq が長方形 box=(x0,y0,x1,y1) と交わるか（Liang–Barsky）。"""
    x0, y0, x1, y1 = box
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pp == 0:
            if qq < 0:
                return False
        else:
            t = qq / pp
            if pp < 0:
                if t > t1:
                    return False
                t0 = max(t0, t)
            else:
                if t < t0:
                    return False
                t1 = min(t1, t)
    return t0 <= t1


class Figure:
    """数学座標の窓 [xmin,xmax]×[ymin,ymax] を持つ図。

    unit は x 方向の 1 が何 px か。yunit を省くと x と同じ縮尺（グラフの既定）。
    margin は窓の外側の余白（px）。数値1つ，または (左, 右, 上, 下)。
    display_width は教材に置くときの表示幅（px）。図の幅より小さいと全体が縮むので，
    縮めた後の文字が最小サイズ（本文字 12px，添字 9px）を下回ると save() が警告する。
    横長の図（レンズ，回路，数直線）では必ず指定する。
    縦横の縮尺を変えたら note() で注記を入れるか，y 軸に数値の目盛りを入れる
    （どちらも無いと save() が警告する。v-t グラフのように縦横が別の量で，
    記号だけの概形を描くときは aspect_ok=True）。
    """

    def __init__(self, xmin, xmax, ymin, ymax, unit=40, yunit=None, margin=28,
                 title="", desc="", font_size=14, id=None, aspect_ok=False, display_width=None):
        if not (xmax > xmin and ymax > ymin):
            raise ValueError("窓の範囲が不正")
        self.xmin, self.xmax, self.ymin, self.ymax = xmin, xmax, ymin, ymax
        self.ux = float(unit)
        self.uy = float(yunit if yunit is not None else unit)
        if isinstance(margin, (int, float)):
            margin = (margin,) * 4
        self.ml, self.mr, self.mt, self.mb = margin
        self.W = self.ml + self.mr + (xmax - xmin) * self.ux
        self._H0 = self.mt + self.mb + (ymax - ymin) * self.uy
        self._note = None
        self._numeric_ytick = False
        self.aspect_ok = aspect_ok
        self.display_width = display_width   # 教材に置くときの表示幅（px）。文字の最小サイズの検査に使う
        self.dim_offset, self.dim_step = DIM_OFFSET, DIM_STEP
        self.force_unit = 1.0   # 力の大きさ 1 を表す矢印の長さ（数学座標）
        self._forces = []
        self.title, self.desc, self.fs = title, desc, font_size
        self.id = id or "f%06x" % (zlib.crc32(f"{title}|{desc}|{self.W}|{self.H}".encode()) & 0xFFFFFF)
        self._items = []     # (layer, 連番, svg 文字列)
        self._segs = []      # ラベルが避ける線分（px）
        self._dots = []      # ラベルが避ける点（px）
        self._labels = []
        self._markers = set()
        self.warnings = []

    @property
    def H(self):
        return self._H0 + (self._note[1] * 2.0 if self._note else 0.0)

    def note(self, text, size=11):
        """図の下に小さな注記を入れる（例 "※ 縦軸方向は拡大して描いてある"）。

        注記は縮尺・模式図であることの断りを1文で書く。記号の説明や凡例は図に入れず，
        本文のキャプションに書く。
        """
        if "。" in text.rstrip("。") or len(text) > 32:
            self.warnings.append(f"注記「{text}」が長い。図の注記は1文にし，説明は本文のキャプションに書く")
        self._note = (text, size)

    # ---- 座標 ----
    def px(self, p):
        """数学座標 → SVG 座標（px）。y の反転はここだけ。"""
        return (self.ml + (p[0] - self.xmin) * self.ux, self.mt + (self.ymax - p[1]) * self.uy)

    def _vec_px(self, v):
        return (v[0] * self.ux, -v[1] * self.uy)

    # ---- 低水準 ----
    def _put(self, svg, layer=1):
        self._items.append((layer, len(self._items), svg))

    def _stroke(self, style="main", dash=None, width=None):
        w = width if width is not None else WIDTH[style]
        d = dash if dash is not None else (style if style in DASH else None)
        if d is True:
            d = "dash"
        s = f' stroke-width="{_f(w)}"'
        if d:
            s += f' stroke-dasharray="{DASH.get(d, d)}" stroke-linecap="butt"'
        return s

    def _marker(self, kind, end):
        name = f"{self.id}-{kind}-{'e' if end else 's'}"
        self._markers.add((kind, end))
        return name

    def _path(self, pts, closed=False, style="main", dash=None, width=None, arrow=None,
              fill=None, layer=1, register=True, cls=None, kind=None):
        """px の点列を1本のパスとして描く。arrow は None / "end" / "start" / "both"。"""
        pts = [tuple(p) for p in pts]
        if len(pts) < 2:
            return
        if register:
            ring = pts + [pts[0]] if closed else pts
            self._segs.extend((a, b) for a, b in zip(ring, ring[1:]))
        attrs = self._stroke(style, dash, width)
        if arrow:
            kind = kind or _arrow_kind(width if width is not None else WIDTH[style])
            short = _ARROW[kind][3]
            if arrow in ("end", "both"):
                a, b = pts[-2], pts[-1]
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                if L > short:
                    pts[-1] = (b[0] - (b[0] - a[0]) / L * short, b[1] - (b[1] - a[1]) / L * short)
                attrs += f' marker-end="url(#{self._marker(kind, True)})"'
            if arrow in ("start", "both"):
                a, b = pts[0], pts[1]
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                if L > short:
                    pts[0] = (a[0] + (b[0] - a[0]) / L * short, a[1] + (b[1] - a[1]) / L * short)
                attrs += f' marker-start="url(#{self._marker(kind, False)})"'
        if fill:
            attrs += f' fill="{fill}"'
        if cls:
            attrs += f' class="{cls}"'
        d = "M" + " L".join(f"{_f(x)},{_f(y)}" for x, y in pts) + (" Z" if closed else "")
        self._put(f'<path d="{d}"{attrs}/>', layer)

    def _mid_arrow(self, a, b, style, kind=None, t=0.5, width=None):
        """px の線分 ab の途中に進行方向の矢じりを付ける（大きさは線幅に合わせる）。"""
        w = width if width is not None else WIDTH[style]
        kind = kind or _arrow_kind(w)
        alen, _, _, short = _ARROW[kind]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 2 * alen:
            self.warnings.append("向きの矢じり: 線が短くて矢じりを置けない（線を長くするか，横に矢印を添える）")
            return
        u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        tip = (a[0] + u[0] * (L * t + alen / 2), a[1] + u[1] * (L * t + alen / 2))
        tail = (tip[0] - u[0] * (short + 3), tip[1] - u[1] * (short + 3))
        self._path([tail, tip], style=style if style not in DASH else "aux", width=w, arrow="end",
                   kind=kind, register=False)

    # ---- 線・多角形・円 ----
    def segment(self, a, b, style="main", dash=None, arrow=None, width=None, arrow_at=0.5):
        """線分 ab。arrow は None / "end" / "start" / "both" / "mid"。

        "mid" は線の途中（arrow_at の割合の位置）に a→b の向きの矢じりを置く。
        矢じりの大きさは線幅に合わせて決まる（太い線でも埋もれない）。
        """
        pa, pb = self.px(a), self.px(b)
        self._path([pa, pb], style=style, dash=dash, width=width,
                   arrow=None if arrow == "mid" else arrow)
        if arrow == "mid":
            self._mid_arrow(pa, pb, style, t=arrow_at, width=width)

    def mid_arrow(self, a, b, t=0.5, style="main", width=None):
        """すでに描いた線・曲線の途中に，a→b の向きの矢じりだけを置く。

        サイクル図の過程の向き，磁力線・電流の向きなど。曲線では，置きたい位置の
        前後の2点（曲線上）を a, b に渡す。style・width は下の線と同じにする。
        """
        pa, pb = self.px(a), self.px(b)
        w = width if width is not None else WIDTH[style]
        kind = _arrow_kind(w)
        alen, _, _, short = _ARROW[kind]
        L = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        u = ((pb[0] - pa[0]) / L, (pb[1] - pa[1]) / L)
        c = (pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t)
        tip = (c[0] + u[0] * alen / 2, c[1] + u[1] * alen / 2)
        self._path([(tip[0] - u[0] * (short + 3), tip[1] - u[1] * (short + 3)), tip],
                   style=style if style not in DASH else "aux", width=w, arrow="end", kind=kind,
                   register=False)

    def arrow(self, a, b, style="main", dash=None):
        """a から b への矢印（ベクトルなど）。"""
        self.segment(a, b, style=style, dash=dash, arrow="end")

    def line_through(self, a, b, style="main", dash=None, pad=0.0):
        """a, b を通る直線を窓いっぱいに描く。戻り値は両端。"""
        d = sub(b, a)
        t0, t1 = -math.inf, math.inf
        for p0, dd, lo, hi in ((a[0], d[0], self.xmin - pad, self.xmax + pad),
                               (a[1], d[1], self.ymin - pad, self.ymax + pad)):
            if abs(dd) < 1e-12:
                if not lo <= p0 <= hi:
                    return None
                continue
            ta, tb = (lo - p0) / dd, (hi - p0) / dd
            t0, t1 = max(t0, min(ta, tb)), min(t1, max(ta, tb))
        if t0 >= t1:
            return None
        p, q = lerp(a, b, t0), lerp(a, b, t1)
        self.segment(p, q, style=style, dash=dash)
        return p, q

    def polyline(self, pts, closed=False, style="main", dash=None, fill=None, arrow=None,
                 width=None):
        """折れ線。arrow="mid" で各辺の中央に進行方向の矢じり（閉じた経路の向きなど）。"""
        px = [self.px(p) for p in pts]
        self._path(px, closed=closed, style=style, dash=dash, fill=fill, width=width,
                   arrow=None if arrow == "mid" else arrow)
        if arrow == "mid":
            ring = px + [px[0]] if closed else px
            for p, q in zip(ring, ring[1:]):
                self._mid_arrow(p, q, style, width=width)

    def polygon(self, pts, style="main", dash=None, fill=None):
        """多角形。fill="#fff" で下の線を隠す，"#ddd" などで薄い灰色。"""
        self.polyline(pts, closed=True, style=style, dash=dash, fill=fill)

    def circle(self, c, r, style="main", dash=None, fill=None):
        """中心 c，半径 r（数学座標）の円。縦横の縮尺が違えば楕円になる。"""
        cx, cy = self.px(c)
        rx, ry = r * self.ux, r * self.uy
        attrs = self._stroke(style, dash) + (f' fill="{fill}"' if fill else "")
        if abs(rx - ry) < 1e-9:
            self._put(f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(rx)}"{attrs}/>')
        else:
            self._put(f'<ellipse cx="{_f(cx)}" cy="{_f(cy)}" rx="{_f(rx)}" ry="{_f(ry)}"{attrs}/>')
        ring = [self.px(p) for p in circle_region(c, r, 48)]
        self._segs.extend(zip(ring, ring[1:] + ring[:1]))

    def ellipse(self, c, a, b, style="main", dash=None, n=120):
        """中心 c，x 方向の半径 a，y 方向の半径 b の楕円。"""
        self.polyline([(c[0] + a * math.cos(2 * math.pi * i / n),
                        c[1] + b * math.sin(2 * math.pi * i / n)) for i in range(n)],
                      closed=True, style=style, dash=dash)

    def arc(self, c, r, a0, a1, style="main", dash=None, arrow=None):
        """中心 c 半径 r の円弧を偏角 a0 度から a1 度へ（a1<a0 なら時計回り）。"""
        n = max(8, int(abs(a1 - a0) / 3))
        pts = [self.px(polar(r, a0 + (a1 - a0) * i / n, c)) for i in range(n + 1)]
        if arrow == "mid":
            self._path(pts, style=style, dash=dash)
            k = n // 2
            self._path([pts[k - 1], pts[k + 1]], style=style, arrow="end", register=False)
        else:
            self._path(pts, style=style, dash=dash, arrow=arrow)

    # ---- 関数のグラフ ----
    def sample(self, f, a, b, n=400, ylim=None):
        """y=f(x) を a..b で n 等分して計算し，窓の上下で切った折れ線の列を返す。

        定義されない点・窓の外に出る点で折れ線を分け，出入りの位置は二分法で求める
        （漸近線をまたぐ縦線は描かれない）。
        """
        lo, hi = ylim or (self.ymin, self.ymax)

        def val(x):
            try:
                y = f(x)
            except (ValueError, ZeroDivisionError, OverflowError):
                return None
            if isinstance(y, complex) or y != y or abs(y) == math.inf:
                return None
            return y

        def inside(x):
            y = val(x)
            return y is not None and lo <= y <= hi

        def edge(x_in, x_out):
            for _ in range(48):
                m = (x_in + x_out) / 2
                if inside(m):
                    x_in = m
                else:
                    x_out = m
            return (x_in, min(max(val(x_in), lo), hi))

        runs, cur, prev = [], [], None
        for i in range(n + 1):
            x = a + (b - a) * i / n
            ins = inside(x)
            if prev is not None:
                if ins and not prev[1]:
                    cur = [edge(x, prev[0])]
                elif not ins and prev[1]:
                    cur.append(edge(prev[0], x))
                    runs.append(cur)
                    cur = []
            if ins:
                cur.append((x, val(x)))
            prev = (x, ins)
        if len(cur) > 1:
            runs.append(cur)
        return [r for r in runs if len(r) > 1]

    def plot(self, f, a, b, n=400, style="main", dash=None, ylim=None):
        """y=f(x) のグラフ。n は分割数（200 以上）。戻り値は描いた折れ線（数学座標）の列。"""
        runs = self.sample(f, a, b, n, ylim)
        for r in runs:
            self.polyline(r, style=style, dash=dash)
        return runs

    def param(self, fx, fy, t0, t1, n=400, style="main", dash=None, closed=False):
        """媒介変数表示 (fx(t), fy(t)) の曲線。"""
        pts = [(fx(t0 + (t1 - t0) * i / n), fy(t0 + (t1 - t0) * i / n))
               for i in range(n + (0 if closed else 1))]
        self.polyline(pts, closed=closed, style=style, dash=dash)

    # ---- 座標軸・数直線 ----
    def _tick(self, spec):
        if isinstance(spec, (tuple, list)):
            v = spec[0]
            text = spec[1] if len(spec) > 1 else None
            d = spec[2] if len(spec) > 2 else None
        else:
            v, text, d = spec, None, None
        if text is None:
            text = f"${int(v) if float(v).is_integer() else v}$"
        return v, text, d

    def xaxis(self, label="$x$", ticks=(), y=0.0, x0=None, x1=None, tick_marks=True,
              label_dir="S"):
        """x 軸（右端に矢じり）。ticks は値，または (値, ラベル[, 向き]) の列。

        label_dir は軸の名前を置く向き（単位つきの長い名前は "N" などに変える）。
        """
        x0 = self.xmin if x0 is None else x0
        x1 = self.xmax if x1 is None else x1
        self.segment((x0, y), (x1, y), style="axis", arrow="end")
        if label:
            self.label(label, (x1, y), dir=label_dir, dist=5)
        for spec in ticks:
            v, text, d = self._tick(spec)
            if tick_marks:
                p = self.px((v, y))
                self._path([(p[0], p[1] - 3), (p[0], p[1] + 3)], style="axis", register=False)
            if text:
                self.label(text, (v, y), dir=d or "S", dist=5)

    def yaxis(self, label="$y$", ticks=(), x=0.0, y0=None, y1=None, tick_marks=True,
              label_dir="W"):
        """y 軸（上端に矢じり）。"""
        y0 = self.ymin if y0 is None else y0
        y1 = self.ymax if y1 is None else y1
        self.segment((x, y0), (x, y1), style="axis", arrow="end")
        if label:
            self.label(label, (x, y1), dir=label_dir, dist=5)
        for spec in ticks:
            v, text, d = self._tick(spec)
            if text and re.fullmatch(r"[-−]?\d+(\.\d+)?", text.replace("$", "").strip()):
                self._numeric_ytick = True
            if tick_marks:
                p = self.px((x, v))
                self._path([(p[0] - 3, p[1]), (p[0] + 3, p[1])], style="axis", register=False)
            if text:
                self.label(text, (x, v), dir=d or "W", dist=5)

    def axes(self, xlabel="$x$", ylabel="$y$", origin="O", xticks=(), yticks=(), tick_marks=True):
        """座標軸。原点の O は左下（第3象限側）に置く。"""
        self.xaxis(xlabel, xticks, tick_marks=tick_marks)
        self.yaxis(ylabel, yticks, tick_marks=tick_marks)
        if origin:
            self.label(origin, (0, 0), dir="SW", dist=4)

    def interval(self, a, b, closed_a=True, closed_b=True, y=0.0, h=14):
        """数直線上の区間の図示。a, b に None を渡すとその側は窓の端まで伸ばす。

        端点は 含む＝黒丸，含まない＝白丸。h は数直線からの高さ（px）。
        """
        xa = self.xmin if a is None else a
        xb = self.xmax if b is None else b
        pa, pb = self.px((xa, y)), self.px((xb, y))
        pts = [(pa[0], pa[1] - h), (pb[0], pb[1] - h)]
        if a is not None:
            pts.insert(0, pa)
        if b is not None:
            pts.append(pb)
        self._path(pts, style="main")
        if a is not None:
            self.dot((a, y), open=not closed_a)
        if b is not None:
            self.dot((b, y), open=not closed_b)

    # ---- 点・ラベル ----
    def dot(self, p, open=False, r=2.6):
        """点（黒丸）。open=True で白丸（含まない端点など）。"""
        x, y = self.px(p)
        if open:
            self._put(f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{_f(r + 0.4)}" fill="#fff" stroke-width="1.2"/>', 2)
        else:
            self._put(f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{_f(r)}" fill="#000" stroke="none"/>', 2)
        self._dots.append((x, y))

    def point(self, p, name=None, dir="auto", dist=6, away=None, dot=True):
        """点を打って名前を付ける。dir="auto" なら線を避け，away（省略時は図の重心）から離す。"""
        if dot:
            self.dot(p)
        if name:
            self.label(name, p, dir=dir, dist=dist, away=away)

    def label(self, text, at, dir="auto", dist=6, size=None, bg=False, away=None):
        """文字を置く。at は基準点（数学座標）。

        dir: "N" "NE" "E" "SE" "S" "SW" "W" "NW"，数学座標での角度（度），
             (dx, dy) の向き，"C"（基準点の真上に中心を置く），"auto"。
        dist: 基準点から文字の箱までの距離（px）。bg=True で白い下地を敷く。
        """
        self._add_label(text, self.px(at), self._dir(dir), dist, size, bg,
                        self.px(away) if away is not None else None)

    def _dir(self, d):
        if d is None or d == "auto":
            return None
        if d == "C":
            return (0.0, 0.0)
        if isinstance(d, str):
            d = _COMPASS[d.upper()]
        if isinstance(d, (int, float)):
            t = math.radians(d)
            return (math.cos(t), -math.sin(t))
        v = self._vec_px(d)
        n = math.hypot(*v)
        return (v[0] / n, v[1] / n)

    def _add_label(self, text, anchor, dsvg, dist=6, size=None, bg=False, away=None):
        fs = size or self.fs
        runs = parse_label(text)
        w = sum(_run_width(r, fs) for r in runs)
        if any(isinstance(r, _Frac) for r in runs):
            h = fs * 2.15
        else:
            h = fs * (1.2 if any(r.script for r in runs) else 1.0)
        if re.search(r"[\dπ]\s*/\s*\d", _plain([r for r in runs if not isinstance(r, _Frac)])):
            self.warnings.append(f"分数「{text}」が斜線になっている。\\frac{{分子}}{{分母}} で縦組みにする")
        plain = _plain(runs)
        if sum(1 for c in plain if ord(c) >= 0x3040) >= 12 or "。" in plain or "，" in plain:
            self.warnings.append(f"図中の文「{text}」は説明文になっている。図中は記号と短い名称だけにし，"
                                 "説明・凡例・式は本文のキャプションに書く")
        self._labels.append(dict(text=text, runs=runs, fs=fs, w=w, h=h, anchor=anchor,
                                 d=dsvg, dist=dist, bg=bg, away=away))

    @staticmethod
    def _center(L, d, dist):
        sx = max(-1.0, min(1.0, d[0] * 1.5))
        sy = max(-1.0, min(1.0, d[1] * 1.5))
        return (L["anchor"][0] + d[0] * dist + sx * L["w"] / 2,
                L["anchor"][1] + d[1] * dist + sy * L["h"] / 2)

    @staticmethod
    def _box(L, c, pad=0.0):
        return (c[0] - L["w"] / 2 - pad, c[1] - L["h"] / 2 - pad,
                c[0] + L["w"] / 2 + pad, c[1] + L["h"] / 2 + pad)

    def _cost(self, L, c, boxes):
        b = self._box(L, c, 1.0)
        cost = 0.0
        if b[0] < 1 or b[1] < 1 or b[2] > self.W - 1 or b[3] > self.H - 1:
            cost += 1e4
        for o in boxes:
            ox = min(b[2], o[2]) - max(b[0], o[0])
            oy = min(b[3], o[3]) - max(b[1], o[1])
            if ox > 0 and oy > 0:
                cost += 500 + ox * oy
        for (x, y) in self._dots:
            if (x, y) != L["anchor"] and b[0] - 3 < x < b[2] + 3 and b[1] - 3 < y < b[3] + 3:
                cost += 300
        inner = (b[0] + 1.5, b[1] + 2.5, b[2] - 1.5, b[3] - 2.5)
        cost += 60 * min(8, sum(1 for p, q in self._segs if _seg_hits_box(p, q, inner)))
        return cost

    def _resolve_labels(self):
        boxes = []
        fixed = [L for L in self._labels if L["d"] is not None]
        auto = [L for L in self._labels if L["d"] is None]
        for L in fixed:
            L["c"] = self._center(L, L["d"], L["dist"])
            boxes.append(self._box(L, L["c"]))
        for L in fixed:
            if L["bg"]:
                continue
            others = [b for b in boxes if b != self._box(L, L["c"])]
            if self._cost(L, L["c"], others) >= 60:
                self.warnings.append(f"ラベル「{L['text']}」が線・他のラベル・枠と重なっている可能性")
        if auto:
            ends = [p for s in self._segs for p in s] or [(self.W / 2, self.H / 2)]
            g = (sum(p[0] for p in ends) / len(ends), sum(p[1] for p in ends) / len(ends))
        for L in auto:
            ref = L["away"] or g
            ax, ay = L["anchor"][0] - ref[0], L["anchor"][1] - ref[1]
            an = math.hypot(ax, ay)
            best = None
            for k in range(16):
                t = 2 * math.pi * k / 16
                d = (math.cos(t), -math.sin(t))
                for mult, extra in ((1, 0.0), (2, 8.0)):
                    c = self._center(L, d, L["dist"] * mult)
                    cost = self._cost(L, c, boxes) + extra + k * 0.01
                    if an > 1e-6:
                        cost += 14 * (1 - (d[0] * ax + d[1] * ay) / an)
                    if best is None or cost < best[0]:
                        best = (cost, c)
            L["c"] = best[1]
            boxes.append(self._box(L, L["c"]))
            if best[0] >= 60:
                self.warnings.append(f"ラベル「{L['text']}」の置き場が無い（dir を指定するか図を広げる）")
        # ラベルどうしが接している（箱の間が 2px 未満）ものを知らせる
        Ls = [L for L in self._labels if not L.get("plain")]
        for i, A in enumerate(Ls):
            a = self._box(A, A["c"], 1.0)
            for B in Ls[i + 1:]:
                b = self._box(B, B["c"], 1.0)
                if min(a[2], b[2]) - max(a[0], b[0]) > 0 and min(a[3], b[3]) - max(a[1], b[1]) > 0:
                    self.warnings.append(f"ラベル「{A['text']}」と「{B['text']}」が接している・重なっている。"
                                         "離すか，leader() で引き出し線を付ける")

    def _runs_svg(self, runs, ax, x, base, fs, anchor, attrs=""):
        """_Run の列を1つの <text> にする。ax は基準の x，x は左端（上付きの線の位置用）。"""
        spans, extra, cur = [], [], 0.0
        for r in runs:
            target = {0: 0.0, -1: 0.26 * fs, 1: -0.40 * fs}[r.script]
            a = ""
            if r.italic:
                a += ' font-style="italic"'
            if r.script:
                a += f' font-size="{_f(fs * 0.7)}"'
            if abs(target - cur) > 1e-9:
                a += f' dy="{_f(target - cur)}"'
                cur = target
            rw = _run_width(r, fs)
            if r.over:
                tall = any(c.isupper() or c.isdigit() or c in "bdfhklt" for c in r.text)
                yy = base + target - (0.80 if tall else 0.58) * fs * (0.7 if r.script else 1)
                line = 'fill="none" stroke="#000" stroke-width="0.7" data-lint="skip"/>'
                if r.over == "vec":
                    x1, x2 = x + 0.5, x + max(rw, 6) + 1.5
                    extra.append(f'<path d="M{_f(x1)},{_f(yy)} L{_f(x2)},{_f(yy)} '
                                 f'M{_f(x2 - 3)},{_f(yy - 1.8)} L{_f(x2)},{_f(yy)} L{_f(x2 - 3)},{_f(yy + 1.8)}" '
                                 + line)
                else:
                    extra.append(f'<path d="M{_f(x - 0.5)},{_f(yy)} L{_f(x + rw + 0.5)},{_f(yy)}" ' + line)
            x += rw
            spans.append(f"<tspan{a}>{escape(r.text)}</tspan>" if a else escape(r.text))
        if fs != self.fs:
            attrs += f' font-size="{_f(fs)}"'
        if anchor != "middle":
            attrs += f' text-anchor="{anchor}"'
        return [f'<text x="{_f(ax)}" y="{_f(base)}"{attrs} xml:space="preserve">{"".join(spans)}</text>'] + extra

    def _label_svg(self, L):
        fs, (cx, cy) = L["fs"], L["c"]
        base = cy + 0.33 * fs
        out = []
        if L["bg"]:
            b = self._box(L, L["c"], 1.5)
            b = (b[0] - 1.5, b[1], b[2] + 1.5, b[3])     # 斜体の張り出しの分だけ左右を広く
            out.append(f'<rect x="{_f(b[0])}" y="{_f(b[1])}" width="{_f(b[2] - b[0])}" '
                       f'height="{_f(b[3] - b[1])}" fill="#fff" stroke="none"/>')
        skip = ' data-lint="skip"' if L["bg"] else ""
        groups = []   # 文字の塊と分数に分ける
        for it in L["runs"]:
            if isinstance(it, _Frac):
                groups.append(it)
            elif groups and isinstance(groups[-1], list):
                groups[-1].append(it)
            else:
                groups.append([it])
        x = cx - L["w"] / 2
        for k, g in enumerate(groups):
            w = sum(_run_width(r, fs) for r in g) if isinstance(g, list) else _run_width(g, fs)
            if isinstance(g, list):
                # 分数の隣の塊は分数側に寄せて固定する（文字幅の見積もりの誤差で隙間が開かない）
                before, after = k > 0, k < len(groups) - 1
                if before == after:
                    out += self._runs_svg(g, x + w / 2, x, base, fs, "middle", skip)
                elif after:
                    out += self._runs_svg(g, x + w, x, base, fs, "end", skip)
                else:
                    out += self._runs_svg(g, x, x, base, fs, "start", skip)
            else:
                mid, bar = x + w / 2, base - 0.30 * fs
                wn = sum(_run_width(r, fs) for r in g.num)
                wd = sum(_run_width(r, fs) for r in g.den)
                out += self._runs_svg(g.num, mid, mid - wn / 2, bar - 0.26 * fs, fs, "middle", skip)
                out += self._runs_svg(g.den, mid, mid - wd / 2, bar + 0.92 * fs, fs, "middle", skip)
                out.append(f'<path d="M{_f(x + 1.5)},{_f(bar)} L{_f(x + w - 1.5)},{_f(bar)}" fill="none" '
                           f'stroke="#000" stroke-width="0.8" stroke-linecap="butt" data-lint="skip"/>')
            x += w
        return "".join(out)

    # ---- 角・直角・等長・平行の印 ----
    def angle_mark(self, a, o, b, r=16, n=1, label=None, label_gap=3, reflex=False):
        """∠AOB の弧（180° 未満の側。reflex=True で優角）。n は弧の本数（等しい角は同じ本数）。"""
        po = self.px(o)
        ta = math.atan2(self.px(a)[1] - po[1], self.px(a)[0] - po[0])
        tb = math.atan2(self.px(b)[1] - po[1], self.px(b)[0] - po[0])
        sweep = (tb - ta) % (2 * math.pi)
        if (sweep > math.pi) != reflex:
            sweep -= 2 * math.pi
        steps = max(6, int(abs(sweep) / 0.1))
        for k in range(n):
            rr = r + 3 * k
            self._path([(po[0] + rr * math.cos(ta + sweep * i / steps),
                         po[1] + rr * math.sin(ta + sweep * i / steps)) for i in range(steps + 1)],
                       style="aux")
        if label:
            tm = ta + sweep / 2
            d = (math.cos(tm), math.sin(tm))
            rr = r + 3 * (n - 1)
            self._add_label(label, (po[0] + d[0] * rr, po[1] + d[1] * rr), d, label_gap)

    def right_angle(self, a, o, b, size=8):
        """直角の印（小さな正方形）。OA ⊥ OB であること。"""
        po, pa, pb = self.px(o), self.px(a), self.px(b)
        u = ((pa[0] - po[0]), (pa[1] - po[1]))
        v = ((pb[0] - po[0]), (pb[1] - po[1]))
        lu, lv = math.hypot(*u), math.hypot(*v)
        if abs(u[0] * v[0] + u[1] * v[1]) > 0.02 * lu * lv:
            self.warnings.append("right_angle: 2辺が直交していない")
        u, v = (u[0] / lu * size, u[1] / lu * size), (v[0] / lv * size, v[1] / lv * size)
        self._path([(po[0] + u[0], po[1] + u[1]), (po[0] + u[0] + v[0], po[1] + u[1] + v[1]),
                    (po[0] + v[0], po[1] + v[1])], style="aux")

    def tick_marks(self, a, b, n=1, size=5, gap=3.5, t=0.5):
        """等しい長さの印。線分 ab の中点に短い線を n 本。"""
        pa, pb = self.px(a), self.px(b)
        L = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        u = ((pb[0] - pa[0]) / L, (pb[1] - pa[1]) / L)
        m = (pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t)
        for k in range(n):
            s = (k - (n - 1) / 2) * gap
            c = (m[0] + u[0] * s, m[1] + u[1] * s)
            self._path([(c[0] - u[1] * size, c[1] + u[0] * size),
                        (c[0] + u[1] * size, c[1] - u[0] * size)], style="aux")

    def parallel_marks(self, a, b, n=1, size=4.5, gap=4, t=0.5):
        """平行の印。線分 ab の中点に「>」を n 個（a→b の向き）。"""
        pa, pb = self.px(a), self.px(b)
        L = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        u = ((pb[0] - pa[0]) / L, (pb[1] - pa[1]) / L)
        m = (pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t)
        for k in range(n):
            s = (k - (n - 1) / 2) * gap + size / 2
            c = (m[0] + u[0] * s, m[1] + u[1] * s)
            self._path([(c[0] - u[0] * size - u[1] * size, c[1] - u[1] * size + u[0] * size), c,
                        (c[0] - u[0] * size + u[1] * size, c[1] - u[1] * size - u[0] * size)],
                       style="aux")

    @staticmethod
    def _label_extent(label, fs, u):
        """ラベルが向き u（px の単位ベクトル）の線に沿って占める長さ。"""
        runs = parse_label(label)
        w = sum(_run_width(r, fs) for r in runs)
        h = fs * (2.15 if any(isinstance(r, _Frac) for r in runs) else 1.0)
        return abs(u[0]) * w + abs(u[1]) * h

    def _dim_frame(self, pts, side, axis):
        """寸法線の向き u，図形から離れる向き n（px），各点の n 方向の深さ，その最大を返す。"""
        px = [self.px(p) for p in pts]
        d = (px[-1][0] - px[0][0], px[-1][1] - px[0][1])
        if axis == "x":
            u = (1.0 if d[0] >= 0 else -1.0, 0.0)
        elif axis == "y":
            u = (0.0, 1.0 if d[1] >= 0 else -1.0)
        elif axis is None:
            L = math.hypot(*d)
            u = (d[0] / L, d[1] / L)
        else:
            raise ValueError('axis は None / "x" / "y"')
        n = (u[1] * side, -u[0] * side)
        depth = [p[0] * n[0] + p[1] * n[1] for p in px]
        return px, u, n, depth, max(depth)

    def dimension(self, a, b, label, offset=None, side=1, row=0, arrows="auto", label_at="auto",
                  ext=True, size=None, axis=None, _ends=None, _base=None):
        """寸法線（長さを示す両矢印＋ラベル）。図形から離した段に置く。

        side:  1 で a→b の左側，-1 で右側に寸法線を出す。
        row:   段。0 が図形に最も近く，1, 2, … と外へ dim_step（20px）ずつ離れる。
               1つの辺に沿う寸法は同じ段にそろえ，全体の長さは外側の段に置く。
        offset: 図形から row=0 の寸法線までの距離（px）。省略時は dim_offset（16px）。
               寸法線が図形のほかの部分（レンズの下端，物体の角）を横切るときは，a, b を
               その部分の端の点に取り，axis で測る向きを指定する。
        axis:  None は ab に沿う長さ。"x" は水平距離，"y" は鉛直距離（a, b の高さが違っても
               寸法線は水平・鉛直になり，補助線が a, b それぞれから伸びる）。
        arrows: "in" は矢じりを内側に置く普通の形。"out" は矢じりを外側に置いて内向きにする形
               （短い区間用）。"auto" は長さで決める。
        label_at: "center"（線の中央，白い下地），"out"（寸法線の外側＝図形と反対側），
               "a" / "b"（a 側・b 側の外）。"auto" は入るなら中央，入らなければ "out"。
        短い区間に普通の両矢印を押し込むと矢じりと文字が詰まるので，"auto" に任せるか，
        図の縮尺を上げる。連続する寸法は dimension_chain() を使う。
        """
        (pa, pb), u, n, (da, db), base = self._dim_frame([a, b], side, axis)
        if _base is not None:
            base = _base
        off = (self.dim_offset if offset is None else offset) + row * self.dim_step
        qa = (pa[0] + n[0] * (base + off - da), pa[1] + n[1] * (base + off - da))
        qb = (pb[0] + n[0] * (base + off - db), pb[1] + n[1] * (base + off - db))
        L = math.hypot(qb[0] - qa[0], qb[1] - qa[1])
        if L < 1:
            raise ValueError("dimension: 2点の間隔が 0（axis の向きを確かめる）")
        fs = size or self.fs
        lw = self._label_extent(label, fs, u)
        alen = _ARROW["dim"][0]
        fits_in = L >= lw + 2 * alen + 8          # 矢じり2個と文字が内側に入る
        if arrows == "auto":
            arrows = "in" if fits_in else "out"
        if arrows == "in" and L < 2 * alen + 4:
            self.warnings.append(f"寸法「{label}」: 区間が短く矢じりがつぶれる。arrows=\"out\" にするか縮尺を上げる")
        if label_at == "auto":
            label_at = "center" if (fits_in if arrows == "in" else L >= lw + 6) else "out"
        if arrows == "in" and label_at == "center" and not fits_in:
            self.warnings.append(f"寸法「{label}」: 矢じりと文字が詰まる。label_at=\"out\" にするか arrows=\"out\" にする")
        ea, eb = _ends or (arrows, arrows)        # 両端それぞれ "in" / "out" / "none" / "dot"
        tail = 13
        if ext:
            for p, q in ((pa, qa), (pb, qb)):
                self._path([(p[0] + n[0] * 3, p[1] + n[1] * 3),
                            (q[0] + n[0] * 4, q[1] + n[1] * 4)], style="thin")
        self._path([qa, qb], style="thin", width=0.8, kind="dim",
                   arrow={(True, True): "both", (True, False): "start", (False, True): "end"}.get(
                       (ea == "in", eb == "in")))
        for q, e, sg in ((qa, ea, -1), (qb, eb, 1)):
            if e == "out":      # 外側から内向きの矢じり
                self._path([(q[0] + u[0] * sg * tail, q[1] + u[1] * sg * tail), q],
                           style="thin", width=0.8, arrow="end", kind="dim")
            elif e == "dot":
                self._put(f'<circle cx="{_f(q[0])}" cy="{_f(q[1])}" r="1.5" fill="#000" stroke="none"/>', 2)
        mid = ((qa[0] + qb[0]) / 2, (qa[1] + qb[1]) / 2)
        if label_at == "center":
            self._add_label(label, mid, (0.0, 0.0), 0, size, bg=True)
        elif label_at == "out":
            self._add_label(label, mid, n, 4, size)
        elif label_at in ("a", "b"):
            sg, q, e = (-1, qa, ea) if label_at == "a" else (1, qb, eb)
            d = tail + 3 if e == "out" else 5
            self._add_label(label, q, (u[0] * sg, u[1] * sg), d, size)
        else:
            raise ValueError("label_at は auto / center / out / a / b")

    def dimension_chain(self, pts, labels, side=1, row=0, offset=None, size=None, axis=None):
        """一直線上に並ぶ点 pts の間の寸法を，同じ段に続けて描く（labels は区間ごと）。

        短い区間は自分の矢じりを持たず，隣の区間の矢じりが境界を示す（矢じりが重ならない）。
        列の端にある短い区間は，外側から内向きの矢じりにする。文字が入らない区間の
        ラベルは寸法線の外側に出る。None のラベルの区間は描かない。
        axis="x"（"y"）にすると水平（鉛直）距離を測り，高さの違う点（レンズの下端，
        スクリーンの下端，軸上の点）から補助線を下ろして1本の段にそろえる。
        """
        if len(labels) != len(pts) - 1:
            raise ValueError("labels は区間の数（点の数 − 1）だけ渡す")
        fs = size or self.fs
        alen = _ARROW["dim"][0]
        px, u, n, depth, base = self._dim_frame(pts, side, axis)
        short = []
        for (p, q), lab in zip(zip(px, px[1:]), labels):
            if lab is None:
                short.append(None)
                continue
            L = abs((q[0] - p[0]) * u[0] + (q[1] - p[1]) * u[1])
            short.append(L < self._label_extent(lab, fs, u) + 2 * alen + 8)
        for k, lab in enumerate(labels):
            if lab is None:
                continue
            if not short[k]:
                self.dimension(pts[k], pts[k + 1], lab, offset, side, row, arrows="in", size=size,
                               axis=axis, _base=base)
                continue
            ends = []
            for nb in (k - 1, k + 1):
                if nb < 0 or nb >= len(labels) or short[nb] is None:
                    ends.append("out")       # 列の端：外側から内向きの矢じり
                elif short[nb]:
                    ends.append("dot")       # 短い区間が続く：境界は黒点
                else:
                    ends.append("none")      # 隣の区間の矢じりが境界を示す
            self.dimension(pts[k], pts[k + 1], lab, offset, side, row, arrows="out", size=size,
                           axis=axis, _ends=tuple(ends), _base=base)

    def leader(self, text, target, at, dir=None, arrow=False, dot=False, gap=3, size=None):
        """引き出し線つきのラベル。対象 target を細い線で指し，文字は離れた at の先に置く。

        近接する2曲線の名前，寸法線から離れた「高さ w/5」のような注記，混み合う場所の
        ラベルに使う。arrow=True で対象側に矢じり，dot=True で対象に小さな黒点。
        文字は at から target と反対の向きへ gap px 離して置く（dir で変えられる）。
        """
        pt, pa = self.px(target), self.px(at)
        L = math.hypot(pa[0] - pt[0], pa[1] - pt[1])
        if L < 8:
            raise ValueError("leader: target と at が近すぎる（引き出し線は 8px 以上）")
        u = ((pa[0] - pt[0]) / L, (pa[1] - pt[1]) / L)
        start = pt if (arrow or dot) else (pt[0] + u[0] * 2, pt[1] + u[1] * 2)
        self._path([pa, start], style="thin", width=0.7, arrow="end" if arrow else None, kind="dim")
        if dot:
            self._put(f'<circle cx="{_f(pt[0])}" cy="{_f(pt[1])}" r="1.8" fill="#000" stroke="none"/>', 2)
        self._add_label(text, pa, self._dir(dir) if dir is not None else u, gap, size)

    # ---- ハッチング ----
    def hatch(self, region, angle=45, spacing=5, intersect=(), exclude=(), width=0.6):
        """領域を斜線で塗る。region は多角形（数学座標の点の列）。

        intersect の各多角形との共通部分だけ，exclude の各多角形を除いた部分だけを塗る
        （ベン図の A∩B，A の補集合など）。円は circle_region()，曲線の間は region_between()。
        斜線は計算で切り取った線分として出力するので clipPath を使わない。
        """
        t = math.radians(angle)
        d = (math.cos(t), -math.sin(t))
        nrm = (math.sin(t), math.cos(t))

        def spans(poly, c):
            ts = []
            pts = [self.px(p) for p in poly]
            for p, q in zip(pts, pts[1:] + pts[:1]):
                sp, sq = p[0] * nrm[0] + p[1] * nrm[1] - c, q[0] * nrm[0] + q[1] * nrm[1] - c
                if (sp < 0) != (sq < 0):
                    k = sp / (sp - sq)
                    x, y = p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k
                    ts.append(x * d[0] + y * d[1])
            ts.sort()
            return list(zip(ts[::2], ts[1::2]))

        def meet(A, B):
            return [(max(a0, b0), min(a1, b1)) for a0, a1 in A for b0, b1 in B
                    if max(a0, b0) < min(a1, b1)]

        def minus(A, B):
            for b0, b1 in B:
                A = [s for a0, a1 in A for s in ((a0, min(a1, b0)), (max(a0, b1), a1)) if s[0] < s[1]]
            return A

        proj = [p[0] * nrm[0] + p[1] * nrm[1] for p in (self.px(q) for q in region)]
        k0, k1 = math.floor(min(proj) / spacing), math.ceil(max(proj) / spacing)
        parts = []
        for k in range(k0, k1 + 1):
            c = k * spacing + 0.013  # 頂点をちょうど通る場合を避ける
            S = spans(region, c)
            for other in intersect:
                S = meet(S, spans(other, c))
            for other in exclude:
                S = minus(S, spans(other, c))
            for s0, s1 in S:
                if s1 - s0 < 0.8:
                    continue
                parts.append(f"M{_f(nrm[0] * c + d[0] * s0)},{_f(nrm[1] * c + d[1] * s0)} "
                             f"L{_f(nrm[0] * c + d[0] * s1)},{_f(nrm[1] * c + d[1] * s1)}")
        if parts:
            self._put(f'<path class="hatch" d="{" ".join(parts)}" stroke-width="{_f(width)}" '
                      f'stroke-linecap="butt"/>', 0)

    # ---- 物理：力学 ----
    def ground(self, a, b, side=-1, depth=6, spacing=6):
        """床・壁・天井。線分 ab と，その片側の短い斜線。side=-1 は a→b の右側（左→右なら下）。"""
        pa, pb = self.px(a), self.px(b)
        self._path([pa, pb], style="main")
        L = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        u = ((pb[0] - pa[0]) / L, (pb[1] - pa[1]) / L)
        n = (u[1] * side, -u[0] * side)
        parts, k = [], 0
        while spacing * (k + 0.5) + depth <= L + 0.01:
            s = spacing * (k + 0.5) + depth
            p = (pa[0] + u[0] * s, pa[1] + u[1] * s)
            q = (p[0] - u[0] * depth + n[0] * depth, p[1] - u[1] * depth + n[1] * depth)
            parts.append(f"M{_f(p[0])},{_f(p[1])} L{_f(q[0])},{_f(q[1])}")
            k += 1
        self._put(f'<path class="hatch" d="{" ".join(parts)}" stroke-width="0.7" stroke-linecap="butt"/>', 0)

    def block(self, base, w, h, angle=0, fill="#fff", label=None, label_at=(0.0, 0.0)):
        """物体（長方形）。base は底辺の中点，angle は底辺の傾き（度）。

        label（質量 m など）は物体の内側に置く。label_at=(u, v) は中心からの位置で，
        u は底辺方向，v は高さ方向，どちらも -1〜1（(0, 0) が中央）。力の矢印が中央を
        通るときは (-0.55, 0.4) のように空いた所へずらす。

        戻り値は {"center": 重心, "corners": 4頂点, "top": 上辺の中点, "left"/"right": 側面の中点}。
        """
        e1, e2 = polar(1, angle), polar(1, angle + 90)
        c = [add(base, mul(e1, -w / 2)), add(base, mul(e1, w / 2))]
        c += [add(c[1], mul(e2, h)), add(c[0], mul(e2, h))]
        self.polygon(c, fill=fill)
        if label:
            at = add(add(base, mul(e2, h / 2 * (1 + label_at[1]))), mul(e1, w / 2 * label_at[0]))
            self.label(label, at, dir="C")
        return {"center": add(base, mul(e2, h / 2)), "corners": c, "top": add(base, mul(e2, h)),
                "left": midpoint(c[0], c[3]), "right": midpoint(c[1], c[2])}

    def set_force_scale(self, length):
        """力の尺度を決める。大きさ 1（例：mg を 1 とする）の力を長さ length（数学座標）で描く。

        1枚の図の力はすべてこの尺度で描く（force_polar / force_len を使う）。
        """
        self.force_unit = float(length)

    def force_len(self, magnitude):
        """力の大きさ → 矢印の長さ（数学座標）。"""
        return magnitude * self.force_unit

    def force(self, p, v, label=None, dir=None, dist=4, shift=0, dot=False, record=True):
        """力の矢印。作用点 p からベクトル v（数学座標での長さ）。戻り値は先端。

        shift: 矢印を v の左側（負なら右側）へ平行にずらす量（px）。接触面に沿う力
               （摩擦力など）が面の線と重なるとき，物体側へ 5 前後ずらす。
        dot:   作用点に小さな黒丸を打つ（矢印の始点が分かり，長さを比べやすい）。
        """
        tip = add(p, v)
        pa, pb = self.px(p), self.px(tip)
        L = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        n = ((pb[1] - pa[1]) / L * shift, -(pb[0] - pa[0]) / L * shift)
        pa, pb = (pa[0] + n[0], pa[1] + n[1]), (pb[0] + n[0], pb[1] + n[1])
        self._path([pa, pb], style="force", arrow="end", kind="frc")  # 力は 2.2 の線に幅 8.8 の矢じり
        if dot:
            self._put(f'<circle cx="{_f(pa[0])}" cy="{_f(pa[1])}" r="2.4" fill="#000" stroke="none"/>', 2)
        if label:
            self._add_label(label, pb, self._dir(dir if dir is not None else v), dist)
        if record:
            self._forces.append(tuple(v))
        return tip

    def force_polar(self, p, magnitude, deg, label=None, **kw):
        """力を大きさと向き（度）で描く。長さは set_force_scale の尺度で決まる。"""
        return self.force(p, polar(magnitude * self.force_unit, deg), label, **kw)

    def components(self, p, v, deg, labels=(None, None), dirs=(None, None), dist=5):
        """力 v を，向き deg の成分とそれに垂直な成分に分解して破線で描く。

        2本の破線の矢印（p から）と，平行四辺形（長方形）を閉じる2本の破線。
        戻り値は2つの成分ベクトル。つり合う力（垂直抗力，摩擦力）はこの成分と
        同じ長さ・逆向きになる。
        """
        e = polar(1, deg)
        v1 = mul(e, dot(v, e))
        v2 = sub(v, v1)
        tip = add(p, v)
        for comp, lab, d in ((v1, labels[0], dirs[0]), (v2, labels[1], dirs[1])):
            if norm(comp) < 1e-9:
                continue
            q = add(p, comp)
            self.segment(p, q, style="dash", arrow="end")
            self.segment(q, tip, style="dash")
            if lab:
                self.label(lab, q, dir=d if d is not None else comp, dist=dist)
        return v1, v2

    def force_balance(self, tol=0.03):
        """force / force_polar で描いた力のベクトル和が 0 か確かめる（つり合いの図で呼ぶ）。

        戻り値は 和の大きさ ÷ 最大の力の大きさ。tol を超えると警告を残す。
        """
        if not self._forces:
            return 0.0
        sx, sy = sum(v[0] for v in self._forces), sum(v[1] for v in self._forces)
        r = math.hypot(sx, sy) / max(norm(v) for v in self._forces)
        if r > tol:
            self.warnings.append(f"力のつり合い: 矢印のベクトル和が 0 にならない（最大の力の {r:.0%}）。"
                                 "すべての力を同じ尺度で計算したか確かめる")
        return r

    def spring(self, a, b, n=6, width=6, lead=7):
        """ばね（ジグザグ）。n は山の数，width は振れ幅（px），lead は両端の直線部（px）。"""
        pa, pb = self.px(a), self.px(b)
        L = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        u = ((pb[0] - pa[0]) / L, (pb[1] - pa[1]) / L)
        nv = (u[1], -u[0])
        seg = (L - 2 * lead) / (2 * n)
        pts = [pa, (pa[0] + u[0] * lead, pa[1] + u[1] * lead)]
        for i in range(2 * n):
            s = lead + (i + 0.5) * seg
            sg = width if i % 2 == 0 else -width
            pts.append((pa[0] + u[0] * s + nv[0] * sg, pa[1] + u[1] * s + nv[1] * sg))
        pts += [(pb[0] - u[0] * lead, pb[1] - u[1] * lead), pb]
        self._path(pts, style="aux", width=1.2)

    def pulley(self, c, r):
        """滑車（円と軸）。r は数学座標での半径。"""
        self.circle(c, r, fill="#fff")
        x, y = self.px(c)
        self._put(f'<circle cx="{_f(x)}" cy="{_f(y)}" r="2" fill="#000" stroke="none"/>')

    def field_mark(self, p, into=True, r=6):
        """紙面に垂直な向きの印。into=True は表→裏（⊗），False は裏→表（⊙）。"""
        x, y = self.px(p)
        self._put(f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{_f(r)}" fill="#fff" stroke-width="1"/>')
        if into:
            k = r * 0.7071
            self._put(f'<path d="M{_f(x - k)},{_f(y - k)} L{_f(x + k)},{_f(y + k)} '
                      f'M{_f(x - k)},{_f(y + k)} L{_f(x + k)},{_f(y - k)}" stroke-width="1"/>')
        else:
            self._put(f'<circle cx="{_f(x)}" cy="{_f(y)}" r="1.6" fill="#000" stroke="none"/>')
        self._dots.append((x, y))

    def field_grid(self, x0, x1, y0, y1, nx, ny, into=True, strength=None, axis="x", r=5):
        """紙面に垂直な磁場の印（⊗ / ⊙）を長方形の範囲に並べる。戻り値は印の位置の列。

        strength を省くと等間隔（一様な磁場）。strength に位置の関数（例 lambda x: 1 / x）を
        渡すと，axis（"x" か "y"）方向の列の間隔を強さに反比例させる。強い所ほど印が密になり，
        「近いほど強い」が図から読める。強さが変わる磁場を等間隔の印で描かない。
        """
        def cells(lo, hi, m, f):
            if f is None:
                return [lo + (hi - lo) * (i + 0.5) / m for i in range(m)]
            N = 800
            xs = [lo + (hi - lo) * (j + 0.5) / N for j in range(N)]
            cum, tot = [], 0.0
            for x in xs:
                tot += abs(f(x))
                cum.append(tot)
            out, j = [], 0
            for i in range(m):
                goal = tot * (i + 0.5) / m
                while cum[j] < goal:
                    j += 1
                out.append(xs[j])
            return out

        xs = cells(x0, x1, nx, strength if axis == "x" else None)
        ys = cells(y0, y1, ny, strength if axis == "y" else None)
        gaps = [abs(b - a) * self.ux for a, b in zip(xs, xs[1:])] + \
               [abs(b - a) * self.uy for a, b in zip(ys, ys[1:])]
        if gaps and min(gaps) < 2 * r + 2:
            self.warnings.append("field_grid: 印どうしが接する。nx・ny を減らすか r を小さくする")
        pts = [(x, y) for y in ys for x in xs]
        for p in pts:
            self.field_mark(p, into=into, r=r)
        return pts

    # ---- 物理：回路（JIS C 0617） ----
    def wire(self, *pts):
        """導線（折れ線）。"""
        self._path([self.px(p) for p in pts], style="circuit")

    def junction(self, p):
        """導線の分岐点（黒丸）。"""
        self.dot(p, r=2.2)

    def _component(self, a, b, half, halfw, label, side):
        pa, pb = self.px(a), self.px(b)
        L = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        if L < 2 * half:
            raise ValueError("素子を置くには2点が近すぎる")
        u = ((pb[0] - pa[0]) / L, (pb[1] - pa[1]) / L)
        n = (u[1], -u[0])  # a→b の左側（数学座標で見て）
        m = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)

        def P(s, t=0.0):
            return (m[0] + u[0] * s + n[0] * t, m[1] + u[1] * s + n[1] * t)

        self._path([pa, P(-half)], style="circuit")
        self._path([P(half), pb], style="circuit")
        box = [P(-half, -halfw), P(half, -halfw), P(half, halfw), P(-half, halfw)]
        self._segs.extend(zip(box, box[1:] + box[:1]))
        if label:
            d = (n[0] * side, n[1] * side)
            self._add_label(label, P(0, side * halfw), d, 4)
        return P, m, u, n

    def resistor(self, a, b, label=None, side=1, variable=False):
        """抵抗（長方形。縦横比 1:3）。variable=True で可変抵抗（斜めの矢印）。"""
        P, m, u, n = self._component(a, b, 15, 5, label, side)
        self._path([P(-15, -5), P(15, -5), P(15, 5), P(-15, 5)], closed=True, style="circuit",
                   fill="#fff", register=False)
        if variable:
            self._path([P(-13, -11), P(13, 11)], style="circuit", width=1.0, arrow="end", register=False)

    def _beside(self, P, s, t, text, size=12):
        """素子の軸方向 s・法線方向 t（px）の位置から，導線と極板を避ける斜め外向きに文字を置く。"""
        o, e = P(0, 0), P(s, t)
        d = ((1 if e[0] - o[0] > 0.5 else -1 if e[0] - o[0] < -0.5 else 0),
             (1 if e[1] - o[1] > 0.5 else -1 if e[1] - o[1] < -0.5 else 0))
        n = math.hypot(*d)
        self._add_label(text, e, (d[0] / n, d[1] / n), 0, size)

    def capacitor(self, a, b, label=None, side=1, charges=None, charge_side=None):
        """コンデンサー（同じ長さの平行な2線）。

        charges=("$+Q$", "$-Q$") で，a 側・b 側の極板のそばに電荷を書く。極板の電荷の
        符号が問題で意味を持つとき（充電の向き，電気量保存，つなぎ替え）は必ず書く。
        charge_side は電荷を書く側（1 が a→b の左，-1 が右）。省略時は label の反対側。
        """
        P, m, u, n = self._component(a, b, 3, 11, label, side)
        self._path([P(-3, -11), P(-3, 11)], style="circuit", width=1.5, register=False)
        self._path([P(3, -11), P(3, 11)], style="circuit", width=1.5, register=False)
        if charges:
            cs = charge_side if charge_side is not None else -side
            for text, sg in zip(charges, (-1, 1)):
                if text:
                    self._beside(P, sg * 8, cs * 5, text, size=self.fs)

    def battery(self, a, b, label=None, side=1, plus_at_a=True, polarity=False, polarity_side=None):
        """電池・直流電源。長く細い線が正極，短く太い線が負極。plus_at_a=True で a 側が正極。

        polarity=True で，長い線（正極）の側に「＋」，短い線（負極）の側に「−」を書く。
        電流・起電力の向きや極板の電荷の符号を論じる図では必ず True にする。
        polarity_side は記号を書く側（1 が a→b の左，-1 が右）。省略時は label の反対側。
        """
        P, m, u, n = self._component(a, b, 3, 12, label, side)
        sp = -3 if plus_at_a else 3
        self._path([P(sp, -12), P(sp, 12)], style="circuit", width=1.2, register=False)
        self._put(f'<path d="M{_f(P(-sp, -6)[0])},{_f(P(-sp, -6)[1])} L{_f(P(-sp, 6)[0])},{_f(P(-sp, 6)[1])}" '
                  f'stroke-width="3" stroke-linecap="butt"/>')
        if polarity:
            ps = polarity_side if polarity_side is not None else -side
            sg = -1 if plus_at_a else 1
            self._beside(P, sg * 8, ps * 4, "+", size=13)
            self._beside(P, -sg * 8, ps * 4, "−", size=13)

    def inductor(self, a, b, label=None, side=1, bumps=4, r=5):
        """コイル（半円を並べる。旧記号のループは使わない）。"""
        half = bumps * r
        P, m, u, n = self._component(a, b, half, r, label, side)
        d = f"M{_f(P(-half)[0])},{_f(P(-half)[1])}"
        for i in range(bumps):
            e = P(-half + 2 * r * (i + 1))
            d += f" A{r},{r} 0 0 {1 if side > 0 else 0} {_f(e[0])},{_f(e[1])}"
        self._put(f'<path d="{d}" stroke-width="1.2"/>')

    def switch(self, a, b, label=None, side=1, closed=False):
        """スイッチ。開いているときは片側から斜めに上がる線。"""
        P, m, u, n = self._component(a, b, 12, 9, label, side)
        self._path([P(-12), P(12) if closed else P(10, 9 * side)], style="circuit", register=False)

    def _round(self, a, b, label, side, r=10):
        P, m, u, n = self._component(a, b, r, r, label, side)
        self._put(f'<circle cx="{_f(m[0])}" cy="{_f(m[1])}" r="{r}" fill="#fff" stroke-width="1.2"/>')
        return P, m

    def lamp(self, a, b, label=None, side=1):
        """電球（円に×）。"""
        P, m = self._round(a, b, label, side, 9)
        k = 9 * 0.7071
        self._put(f'<path d="M{_f(m[0] - k)},{_f(m[1] - k)} L{_f(m[0] + k)},{_f(m[1] + k)} '
                  f'M{_f(m[0] - k)},{_f(m[1] + k)} L{_f(m[0] + k)},{_f(m[1] - k)}" stroke-width="1.2"/>')

    def meter(self, a, b, letter, label=None, side=1):
        """計器（円に立体の文字）。電流計は "A"，電圧計は "V"，検流計は "G"。"""
        P, m = self._round(a, b, label, side, 10)
        self._labels.append(dict(text=letter, runs=parse_label(letter), fs=12, w=8, h=12, anchor=m,
                                 d=(0.0, 0.0), dist=0, bg=True, away=None, plain=True))

    def ammeter(self, a, b, label=None, side=1):
        self.meter(a, b, "A", label, side)

    def voltmeter(self, a, b, label=None, side=1):
        self.meter(a, b, "V", label, side)

    def ac_source(self, a, b, label=None, side=1):
        """交流電源（円に正弦波）。"""
        P, m = self._round(a, b, label, side, 10)
        x, y = m
        self._put(f'<path d="M{_f(x - 6)},{_f(y)} Q{_f(x - 3)},{_f(y - 7)} {_f(x)},{_f(y)} '
                  f'Q{_f(x + 3)},{_f(y + 7)} {_f(x + 6)},{_f(y)}" stroke-width="1.1"/>')

    # ---- 物理：レンズ ----
    def optical_axis(self, x0=None, x1=None, y=0.0):
        """光軸（一点鎖線）。"""
        self.segment((self.xmin if x0 is None else x0, y), (self.xmax if x1 is None else x1, y),
                     style="chain")

    def lens(self, x, half_height, kind="convex", y=0.0, bulge=7):
        """薄いレンズ。kind は "convex"（凸）か "concave"（凹）。bulge は厚みの半分（px）。"""
        cx, cy = self.px((x, y))
        h = half_height * self.uy
        R = (h * h + bulge * bulge) / (2 * bulge)
        if kind == "convex":
            d = (f"M{_f(cx)},{_f(cy - h)} A{_f(R)},{_f(R)} 0 0 1 {_f(cx)},{_f(cy + h)} "
                 f"A{_f(R)},{_f(R)} 0 0 1 {_f(cx)},{_f(cy - h)} Z")
        else:
            e = bulge + 2
            d = (f"M{_f(cx - e)},{_f(cy - h)} A{_f(R)},{_f(R)} 0 0 1 {_f(cx - e)},{_f(cy + h)} "
                 f"L{_f(cx + e)},{_f(cy + h)} A{_f(R)},{_f(R)} 0 0 1 {_f(cx + e)},{_f(cy - h)} Z")
        self._put(f'<path d="{d}" stroke-width="1.2" fill="#fff"/>')
        self._segs.append(((cx, cy - h), (cx, cy + h)))

    def ray(self, *pts, dash=None, arrows=True, at=0.5):
        """光線（折れ線）。各区間の途中（at の割合の位置）に進行方向の矢じり。虚像側の延長は dash=True。"""
        px = [self.px(p) for p in pts]
        self._path(px, style="aux", dash=dash)
        if arrows and not dash:
            for p, q in zip(px, px[1:]):
                self._mid_arrow(p, q, "aux", t=at)

    # ---- 出力 ----
    def svg(self):
        if not any("c" in L for L in self._labels) or any("c" not in L for L in self._labels):
            self.warnings = [w for w in self.warnings if not w.startswith("ラベル")]
            self._resolve_labels()
        msg = ("縮尺: 縦横の縮尺が違うのに注記も y 軸の数値の目盛りも無い。"
               'note("※ 縦軸方向は拡大して描いてある") などを入れる')
        if (abs(self.ux - self.uy) > 1e-9 and not self.aspect_ok and not self._note
                and not self._numeric_ytick and msg not in self.warnings):
            self.warnings.append(msg)
        W, H, i = _f(self.W), _f(self.H), self.id
        k = min(1.0, self.display_width / self.W) if self.display_width else 1.0
        sizes = [L["fs"] for L in self._labels] or [self.fs]
        script = any(not isinstance(r, _Frac) and r.script for L in self._labels for r in L["runs"])
        self.warnings = [w for w in self.warnings if not w.startswith("文字の大きさ")]
        if min(sizes) * k < MIN_TEXT_PX - 0.05 or (script and min(sizes) * 0.7 * k < 9 - 0.05):
            need = max(MIN_TEXT_PX, 9 / 0.7 if script else 0) / k
            self.warnings.append(
                f"文字の大きさ: 表示幅 {_f(self.W * k)}px で最小の文字が {min(sizes) * k:.1f}px になる"
                f"（本文字 {MIN_TEXT_PX}px・添字 9px 以上にする）。unit を下げて図の幅を表示幅に合わせるか，"
                f"font_size={math.ceil(need)} 以上にする")
        elif not self.display_width and self.W > 560:
            self.warnings.append(
                f"文字の大きさ: 図の幅が {_f(self.W)}px ある。教材の表示幅に縮めると文字が小さくなるので，"
                "Figure(display_width=表示幅) を指定して確かめる")
        dw, dh = _f(self.W * k), _f(self.H * k)
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{dw}" height="{dh}" '
               f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="{i}-t {i}-d">',
               f'<title id="{i}-t">{escape(self.title or "図")}</title>',
               f'<desc id="{i}-d">{escape(self.desc or self.title or "図")}</desc>']
        if self._markers:
            out.append("<defs>")
            for kind, end in sorted(self._markers):
                L, hw, notch, short = _ARROW[kind]
                if end:
                    d = f"M0,0 L{_f(L)},{_f(hw)} L0,{_f(2 * hw)} L{_f(notch)},{_f(hw)} Z"
                    ref = L - short
                else:
                    d = f"M{_f(L)},0 L0,{_f(hw)} L{_f(L)},{_f(2 * hw)} L{_f(L - notch)},{_f(hw)} Z"
                    ref = short
                out.append(f'<marker id="{i}-{kind}-{"e" if end else "s"}" markerUnits="userSpaceOnUse" '
                           f'markerWidth="{_f(L)}" markerHeight="{_f(2 * hw)}" refX="{_f(ref)}" '
                           f'refY="{_f(hw)}" orient="auto" overflow="visible">'
                           f'<path d="{d}" fill="#000" stroke="none"/></marker>')
            out.append("</defs>")
        out.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#fff"/>')
        out.append('<g fill="none" stroke="#000" stroke-width="1.5" stroke-linecap="round" '
                   'stroke-linejoin="round">')
        out.extend(s for _, _, s in sorted(self._items, key=lambda t: (t[0], t[1])))
        out.append("</g>")
        if self._labels or self._note:
            out.append(f'<g font-family="{FONT}" font-size="{_f(self.fs)}" fill="#000" '
                       f'stroke="none" text-anchor="middle">')
            out.extend(self._label_svg(L) for L in self._labels)
            if self._note:
                text, size = self._note
                runs = parse_label(text)
                w = sum(_run_width(r, size) for r in runs)
                cx = self.ml + (self.xmax - self.xmin) * self.ux / 2
                cx = min(max(cx, w / 2 + 4), self.W - w / 2 - 4)
                out.extend(self._runs_svg(runs, cx, cx - w / 2, self.H - size * 0.75, size, "middle"))
            out.append("</g>")
        out.append("</svg>")
        return "\n".join(out) + "\n"

    def save(self, path):
        """SVG を書き出す。ラベルの重なりなどの警告は標準エラーに出す。"""
        data = self.svg()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(data)
        for w in self.warnings:
            print(f"[hsfig] {path}: {w}", file=sys.stderr)
        return path


if __name__ == "__main__":
    print(__doc__)
