#!/usr/bin/env python3
"""hs_check.py - 高校数学・物理の答案（Markdown＋LaTeX）の機械検査と，検査の記録。

標準ライブラリだけで動く（Python 3.9 以上）。モデルは呼ばない。外へ通信しない。__pycache__ を作らない。

  lint    答案を検査し，ERROR / WARN を行番号つきで出す（何も書かない）。
  run     lint をまとめて実行し（答案が参照する SVG 図があれば svg-figures の lint_svg.py も），
          最終稿のハッシュと結果を状態フォルダ（既定は git の最上位か作業ディレクトリの .hs-check/）に記録する。
  verify  最終稿が最後の run の記録と同じ本文かを照らす（読むだけ）。

返す状態は「検査を実行した」であって，答案の正しさ（数学・物理として正しいか，範囲内の解き方か）の
合格ではない。検査するのは，スキル本文と references にある規則のうち，機械的に判定できるものだけ。
確実に規則に反するものを ERROR，文脈で判断が要るもの（頼まれた別解，問題文の用語など）を WARN にする。

規則の正本は SKILL.md と references/*.md。下の RULES・WORDS の各項目は，正本のどこに対応するかを
(ファイル, 正本にある文言) で持つ。tests/test_hs_check.py が，その文言が正本に今もあること，
forbidden.md 5節・notation.md 13節・notation-units.md 10節の表にある命令がすべて検査されるか
「機械では判定しない」と理由つきで除外されていることを確かめる（正本を直したのにここが古いままだと
テストが落ちる。二重管理で食い違わないための仕組み）。

このファイルは high-school-math-answers/scripts/ と high-school-physics-answers/scripts/ に同じものを置く
（どちらのスキルも単独で配置できるように）。2つが同じであることもテストで確かめる。
"""
__version__ = "1.0.0"

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import datetime  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
from bisect import bisect_right  # noqa: E402

DISCLAIMER = ("この結果は検査を実行したことを示すだけで，答案の正しさ（解き方・計算・範囲）の合格を示すものではありません。")

M = "high-school-math-answers/"
P = "high-school-physics-answers/"
MS = M + "SKILL.md"
PS = P + "SKILL.md"
FB = M + "references/forbidden.md"
NT = M + "references/notation.md"
AS = M + "references/answer-style.md"
SC = P + "references/scope.md"
NU = P + "references/notation-units.md"
PA = P + "references/answer-style.md"
SV = "svg-figures/SKILL.md"

BOTH = ("math", "physics")
MATH = ("math",)
PHYS = ("physics",)

# ---------------------------------------------------------------------------------------------
# 命令・記号の検査（本文全体。コードの中は見ない）
# (id, 水準, 科目, 正規表現, 直し方, (正本のファイル, 正本の文言))
# ---------------------------------------------------------------------------------------------
_CMD = r"(?![A-Za-z])"
RULES = [
    ("boxed", "ERROR", BOTH, r"\\boxed" + _CMD, "答は \\boxed で囲まず，独立した行の「**答**　…」に書く",
     (MS, "**答** は独立した行で")),
    ("ineq", "ERROR", BOTH, r"\\(?:le|ge|leq|geq|leqslant|geqslant)" + _CMD + r"|[≤≥]",
     "不等号は \\leqq・\\geqq", (MS, "不等号は `\\leqq`・`\\geqq`")),
    ("implies", "ERROR", BOTH, r"\\implies" + _CMD, "「ならば」は \\Rightarrow（\\implies は使わない）",
     (NT, "`\\implies`，`\\to` は使わない")),
    ("longrightarrow-if", "WARN", BOTH, r"\\Longrightarrow" + _CMD + r"|⟹",
     "「ならば」なら \\Rightarrow。式変形の矢印なら言葉（よって）でつなぐ", (NT, "| ならば | $p\\Rightarrow q$ | `\\Rightarrow`")),
    ("iff", "WARN", MATH, r"\\(?:iff|Leftrightarrow|Longleftrightarrow)" + _CMD,
     "同値記号は本当に同値なところだけ", (MS, "$\\iff$ は本当に同値なときだけ使う")),
    ("forall-exists", "ERROR", BOTH, r"\\(?:forall|exists|nexists)" + _CMD + r"|[∀∃]",
     "「すべての…について」「…が存在する」と言葉で書く", (FB, "`\\forall`，`\\exists`")),
    ("prod", "ERROR", BOTH, r"\\prod" + _CMD, "積は書き並べる（$a_{1}a_{2}\\cdots a_{n}$，$n!$）", (FB, "| $\\prod$ | `\\prod` |")),
    ("binom", "ERROR", BOTH, r"\\[dt]?binom" + _CMD, "組合せは {}_{n}\\mathrm{C}_{r}", (FB, "`\\binom{n}{r}`")),
    ("mathbb", "ERROR", BOTH, r"\\mathbb" + _CMD, "「実数」などと言葉で書く", (FB, "`\\mathbb{R}`")),
    ("logic", "ERROR", BOTH, r"\\(?:land|lor|lnot|neg|wedge|vee)" + _CMD, "「かつ」「または」「…でない」",
     (FB, "`\\land`，`\\lor`，`\\lnot`")),
    ("langle", "ERROR", MATH, r"\\(?:langle|rangle)" + _CMD, "内積は $\\vec{a}\\cdot\\vec{b}$", (FB, "`\\langle`，`\\rangle`")),
    ("Vert", "ERROR", MATH, r"\\Vert" + _CMD, "ベクトルの大きさは絶対値記号（\\lvert \\rvert）", (FB, "`\\Vert`")),
    ("bold-vector", "ERROR", BOTH, r"\\(?:mathbf|boldsymbol|bm)" + _CMD, "ベクトルは \\vec{a}",
     (FB, "`\\mathbf{a}`，`\\boldsymbol{a}`")),
    ("arc-trig", "ERROR", BOTH, r"\\arc(?:sin|cos|tan)" + _CMD + r"|\\(?:sin|cos|tan)\s*\^\s*\{?\s*-\s*1",
     "逆三角関数は使わない（角を文字でおく，置換積分）", (FB, "`\\arcsin`")),
    ("hyperbolic", "ERROR", BOTH, r"\\(?:sinh|cosh|tanh|coth)" + _CMD, "$\\dfrac{e^{x}-e^{-x}}{2}$ をそのまま書く",
     (FB, "`\\sinh`")),
    ("cot-sec-csc", "ERROR", BOTH, r"\\(?:cot|sec|csc)" + _CMD, "$\\dfrac{1}{\\tan\\theta}$ などで書く",
     (FB, "`\\cot`，`\\sec`，`\\csc`")),
    ("ln", "ERROR", BOTH, r"\\ln" + _CMD, "自然対数は \\log", (FB, "| $\\ln x$ | `\\ln` | $\\log x$ |")),
    ("exp", "ERROR", BOTH, r"\\exp" + _CMD, "$e^{x}$ と書く", (FB, "| $\\exp(x)$ | `\\exp` | $e^{x}$ |")),
    ("floor-ceil", "ERROR", MATH, r"\\(?:lfloor|rfloor|lceil|rceil)" + _CMD,
     "[x]（定義を添える），または言葉で書く", (FB, "`\\lfloor`，`\\rfloor`")),
    ("partial-nabla", "ERROR", BOTH, r"\\(?:partial|nabla)" + _CMD, "偏微分・ナブラは範囲外。その解法ごと避ける",
     (FB, "`\\partial`，`\\nabla`")),
    ("landau", "ERROR", MATH, r"(?<![A-Za-z\\}])[oO]\s*\(\s*(?:[xhnt](?:\^\{?\d+\}?)?|1|\\d?frac\{1\}\{[nx]\})\s*\)",
     "ランダウの記号 o( )・O( ) は範囲外", (FB, "$o(x)$，$O(x)$")),
    ("complex-exp", "ERROR", BOTH, r"e\s*\^\s*\{\s*-?\s*i", "$e^{i\\theta}$ は使わず極形式（$\\cos\\theta+i\\sin\\theta$）",
     (FB, "| $e^{i\\theta}$ | `e^{i\\theta}`")),
    ("nmid", "ERROR", MATH, r"\\nmid" + _CMD, "「$b$ は $a$ の倍数」と言葉で書く", (FB, "`\\mid`，`\\nmid`")),
    ("gcd", "ERROR", MATH, r"\\(?:gcd|lcm)" + _CMD + r"|\\mathrm\{lcm\}|\\operatorname\{lcm\}",
     "「最大公約数」「最小公倍数」", (FB, "| $\\gcd$，$\\mathrm{lcm}$ | `\\gcd` |")),
    ("bmod", "ERROR", MATH, r"\\bmod" + _CMD, "「$a$ を $b$ で割った余り」", (FB, "`\\bmod`")),
    ("cond-prob", "ERROR", MATH, r"P\s*\(\s*[^()$]*?\\mid(?![A-Za-z])|P\s*\(\s*[A-Z]\s*\|\s*[A-Z]\s*\)", "条件付き確率は $P_{A}(B)$",
     (FB, "| $P(B\\mid A)$ | `P(B\\mid A)` | $P_{A}(B)$ |")),
    ("Pi-perm", "ERROR", MATH, r"\\Pi\s*_", "重複順列は $n^{r}$", (FB, "${}_{n}\\Pi_{r}$（重複順列）")),
    ("max-min", "WARN", MATH, r"\\(?:max|min)" + _CMD, "「最大値」「最小値」と言葉で書くか，意味を添える",
     (FB, "| $\\max$，$\\min$ | `\\max`，`\\min`")),
    ("pmatrix", "ERROR", BOTH, r"\\begin\{[pbvBV]?matrix\}", "ベクトルの成分は $(a_{1},a_{2})$ と横に並べる",
     (FB, "| 成分を縦に並べたベクトル | `\\begin{pmatrix}`")),
    ("mapsto", "ERROR", MATH, r"\\mapsto" + _CMD, "「関数 $y=f(x)$」と書く", (FB, "`\\mapsto`")),
    ("approx", "ERROR", BOTH, r"\\(?:approx|simeq|sim)" + _CMD, "ほぼ等しいは \\fallingdotseq，分布は「…に従う」",
     (FB, "| $\\sim$（従う），$\\approx$，$\\simeq$ | `\\sim`，`\\approx`")),
    ("therefore", "ERROR", BOTH, r"\\(?:therefore|because)" + _CMD + r"|[∴∵]", "「よって」「…であるから」",
     (FB, "`\\therefore`，`\\because`")),
    ("qed-square", "ERROR", MATH, r"\\(?:square|blacksquare|Box|qed)" + _CMD + r"|[□■∎]", "「（証明終）」",
     (FB, "| $\\square$，$\\blacksquare$（証明終） | `\\square` |")),
    ("defeq", "ERROR", MATH, r"\\triangleq" + _CMD + r"|(?<![<>!=]):=", "「…とおく」「…と定める」",
     (FB, "| $\\triangleq$，$:=$ | `:=` |")),
    ("words-en", "ERROR", MATH, r"(?<![\\A-Za-z])(?:s\.t\.|iff|Q\.E\.D\.?|QED|w\.l\.o\.g\.?)(?![A-Za-z])", "「…を満たす」「…と同値」「（証明終）」",
     (FB, "| s.t.，iff，Q.E.D. |")),
    ("phi", "ERROR", BOTH, r"\\phi" + _CMD + r"|ϕ", "φ は \\varphi", (NT, "| `\\phi`（ϕ） | `\\varphi`")),
    ("env", "ERROR", BOTH, r"\\begin\{(?:align|equation|eqnarray|gather|multline|flalign)\*?\}",
     "複数行は $$\\begin{aligned}…\\end{aligned}$$", (NT, "| `\\begin{align}`，`\\begin{equation}`，`\\begin{eqnarray}` |")),
    ("tag-label", "ERROR", BOTH, r"\\(?:tag|label|ref|eqref)" + _CMD, "式番号は「　$式$　……①」の形で数式の外に書く",
     (NT, "| `\\label`，`\\ref`，`\\eqref`，`\\tag` |")),
    ("macro-def", "ERROR", BOTH, r"\\(?:newcommand|renewcommand|def|DeclareMathOperator)" + _CMD, "命令を定義せず毎回そのまま書く",
     (NT, "| `\\newcommand`，`\\def`，`\\renewcommand` |")),
    ("custom-macro", "ERROR", BOTH, r"\\(?:nCr|nPr|C|vector)" + _CMD, "独自マクロは描画できない（{}_{n}\\mathrm{C}_{r}，\\vec{a}）",
     (NT, "`\\nCr`，`\\C`，`\\bm`，`\\vector` などの独自マクロ")),
    ("tabular", "ERROR", BOTH, r"\\begin\{tabular\}", "Markdown の表か \\begin{array}", (NT, "| `\\begin{tabular}` |")),
    ("textcircled", "ERROR", BOTH, r"\\textcircled" + _CMD, "丸数字は数式の外に ① と書く", (NT, "| `\\textcircled{1}` |")),
    ("mbox", "WARN", BOTH, r"\\(?:mbox|hbox)" + _CMD, "説明文は地の文に出す", (NT, "| `\\mbox`，`\\hbox` に長い文 |")),
    ("vec-subscript", "ERROR", BOTH, r"\\vec\s*\{\s*\\?[A-Za-z]+\s*_", "添字は矢印の外（\\vec{e}_1）",
     (NT, "| `\\vec{e_1}` | `\\vec{e}_1` |")),
    ("prime-power", "ERROR", BOTH, r"(?<!\})'\s*\^", "プライムつきの2乗は {V'}^{2}", (NT, "| `V'^{2}` | `{V'}^{2}` |")),
    ("vec-cross", "ERROR", BOTH, r"\\vec\s*\{[^{}]*\}\s*(?:_\{?[^{}\s]*\}?)?\s*\\times\s*\\vec",
     "外積は範囲外（数学：内積が 0 の連立方程式，物理：大きさとフレミングの左手の法則）", (FB, "| $\\vec{a}\\times\\vec{b}$ | `\\times` |")),
    ("si-units", "ERROR", PHYS, r"\\(?:si|SI|unit|degree|celsius|ohm)" + _CMD, "単位は \\mathrm{}，^{\\circ}，{}^{\\circ}\\mathrm{C}，\\Omega",
     (NU, "| `\\si{}`，`\\SI{}{}`，`\\unit{}`，`\\degree`，`\\celsius`，`\\ohm` |")),
    ("dot-derivative", "ERROR", PHYS, r"\\d?dot\s*\{\s*\\?[A-Za-z]", "$v$，$a$ と文字でおく（導関数の記号は使わない）",
     (NU, "| `\\dot{x}`，`\\ddot{x}` |")),
    ("d-dt", "ERROR", PHYS, r"\\[dt]?frac\s*\{\s*d\s*\\?[A-Za-z]*[^{}]*\}\s*\{\s*d\s*\\?[A-Za-z]",
     "変化の割合は $\\dfrac{\\Delta x}{\\Delta t}$（微分の記号は使わない）", (SC, "| $v=\\dfrac{dx}{dt}$，$a=\\dfrac{dv}{dt}$ |")),
    ("integral", "ERROR", PHYS, r"\\(?:i*int|oint)" + _CMD, "積分は使わない（グラフの面積で書く）",
     (SC, "| 積分で変位・仕事・力積を求める |")),
]

# 数式の中だけを見る検査の正本（コードの中は見ない）
MATH_RULES = {
    "frac": ("ERROR", BOTH, "分数は \\dfrac（\\frac は指数・添字の中だけ）", (MS, "分数は `\\dfrac`（指数・添字の中だけ `\\frac`）")),
    "circled-in-math": ("ERROR", BOTH, "丸数字・丸囲み文字は数式の外に書く（KaTeX が警告を出す）", (MS, "**丸数字は数式の外**に書く")),
    "table-pipe": ("ERROR", BOTH, "表の中の数式に縦線 | を書かない（\\lvert x\\rvert）",
                   (MS, "Markdown の表の中では数式に縦線 `|` を書かない")),
    "text-long": ("WARN", BOTH, "\\text{} に入れてよいのは「かつ」「または」程度の短い語だけ",
                  (MS, "`\\text{}` に入れてよいのは「かつ」「または」程度の短い語だけ")),
    "text-unit": ("WARN", BOTH, "点の名前・単位は \\mathrm{}（\\text{} にしない）", (MS, "点の名前・単位は `\\mathrm{}`")),
    "text-blank": ("ERROR", PHYS, "空欄の記号を数式に入れない（「アは $mg\\sin\\theta$」と文で書く）",
                   (PS, "空欄の記号を数式に入れない")),
    "displaystyle": ("WARN", BOTH, "文中の \\lim・\\sum・\\int には \\displaystyle", (MS, "文中の $\\lim$・$\\sum$・$\\int$ には `\\displaystyle`")),
    "unit-italic": ("ERROR", PHYS, "単位は立体で数値との間に空白1つ（3.0\\ \\mathrm{m/s}）",
                    (NU, "| `3.0 m/s`（単位が斜体になる），`3.0\\mathrm{m/s}`（空きがない） |")),
    "unit-nospace": ("ERROR", PHYS, "数値と単位の間は空白1つ（3.0\\ \\mathrm{m/s}）",
                     (NU, "数値と単位の間は空白1つ（`\\ `）")),
    "unit-maybe": ("WARN", PHYS, "1文字の単位なら \\mathrm{}（量記号との積なら問題ない）",
                   (NU, "| `3.0 m/s`（単位が斜体になる），`3.0\\mathrm{m/s}`（空きがない） |")),
}

# 形式・構成の検査
FORM_RULES = {
    "dollar-unclosed": ("ERROR", BOTH, "$ の対応がとれていない（閉じ忘れ，または段落をまたいでいる）",
                        (NT, "| `$` を閉じ忘れる，`$$` の中に空行を入れる |")),
    "display-blank": ("ERROR", BOTH, "$$ の中に空行を入れない", (NT, "| `$` を閉じ忘れる，`$$` の中に空行を入れる |")),
    "paren-delim": ("ERROR", BOTH, "数式の区切りは $…$・$$…$$（\\( \\) と \\[ \\] は使わない）",
                    (MS, "文中は `$...$`，別行は `$$...$$`")),
    "code-wrap": ("ERROR", BOTH, "全体をコードブロックで囲まない（数式が描画されなくなる）", (MS, "全体をコードブロックで囲まない")),
    "bullet": ("ERROR", BOTH, "解答本体に Markdown の箇条書きを使わない（文でつなぐか (i)(ii)・[1][2] で区切る）",
               (MS, "**解答本体に Markdown の箇条書き（`-`，`1.`）を使わない。**")),
    "answer-missing": ("ERROR", BOTH, "独立した行の「**答**　…」がない", (MS, "**答** は独立した行で")),
    "answer-missing-proof": ("WARN", MATH, "「**答**」の行がない（証明だけの問題でも，結論を **答** に書くか確かめる）",
                             (MS, "**答** は独立した行で，問いの形（値・範囲・個数・「…であることが示された」）に合わせ")),
    "answer-inline": ("WARN", BOTH, "**答** が行の途中にある（独立した行にする）", (MS, "**答** は独立した行で")),
    "after-answer-check": ("ERROR", BOTH, "**答** の後に確認・検算・補足を続けない", (MS, "**答** の直後に「（確認：…）」や補足を続けない")),
    "after-answer": ("WARN", BOTH, "最後の **答** の後に本文が続いている（答案は **答** で閉じる。利用者への連絡なら --- で区切る）",
                     (MS, "**答案は **答** で閉じる。**")),
    "kaitou-missing": ("WARN", BOTH, "「**解答**」の行がない（既存の書式に合わせたのなら問題ない）", (MS, "**解答**")),
    "sections": ("WARN", BOTH, "頼まれていない方針・解説・別解・参考は書かない（頼まれたなら問題ない）",
                 (MS, "**求められない限り，方針・解説・別解・参考は書かず，解答と答だけを書く。**")),
    "eqno-format": ("ERROR", BOTH, "式番号の書式は「　$式$　……①」（行頭に全角空白，文中数式，全角空白，「……」，番号）",
                    (MS, "書式は1通り：`　$x>1$　……①`")),
    "eqno-paren-digit": ("ERROR", BOTH, "式番号に (1)(2) を使わない（小問番号と紛れる）", (NT, "`(1)`，`(2)` は小問の番号と紛れるので，式番号には使わない")),
    "eqno-mixed": ("WARN", BOTH, "式番号の系列が1題の中で混ざっている", (MS, "1題の中で変えない")),
    "eqno-display-mix": ("WARN", BOTH, "番号つきの式がある導出では，1行の式も「　$式$」の字下げにそろえる（$$ は複数行の aligned・cases だけ）",
                         (MS, "**番号つきの式がある導出（小問・場合分けの1区分）では，1行の式はすべてこの字下げの形でそろえる**")),
    "eqno-problem": ("WARN", BOTH, "問題文に丸数字がある。選択肢・空欄・条件の番号なら式番号は (a)(b)… にする",
                     (MS, "問題文に丸数字の選択肢・空欄・条件があれば (a)(b)…")),
    "memo": ("ERROR", BOTH, "検算・確認・作業メモを本文に書かない", (AS, "**検算・確認を載せない。**")),
    "memo-file": ("ERROR", BOTH, "図の保存・ファイル名・描画の確認などの作業メモを本文に書かない",
                  (SV, "図を含む本文に，SVG の保存方法・ファイル名の説明・描画を確認したかどうか・作業メモを書かない。")),
    "memo-scope": ("ERROR", BOTH, "「範囲外だが」と断って範囲外の方法を書かない（名前だけの紹介もしない）",
                   (SC, "「範囲外だが」「発展」と断っても書かない")),
    "desu-masu": ("WARN", BOTH, "文体は「である」体（指定があれば従う）。です・ます は利用者への連絡が混ざっていないかも確かめる",
                  (MS, "文体は「である」体（指定があればそれに従う）")),
    "touten": ("WARN", BOTH, "句読点は「，」「。」（指定があれば従う）", (MS, "句読点は「，」「。」")),
    "alt-text": ("ERROR", BOTH, "画像の代替テキストは図の名前だけの平文（< $ | 式を入れない）",
                 (MS, "代替テキストは図の名前だけの平文（`<`・`$`・`|`・式を入れない）")),
    "fig-number": ("WARN", BOTH, "問題に図があるときは解答の図を「解図1」，問題の図を「問題の図1」と書く",
                   (MS, "問題文に図があるときは解答の図を「解図1，解図2 …」とし")),
    "congruence": ("WARN", MATH, "合同式は発展。使うなら定義を書いてから（割った余りで分類する書き方が原則）",
                   (FB, "| 合同式 | 発展。")),
    "sufficient": ("WARN", MATH, "条件を求める問題では「〜であればよい」でなく「〜となるための条件は」",
                   (MS, "条件を求める問題で「〜であればよい」（十分条件）と書かず")),
    "obvious": ("WARN", BOTH, "「自明」「明らか」を理由の代わりにしない", (MS, "「自明」「明らか」を理由の代わりにしない")),
    "svg-missing": ("WARN", BOTH, "答案が参照する SVG 図が見つからない", (MS, "画像は `![解図1](fig1.svg)`")),
}

# ---------------------------------------------------------------------------------------------
# 範囲外の方法・用語（数式の外の地の文）。問題文（--problem）にある語は，問題文に合わせたものとして出さない
# (語の正規表現, 水準, 科目, 直し方, (正本, 文言))
# ---------------------------------------------------------------------------------------------
WORDS = [
    # forbidden.md 2節（範囲外の定理・解法）
    (r"ロピタル", "ERROR", BOTH, "式変形・はさみうちの原理・微分係数の定義", (FB, "ロピタルの定理")),
    (r"テイラー(?:展開|の定理)?|マクローリン", "ERROR", BOTH, "差をとった関数の増減，教科書の近似式", (FB, "テイラー展開，マクローリン展開")),
    (r"-\s*論法|[εδ]\s*-\s*[δN]\s*論法|イプシロン.?デルタ", "ERROR", MATH, "「限りなく近づく」とはさみうちの原理", (FB, "$\\varepsilon$-$\\delta$ 論法")),
    (r"単調で有界", "WARN", MATH, "極限値の候補をとってはさみうちの原理で示す", (FB, "「単調で有界な数列は収束する」")),
    (r"外積", "ERROR", BOTH, "内積が 0 の連立方程式（数学），大きさとフレミングの左手の法則（物理）", (FB, "| 外積 |")),
    (r"行列式|逆行列|固有値|固有ベクトル|[1一]次変換", "ERROR", BOTH, "連立方程式・加法定理・複素数平面", (FB, "行列式，逆行列，固有値，1次変換")),
    (r"斜交座標", "ERROR", MATH, "$s$，$t$ の条件として存在範囲を述べる", (FB, "| 斜交座標 |")),
    (r"点と平面の距離|平面の方程式", "WARN", MATH, "発展扱い。垂線の足を垂直条件から求める", (FB, "平面の方程式 $ax+by+cz+d=0$，点と平面の距離の公式")),
    (r"フェルマーの小定理|オイラーの定理", "ERROR", MATH, "余りの周期を計算するか二項定理", (FB, "フェルマーの小定理，オイラーの定理")),
    (r"中国(?:式)?剰余定理", "ERROR", MATH, "1次不定方程式として解く", (FB, "中国剰余定理")),
    (r"イェンセン|ジェンセン", "ERROR", MATH, "相加平均と相乗平均の大小関係，差をとって微分", (FB, "イェンセンの不等式")),
    (r"コーシー.?シュワル[ツッ]|シュワル[ツッ]の不等式", "ERROR", MATH, "差を平方の和に変形して示す", (FB, "コーシー・シュワルツの不等式")),
    (r"並べ替えの不等式|チェビシェフ", "ERROR", MATH, "差をとって因数分解する", (FB, "並べ替えの不等式，チェビシェフの不等式")),
    (r"ラグランジュの未定乗数", "ERROR", MATH, "1文字を消す，共有点をもつ条件", (FB, "ラグランジュの未定乗数法")),
    (r"偏微分|重積分", "ERROR", BOTH, "1文字を固定する（予選決勝法），断面積を積分", (FB, "偏微分，重積分")),
    (r"パップス|ギュルダン", "ERROR", MATH, "$\\pi\\int y^{2}dx$ で計算する", (FB, "パップス・ギュルダンの定理")),
    (r"バウムクーヘン", "WARN", MATH, "教科書の本文にない。使うなら導出を書く", (FB, "バウムクーヘン分割")),
    (r"傘型分割", "ERROR", MATH, "軸に垂直な断面で積分する", (FB, "傘型分割")),
    (r"逆三角関数", "ERROR", MATH, "$x=\\tan\\theta$ とおく置換積分", (FB, "| 逆三角関数 |")),
    (r"双曲線関数", "ERROR", MATH, "$\\dfrac{e^{x}+e^{-x}}{2}$ をそのまま書く", (FB, "| 双曲線関数 |")),
    (r"オイラーの公式", "ERROR", MATH, "極形式とド・モアブルの定理", (FB, "オイラーの公式")),
    (r"微分方程式", "WARN", MATH, "発展扱い。問題が誘導していない限り使わない", (FB, "| 微分方程式の解法 | 発展扱い。")),
    (r"微分方程式", "ERROR", PHYS, "運動方程式を $a=-\\omega^{2}x$ の形に直して単振動と読む", (SC, "| 微分方程式を立てて解く |")),
    (r"広義積分", "ERROR", MATH, "定積分の極限として書く", (FB, "| 広義積分 |")),
    (r"ガンマ関数|ベータ関数|ウォリス", "ERROR", MATH, "部分積分で漸化式を作る", (FB, "ガンマ関数，ベータ関数，ウォリスの公式")),
    (r"トレミー|スチュワートの定理", "ERROR", MATH, "余弦定理，円に内接する四角形の性質", (FB, "トレミーの定理，スチュワートの定理")),
    (r"包絡線", "ERROR", MATH, "逆像法・順像法", (FB, "| 包絡線 |")),
    (r"ベイズ", "ERROR", MATH, "条件付き確率の定義と乗法定理", (FB, "ベイズの定理（名前で使う）")),
    (r"不偏分散|\$?t\$?\s*分布|\$?p\$?\s*値", "ERROR", MATH, "分散は $n$ で割る。検定は標準正規分布の棄却域", (FB, "不偏分散，$t$ 分布，$p$ 値")),
    (r"カタラン数|完全順列|スターリング数", "ERROR", MATH, "数え上げるか漸化式を立てる", (FB, "カタラン数，完全順列の公式，スターリング数")),
    (r"生成関数|母関数", "ERROR", MATH, "漸化式，二項定理", (FB, "生成関数（母関数）")),
    (r"ロルの定理", "WARN", MATH, "平均値の定理で書く", (FB, "| ロルの定理 |")),
    (r"合同式", "WARN", MATH, "発展。定義を書いてから使う", (FB, "| 合同式 | 発展。")),
    # forbidden.md 6節（範囲外の用語）
    (r"多項式", "ERROR", MATH, "整式", (FB, "| 多項式 | 整式 |")),
    (r"線[形型]", "ERROR", MATH, "1次（1次結合は「$s\\vec{a}+t\\vec{b}$ の形」）", (FB, "| 線形，線型 |")),
    (r"ノルム", "ERROR", BOTH, "大きさ", (FB, "| ノルム，長さ（ベクトル） | 大きさ |")),
    (r"スカラー", "ERROR", MATH, "実数", (FB, "| スカラー | 実数 |")),
    (r"直交(?!座標)", "ERROR", MATH, "垂直", (FB, "| 直交 | 垂直 |")),
    (r"正規化", "ERROR", MATH, "同じ向きの単位ベクトルを求める", (FB, "| 正規化する |")),
    (r"写像|単射|全射", "ERROR", MATH, "関数，対応。内容を書く", (FB, "| 写像，単射，全射 |")),
    (r"一意", "ERROR", BOTH, "ただ1つに", (FB, "| 一意に定まる | ただ1つに定まる |")),
    (r"狭義単調", "ERROR", MATH, "常に増加する（数学Ⅲでは「単調に増加する」）", (FB, "| 狭義単調増加 |")),
    (r"凸関数|凹関数", "ERROR", MATH, "下に凸，上に凸", (FB, "| 凸関数，凹関数 |")),
    (r"上界|下界|有界", "ERROR", MATH, "内容を書く（「$a_n<2$ がすべての $n$ で成り立つ」）", (FB, "| 上界，上限，有界 |")),
    (r"上限|下限", "WARN", MATH, "数列の上限・下限の意味なら内容を書く", (FB, "| 上界，上限，有界 |")),
    (r"剰余(?!の定理)", "ERROR", MATH, "余り，「$m$ で割った余り」", (FB, "| 剰余，法 |")),
    (r"特性方程式|不動点", "ERROR", MATH, "「$\\alpha=p\\alpha+q$ を満たす $\\alpha$」と式で書く", (FB, "| 特性方程式，不動点 |")),
    (r"テレスコーピング", "ERROR", MATH, "「途中の項が打ち消し合う」", (FB, "| テレスコーピング |")),
    (r"一般性を失わ", "ERROR", BOTH, "「対称性から $a\\leqq b$ としてよい」と理由を書く", (FB, "| 一般性を失わず |")),
    (r"全単射|逆写像", "ERROR", MATH, "「1対1に対応する」，逆関数", (FB, "| 全単射，逆写像 |")),
    (r"同値類|剰余類", "ERROR", MATH, "「$3$ で割った余りが同じ整数」", (FB, "| 同値類，剰余類 |")),
    (r"可換|結合的", "ERROR", MATH, "「順序を変えてもよい」", (FB, "| 可換，結合的 |")),
    (r"閉包|開集合|近傍", "ERROR", MATH, "使わない（「$x=a$ の近くで」）", (FB, "| 閉包，開集合，近傍 |")),
    (r"連続微分可能|\$?C\^\{?1\}?\$?\s*級", "ERROR", MATH, "「微分可能」「$f'(x)$ が連続」", (FB, "| 連続微分可能，滑らか，$C^{1}$ 級 |")),
    (r"収束半径|一様収束|絶対収束", "ERROR", MATH, "使わない", (FB, "| 収束半径，一様収束，絶対収束 |")),
    (r"極限の交換|項別微分", "ERROR", MATH, "その解法を避ける", (FB, "| 極限の交換，項別微分 |")),
    (r"基底", "ERROR", MATH, "「$s\\vec{a}+t\\vec{b}$ の形にただ1通りに表せる」", (FB, "| 基底，次元，張る |")),
    (r"無限降下法", "ERROR", MATH, "背理法として書き下す", (FB, "| 無限降下法 |")),
    (r"適当な", "WARN", MATH, "「ある実数 $k$ を用いて」", (FB, "| 「適当な $k$ をとると」 |")),
    (r"非自明|自明な解", "ERROR", MATH, "「$x=y=0$ 以外の解」", (FB, "| 自明な解，非自明 |")),
    (r"退化", "WARN", MATH, "「1点になる」「直線になる」と具体的に書く", (FB, "| 退化する |")),
    (r"オーダー|漸近的", "ERROR", MATH, "使わない", (FB, "| オーダー，漸近的に |")),
    # scope.md（物理の範囲外の方法）
    (r"高次の近似", "ERROR", PHYS, "$\\lvert x\\rvert\\ll1$ のとき $(1+x)^{n}\\fallingdotseq1+nx$", (SC, "| テイラー展開，高次の近似 |")),
    (r"ナブラ|線積分|面積分", "ERROR", PHYS, "範囲外。その方法ごと避ける", (SC, "| 偏微分，ナブラ，線積分・面積分 |")),
    (r"慣性モーメント|回転の運動方程式|回転の運動エネルギー", "ERROR", PHYS, "剛体はつり合いだけ。問題文が与える関係式で解く",
     (SC, "| 慣性モーメント，回転の運動方程式，回転の運動エネルギー |")),
    (r"角運動量", "ERROR", PHYS, "面積速度一定の法則（ケプラーの第2法則）", (SC, "| 角運動量，角運動量保存の法則 |")),
    (r"換算質量|重心系", "ERROR", PHYS, "運動量保存の法則と力学的エネルギー保存の法則（または反発係数の式）", (SC, "| 換算質量，重心系への変換 |")),
    (r"ラグランジアン|ハミルトニアン|仮想仕事", "ERROR", PHYS, "運動方程式とつり合いの式", (SC, "| ラグランジアン，ハミルトニアン，仮想仕事の原理 |")),
    (r"コリオリ", "ERROR", PHYS, "静止した観測者から見て解く", (SC, "| コリオリの力 |")),
    (r"有効ポテンシャル", "ERROR", PHYS, "力学的エネルギー保存の法則と $U=-G\\dfrac{Mm}{r}$", (SC, "| 有効ポテンシャル，脱出速度の導出に積分 |")),
    (r"エントロピー", "ERROR", PHYS, "各過程の熱量から熱効率を計算する", (SC, "| エントロピー，カルノーサイクルの効率の導出")),
    (r"マクスウェル分布|エネルギー等分配|等分配則", "ERROR", PHYS, "単原子分子理想気体の $U=\\dfrac{3}{2}nRT$", (SC, "| マクスウェル分布，エネルギー等分配則（自由度） |")),
    (r"ファンデルワールス", "ERROR", PHYS, "範囲外", (SC, "| ファンデルワールスの状態方程式 |")),
    (r"波動方程式", "ERROR", PHYS, "正弦波の式 $y=A\\sin2\\pi\\Bigl(\\dfrac{t}{T}-\\dfrac{x}{\\lambda}\\Bigr)$", (SC, "| 波動方程式，複素数による波の表示")),
    (r"波数", "WARN", PHYS, "問題文が使っていなければ $T$，$\\lambda$，$f$，$v$ で書く", (SC, "| 波数 $k$，角振動数だけで書いた")),
    (r"フーリエ|群速度|分散関係", "ERROR", PHYS, "範囲外", (SC, "| フーリエ級数，群速度，分散関係 |")),
    (r"レンズメーカー|球面収差|行列光学", "ERROR", PHYS, "範囲外", (SC, "| レンズメーカーの式，球面収差，行列光学 |")),
    (r"フレネルの式|反射率", "ERROR", PHYS, "反射での位相の変化だけを使う", (SC, "| フレネルの式，反射率 |")),
    (r"ビオ.?サバール", "ERROR", PHYS, "右ねじの法則と直線電流・円形電流・ソレノイドの公式", (SC, "ビオ・サバールの法則")),
    (r"アンペールの法則", "WARN", PHYS, "積分形は使わず，直線電流・円形電流・ソレノイドの公式で書く", (SC, "| アンペールの法則の積分形 |")),
    (r"ガウスの法則", "WARN", PHYS, "積分形は使わず，電気力線の本数（$4\\pi kQ$ 本）で書く", (SC, "| ガウスの法則の積分形")),
    (r"複素インピーダンス|フェーザ", "ERROR", PHYS, "電圧と電流の最大値の関係と位相，教科書の $Z$ の式", (SC, "| 複素インピーダンス，フェーザを複素数で |")),
    (r"時定数", "ERROR", PHYS, "「スイッチを入れた直後」と「十分時間が経過した後」の2つの状態で論じる", (SC, "RC・RL 回路の過渡現象を指数関数で（時定数）")),
    (r"マクスウェル方程式|変位電流|ポインティング", "ERROR", PHYS, "範囲外", (SC, "| マクスウェル方程式，変位電流，ポインティングベクトル |")),
    (r"電気影像|鏡像法", "ERROR", PHYS, "範囲外", (SC, "| 電気影像法 |")),
    (r"磁気モーメント|磁気双極子", "ERROR", PHYS, "コイルの各辺が受ける力と，その力のモーメント", (SC, "| 磁気モーメント，磁気双極子 |")),
    (r"シュレーディンガー|シュレディンガー|波動関数|不確定性原理", "ERROR", PHYS, "ボーアの量子条件と振動数条件", (SC, "| シュレーディンガー方程式，波動関数，不確定性原理の式 |")),
    (r"崩壊定数", "ERROR", PHYS, "半減期の式 $N=N_{0}\\Bigl(\\dfrac{1}{2}\\Bigr)^{\\frac{t}{T}}$", (SC, "崩壊の式を微分方程式から導く（崩壊定数）")),
    (r"(?<!逆)行列(?!式)", "ERROR", PHYS, "範囲外", (SC, "| 行列，固有値，複素数の指数関数 |")),
    # notation-units.md 9節（物理の用語）
    (r"熱力学第[1１]法則", "ERROR", PHYS, "熱力学第一法則", (NU, "| 熱力学第1法則 | 熱力学第一法則 |")),
    (r"エネルギー保存則|運動量保存則", "ERROR", PHYS, "力学的エネルギー保存の法則，運動量保存の法則", (NU, "| エネルギー保存則，運動量保存則 |")),
    (r"キルヒホッフ則", "ERROR", PHYS, "キルヒホッフの第1法則（電流），第2法則（電圧）", (NU, "| キルヒホッフ則 |")),
    (r"電荷保存", "ERROR", PHYS, "電気量保存の法則", (NU, "| 電荷保存 | 電気量保存の法則 |")),
    (r"コンデンサ(?!ー)|キャパシタ", "ERROR", PHYS, "コンデンサー", (NU, "| コンデンサ，キャパシタ | コンデンサー |")),
    (r"はねかえり係数|跳ね返り係数", "WARN", PHYS, "反発係数（問題文が「はねかえり係数」ならそれに合わせる）", (NU, "| はねかえり係数 | 反発係数")),
    (r"電界|磁界", "WARN", PHYS, "電場，磁場（問題文が電界・磁界ならそれに合わせる）", (NU, "| 電界，磁界 | 電場，磁場")),
    (r"ノーマルフォース|テンション|\bEOM\b", "ERROR", PHYS, "垂直抗力，張力，運動方程式", (NU, "| ノーマルフォース，テンション |")),
]

# 作業メモ（本文に書かないもの）
MEMO = [
    (r"検算", "memo"), (r"[（(]\s*確認\s*[:：]", "memo"), (r"^\s*確認\s*[:：]", "memo"),
    (r"この例で守っている点", "memo"),
    (r"保存しました|書き出しました|出力しました|生成しました|描画を確認|描画しました|ファイル名|\.svg\s*に", "memo-file"),
    (r"範囲外(?:だが|ですが|であるが|の方法だが)|発展(?:的|事項|内容|扱い)?(?:だが|ですが|であるが)", "memo-scope"),
]

ANSWER_RE = re.compile(r"^\s*\*\*\s*答\s*(?:[（(][^）)*]*[）)])?\s*\*\*")
SECTION_WORDS = r"(?:方針|解説|別解|参考|補足|考え方|解き方の方針|ポイント)"
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚㋐㋑㋒㋓㋔㋕㋖㋗㋘㋙㋚㋛㋜㋝㋞"
EQNO = r"(?:[" + CIRCLED + r"]|\([a-z]\)|\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\)|\([A-Z]\)|\(\d+\))"
UNITS = (r"m/s\^?\{?2?\}?|m/s|km/h|kg|m|cm|mm|km|nm|s|N|J|W|V|A|mA|Hz|Pa|hPa|K|mol|C|F|μF|H|T|Wb|eV|MeV|rad|"
         r"N/m|J/K|J/\(mol\\cdot K\)|kWh|Ω|mL")
UNIT_MULTI = re.compile(r"^(?:m/s|km/h|kg|cm|mm|km|nm|mA|Hz|Pa|hPa|mol|μF|Wb|eV|MeV|rad|N/m|J/K|kWh|mL)")


# ---------------------------------------------------------------------------------------------
# 本文の解析
# ---------------------------------------------------------------------------------------------
class Doc:
    def __init__(self, text):
        self.raw = text
        self.findings = []
        self.code_wrapped = False
        stripped = text.strip()
        if re.match(r"^(```|~~~)[^\n]*\n", stripped) and re.search(r"\n(```|~~~)\s*$", stripped):
            fence = stripped[:3]
            inner = stripped.split("\n", 1)[1]
            inner = inner[: inner.rstrip().rfind(fence)]
            if fence not in inner:
                self.code_wrapped = True
                lead = text[: text.find(stripped)].count("\n") + 1
                text = "\n" * lead + inner
        self.text = text
        self.clean = _mask_code(text)
        self.lines = self.clean.split("\n")
        self.starts = [0]
        for i, ch in enumerate(self.clean):
            if ch == "\n":
                self.starts.append(i + 1)
        self.segments, self.delim_problems = _math_segments(self.clean)
        self.math_mask = _mask_ranges(self.clean, [(s, e) for s, e, _k, _b in self.segments])
        self.prose_lines = self.math_mask.split("\n")
        self.display_lines = set()
        for s, e, kind, _b in self.segments:
            if kind != "inline":
                a, b = self.line_of(s), self.line_of(e)
                self.display_lines.update(range(a, b + 1))

    def line_of(self, offset):
        return bisect_right(self.starts, offset)

    def add(self, rid, line, excerpt="", rules=None, level=None, note=None):
        table = rules if rules is not None else FORM_RULES
        lvl, _subj, msg, ref = table[rid] if rid in table else (level, None, note, None)
        self.findings.append({"level": level or lvl, "id": rid, "line": line, "message": note or msg,
                              "ref": ref, "excerpt": _one_line(excerpt)})


def _one_line(text, limit=60):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _mask_code(text):
    """コードブロックと `コード` を空白にする（改行は残す）。"""
    out = list(text)
    for m in re.finditer(r"(?ms)^[ \t]*(```|~~~)[^\n]*\n.*?^[ \t]*\1[ \t]*$", text):
        for i in range(m.start(), m.end()):
            if out[i] != "\n":
                out[i] = " "
    masked = "".join(out)
    out = list(masked)
    for m in re.finditer(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)", masked):
        for i in range(m.start(), m.end()):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)


def _mask_ranges(text, ranges):
    out = list(text)
    for s, e in ranges:
        for i in range(s, min(e, len(out))):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)


def _math_segments(t):
    """$…$，$$…$$，\\(…\\)，\\[…\\] を拾う。戻り値は ([(開始, 終了, 種類, 中身)], [(種類, 位置)])。"""
    segs, problems = [], []
    n, i = len(t), 0
    state, start, body_start = None, 0, 0

    def blank_follows(pos):
        j = pos + 1
        while j < n and t[j] in " \t":
            j += 1
        return j >= n or t[j] == "\n"

    while i < n:
        c = t[i]
        if c == "\\" and i + 1 < n:
            nxt = t[i + 1]
            if state is None and nxt in "([":
                state = "paren" if nxt == "(" else "bracket"
                start, body_start = i, i + 2
                problems.append(("paren-delim", i))
            elif (state == "paren" and nxt == ")") or (state == "bracket" and nxt == "]"):
                segs.append((start, i + 2, state, t[body_start:i]))
                state = None
            i += 2
            continue
        if c == "$":
            if t.startswith("$$", i):
                if state is None:
                    state, start, body_start = "display", i, i + 2
                    i += 2
                    continue
                if state == "display":
                    segs.append((start, i + 2, "display", t[body_start:i]))
                    state = None
                    i += 2
                    continue
            if state is None:
                state, start, body_start = "inline", i, i + 1
            elif state == "inline":
                segs.append((start, i + 1, "inline", t[body_start:i]))
                state = None
            i += 1
            continue
        if c == "\n" and state is not None and blank_follows(i):
            if state == "inline":
                problems.append(("dollar-unclosed", start))
                state = None
            elif state == "display":
                problems.append(("display-blank", i + 1))
        i += 1
    if state in ("inline", "display", "paren", "bracket"):
        problems.append(("dollar-unclosed", start))
    return segs, problems


def _in_script(body, pos):
    """body[pos] が指数・添字（^{…}，_{…}，^\\frac）の中か。"""
    j = pos - 1
    while j >= 0 and body[j] == " ":
        j -= 1
    if j >= 0 and body[j] in "^_":
        return True
    stack, k = [], 0
    while k < pos:
        ch = body[k]
        if ch == "\\":
            k += 2
            continue
        if ch == "{":
            p = k - 1
            while p >= 0 and body[p] == " ":
                p -= 1
            stack.append(p >= 0 and body[p] in "^_")
        elif ch == "}" and stack:
            stack.pop()
        k += 1
    return any(stack)


def _line_text(doc, ln):
    return doc.lines[ln - 1] if 0 < ln <= len(doc.lines) else ""


# ---------------------------------------------------------------------------------------------
# 検査
# ---------------------------------------------------------------------------------------------
def lint_text(text, subject, problem=None, fmt="md"):
    doc = Doc(text)
    subj = subject
    if doc.code_wrapped:
        doc.add("code-wrap", 1, "```")
    if fmt == "md":
        for kind, pos in doc.delim_problems:
            if kind == "paren-delim":
                doc.add(kind, doc.line_of(pos), _line_text(doc, doc.line_of(pos)))
    for kind, pos in doc.delim_problems:
        if kind != "paren-delim":
            doc.add(kind, doc.line_of(pos), _line_text(doc, doc.line_of(pos)))
    # paren-delim は1件にまとめる（件数が多いと読みにくい）
    _collapse(doc, "paren-delim")

    _check_commands(doc, subj)
    _check_math(doc, subj)
    if fmt == "md":
        _check_lines(doc, subj, problem)
    _check_words(doc, subj, problem)
    doc.findings.sort(key=lambda f: (0 if f["level"] == "ERROR" else 1, f["line"], f["id"]))
    return doc.findings


def _collapse(doc, rid):
    hits = [f for f in doc.findings if f["id"] == rid]
    if len(hits) > 1:
        first = hits[0]
        first["message"] += "（ほか {} か所）".format(len(hits) - 1)
        doc.findings = [f for f in doc.findings if f["id"] != rid or f is first]


def _check_commands(doc, subj):
    seen = set()
    for rid, level, subjects, pattern, msg, ref in RULES:
        if subj not in subjects:
            continue
        for m in re.finditer(pattern, doc.clean):
            ln = doc.line_of(m.start())
            if (rid, ln) in seen:
                continue
            if rid == "cond-prob" and not _offset_in_math(doc, m.start()):
                continue
            seen.add((rid, ln))
            doc.findings.append({"level": level, "id": rid, "line": ln, "message": msg, "ref": ref,
                                 "excerpt": m.group(0)})


def _offset_in_math(doc, off):
    return any(s <= off < e for s, e, _k, _b in doc.segments)


def _check_math(doc, subj):
    seen = set()

    def add(rid, ln, ex):
        if (rid, ln) in seen:
            return
        seen.add((rid, ln))
        level, subjects, msg, ref = MATH_RULES[rid]
        if subj in subjects:
            doc.findings.append({"level": level, "id": rid, "line": ln, "message": msg, "ref": ref, "excerpt": _one_line(ex)})

    for s, _e, kind, body in doc.segments:
        off = s + (1 if kind == "inline" else 2)
        for m in re.finditer(r"\\frac(?![A-Za-z])", body):
            if not _in_script(body, m.start()):
                add("frac", doc.line_of(off + m.start()), body[m.start():m.start() + 30])
        for m in re.finditer("[" + CIRCLED + "]", body):
            add("circled-in-math", doc.line_of(off + m.start()), body)
        line_no = doc.line_of(s)
        if kind == "inline" and _line_text(doc, line_no).lstrip().startswith("|"):
            if re.search(r"(?<!\\)\|", body):
                add("table-pipe", line_no, body)
        for m in re.finditer(r"\\text\s*\{([^{}]*)\}", body):
            content = m.group(1).strip()
            ln = doc.line_of(off + m.start())
            if re.fullmatch(r"[ァ-ヶ]{1,2}", content):
                add("text-blank", ln, m.group(0))
            elif re.fullmatch(r"(?:" + UNITS + r")(?:\^\{?-?\d\}?)?", content):
                add("text-unit", ln, m.group(0))
            elif len(content) >= 8 or re.search(r"[。、，．]", content):
                add("text-long", ln, m.group(0))
        if kind == "inline" and re.search(r"\\(?:lim|sum|int)(?![A-Za-z])", body) and "\\displaystyle" not in body:
            # 指数・添字の中だけにあるものは除く
            m = re.search(r"\\(?:lim|sum|int)(?![A-Za-z])", body)
            if not _in_script(body, m.start()):
                add("displaystyle", line_no, body)
        if subj == "physics":
            for m in re.finditer(r"(\d)(\\[ ,;:!]|\\quad|~|\s+)?\s*(?!\\mathrm|\\Omega|\\mu|\\times|\\cdot)((?:" + UNITS + r"))(?![A-Za-z])",
                                 body):
                sep, unit = m.group(2), m.group(3)
                ln = doc.line_of(off + m.start())
                before = body[:m.start() + 1]
                if re.search(r"[A-Za-z_^]\{?\d$", before) or re.search(r"\\[a-zA-Z]+\{?\d$", before):
                    continue  # 添字・指数の中の数（v_{1}，10^{2}）
                if sep is None:
                    continue  # 2m のような積は判定しない
                if UNIT_MULTI.match(unit) or "/" in unit:
                    add("unit-italic", ln, m.group(0))
                elif sep.startswith("\\") or sep == "~":
                    add("unit-italic", ln, m.group(0))
                else:
                    add("unit-maybe", ln, m.group(0))
            for m in re.finditer(r"(?:\d|\})\\mathrm\s*\{\s*(" + UNITS + r")(?![A-Za-z])", body):
                pre = body[:m.start() + 1]
                if pre.endswith("}") and re.search(r"(?:_|\{\})\{[^{}]*\}$", pre):
                    continue  # 添字の後（v_{\mathrm{A}}）や {}^{4}_{2}\mathrm{He}
                add("unit-nospace", doc.line_of(off + m.start()), m.group(0))


def _check_lines(doc, subj, problem):
    lines = doc.lines
    nlines = len(lines)
    answer_lines = [i + 1 for i, l in enumerate(lines) if ANSWER_RE.match(l)]
    sep_after = None
    if answer_lines:
        for i in range(answer_lines[-1], nlines):
            if re.match(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", lines[i]):
                sep_after = i + 1
                break
    body_end = (sep_after - 1) if sep_after else nlines

    # **答**
    if not answer_lines:
        if any("（証明終）" in l or "(証明終)" in l for l in lines):
            doc.add("answer-missing-proof" if subj == "math" else "answer-missing", 1, "")
        else:
            doc.add("answer-missing", 1, "")
    for i, l in enumerate(lines[:body_end], 1):
        if re.search(r"\*\*\s*答\s*\*\*", l) and not ANSWER_RE.match(l) and i not in doc.display_lines:
            doc.add("answer-inline", i, l)
    if answer_lines:
        last = answer_lines[-1]
        bare = not ANSWER_RE.sub("", lines[last - 1]).strip()
        for i in range(last, body_end):
            l = lines[i].strip()
            if not l:
                continue
            if bare and "。" not in _prose(doc, i + 1) and not re.match(r"^[（(]?\s*(?:確認|検算|補足|注|※|参考)", l):
                continue  # 「**答**」だけの行の後に並べた答（場合分けの答など）
            if re.match(r"^[（(]?\s*(?:確認|検算|補足|注|※|参考)", l):
                doc.add("after-answer-check", i + 1, l)
            else:
                doc.add("after-answer", i + 1, l)
            break
    if not any(re.match(r"^\s*\*\*\s*解答\s*\*\*\s*$", l) for l in lines[:body_end]):
        doc.add("kaitou-missing", 1, "")

    # 行ごと
    eq_series = {}
    blocks, current = [], {"numbered": [], "displays": []}
    for i, l in enumerate(lines[:body_end], 1):
        if i in doc.display_lines and not l.lstrip().startswith("$$"):
            continue
        if re.match(r"^\s{0,3}(?:[-*+]|\d+\.)\s+\S", l) and not re.match(r"^\s*(?:-{3,}|\*{3,})\s*$", l):
            doc.add("bullet", i, l)
        if re.match(r"^\s*(?:#{1,6}\s*|\*\*|【|［|\[)?\s*" + SECTION_WORDS + r"\s*(?:\*\*|】|］|\])?\s*[:：]?\s*(?:\*\*)?\s*$", l) \
                or re.match(r"^\s*(?:\*\*|【)?" + SECTION_WORDS + r"(?:\*\*|】)?\s*[:：]", l):
            doc.add("sections", i, l)
        # 導出の区切り（小問・場合分けの見出し）：### …，**(1)**，(1)，［前半］，[1]，(i)
        if re.match(r"^\s*(?:#{1,6}\s|(?:\*\*)?\s*[（(]\d+[)）]|(?:\*\*)?\s*[\[［【][^\]］】]{1,8}[\]］】]|[（(](?:i|ii|iii|iv|v)[)）])", l):
            blocks.append(current)
            current = {"numbered": [], "displays": []}
        _check_eqno_line(doc, i, l, eq_series, current)
        if l.lstrip().startswith("$$"):
            # 1行の $$ 式（aligned・cases を含まない）
            seg = next((sg for sg in doc.segments if sg[2] == "display" and doc.line_of(sg[0]) == i), None)
            if seg and not re.search(r"\\begin\{(?:aligned|cases|array|gathered|split)\}", seg[3]):
                current["displays"].append(i)
        prose = _prose(doc, i)
        for pat, rid in MEMO:
            if re.search(pat, prose):
                doc.add(rid, i, l)
                break
        if re.search(r"(?:です|ます|ました|ません|でした|ましょう)(?:[。，、）)]|$)", prose):
            doc.add("desu-masu", i, l)
        if re.search(r"であればよい|ならばよい|であれば十分", prose) and subj == "math":
            doc.add("sufficient", i, l)
        if re.search(r"自明|明らか", prose):
            doc.add("obvious", i, l)
        if re.search(r"(?:\\equiv|\\pmod)", l) and subj == "math":
            doc.add("congruence", i, l)
        for m in re.finditer(r"!\[([^\]]*)\]\(", l):
            alt = m.group(1)
            if re.search(r"[<$|\\]", alt):
                doc.add("alt-text", i, alt)
    blocks.append(current)
    for b in blocks:
        if b["numbered"] and b["displays"]:
            doc.add("eqno-display-mix", b["displays"][0], _line_text(doc, b["displays"][0]))
    if len(eq_series) > 1:
        first = min(eq_series.values())
        doc.add("eqno-mixed", first, "系列: " + "，".join(sorted(eq_series)))
    touten = [i for i, l in enumerate(lines[:body_end], 1) if "、" in _prose(doc, i)]
    if touten:
        doc.add("touten", touten[0], "「、」が {} 行".format(len(touten)))
    _collapse(doc, "desu-masu")
    _collapse(doc, "bullet")
    if problem:
        if re.search("[" + CIRCLED + "]", problem) and "circled" in eq_series:
            doc.add("eqno-problem", eq_series["circled"], _line_text(doc, eq_series["circled"]))
        if re.search(r"図\s*\d|下の図|右の図|左の図|上の図|図のように", problem):
            for i, l in enumerate(lines[:body_end], 1):
                if re.search(r"!\[図\s*\d", l) or re.search(r"(?<![解の])図\s*[0-9０-９]", _prose(doc, i)):
                    doc.add("fig-number", i, l)
                    break


def _prose(doc, ln):
    """行の地の文（数式とコードを除いたもの）。"""
    return doc.prose_lines[ln - 1] if 0 < ln <= len(doc.prose_lines) else ""


def _check_eqno_line(doc, i, l, series, block):
    prose = _prose(doc, i).rstrip()
    m = re.search(r"(?:……|…|\.\.\.|\s|　)(" + EQNO + r")\s*$", prose)
    if not m or "$" not in l:
        return
    if re.match(r"^\s*\*\*\s*答", l):
        return
    marker = m.group(1)
    if not re.search(r"\$\s*(?:\\quad|\\qquad|[ 　…\.])*\s*" + re.escape(marker) + r"\s*$", l) and "……" not in l:
        return
    if re.fullmatch(r"\(\d+\)", marker):
        doc.add("eqno-paren-digit", i, l)
        return
    kind = ("circled" if marker in CIRCLED else "roman" if re.fullmatch(r"\([ivx]+\)", marker)
            else "latin" if re.fullmatch(r"\([a-z]\)", marker) else "capital")
    series.setdefault(kind, i)
    block["numbered"].append(i)
    # 「　$式$　すなわち　$式$　……②」のように，式の間に短い語をはさむ形は正本の見本にあるので認める
    if not re.fullmatch(r"　\$[^$]+\$(?:[^$]*\$[^$]+\$)*　……" + re.escape(marker), l.rstrip()):
        doc.add("eqno-format", i, l)


def _check_words(doc, subj, problem):
    prose_all = doc.math_mask
    seen = set()
    for pattern, level, subjects, fix, ref in WORDS:
        if subj not in subjects:
            continue
        for m in re.finditer(pattern, prose_all):
            word = m.group(0)
            if problem and re.search(pattern, problem):
                continue  # 問題文の用語・問題文が与えた定義に合わせたもの
            ln = doc.line_of(m.start())
            if (pattern, ln) in seen:
                continue
            seen.add((pattern, ln))
            doc.findings.append({"level": level, "id": "scope-word", "line": ln,
                                 "message": "「{}」は範囲外・教科書にない語。{}".format(word, fix), "ref": ref,
                                 "excerpt": _line_text(doc, ln)})


# ---------------------------------------------------------------------------------------------
# 図（svg-figures の lint_svg.py を呼ぶ）
# ---------------------------------------------------------------------------------------------
def svg_lint_path():
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.normpath(os.path.join(here, "..", "..", "svg-figures", "scripts", "lint_svg.py"))
    return cand if os.path.isfile(cand) else None


def check_figures(text, base_dir):
    """答案が参照する .svg を lint_svg.py にかける。戻り値は (findings, 実行したか, 説明)。"""
    paths = re.findall(r"!\[[^\]]*\]\(\s*<?([^)\s>]+\.svg)>?\s*\)", _mask_code(text))
    if not paths:
        return [], None, "図なし"
    tool = svg_lint_path()
    findings, ran = [], False
    for rel in dict.fromkeys(paths):
        full = rel if os.path.isabs(rel) else os.path.join(base_dir, rel)
        if not os.path.isfile(full):
            findings.append({"level": "WARN", "id": "svg-missing", "line": 0, "message": FORM_RULES["svg-missing"][2],
                             "ref": FORM_RULES["svg-missing"][3], "excerpt": rel})
            continue
        if tool is None:
            continue
        ran = True
        try:
            proc = subprocess.run([sys.executable, "-B", "-E", "-s", tool, "--display-width=650", full],
                                  capture_output=True, text=True, timeout=60)
            out = proc.stdout
        except (OSError, subprocess.SubprocessError) as exc:
            out = "{}: ERROR lint_svg.py を実行できない（{}）".format(full, exc)
        for line in out.splitlines():
            mm = re.match(r"^.*?: (ERROR|WARN)\s+(.*)$", line)
            if mm:
                findings.append({"level": mm.group(1), "id": "svg", "line": 0, "message": mm.group(2),
                                 "ref": (SV, "ERROR は直し，WARN は該当箇所を目で見て判断する。"), "excerpt": rel})
    if tool is None:
        return findings, False, "svg-figures の lint_svg.py が見つからないので，図の検査は実行していない"
    return findings, ran, "lint_svg.py を実行した" if ran else "図のファイルがないので lint_svg.py は実行していない"


# ---------------------------------------------------------------------------------------------
# 入出力・記録
# ---------------------------------------------------------------------------------------------
def read_input(path):
    if path == "-":
        data = sys.stdin.buffer.read()
    else:
        with open(path, "rb") as handle:
            data = handle.read()
    text = data.decode("utf-8-sig", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def text_hash(text):
    body = text.rstrip()
    body = body + "\n" if body else ""
    return hashlib.sha256(body.encode("utf-8", "surrogatepass")).hexdigest()


def state_dir(option=None):
    if option:
        return os.path.abspath(option)
    env = os.environ.get("HS_CHECK_STATE_DIR")
    if env and env.strip() and "${" not in env:
        return os.path.abspath(env)
    cwd = os.path.abspath(os.getcwd())
    cur = cwd
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return os.path.join(cur, ".hs-check")
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.join(cwd, ".hs-check")
        cur = parent


def load_state(folder):
    try:
        with open(os.path.join(folder, "state.json"), encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict) and isinstance(data.get("entries"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"version": 1, "entries": {}}


def save_state(folder, data):
    os.makedirs(folder, exist_ok=True)
    ignore = os.path.join(folder, ".gitignore")
    if not os.path.lexists(ignore):
        with open(ignore, "w", encoding="utf-8") as handle:
            handle.write("# hs_check.py の検査記録。git に入れない。\n*\n")
    tmp = os.path.join(folder, "state.json.tmp{}".format(os.getpid()))
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(folder, "state.json"))


def input_key(path):
    return "stdin" if path == "-" else os.path.realpath(path)


def counts(findings):
    e = sum(1 for f in findings if f["level"] == "ERROR")
    return e, len(findings) - e


def format_findings(findings, per_id=5):
    """1つの検査で出す行は per_id 件まで（件数の数え方は変えない）。"""
    out, shown, hidden = [], {}, {}
    for f in findings:
        key = (f["level"], f["id"])
        shown[key] = shown.get(key, 0) + 1
        if per_id and shown[key] > per_id:
            hidden[key] = hidden.get(key, 0) + 1
            continue
        where = "{}行".format(f["line"]) if f["line"] else "図"
        ref = f["ref"]
        refs = "（{}）".format(_short(ref[0])) if ref else ""
        ex = " ｜ " + f["excerpt"] if f["excerpt"] else ""
        out.append("{:<5} {:>4} [{}] {}{}{}".format(f["level"], where, f["id"], f["message"], refs, _one_line(ex, 70)))
    for (level, rid), n in hidden.items():
        out.append("{:<5}      [{}] 同じ検査の候補がほかに {} 件（同じ直し方で直す）".format(level, rid, n))
    return out


def _short(path):
    return path.replace("high-school-math-answers/", "math:").replace("high-school-physics-answers/", "physics:")


def cmd_lint(args):
    text = read_input(args.file)
    problem = read_input(args.problem) if args.problem else None
    findings = lint_text(text, args.subject, problem, args.format)
    e, w = counts(findings)
    print("hs_check lint（{}）：ERROR {} 件・WARN {} 件。{}".format(args.subject, e, w, DISCLAIMER))
    for line in format_findings(findings):
        print(line)
    return 1 if e else 0


def cmd_run(args):
    text = read_input(args.final)
    problem = read_input(args.problem) if args.problem else None
    findings = lint_text(text, args.subject, problem, args.format)
    base = os.getcwd() if args.final == "-" else os.path.dirname(os.path.abspath(args.final))
    if args.figdir:
        base = os.path.abspath(args.figdir)
    fig_findings, fig_ran, fig_note = check_figures(text, base)
    findings += fig_findings
    e, w = counts(findings)
    digest = text_hash(text)
    folder = state_dir(args.state_dir)
    state = load_state(folder)
    key = input_key(args.final)
    entry = state["entries"].get(key) or {"runs": []}
    pdigest = text_hash(problem) if problem is not None else None
    runs = entry["runs"]
    if args.new or (runs and runs[-1].get("problem_sha256") != pdigest) or (runs and runs[-1].get("subject") != args.subject):
        runs = []
    same = bool(runs) and runs[-1]["sha256"] == digest
    attempt = len([r for r in runs if not r.get("same")]) + (0 if same else 1)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = {"time": now, "sha256": digest, "subject": args.subject, "errors": e, "warns": w,
              "problem_sha256": pdigest, "figures": fig_note, "same": same, "attempt": attempt,
              "findings": [{k: f[k] for k in ("level", "id", "line", "message")} for f in findings],
              "tool": "hs_check.py " + __version__}
    runs.append(record)
    entry["runs"] = runs[-20:]
    state["entries"][key] = entry
    written = True
    try:
        save_state(folder, state)
    except OSError as exc:
        written = False
        fig_note += "。記録を書けなかった（{}）".format(exc)
    tally = "ERROR {} 件・WARN {} 件".format(e, w)
    if not written:
        head = "検査を実行しましたが，記録を書けませんでした：{}。--state-dir に書ける場所を指定して run をやり直してください。".format(tally)
    elif same:
        head = "検査を実行しました（前回と同じ最終稿）：{}。本文を変えずに，提出の直前に verify を実行してください。".format(tally)
    elif attempt == 1 and (e or w):
        head = ("検査を実行しました（1回目）：{}。候補を1つずつ答案と規則に照らし，当たっているものだけを1回でまとめて直し"
                "（検査を消すためだけの言い換えはしない），run をもう一度実行してください。").format(tally)
    elif attempt == 1:
        head = "検査を実行しました（1回目）：{}。本文を変えずに，提出の直前に verify を実行してください。".format(tally)
    elif attempt == 2:
        head = ("検査を実行しました（修正後の2回目）：{}。本文はもう変えず，提出の直前に verify を実行してください。"
                "残った候補は，残した理由とともに報告します。").format(tally)
    else:
        head = ("検査を実行しました（{}回目）：{}。修正は1回までの決まりを超えています（このコマンドは止めません）。"
                "本文はもう変えず，verify を実行してください。").format(attempt, tally)
    print(head)
    print(DISCLAIMER)
    print("図：" + fig_note)
    for line in format_findings(findings):
        print(line)
    if written:
        print("記録：{}（sha256:{}）".format(os.path.join(folder, "state.json"), digest[:12]))
    return 0 if written else 2


def cmd_verify(args):
    text = read_input(args.final)
    digest = text_hash(text)
    state = load_state(state_dir(args.state_dir))
    key = input_key(args.final)
    entry = state["entries"].get(key)
    latest = entry["runs"][-1] if entry and entry.get("runs") else None
    if latest is None or latest["sha256"] != digest:
        # 別の入力（ファイルで run し，標準入力で verify したときなど）の最後の記録と合うか
        others = [(e["runs"][-1], k) for k, e in state["entries"].items() if e.get("runs") and k != key]
        others = [o for o in others if o[0]["sha256"] == digest]
        if latest is None and others:
            latest = max(others, key=lambda o: o[0]["time"])[0]
        elif latest is None:
            print("照合できません：この最終稿を検査した run の記録がありません。run を実行してから verify してください。")
            return 1
        else:
            print("最終稿が最後の run の記録と違います（記録 sha256:{}，今 sha256:{}）。本文を変えたなら run をやり直し，"
                  "そのあと本文を変えずに verify してください。".format(latest["sha256"][:12], digest[:12]))
            return 1
    rest = "ERROR {} 件・WARN {} 件".format(latest["errors"], latest["warns"])
    print("照合しました：最終稿のハッシュが最後の run の記録と合いました（{}，{}回目の run，{}）。".format(
        rest, latest.get("attempt", "?"), latest["time"]))
    print("この照合は検査を実行した本文と同じであることを示すだけで，答案の正しさの合格を示すものではありません。")
    if latest["errors"]:
        print("ERROR が残った記録です。残した理由を報告してください。")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hs_check.py", description="高校数学・物理の答案の機械検査と記録。" + DISCLAIMER)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    def common(p):
        p.add_argument("--subject", choices=("math", "physics"), required=True, help="科目")
        p.add_argument("--problem", help="問題文のファイル（問題文の用語・番号・図との照合に使う）")
        p.add_argument("--format", choices=("md", "other"), default="md",
                       help="md（既定。Markdown＋$）/ other（呼び出し側が別の形式を指定したとき。Markdown の検査を省く）")

    p_lint = sub.add_parser("lint", help="答案を検査する（記録しない）")
    common(p_lint)
    p_lint.add_argument("file", help="答案の Markdown（- で標準入力）")
    p_run = sub.add_parser("run", help="lint をまとめて実行し，最終稿のハッシュと結果を記録する")
    common(p_run)
    p_run.add_argument("--final", required=True, help="最終稿（- で標準入力）")
    p_run.add_argument("--figdir", help="図のファイルを探すフォルダ（既定は最終稿のフォルダ，標準入力なら作業ディレクトリ）")
    p_run.add_argument("--state-dir", help="記録のフォルダ（既定は git の最上位か作業ディレクトリの .hs-check/）")
    p_run.add_argument("--new", action="store_true", help="同じファイルで別の答案を書き始めたとき，回数を数え直す")
    p_verify = sub.add_parser("verify", help="最終稿が最後の run の記録と同じかを照らす（読むだけ）")
    p_verify.add_argument("--final", required=True, help="提出する最終稿（- で標準入力）")
    p_verify.add_argument("--state-dir", help="記録のフォルダ")
    args = parser.parse_args(argv)
    if args.command == "lint":
        return cmd_lint(args)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "verify":
        return cmd_verify(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
