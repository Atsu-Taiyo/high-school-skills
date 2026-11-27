# high-school-skills

日本の高校数学・物理の答案らしい解答を書き，教材用の図を SVG で描くための Agent Skills 集（Claude Code プラグイン）。

## 入っているスキル

| スキル | できること |
|---|---|
| `high-school-math-answers` | 高校数学（数学Ⅰ・Ⅱ・Ⅲ・A・B・C，2022年度〜の新課程）の問題に，教科書の記号・用語・論理で答案らしい解答を書く。既存の答案の添削・点検にも使う。 |
| `high-school-physics-answers` | 高校物理（物理基礎・物理）の問題に，対象・正の向き・法則名・単位と有効数字をそろえた答案らしい解答を書く。既存の答案の添削・点検にも使う。 |
| `svg-figures` | 高校数学・物理・化学の教材用の図（グラフ，図形，力の図，回路，光線図，構造式など）を SVG で描く。手描きの図の清書と，印刷図の再現を含む。 |

数学・物理のスキルは，求められない限り方針・解説・別解・参考を書かず，解答と答だけを書きます。範囲外の定理・記号（ロピタルの定理，外積，微分方程式など）は使わず，高校の方法に書き換えます。

## インストール（Claude Code）

Claude Code のセッションの中で：

```
/plugin marketplace add Atsu-Taiyo/high-school-skills
/plugin install high-school-skills@high-school-skills
```

シェルからは：

```sh
claude plugin marketplace add Atsu-Taiyo/high-school-skills
claude plugin install high-school-skills@high-school-skills
```

入れたあと，スキルは `high-school-skills:high-school-math-answers` のように，プラグイン名を前に付けた名前で表示されます。問題を渡せば自動で使われます。

## Claude Code 以外で使う

`skills/` の下の各フォルダは Agent Skills の形式（`SKILL.md` と `references/`）です。Codex など，この形式を読めるツールでは，`skills/` の中のフォルダをそのツールのスキルの置き場にコピーすれば使えます。

## svg-figures の補助スクリプト

`skills/svg-figures/scripts/` の Python スクリプト（作図の補助，体裁の検査，PNG への描画，原図との比較）は任意です。Python が無い環境でも，スキルの手順どおりに SVG を直接書いて目で点検できます。一部のスクリプトは Pillow・NumPy・OpenCV・Chrome を使います。

## ライセンス

MIT（[LICENSE](LICENSE)）。

---

## English

**high-school-skills** is a set of Agent Skills, packaged as a Claude Code plugin, for Japanese high-school mathematics and physics.

- `high-school-math-answers` and `high-school-physics-answers` write and review answers in the style of a Japanese high-school exam answer. They use only the notation, terms and methods in the current (2022–) curriculum textbooks.
- `svg-figures` draws textbook-style figures as SVG.

Install in Claude Code:

```
/plugin marketplace add Atsu-Taiyo/high-school-skills
/plugin install high-school-skills@high-school-skills
```

Other tools that read the Agent Skills format can use the folders under `skills/` as they are. The Python scripts in `svg-figures` are optional. The skills are written in Japanese. License: MIT.
