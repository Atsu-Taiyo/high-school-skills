#!/usr/bin/env python3
"""サンプル図を作る。  python3 make_examples.py  （このフォルダに SVG を書き出す）"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import hsfig as hs  # noqa: E402
from hsfig import Figure  # noqa: E402


def out(name):
    return os.path.join(HERE, name)


def parabola_area():
    """放物線と直線で囲まれた部分の面積。交点は方程式を解いて求める。"""
    f = lambda x: x * x
    g = lambda x: x + 2
    x1 = hs.solve(lambda x: f(x) - g(x), -2, 0)   # -1
    x2 = hs.solve(lambda x: f(x) - g(x), 0, 3)    # 2
    fig = Figure(-2.6, 3.4, -1, 6.4, unit=40, title="放物線と直線で囲まれた部分",
                 desc="放物線 y=x^2 と直線 y=x+2 が x=-1, 2 で交わり，その間の囲まれた部分に斜線を引いた図")
    fig.hatch(hs.region_between(g, f, x1, x2))
    fig.axes(xticks=[(x1, "$-1$"), (x2, "$2$")], yticks=[(2, "$2$", "NW")])
    fig.plot(f, -2.6, 3.4)
    fig.line_through((x1, g(x1)), (x2, g(x2)))
    for x in (x1, x2):
        fig.segment((x, 0), (x, f(x)), style="guide")
        fig.dot((x, f(x)))
    fig.label("$y=x^2$", (-2.3, f(-2.3)), dir="E", dist=8)
    fig.label("$y=x+2$", (2.6, g(2.6)), dir="SE", dist=3)
    fig.save(out("parabola-area.svg"))


def triangle_circumcircle():
    """三角形の外接円，垂線の足，中点。すべて計算で求める。"""
    A, B, C = (1.8, 3.6), (0, 0), (5, 0)
    O = hs.circumcenter(A, B, C)
    R = hs.dist(O, A)
    H = hs.foot(A, B, C)
    M = hs.midpoint(B, C)
    fig = Figure(-0.9, 5.9, -1.5, 4.3, unit=44, title="三角形 ABC と外接円",
                 desc="三角形 ABC の外接円（中心 O），A から BC に下ろした垂線 AH，BC の中点 M を示した図")
    fig.circle(O, R, style="aux")
    fig.polygon([A, B, C])
    fig.segment(A, H, style="dash")
    fig.right_angle(A, H, C)
    fig.segment(O, M, style="dash")
    fig.right_angle(O, M, C)
    fig.tick_marks(B, M)
    fig.tick_marks(M, C)
    fig.angle_mark(C, B, A, label="$\\theta$")
    G = hs.centroid(A, B, C)
    for name, p in (("A", A), ("B", B), ("C", C)):
        fig.point(p, name, away=G)
    fig.point(H, "H", dir="S")
    fig.point(M, "M", dir="S")
    fig.point(O, "O", dir="NE")
    fig.save(out("triangle-circumcircle.svg"))


def incline_forces():
    """粗い斜面上で静止する物体にはたらく力と，重力の分解。

    力はすべて同じ尺度（mg を 1 として長さ 2.3）で描く。垂直抗力と静止摩擦力の作用点は，
    重力の作用線が接触面と交わる点（3力がつり合うとき作用線は1点で交わる）。
    """
    th = 30
    c, s = math.cos(math.radians(th)), math.sin(math.radians(th))
    e = hs.polar(1, th)                      # 斜面に沿って上向き
    Q = (7, 7 * s / c)
    fig = Figure(-0.6, 8.0, -0.5, 5.3, unit=50, title="斜面上の物体にはたらく力",
                 desc="傾き θ の粗い斜面上で静止する質量 m の物体にはたらく重力 mg，垂直抗力 N，静止摩擦力 F と，"
                      "重力の斜面に平行な成分 mg sinθ，垂直な成分 mg cosθ を示した図。矢印の長さは力の大きさに比例する")
    fig.set_force_scale(2.3)                 # mg = 1 を長さ 2.3 で描く
    fig.ground((-0.4, 0), (7.8, 0))
    fig.polygon([(0, 0), (7, 0), Q])
    fig.angle_mark((7, 0), (0, 0), Q, r=34, label="$\\theta$")
    w, h = 1.5, 0.9
    base = hs.mul(e, 5.2)
    blk = fig.block(base, w, h, angle=th, fill="#e6e6e6", label="$m$", label_at=(0.62, 0.42))
    G = blk["center"]
    P = hs.intersect_lines(G, hs.add(G, (0, -1)), (0, 0), Q)   # 重力の作用線と接触面の交点
    v1, v2 = fig.components(G, (0, -fig.force_len(1)), th,
                            labels=("$mg\\sin\\theta$", "$mg\\cos\\theta$"), dirs=("W", "E"))
    fig.angle_mark(hs.add(G, (0, -1)), G, hs.add(G, v2), r=44, label="$\\theta$")
    fig.force_polar(G, 1, -90, "$mg$", dir="SW", dot=True)
    fig.force_polar(P, c, th + 90, "$N$", dot=True)             # N = mg cosθ
    fig.force_polar(P, s, th, "$F$", dir=th - 90, dist=7, shift=5)          # F = mg sinθ，物体側へ 5px ずらす
    fig.force_balance()
    fig.save(out("incline-forces.svg"))


def circuit():
    """直流回路（JIS 記号）。電池，スイッチ，抵抗，電球，電流計，電圧計。"""
    fig = Figure(-0.6, 8.2, -0.7, 3.7, unit=44, title="直流回路",
                 desc="電池 E，スイッチ S，抵抗 R，電球，電流計を直列につなぎ，電球に電圧計を並列につないだ回路図")
    fig.battery((0, 3), (0, 0), "$E$", side=-1)
    fig.switch((0, 3), (2.6, 3), "S")
    fig.resistor((2.6, 3), (6, 3), "$R$")
    fig.lamp((6, 3), (6, 0))
    fig.ammeter((6, 0), (0, 0))
    fig.wire((6, 3), (7.6, 3))
    fig.voltmeter((7.6, 3), (7.6, 0))
    fig.wire((7.6, 0), (6, 0))
    fig.junction((6, 3))
    fig.junction((6, 0))
    fig.save(out("circuit.svg"))


def convex_lens():
    """凸レンズによる実像の作図。像の位置は写像公式で計算する。"""
    f, a, h = 2.0, 5.0, 1.2
    b, m = hs.lens_image(a, f)               # b = 10/3, m = -2/3
    tip, img = (-a, h), (b, m * h)
    fig = Figure(-6.2, 4.6, -1.7, 2.0, unit=44, title="凸レンズによる実像",
                 desc="焦点距離 f の凸レンズの前方，焦点の外側に置いた物体から出た3本の光線が，レンズの後方で倒立の実像を結ぶ図")
    fig.optical_axis()
    fig.lens(0, 1.75)
    fig.arrow((-a, 0), tip)                  # 物体
    fig.arrow((b, 0), img)                   # 像
    fig.ray(tip, (0, h), img)                # 光軸に平行 → 後方の焦点を通る
    fig.ray(tip, img)                        # レンズの中心を直進
    fig.ray(tip, (0, m * h), img, at=0.3)            # 前方の焦点を通る → 光軸に平行
    fig.point((-f, 0), "F", dir="S")
    fig.point((f, 0), "F′", dir="NE")
    fig.label("O", (0, 0), dir="SW", dist=12)
    fig.label("物体", (-a, h), dir="N")
    fig.label("実像", img, dir="S")
    fig.save(out("convex-lens.svg"))


def lens_dimensions():
    """凸レンズと凹レンズの組み合わせ。寸法線を段に分け，短い区間は矢じりを外向きにする。

    右から来た光軸に平行な光線が凸レンズ L1（焦点距離 8d）で点 P1 に向かい，途中の
    凹レンズ L2（焦点距離 12d）で曲げられてスクリーン S 上の点 P2 に集まる。
    """
    w = 1.6                                   # 光線の高さ（d を 1 とする）
    xS, xP1, x2, x1 = 0.0, 1.0, 4.0, 9.0      # S，P1，凹レンズ L2，凸レンズ L1 の位置
    f1 = x1 - xP1                             # L1 の焦点が P1
    h2 = w * (x2 - xP1) / f1                  # L2 を通る高さ（相似）
    b, _ = hs.lens_image(-(x2 - xP1), -12.0)  # L2：P1 を虚光源として像の位置を確かめる
    assert abs(b - (x2 - xS)) < 1e-9
    fig = Figure(-0.9, 10.6, -4.2, 3.0, unit=29,
                 title="凸レンズと凹レンズの組み合わせ",
                 desc="光軸に平行な光線が凸レンズ L1 と凹レンズ L2 を通ってスクリーン S 上の点 P2 に集まる図。"
                      "レンズとスクリーンの間隔を段に分けた寸法線で示す")
    fig.optical_axis()
    fig.segment((xS, -2.0), (xS, 2.0))
    fig.lens(x1, 2.2)
    fig.lens(x2, 1.1, kind="concave")
    fig.ray((10.6, w), (x1, w), (x2, h2), (xS, 0))
    fig.segment((x2, h2), (xP1, 0), style="dash")          # L2 が無いときの進路
    fig.dot((x2, h2))
    fig.dot((xP1, 0))
    fig.leader("P$_1$", (xP1, 0), (xP1 + 0.9, -0.95), dot=True)   # 混み合う所の名前は引き出し線
    fig.point((xS, 0), "P$_2$", dir="SW")
    fig.label("S", (xS, 2.0), dir="N")
    fig.label("L$_2$", (x2, 1.1), dir="N")
    fig.label("L$_1$", (x1, 2.2), dir="N")
    fig.dimension((10.0, 0), (10.0, w), "$w$", side=-1, offset=10, ext=False)
    # 寸法線は図形の下にまとめる。1段目は区間ごと，2段目は全体。
    # 補助線は S・L2・L1 の下端と軸上の P1 から下ろす。区間 d は短いので矢じりが外に出る。
    feet = [(xS, -2.0), (xP1, 0), (x2, -1.1), (x1, -2.2)]
    fig.dimension_chain(feet, ["$d$", "$3d$", "$5d$"], side=-1, axis="x")
    fig.dimension(feet[0], feet[-1], "$9d$", side=-1, axis="x", row=1)
    fig.save(out("lens-dimensions.svg"))


def circuit_polarity():
    """電池の極性とコンデンサーの極板の電荷を記入した回路。"""
    fig = Figure(-1.1, 6.9, -0.7, 3.8, unit=44, title="コンデンサーの充電",
                 desc="起電力 E の電池，スイッチ S，抵抗 R，電気容量 C のコンデンサーを直列につないだ回路。"
                      "電池の正極の側の極板に +Q，負極の側の極板に −Q がたまる")
    fig.battery((0, 3), (0, 0), "$E$", side=-1, polarity=True)        # 上が正極。＋−は回路の内側
    fig.switch((0, 3), (2.4, 3), "S")
    fig.resistor((2.4, 3), (6, 3), "$R$")
    fig.capacitor((6, 3), (6, 0), "$C$", side=1, charges=("$+Q$", "$-Q$"))
    fig.wire((6, 0), (0, 0))
    fig.arrow((3.3, 2.45), (5.1, 2.45), style="aux")                  # 充電中の電流の向き
    fig.label("$I$", (4.2, 2.45), dir="S", dist=4)
    fig.save(out("circuit-polarity.svg"))


def cycle_direction():
    """p-V 図のサイクル。全過程を同じ太さで描き，各過程の中央に向きの矢じりを置く。"""
    p1, p2, V1, V2 = 1.0, 2.5, 1.0, 2.5
    iso = lambda V: p2 * V1 / V                      # 状態 B を通る等温線 pV = 一定
    V3 = V2
    A, B, C = (V1, p1), (V1, p2), (V3, iso(V3))
    fig = Figure(-0.5, 3.6, -0.5, 3.4, unit=70, aspect_ok=True, title="p-V 図のサイクル",
                 desc="定積変化 A→B，等温変化 B→C，定圧変化 C→A からなるサイクルの p-V 図。"
                      "各過程の中央に変化の向きの矢じりがある")
    fig.xaxis("$V$", ticks=[(V1, "$V_1$"), (V3, "$V_2$")])
    fig.yaxis("$p$", ticks=[(p1, "$p_1$"), (p2, "$p_2$")])
    fig.label("O", (0, 0), dir="SW", dist=4)
    for P in (A, B, C):
        fig.segment((P[0], 0), P, style="guide")
        fig.segment((0, P[1]), P, style="guide")
    fig.segment(A, B, arrow="mid")                   # 定積
    fig.plot(iso, V1, V3)                            # 等温（曲線）
    Vm = (V1 + V3) / 2
    fig.mid_arrow((Vm - 0.05, iso(Vm - 0.05)), (Vm + 0.05, iso(Vm + 0.05)))
    fig.segment(C, A, arrow="mid")                   # 定圧
    fig.point(A, "A", dir="SW")
    fig.point(B, "B", dir="NE")
    fig.point(C, "C", dir="NE")
    fig.save(out("cycle-direction.svg"))


def field_density():
    """直線電流がつくる磁場。導線に近いほど強いことを ⊗ の密度で表す。"""
    fig = Figure(-0.9, 5.4, -0.3, 3.5, unit=50, title="直線電流のまわりの磁場",
                 desc="紙面内を上向きに流れる直線電流 I の右側の磁場。向きは紙面の表から裏で，"
                      "導線に近いほど強いので ⊗ を密に描いてある")
    fig.segment((0, 0), (0, 3.3), style="main", arrow="mid", width=2.2)
    fig.label("$I$", (0, 1.65), dir="W", dist=9)
    fig.field_grid(0.5, 5.1, 0.25, 3.05, nx=6, ny=5, into=True, strength=lambda x: 1 / x, r=4.5)
    fig.dimension((0, 0.25), (2.2, 0.25), "$r$", side=-1, offset=14)
    fig.save(out("field-density.svg"))


def region_boundary():
    """不等式の表す領域。含まない境界線（bound）と座標を読む補助線（guide）を描き分ける。"""
    f = lambda x: x * x
    g = lambda x: x + 2
    x1 = hs.solve(lambda x: f(x) - g(x), -2, 0)   # -1
    x2 = hs.solve(lambda x: f(x) - g(x), 0, 3)    # 2
    fig = Figure(-2.4, 3.6, -0.9, 5.6, unit=50, title="不等式の表す領域",
                 desc="連立不等式 y>x^2，y<x+2 の表す領域を斜線で示した図。境界線は含まないので破線で，"
                      "交点 (-1, 1)，(2, 4) は白丸で示す")
    fig.hatch(hs.region_between(g, f, x1, x2))
    fig.axes()
    # 境界である区間は bound（太い破線），その外は細い実線で形だけ示す
    fig.plot(f, x1, x2, style="bound")
    fig.segment((x1, g(x1)), (x2, g(x2)), style="bound")
    for a, b in ((-2.2, x1), (x2, 2.3)):
        fig.plot(f, a, b, style="aux")
    fig.segment((-2.4, g(-2.4)), (x1, g(x1)), style="aux")
    fig.segment((x2, g(x2)), (3.3, g(3.3)), style="aux")
    # 座標を読む補助線は guide（細い点線）
    for x in (x1, x2):
        fig.segment((x, 0), (x, f(x)), style="guide")
        fig.dot((x, f(x)), open=True)
    fig.label("$-1$", (x1, 0), dir="S", dist=5)
    fig.label("$2$", (x2, 0), dir="S", dist=5)
    # 曲線の名前は領域の外側へ引き出す（斜線・補助線を横切らない）
    fig.leader("$y=x^2$", (0.95, f(0.95)), (1.3, 0.5), dir="S")
    fig.leader("$y=x+2$", (1.2, g(1.2)), (0.95, 4.45), dir="N")
    fig.save(out("region-boundary.svg"))


if __name__ == "__main__":
    parabola_area()
    triangle_circumcircle()
    incline_forces()
    circuit()
    convex_lens()
    lens_dimensions()
    circuit_polarity()
    cycle_direction()
    field_density()
    region_boundary()
