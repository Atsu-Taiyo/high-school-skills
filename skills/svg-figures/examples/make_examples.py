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
        fig.segment((x, 0), (x, f(x)), style="dash")
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
    fig.point((f, 0), "F′", dir="S")
    fig.label("O", (0, 0), dir="SW", dist=12)
    fig.label("物体", (-a, h), dir="N", size=12)
    fig.label("実像", img, dir="S", size=12)
    fig.save(out("convex-lens.svg"))


if __name__ == "__main__":
    parabola_area()
    triangle_circumcircle()
    incline_forces()
    circuit()
    convex_lens()
