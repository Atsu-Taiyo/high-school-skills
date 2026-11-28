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

- 記号・命令・書式・範囲外の語のように機械的に判定できる規則は `hs_check.py` が正本で，SKILL.md と references には書きません。出力の各行が「なぜだめか → 何に直すか」を示し，確実に反するものを ERROR，文脈で判断が要るものを WARN にします。
- 結果は「検査を実行した」という記録で，答案の正しさの合格ではありません。
- `run` は最終稿のハッシュと結果を `.hs-check/`（git の最上位か作業ディレクトリ。中に `.gitignore` を置く）に記録します。場所は `--state-dir` か環境変数 `HS_CHECK_STATE_DIR` で変えられます。
- 答案が `![解図1](fig1.svg)` のように SVG を参照し，svg-figures が隣にあれば，`run` は `lint_svg.py` もかけます。
- `python3 hs_check.py rules --subject math` で規則の一覧を Markdown で出せます。各スキルの `references/check-rules.md` はこの出力で，`python3 -B -m unittest discover -s tests` が今の規則と一致することを確かめます。2つのスキルの `hs_check.py` は同じファイルです。
- Python が使えない環境では，`references/check-rules.md` で同じ規則を目で確かめます（検査を実行したことにはなりません）。
- 今後の候補：答案を保存したときに検査を促すフック（任意。設定は表示するだけにする）。

## 評価で分かったこと

同じ5問（数学4・物理1，問題は画像）を各条件10回ずつ解かせ，Claude Opus が盲検で採点しました。1条件10回の小さな評価です。範囲外の方法（ロピタルの定理，テイラー展開，一様収束，微分方程式など）を答案で使った回の数は，次のとおりでした。

| モデル | スキルなし | スキルあり |
|---|---|---|
| gpt-6.2-sol | 8/10 | 0/10 |
| DeepSeek v4.1 Flash | 10/10 | 0/10 |
| Claude Haiku 5.5 | 9/10 | 3〜5/10（検査つきでスキルを読んだ回は 0〜1） |
| gpt-6-luna | 8/10 | 3〜6/10 |

- **スキルが読まれないことがあります（特に小さいモデル）。** Haiku は10回のうち5〜9回しかスキルを読まず，読まなかった回はスキルなしと同じ解き方をしました。確実に使わせたいときは，プロジェクトの `CLAUDE.md` や `AGENTS.md` に「数学・物理の問題の解答には high-school-math-answers / high-school-physics-answers を使う」と書いてください。
- 検査を回すと，時間とトークンが約2倍になります。速さを優先するなら，検査を省いてもスキルの本文だけで範囲外の方法は大きく減ります。

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

The math and physics skills ship `scripts/hs_check.py` (Python 3.9+, standard library only, no model calls, no network). It checks an answer for the rules that can be judged mechanically (forbidden commands such as `\boxed`, `\le`, `\frac`, `\(`; out-of-curriculum theorems and terms; `$` pairing; equation-number format; bullets; the **答** line; work notes; the final check line, which must give only the counts; physics unit typography). The skill runs it as: write → `run` → check each finding and fix once → `run` again → `verify` just before submitting. `run` records the final text's hash and results in `.hs-check/`; `verify` confirms the submitted text is the one that was checked. A passing record means the checks were executed, not that the answer is correct. Run the tests with `python3 -B -m unittest discover -s tests`. A small blind evaluation (5 problems, 10 runs per condition) found that the skills cut out-of-curriculum methods from 8–10/10 runs to 0/10 for gpt-6.2-sol and DeepSeek v4.1 Flash. Smaller models (Claude Haiku 5.5, gpt-6-luna) did not always load the skill: Haiku loaded it in only 5–9 of 10 runs. To make sure the skills are used, add a line such as "use high-school-math-answers / high-school-physics-answers for math and physics problems" to your project's `CLAUDE.md` or `AGENTS.md`. Running the checker roughly doubles time and tokens. If speed matters more, you can skip it. The Python scripts in `svg-figures` are optional. The skills are written in Japanese. License: MIT.
