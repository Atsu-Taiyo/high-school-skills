#!/usr/bin/env python3
"""教材用 SVG の機械検査（Python 標準ライブラリのみ）。

    python3 lint_svg.py fig.svg [fig2.svg ...] [--strict] [--display-width=650]

--display-width は教材に置くときの表示幅（px。省略時は 650）。図（viewBox の幅 W）がそれより
広いと縮めて表示されるので，縮めた後の大きさで文字と寸法を判定する。基準は
  最小の文字（添字・指数・注記を含む）  12px 以上  ＝ font-size ≧ 12 × max(1, W ÷ 表示幅)
  本文字（ラベル）                      16px 以上  ＝ font-size ≧ 16 × max(1, W ÷ 表示幅)
  寸法を付ける区間                      28px 以上

検査すること
  ERROR  整形式でない／ルートが svg でない／viewBox が無い・不正／<title> が無い
         外部参照（外部の href，@import，url(http…)，@font-face，<script>）
         文字が viewBox の外にはみ出している／描画要素が1つも無い
  WARN   <desc>・role="img" が無い／width・height が無い
         文字が小さい（上の基準。添字の <tspan> も調べる）／寸法の区間が短い
         引き出し線が他の線・斜線の領域を横切る／太い矢印（力）が文字に接している
         文字どうしの重なり／文字と線の重なり／線が viewBox の外に出ている
         斜線の分数（5/6 など）／座標のカンマの後に空白が無い（(0,0,2) など）
         白黒以外の色／<foreignObject>・<image> の使用
         図中の説明文（長い和文，句読点のある文）／2文以上の注記／度の記号が「˚」「º」

文字の箱は字数と font-size からの概算なので，重なりの指摘は「見に行く場所」の案内と考える。
最終判断は PNG にして目で見る。class="hatch" の要素と data-lint="skip" の付いた要素
（とその子孫）は，線との重なりの検査から外す（斜線の上に白い下地つきで置いた文字など）。
終了コード: ERROR があれば 1（--strict なら WARN でも 1），無ければ 0。
"""
import math
import re
import sys
import xml.etree.ElementTree as ET

SVG = "{http://www.w3.org/2000/svg}"
XLINK = "{http://www.w3.org/1999/xlink}"
SKIP_TAGS = {"defs", "clipPath", "mask", "marker", "pattern", "symbol", "title", "desc",
             "style", "metadata", "linearGradient", "radialGradient"}
NUM = r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"
GRAY = {"none", "black", "white", "gray", "grey", "silver", "dimgray", "darkgray", "lightgray",
        "gainsboro", "whitesmoke", "currentcolor", "transparent", "inherit"}


def local(tag):
    return tag.split("}", 1)[1] if isinstance(tag, str) and tag.startswith("{") else tag


def prop(el, name):
    """属性，なければ style="..." の中の値。"""
    v = el.get(name)
    if v is not None:
        return v.strip()
    m = re.search(r"(?:^|;)\s*" + re.escape(name) + r"\s*:\s*([^;]+)", el.get("style") or "")
    return m.group(1).strip() if m else None


def nums(s):
    return [float(x) for x in re.findall(NUM, s or "")]


def length(v, default=0.0):
    m = re.match(r"\s*(" + NUM + r")\s*([a-z%]*)", v or "")
    if not m:
        return default
    k = {"": 1, "px": 1, "pt": 96 / 72, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96}.get(m.group(2))
    return float(m.group(1)) * k if k else default


# ---- 変換行列 (a, b, c, d, e, f) ----
def mat_mul(m, n):
    return (m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1],
            m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3],
            m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5])


def mat_apply(m, p):
    return (m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5])


def parse_transform(s):
    m = (1, 0, 0, 1, 0, 0)
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", s or ""):
        a = nums(args)
        if name == "matrix" and len(a) == 6:
            t = tuple(a)
        elif name == "translate" and a:
            t = (1, 0, 0, 1, a[0], a[1] if len(a) > 1 else 0)
        elif name == "scale" and a:
            t = (a[0], 0, 0, a[1] if len(a) > 1 else a[0], 0, 0)
        elif name == "rotate" and a:
            c, sn = math.cos(math.radians(a[0])), math.sin(math.radians(a[0]))
            t = (c, sn, -sn, c, 0, 0)
            if len(a) == 3:
                t = mat_mul(mat_mul((1, 0, 0, 1, a[1], a[2]), t), (1, 0, 0, 1, -a[1], -a[2]))
        else:
            continue
        m = mat_mul(m, t)
    return m


# ---- パスを折れ線にする ----
def _arc(p0, rx, ry, phi, large, sweep, p1, n=16):
    if rx == 0 or ry == 0 or p0 == p1:
        return [p1]
    rx, ry, ph = abs(rx), abs(ry), math.radians(phi)
    c, s = math.cos(ph), math.sin(ph)
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    x1, y1 = c * dx + s * dy, -s * dx + c * dy
    lam = x1 * x1 / (rx * rx) + y1 * y1 / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    k = math.sqrt(max(num / den, 0)) * (-1 if large == sweep else 1)
    cx1, cy1 = k * rx * y1 / ry, -k * ry * x1 / rx
    cx, cy = c * cx1 - s * cy1 + (p0[0] + p1[0]) / 2, s * cx1 + c * cy1 + (p0[1] + p1[1]) / 2
    t0 = math.atan2((y1 - cy1) / ry, (x1 - cx1) / rx)
    t1 = math.atan2((-y1 - cy1) / ry, (-x1 - cx1) / rx)
    dt = (t1 - t0) % (2 * math.pi)
    if not sweep:
        dt -= 2 * math.pi
    out = []
    for i in range(1, n + 1):
        t = t0 + dt * i / n
        out.append((cx + rx * math.cos(t) * c - ry * math.sin(t) * s,
                    cy + rx * math.cos(t) * s + ry * math.sin(t) * c))
    return out


def flatten_path(d):
    """パスデータを折れ線（点の列）の列にする。曲線は細かい折れ線で近似。"""
    toks = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|" + NUM, d or "")
    subs, cur, pos, start, i, cmd = [], [], (0.0, 0.0), (0.0, 0.0), 0, None
    need = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}

    def bez(pts, n=12):
        out = []
        for k in range(1, n + 1):
            t, q = k / n, list(pts)
            while len(q) > 1:
                q = [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for a, b in zip(q, q[1:])]
            out.append(q[0])
        return out

    while i < len(toks):
        if re.fullmatch(r"[A-Za-z]", toks[i]):
            cmd = toks[i]
            i += 1
        elif cmd is None:
            break
        elif cmd in "Mm" and cur:  # M の後続の座標は L として扱う
            cmd = "L" if cmd == "M" else "l"
        C, rel = cmd.upper(), cmd.islower()
        k = need[C]
        if C == "Z":
            if cur:
                cur.append(start)
                subs.append(cur)
            cur, pos = [], start
            cmd = None
            continue
        try:
            a = [float(t) for t in toks[i:i + k]]
        except ValueError:
            break
        if len(a) < k:
            break
        i += k
        ox, oy = pos if rel else (0.0, 0.0)
        if C == "M":
            if len(cur) > 1:
                subs.append(cur)
            pos = start = (a[0] + ox, a[1] + oy)
            cur = [pos]
        elif C == "L" or C == "T":
            pos = (a[0] + ox, a[1] + oy)
            cur.append(pos)
        elif C == "H":
            pos = (a[0] + ox, pos[1])
            cur.append(pos)
        elif C == "V":
            pos = (pos[0], a[0] + oy)
            cur.append(pos)
        elif C in "CSQ":
            pts = [pos] + [(a[j] + ox, a[j + 1] + oy) for j in range(0, k, 2)]
            cur.extend(bez(pts))
            pos = pts[-1]
        elif C == "A":
            end = (a[5] + ox, a[6] + oy)
            cur.extend(_arc(pos, a[0], a[1], a[2], bool(a[3]), bool(a[4]), end))
            pos = end
    if len(cur) > 1:
        subs.append(cur)
    return subs


# ---- 文字の箱の概算 ----
def char_em(c):
    if ord(c) >= 0x2E80:
        return 1.0
    if c == " ":
        return 0.25
    if c == "\u2009":
        return 0.17
    if c in "MWmw":
        return 0.82
    if c in "ijlItfr":
        return 0.32
    if c.isupper():
        return 0.68
    if c.isdigit():
        return 0.5
    if c in "=+−<>≦≧≠±×÷→∥⊥∠△∩∪√∞":
        return 0.6
    if c in "()[],.′'·°:;":
        return 0.33
    return 0.48


def font_px(v, parent):
    if not v:
        return parent
    v = v.strip()
    if v.endswith("%"):
        return parent * float(v[:-1]) / 100
    if v.endswith("em"):
        return parent * float(v[:-2])
    return length(v, parent)


def text_width(el, fs):
    w = sum(char_em(c) for c in re.sub(r"\s+", " ", el.text or "")) * fs
    for ch in el:
        if local(ch.tag) == "tspan":
            w += text_width(ch, font_px(prop(ch, "font-size"), fs))
        w += sum(char_em(c) for c in re.sub(r"\s+", " ", ch.tail or "")) * fs
    return w


def seg_hits_box(p, q, box):
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


def is_white(v):
    return (v or "").lower().replace(" ", "") in ("#fff", "#ffffff", "white", "rgb(255,255,255)")


def is_gray(v):
    v = (v or "").strip().lower()
    if v in GRAY or v.startswith("url("):
        return True
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            return h[0] == h[1] == h[2]
        return h[0:2] == h[2:4] == h[4:6]
    m = re.fullmatch(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", v)
    return bool(m) and m.group(1) == m.group(2) == m.group(3)


MIN_TEXT_PX, MIN_BODY_PX, MIN_DIM_PX, DISPLAY_WIDTH = 12.0, 16.0, 28.0, 650.0


def _cross(p, q, a, b):
    d1 = (q[0] - p[0]) * (a[1] - p[1]) - (q[1] - p[1]) * (a[0] - p[0])
    d2 = (q[0] - p[0]) * (b[1] - p[1]) - (q[1] - p[1]) * (b[0] - p[0])
    d3 = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    d4 = (b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0])
    return d1 * d2 < 0 and d3 * d4 < 0


def lint(path, display_width=None):
    """(errors, warnings) を返す。display_width は教材に置くときの表示幅（px）。"""
    E, Wn = [], []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        return [f"整形式でない XML: {e}"], []
    except OSError as e:
        return [f"読めない: {e}"], []
    if root.tag != SVG + "svg":
        return ['ルート要素が <svg xmlns="http://www.w3.org/2000/svg"> でない'], []

    vb = nums(root.get("viewBox"))
    if len(vb) != 4 or vb[2] <= 0 or vb[3] <= 0:
        E.append("viewBox が無い，または不正（\"0 0 幅 高さ\" を指定する）")
        vb = None
    if not root.get("width") or not root.get("height"):
        Wn.append("width / height が無い（表示サイズを指定する）")
    if root.find(SVG + "title") is None:
        E.append("<title> が無い（svg の直下に置く）")
    if root.find(SVG + "desc") is None:
        Wn.append("<desc> が無い（図の内容を1〜2文で書く）")
    if root.get("role") != "img":
        Wn.append('role="img" が無い')

    # 外部参照
    for el in root.iter():
        tag = local(el.tag)
        for attr in ("href", XLINK + "href", "src"):
            v = el.get(attr)
            if v and not v.startswith("#"):
                if v.startswith("data:"):
                    Wn.append(f"<{tag}> に data: URI の埋め込みがある")
                else:
                    E.append(f"外部参照: <{tag}> の href=\"{v[:60]}\"")
        if tag == "script":
            E.append("<script> がある")
        elif tag == "foreignObject":
            Wn.append("<foreignObject> がある（表示できない環境が多い）")
        elif tag == "image":
            Wn.append("<image> がある（線画は SVG の図形で描く）")
        blob = (el.text or "") if tag == "style" else (el.get("style") or "")
        if "@import" in blob or "@font-face" in blob:
            E.append("外部の CSS・フォントの読み込み（@import / @font-face）がある")
        for u in re.findall(r"url\(\s*['\"]?([^)'\"]+)", blob + " " + " ".join(
                el.get(a) or "" for a in ("fill", "stroke", "clip-path", "mask", "filter",
                                           "marker-start", "marker-mid", "marker-end"))):
            if not u.startswith("#"):
                E.append(f"外部参照: url({u[:60]})")

    scale = 1.0
    if vb and root.get("width"):
        scale = length(root.get("width"), vb[2]) / vb[2]
    if vb:
        scale = min(scale, (display_width or DISPLAY_WIDTH) / vb[2])

    texts, segs, colors = [], [], set()
    arrows, thick, leaders, hatchsegs = [], [], [], []   # 矢印つきの細線，太線，引き出し線，斜線
    ids = {}
    for el in root.iter():
        if el.get("id"):
            ids[el.get("id")] = ids.get(el.get("id"), 0) + 1
    for k, c in ids.items():
        if c > 1:
            E.append(f'id="{k}" が重複している')

    def walk(el, ctm, st):
        tag = local(el.tag)
        if tag in SKIP_TAGS or not isinstance(el.tag, str):
            return
        ctm = mat_mul(ctm, parse_transform(el.get("transform")))
        st = dict(st)
        for name in ("stroke", "fill", "text-anchor"):
            v = prop(el, name)
            if v is not None:
                st[name] = v
        st["fs"] = font_px(prop(el, "font-size"), st["fs"])
        sw = prop(el, "stroke-width")
        if sw is not None:
            st["sw"] = length(sw, 1.0)
        if el.get("data-lint") == "skip" or "hatch" in (el.get("class") or "").split():
            st["skip"] = True
        if prop(el, "display") == "none" or prop(el, "visibility") == "hidden":
            return
        for name in ("stroke", "fill"):
            if st.get(name) and tag not in ("svg", "g"):
                colors.add(st[name])

        stroked = st.get("stroke", "none") not in ("none", "transparent")
        filled = tag != "line" and not is_white(st.get("fill", "black")) and st.get("fill", "black") != "none"
        polys = []
        if tag == "line":
            polys = [[(length(el.get("x1")), length(el.get("y1"))), (length(el.get("x2")), length(el.get("y2")))]]
        elif tag in ("polyline", "polygon"):
            a = nums(el.get("points"))
            pts = list(zip(a[::2], a[1::2]))
            polys = [pts + pts[:1] if tag == "polygon" else pts]
        elif tag == "rect":
            x, y, w, h = (length(el.get(k)) for k in ("x", "y", "width", "height"))
            polys = [[(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]]
        elif tag in ("circle", "ellipse"):
            cx, cy = length(el.get("cx")), length(el.get("cy"))
            rx = length(el.get("r") if tag == "circle" else el.get("rx"))
            ry = length(el.get("r") if tag == "circle" else el.get("ry"))
            polys = [[(cx + rx * math.cos(2 * math.pi * i / 24), cy + ry * math.sin(2 * math.pi * i / 24))
                      for i in range(25)]]
        elif tag == "path":
            polys = flatten_path(el.get("d"))
        elif tag == "text":
            fs = st["fs"]
            w = text_width(el, fs)
            x = (nums(el.get("x")) or [0.0])[0]
            y = (nums(el.get("y")) or [0.0])[0]
            anchor = st.get("text-anchor", "start")
            x0 = x - (w / 2 if anchor == "middle" else w if anchor == "end" else 0)
            corners = [mat_apply(ctm, p) for p in ((x0, y - 0.8 * fs), (x0 + w, y - 0.8 * fs),
                                                    (x0 + w, y + 0.2 * fs), (x0, y + 0.2 * fs))]
            inner = [mat_apply(ctm, p) for p in ((x0 + 1.5, y - 0.66 * fs), (x0 + w - 1.5, y - 0.66 * fs),
                                                  (x0 + w - 1.5, y + 0.04 * fs), (x0 + 1.5, y + 0.04 * fs))]
            box = lambda c: (min(p[0] for p in c), min(p[1] for p in c), max(p[0] for p in c), max(p[1] for p in c))
            content = re.sub(r"\s+", " ", "".join(el.itertext())).strip()
            if content:
                k = math.sqrt(abs(ctm[0] * ctm[3] - ctm[1] * ctm[2]))
                sub = [font_px(prop(ch, "font-size"), fs) for ch in el.iter()
                       if ch is not el and prop(ch, "font-size") and "".join(ch.itertext()).strip()]
                texts.append(dict(s=content, box=box(corners), inner=box(inner), fs=fs * k,
                                  fsmin=min([fs] + sub) * k, skip=st.get("skip", False)))
            return
        if polys and (stroked or filled):
            hatch = "hatch" in (el.get("class") or "").split()
            role = el.get("data-role") or ""
            w = st.get("sw", 1.0)
            ms, me = el.get("marker-start"), el.get("marker-end")
            dashed = bool(prop(el, "stroke-dasharray"))
            for pts in polys:
                pts = [mat_apply(ctm, p) for p in pts]
                segs.extend((a, b, st.get("skip", False), tag) for a, b in zip(pts, pts[1:]))
                if hatch:
                    hatchsegs.extend(zip(pts, pts[1:]))
                if not stroked or st.get("skip") or hatch:
                    continue
                if w >= 2.0 and (ms or me):
                    thick.extend(zip(pts, pts[1:]))
                if len(pts) == 2 and not dashed and w <= 1.0 and (ms or me):
                    arrows.append((pts[0], pts[1], bool(ms), bool(me), role))
                if len(pts) == 2 and not dashed and (role == "leader" or (
                        not role and not ms and abs(w - 0.7) < 0.01)):
                    leaders.append((pts[0], pts[1]))
        for ch in el:
            walk(ch, ctm, st)

    walk(root, (1, 0, 0, 1, 0, 0), {"fs": 16.0, "fill": "black"})

    # 背景の白い矩形などを除いた「描いたもの」
    if not segs and not texts:
        E.append("描画要素が1つも無い（空の図）")

    fmt = lambda b: f"({b[0]:.0f},{b[1]:.0f})–({b[2]:.0f},{b[3]:.0f})"
    if vb:
        x0, y0, x1, y1 = vb[0], vb[1], vb[0] + vb[2], vb[1] + vb[3]
        for t in texts:
            b = t["box"]
            if b[0] < x0 - 0.5 or b[1] < y0 - 0.5 or b[2] > x1 + 0.5 or b[3] > y1 + 0.5:
                E.append(f"文字「{t['s']}」が viewBox の外にはみ出している {fmt(b)}")
        out = [(a, b) for a, b, skip, tag in segs
               for p in (a, b) if p[0] < x0 - 1 or p[1] < y0 - 1 or p[0] > x1 + 1 or p[1] > y1 + 1]
        if out:
            p = out[0][0]
            Wn.append(f"線が viewBox の外に出ている（{len(out)} か所。例 ({p[0]:.0f},{p[1]:.0f}) 付近）")
    vw = vb[2] if vb else 0.0
    shown = f"表示幅 {vw * scale:.0f}px" + (f"（viewBox の幅 {vw:.0f}px を {scale:.2f} 倍）" if scale < 0.999 else "")
    body = [t for t in texts if t["fs"] * scale < MIN_BODY_PX - 0.05 and not t["s"].startswith("※")
            and not t["skip"]]
    tiny = [t for t in texts if t["fsmin"] * scale < MIN_TEXT_PX - 0.05]
    if body:
        Wn.append(f"本文字が小さい: {shown}で {min(t['fs'] for t in body) * scale:.1f}px の文字が {len(body)} 個"
                  f"（例「{body[0]['s']}」）。{MIN_BODY_PX:.0f}px 以上＝font-size {MIN_BODY_PX / scale:.1f} 以上にする"
                  "（図の幅を表示幅以下にし，一部の文字だけ小さくしない）")
    if tiny:
        Wn.append(f"最小の文字が小さい: {shown}で {min(t['fsmin'] for t in tiny) * scale:.1f}px の文字（添字・指数・注記）が "
                  f"{len(tiny)} 個（例「{tiny[0]['s']}」）。{MIN_TEXT_PX:.0f}px 以上＝font-size {MIN_TEXT_PX / scale:.1f} 以上にする")
    # 短い寸法：細い両矢印の線，または向かい合う2つの矢じり（外向きの寸法）の間隔
    short = []
    for a, b, ms, me, role in arrows:
        if ms and me:
            L = math.hypot(b[0] - a[0], b[1] - a[1]) + 8
            if L * scale < MIN_DIM_PX - 0.5:
                short.append((L, a))
    ends = [(b, (b[0] - a[0], b[1] - a[1]), role) for a, b, ms, me, role in arrows if me and not ms] + \
           [(a, (a[0] - b[0], a[1] - b[1]), role) for a, b, ms, me, role in arrows if ms and not me]
    for i, (p, d, r1) in enumerate(ends):
        for q, e, r2 in ends[i + 1:]:
            ld, le = math.hypot(*d), math.hypot(*e)
            if ld < 1 or le < 1 or ld > 20 or le > 20:
                continue           # 外向きの寸法の矢じりは短い線（約 13px）に付く
            pq = (q[0] - p[0], q[1] - p[1])
            gap = math.hypot(*pq)
            if gap < 1:
                continue
            facing = (d[0] * e[0] + d[1] * e[1]) / (ld * le) < -0.98          # 逆向き
            inline = abs(d[0] * pq[1] - d[1] * pq[0]) / (ld * gap) < 0.05      # 一直線上
            toward = (d[0] * pq[0] + d[1] * pq[1]) > 0                         # 互いに向かい合う
            if facing and inline and toward and (gap - 8) * scale < MIN_DIM_PX - 0.5:
                short.append((max(gap - 8, 0.0), p))
    for L, a in short:
        Wn.append(f"寸法の区間が短い: ({a[0]:.0f},{a[1]:.0f}) 付近の寸法が表示で約 {L * scale:.0f}px"
                  f"（{MIN_DIM_PX:.0f}px 以上にする。縮尺を上げる・誇張して模式図と断る・拡大図を別に描く）")
    # 引き出し線が他の線・斜線を横切る
    for p, q in leaders:
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        if L < 10:
            continue
        u = ((q[0] - p[0]) / L, (q[1] - p[1]) / L)
        a, b = (p[0] + u[0] * 4, p[1] + u[1] * 4), (q[0] - u[0] * 4, q[1] - u[1] * 4)
        n = sum(1 for s0, s1, skip, tag in segs if not skip and (s0, s1) != (p, q) and _cross(a, b, s0, s1))
        h = sum(1 for s0, s1 in hatchsegs if _cross(a, b, s0, s1))
        if n or h >= 2:
            what = "，".join(x for x in (f"他の線を {n} か所" if n else "", f"斜線の領域（斜線 {h} 本）" if h >= 2 else "") if x)
            Wn.append(f"引き出し線 ({p[0]:.0f},{p[1]:.0f})→({q[0]:.0f},{q[1]:.0f}) が{what}横切る"
                      "（線・領域を横切らない側から引くか，ラベルを対象のそばに置く）")
    # 太い矢印（力）が文字に接している
    for t in texts:
        if t["skip"]:
            continue
        b = t["box"]
        box = (b[0] - 2.5, b[1] - 1, b[2] + 2.5, b[3] + 1)
        if any(seg_hits_box(p, q, box) for p, q in thick):
            Wn.append(f"文字「{t['s']}」に太い矢印（力）が重なっている・接している {fmt(t['box'])}")
    for t in texts:
        if "\u02da" in t["s"] or "\u00ba" in t["s"]:
            Wn.append(f"文字「{t['s']}」の度の記号が「˚」「º」になっている（「°」U+00B0 を使う）")
        body = t["s"].strip()
        cjk = sum(1 for c in body if ord(c) >= 0x3040)
        if body.startswith("※"):
            if "。" in body.rstrip("。"):
                Wn.append(f"注記「{body}」が2文以上ある（図の注記は1文。説明は本文のキャプションへ）")
        elif cjk >= 12 or "。" in body or "，" in body:
            Wn.append(f"文字「{body}」は説明文になっている（図中は記号と短い名称だけ。説明・凡例は本文のキャプションへ）")
    for t in texts:
        if re.search(r"[\dπ]\s*/\s*\d", t["s"]):
            Wn.append(f"文字「{t['s']}」に斜線の分数がある（分数は分子・括線・分母の縦組みにする）")
        if re.search(r"\([^()]*,\S", t["s"]):
            Wn.append(f"文字「{t['s']}」の座標のカンマの後に空白が無い（(0, 0, 2) のように空ける）")
    for i, a in enumerate(texts):
        for b in texts[i + 1:]:
            ox = min(a["box"][2], b["box"][2]) - max(a["box"][0], b["box"][0])
            oy = min(a["inner"][3], b["inner"][3]) - max(a["inner"][1], b["inner"][1])
            if ox > 1 and oy > 1 and ox * oy > 4:
                Wn.append(f"文字「{a['s']}」と「{b['s']}」が重なっている {fmt(a['box'])} / {fmt(b['box'])}")
    for t in texts:
        if t["skip"]:
            continue
        hits = [(a, b) for a, b, skip, tag in segs if not skip and seg_hits_box(a, b, t["inner"])]
        if hits:
            a, b = hits[0]
            Wn.append(f"文字「{t['s']}」に線が重なっている {fmt(t['box'])}"
                      f"（線 ({a[0]:.0f},{a[1]:.0f})→({b[0]:.0f},{b[1]:.0f}) ほか計 {len(hits)} 本）")
    bad = sorted(c for c in colors if not is_gray(c))
    if bad:
        Wn.append("白黒以外の色がある: " + ", ".join(bad[:6]) + "（白黒印刷で区別できるか確かめる）")
    return E, Wn


def main(argv):
    strict = "--strict" in argv
    files = [a for a in argv if not a.startswith("--")]
    dw = next((float(a.split("=", 1)[1]) for a in argv if a.startswith("--display-width=")), None)
    if not files:
        print(__doc__)
        return 2
    code = 0
    for path in files:
        E, Wn = lint(path, dw)
        for m in E:
            print(f"{path}: ERROR {m}")
        for m in Wn:
            print(f"{path}: WARN  {m}")
        if not E and not Wn:
            print(f"{path}: OK")
        if E or (strict and Wn):
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
