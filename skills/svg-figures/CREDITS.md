# CREDITS

このスキルのコード（`scripts/`，`examples/`）と文章（`SKILL.md`，`references/`）は，すべて新しく書いたものである。下記のリポジトリからは，図の描き方の作法と検証の進め方（考え方）を参考にした。**コードや文章をそのまま流用した部分は無い**ので，各ライセンスの許諾文の同梱は不要だが，出典として著作権表示を記す。

## 参考にしたリポジトリ

| リポジトリ | ライセンス | 参考にしたこと |
|---|---|---|
| KKTeX/Publicated-Files の `tikzify/`<br>https://github.com/KKTeX/Publicated-Files | MIT<br>Copyright (c) 2026 Kosei Kawaguchi | 点を名前付きの座標にし，中点・垂線の足・交点は計算で求める作法。直角は小さな正方形，角は円弧＋外側のラベル，点のラベルは方向を指定して置くこと。力は太い矢印，斜面・床は斜線，ばねは繰り返しの形を式で描くこと。回路は長方形の抵抗（欧州式＝新 JIS と同系）。全体を拡大縮小して文字まで縮めない，という大きさの決め方。描いたら画像にして目で確認し，重なりを直す検証手順。`references/pitfalls.md` の「見た目の落とし穴」の整理の仕方 |
| hamukazu/math_figures<br>https://github.com/hamukazu/math_figures | MIT<br>Copyright (c) 2023 Kimikazu Kato | ベクトルの和・平行四辺形（補助線は破線），三角関数の図で，ラベルを辺の中点付近の外側に置く教科書的な描き方 |
| SciMigo/straightedge<br>https://github.com/SciMigo/straightedge | MIT | 座標を AI に決めさせず計算で決める方針。ラベルの衝突・キャンバス外へのはみ出しを機械的に検出して報告する lint の考え方 |
| RenaissancePhilanthropy/geometry-diagram-generator<br>https://github.com/RenaissancePhilanthropy/geometry-diagram-generator | MIT | 図を作図手順（中点・交点・外心など）で記述し，座標は数値計算で求めてから描く設計 |
| alexn11/mathsvg，nedbat/cupid | MIT | 数学座標から SVG 座標への変換（y の反転，窓）を1か所にまとめる設計。依存を増やさないため取り込まず，自前で書いた |
| PM-Shawn/tikz-scientific-figures，alterlab-ieu/alterlab-academic-skills，NousResearch/hermes-agent（concept-diagrams） | MIT ほか | 「コードで描く → 手元でレンダリング → 自分で画像を見る → 直す」の検証ループと，lint の項目（小さすぎる文字，はみ出し，外部参照，空の描画） |

`refs/` に clone して中身を読んだのは KKTeX/Publicated-Files と hamukazu/math_figures の2つ。ほかは調査メモ（`RESEARCH_NOTES.md`）の記述に基づく。

## コピーしていないもの

- ro-smtz/ars-mathematica-content（GPL-3.0）は，ライセンスの条件が強いため参照も流用もしていない。

## 規格・慣習の出典

- 回路図の記号は JIS C 0617（電気用図記号）に基づく高校教科書の表記に合わせた。記号の図形はこのスキルで描き起こしたもので，規格票の図を複製したものではない。
- 図の体裁（線の太さの段階，イタリックと立体の使い分け，ラベルの置き方）は，日本の高校教科書・入試問題で一般的な慣習に合わせた。
