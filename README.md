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

## 答案の検査（hs_check.py）

数学・物理のスキルには，答案を書いたあとに回す機械検査 `scripts/hs_check.py` が入っています（Python 3.9 以上の標準ライブラリだけ。モデルを呼ばず，外へ通信しません）。スキルの手順では，書く → `run` → 候補を1つずつ確かめて1回だけ直す → もう一度 `run` → 提出の直前に `verify`，の順に回します。

```sh
S=skills/high-school-math-answers          # 物理なら skills/high-school-physics-answers
python3 "$S/scripts/hs_check.py" lint --subject math answer.md                      # 検査だけ（記録しない）
python3 "$S/scripts/hs_check.py" run --subject math --final answer.md --problem problem.md
python3 "$S/scripts/hs_check.py" verify --final answer.md                           # 記録と同じ本文か
```

- 検査するのは，SKILL.md と references にある規則のうち機械的に判定できるもの（`\boxed`・`\le`・`\frac`・`\(`，範囲外の定理・用語，`$` の対応，式番号の書式，箇条書き，**答** の行，作業メモ，物理の単位の書体など）。確実に反するものを ERROR，文脈で判断が要るものを WARN にします。どの規則に当たるかは出力の括弧に出ます。
- 結果は「検査を実行した」という記録で，答案の正しさの合格ではありません。
- `run` は最終稿のハッシュと結果を `.hs-check/`（git の最上位か作業ディレクトリ。中に `.gitignore` を置く）に記録します。場所は `--state-dir` か環境変数 `HS_CHECK_STATE_DIR` で変えられます。
- 答案が `![解図1](fig1.svg)` のように SVG を参照し，svg-figures が隣にあれば，`run` は `lint_svg.py` もかけます。
- 検査の一覧は正本（references）から作ってあり，`python3 -B -m unittest discover -s tests` が，一覧の各項目が正本の文言を指していること，正本の表の命令がすべて検査されているか理由つきで除外されていることを確かめます。2つのスキルの `hs_check.py` は同じファイルです。
- Python が使えない環境では，SKILL.md の「出力前の点検」で同じ観点を目で確かめます（検査を実行したことにはなりません）。
- 今後の候補：答案を保存したときに検査を促すフック（任意。設定は表示するだけにする）。

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

Other tools that read the Agent Skills format can use the folders under `skills/` as they are.

The math and physics skills ship `scripts/hs_check.py` (Python 3.9+, standard library only, no model calls, no network). It checks an answer for the rules that can be judged mechanically (forbidden commands such as `\boxed`, `\le`, `\frac`, `\(`; out-of-curriculum theorems and terms; `$` pairing; equation-number format; bullets; the **答** line; work notes; physics unit typography). The skill runs it as: write → `run` → check each finding and fix once → `run` again → `verify` just before submitting. `run` records the final text's hash and results in `.hs-check/`; `verify` confirms the submitted text is the one that was checked. A passing record means the checks were executed, not that the answer is correct. Run the tests with `python3 -B -m unittest discover -s tests`. The Python scripts in `svg-figures` are optional. The skills are written in Japanese. License: MIT.
