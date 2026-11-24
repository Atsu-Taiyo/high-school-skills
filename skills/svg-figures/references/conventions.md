# SVG の書き方と既定値

手で SVG を書く・既存の SVG を直すときの書き方と，`hsfig.py`・`lint_svg.py`・`fidelity_loop.py` が使う既定値をまとめる。図の描き方の原則は [principles.md](principles.md)。

## 骨組み

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="296" height="352" viewBox="0 0 296 352"
     role="img" aria-labelledby="fig1-t fig1-d">
  <title id="fig1-t">図の名前</title>
  <desc id="fig1-d">何がどう描かれているか</desc>
  <defs><!-- 矢じりの marker --></defs>
  <rect x="0" y="0" width="296" height="352" fill="#fff"/>
  <g fill="none" stroke="#000" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
    <!-- 線・図形 -->
  </g>
  <g font-family="'Times New Roman', Times, 'Nimbus Roman', 'Liberation Serif', 'Hiragino Mincho ProN', 'Yu Mincho', 'Noto Serif CJK JP', serif"
     font-size="16" fill="#000" stroke="none" text-anchor="middle">
    <!-- 文字（最後に置き，線の上に来るようにする） -->
  </g>
</svg>
```

## どのレンダラーでも同じに見える書き方

原則は「表示環境によって結果が変わる機能を使わない」。

- 外部リソース（`<image>`，外部フォント，`@import`，`<script>`，外部への `href`），`<style>` と class による装飾，`<pattern>` の塗りを使わない。表示属性を要素に直接書く。
- `transform` を使わず，座標変換（数学座標の y の反転など）は生成時に済ませて px で書く。変換は1か所の式で行う。
- `id` は図ごとに違う接頭辞を付ける（複数の SVG を1ページに置くと衝突する）。
- 矢じりは `markerUnits="userSpaceOnUse"` の marker で大きさを px で決め，線は矢じりの先の手前で止める。始点側は向きを逆にした別の marker を使う（`auto-start-reverse` は古いレンダラーが対応しない）。線の途中の向きは，そこで終わる短い線に `marker-end` を付ける。
- 添字・指数は `<tspan dy>` で上下させ，次の文字で逆向きの `dy` を入れて基線に戻す（`baseline-shift` は効かない環境がある）。ベクトルの矢印は文字の上に別の線で描く（結合文字は位置がずれる）。
- 破線は `stroke-linecap="butt"`（丸い線端だと切れ目が埋まる）。それ以外の線端・角は丸。
- 斜線の領域は，領域の多角形で切り取った線分を書く（`clipPath` でもよい）。斜線を最初に描き，境界・軸・点・文字の順に重ねる。白丸・物体は白で塗って下の線を隠す。
- 座標は小数第2位まで。文字は `text-anchor="middle"` で中心を決めて置く。

## 既定値

ここにある数値だけが基準である（ほかのファイルでは繰り返さない）。表示での px。`hsfig` と lint が同じ値を使う。

| 項目 | 既定値 |
|---|---|
| 表示幅 | 650（分からないとき。`--display-width`，`Figure(display_width=)`） |
| 文字 | 本文字 16 以上，最小の文字（添字・指数・注記・計器の文字）12 以上。添字は本文字の 0.75 倍。図が表示幅 $D$ より広い（幅 $W$）なら font-size は 16×$W$÷$D$，12×$W$÷$D$ 以上 |
| 線幅（`hsfig` の style） | 本体 `main` 1.5，補助 `aux`・軸 `axis` 1.0，回路 `circuit` 1.2，力 `force`・強調 `heavy` 2.2，座標を読む補助線 `guide` 0.7，ハッチ・寸法の補助線 `thin` 0.6，寸法線 約 0.8 |
| 破線 | 補助・隠れ線 `5 3`，含まない境界 `7 3.5`（太さ 1.5），読取り線 `2 2.5`，一点鎖線 `9 3 1.5 3`，点線 `1.5 3.5` |
| 矢じり（長さ・幅） | 線幅 1.6 以下 9・6.4，力 12・8.8，寸法線 7・4.6。太い線では線幅に比例（幅は線幅の4倍以上）。線は先端の 5 手前で止める |
| 点 | 黒丸 半径 2.6，白丸 半径 3（線幅 1.2），作用点 半径 2.4 |
| 印 | 角の弧 半径 16 前後（2本目は +3），直角の正方形 一辺 8，等長の短線 長さ 10 |
| 斜線 | 45°，間隔 5，太さ 0.6。2種類目は 135° か間隔を変える。床・壁の斜線は長さ 8・間隔 6 |
| 余白・間隔 | 外周の余白 28 前後，ラベルと線・他のラベル 2 以上，点の名前は点から 6 |
| 下限 | 力の矢印の長さ 36，寸法を付ける区間 28，矢印が3本以上出る物体の一辺 60 |
| 寸法線 | 1段目は図形から 16，以後 20 ごと |
| 忠実度の採点（Mode B） | 輝度しきい値 `--cutoff` 200，膨張半径 `--dilate` 2，目標 `iou_norm` 0.90，初回の後の修正は最大 8 回，最高値を更新しない採点が2回続いたら終了 |

## 文字組み

- 数式ラベルは，Python が使えるなら `fig.label(...)` か `math_label.py`（`label_svg`）で組む。本文の KaTeX でも通る TeX の部分集合（添字・指数・`\frac`・`\vec`・`\sqrt`・ギリシャ文字・`\mathrm`）を text・tspan・path に展開する。根号の中の長い式・積分・Σ のように組めない式は図に入れず，記号だけを置く。
- 原図に波括弧が印刷されているときは `\{`・`\}`（`{...}` は引数のまとまりで表示されない）。
- 等号・不等号の両側に細い空き，座標はカンマの後に空白（`C(0, 0, 2)`）。

## 補助関数の索引（Python が使える環境）

関数の引数と既定は各スクリプトの docstring にある。完成例は `examples/make_examples.py`。

| 用途 | 関数 |
|---|---|
| 幾何の計算 | `hsfig` の `midpoint` `lerp` `foot` `intersect_lines` `intersect_line_circle` `intersect_circles` `tangent_points` `circumcenter` `incenter` `orthocenter` `rotate` `reflect` `solve` `tangent_at` `oblique` `lens_image` `region_between` |
| 線・曲線 | `segment` `arrow` `polyline` `smooth` `plot` `param` `circle` `arc` `line_through` `mid_arrow` |
| 軸・目盛り・点 | `axes` `xaxis` `yaxis` `coordinate_guides` `interval` `dot` `point` `label` `leader` `note` |
| 印・寸法・領域 | `angle_mark` `right_angle` `tick_marks` `parallel_marks` `dimension` `dimension_chain` `hatch` |
| 力 | `set_force_scale` `force_polar` `force` `components` `force_balance` `block` `ground` `spring` `pulley` |
| 回路・場・光 | `resistor` `capacitor` `battery` `inductor` `switch` `lamp` `meter` `ammeter` `voltmeter` `ac_source` `wire` `junction` `field_mark` `field_grid` `optical_axis` `lens` `ray` |
| 画面座標で測った部品 | `physics_symbols.py`（ダイオード，接地，枠内の斜線，検出器，省略された段），`chemistry_symbols.py`（化学式，反応の矢印，原子名，結合，ベンゼン環，くさび，器具，電極，エネルギー図，単位格子，曲線，周期表の枠） |
