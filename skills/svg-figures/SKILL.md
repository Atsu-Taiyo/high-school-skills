---
name: svg-figures
description: 高校数学・物理・化学の教材用の図（グラフ，図形，力の図，回路，光線図，化学の構造式・装置など）をSVGで作成・修正するときに使う。手描きの図の清書と，印刷図・既存の図の再現を含む。
license: MIT
metadata:
  version: "1.0.0"
---

# 高校数学・物理・化学の図を描く

## 作図の種類を決める

| 種類 | 入力 | 従うもの |
|---|---|---|
| 新規作図 | 条件・式・問題文 | 下の「新規作図と Mode A の規約」 |
| Mode A（手描きの清書） | 板書・ノート・スケッチ | 意図を読み取り，同じ規約で描き直す |
| Mode B（清書済みの図の再現） | 印刷図・製図された図・既存の SVG／PNG | 下の「Mode B の規約」 |

画像は，写っている図の描き方で判定する（線幅の揺れ・重ね書き・罫線なら A，活字・規則的な線なら B。撮影の傾きや汚れだけで A にしない）。判別できなければ，迷う箇所を示して確認する。Mode A・B の手順の正本は [画像から教材図を作る](references/image-to-svg.md)。

## 新規作図と Mode A の規約

- [作図標準](references/standard.md) の線幅・書体・文字の大きさ・配置に従う（主線 1.5 px，本文字 16 px・添字 12 px 以上，和文は明朝・欧文はセリフ，変数は斜体・点名と数字は立体）。白地に黒が基本。
- 交点・極値・接点・垂線の足・像の位置は式から求め，図形は等縮尺で描く。縦横の倍率を変えたグラフには数値目盛りか注記を付ける。
- 大きさが分かっている力には共通の尺度を使う（つり合う2力は同じ長さ，分力は元の力より短い）。
- Mode A では，描く前に意図仕様 `<図>.intent.md`（[書式](references/intent-template.md)）を書く。筆跡をなぞらず，揺れ・崩れた対称・比率を直す。筆者が書いていない要素を足さず，読めない文字は `[?]` として描かない。

## Mode B の規約

- 原図の配置・範囲・線種・線幅・文字位置と，**図題・番号・凡例・ラベルの表記・色**を保つ。作図標準で置き換えない。標準は，原図が決めていない事項にだけ使う。
- 色のある原図は，その色を測って平塗りで写し，ルートの `data-source-colors` に書く。ルートに `data-mode="B"` を付ける。

## 図中の文字

- 図に置くのは記号（$F$，$\theta$，P）・短い名称・**短い式や量のラベル**（曲線の $y=x^{2}$，矢印の $mg\sin\theta$）。
- 説明文・凡例・記号の意味・線種の区別・関係を述べる式や長い式は，図の直下の本文（キャプション）に書く。Mode B で原図にあるものは写す。
- 図を含む本文に，SVG の保存方法・ファイル名の説明・描画を確認したかどうか・作業メモを書かない。
- 字形は本文と同じにする（φ は本文の `\varphi` と同じ形）。図の番号とキャプションの置き方は high-school-math-answers の SKILL.md「図」が正本。

## 確認

- **普段の図**：最終の掲載幅（既定 650 px）で描画して見る。接点・交点・矢じり・ラベルの重なりは拡大して局所的に確かめる。Mode B は原図と同じ寸法で並べて比べる。点検項目は [仕上げの点検](references/qa-checklist.md)。
- **数値による忠実度の採点**（`fidelity_loop.py`，`iou_norm ≥ 0.90`，初回＋最大8回の修正）は，原図への忠実さを数値で示す必要がある Mode B の案件だけに使う（依頼で求められたとき，多段回路などで目視では判断できないとき）。Chrome／Chromium，Pillow，NumPy，OpenCV が要る。手順は [image-to-svg.md](references/image-to-svg.md)。

## 補助スクリプト（使える環境で）

Python 3 があれば，`scripts/` の道具で作図と検査を速くできる。`S` はこのスキルの scripts ディレクトリ。

```sh
python3 "$S/math_label.py" '$p_0+\frac{Mg}{S}$' --x 200 --y 80   # 数式ラベルの断片を出力
python3 "$S/lint_svg.py" --strict --display-width=650 fig.svg     # 体裁の検査
python3 "$S/lint_svg.py" --strict --intent=fig.intent.md fig.svg  # Mode A：意図仕様と照合
python3 "$S/render_png.py" --renderer chrome fig.svg              # PNG にして目視
```

- `hsfig.py` の `Figure`（標準ライブラリだけで動く）で新規作図を生成できる。実例は [make_examples.py](examples/make_examples.py)。
- lint が意図仕様と照合するのは，ルートに `data-mode="A"` があるか `--intent=PATH` を渡したときだけ。ERROR は直し，WARN は該当箇所を目で見て判断する。
- Python が使えない環境では，[SVG と文字組み](references/conventions.md) の骨組みで SVG を直接書き，ブラウザで掲載幅に表示して点検項目を目で確かめる。

## 図に応じて読む資料

- [数学](references/math-figures.md)：グラフ，領域，角・円，ベクトル，立体。
- [物理](references/physics-figures.md)：力の分解，ばね・滑車，回路，波，光，運動，磁場。
- [化学](references/chemistry-figures.md)：構造式・反応式，器具，エネルギー図，結晶，滴定曲線，周期表。原子名は立体の元素記号で組む。
- [SVG と文字組み](references/conventions.md)：骨組み，線種，矢じり，ラベル，寸法線，ハッチ。
