#!/usr/bin/env python3
"""hs_check.py - 高校数学・物理の答案（Markdown＋LaTeX）の機械検査と，検査の記録。

標準ライブラリだけで動く（Python 3.9 以上）。モデルは呼ばない。外へ通信しない。__pycache__ を作らない。

  lint    答案を検査し，ERROR / WARN を行番号つきで出す（何も書かない）。
  run     lint をまとめて実行し（答案が参照する SVG 図があれば svg-figures の lint_svg.py も），
          最終稿のハッシュと結果を状態フォルダ（既定は git の最上位か作業ディレクトリの .hs-check/）に記録する。
  verify  最終稿が最後の run の記録と同じ本文かを照らす（読むだけ）。

返す状態は「検査を実行した」であって，答案の正しさ（数学・物理として正しいか，範囲内の解き方か）の
合格ではない。確実に規則に反するものを ERROR，文脈で判断が要るもの（頼まれた別解，問題文の用語など）を WARN にする。

記号・命令・書式・範囲外の語のように機械的に判定できる規則は，このファイルが正本である（SKILL.md と
references には書かない）。各規則は「なぜだめか」と「何に直すか」を持ち，検査の出力の1行がそのまま
直し方の説明になる。

  rules   規則の一覧を Markdown で出す。references/check-rules.md はこの出力で作り
          （python3 hs_check.py rules --subject math > references/check-rules.md），Python が使えない環境で
          目で点検するときに読む。tests/test_hs_check.py が，生成した一覧が今の規則と同じであることを確かめる。

このファイルは high-school-math-answers/scripts/ と high-school-physics-answers/scripts/ に同じものを置く
（どちらのスキルも単独で配置できるように）。2つが同じであることもテストで確かめる。
"""
__version__ = "1.1.0"

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

SV = "svg-figures/SKILL.md"

BOTH = ("math", "physics")
MATH = ("math",)
PHYS = ("physics",)

# ---------------------------------------------------------------------------------------------
# 命令・記号の検査（本文全体。コードの中は見ない）
# ---------------------------------------------------------------------------------------------
_CMD = r"(?![A-Za-z])"
# (id, 水準, 科目, 正規表現, なぜだめか, 何に直すか)
RULES = [
    ("boxed", "ERROR", BOTH, r"\\boxed(?![A-Za-z])",
     "教科書の答案は答を枠で囲まず，答の行で示す", "\\boxed を外し，独立した行の「**答**　…」に書く"),
    ("ineq", "ERROR", BOTH, r"\\(?:le|ge|leq|geq|leqslant|geqslant)(?![A-Za-z])|[≤≥]",
     "教科書の不等号は ≦ ≧（\\le・≤ は大学・海外の書き方）", "不等号は \\leqq・\\geqq"),
    ("implies", "ERROR", BOTH, r"\\implies(?![A-Za-z])",
     "教科書の「ならば」は ⇒（\\implies は使わない）", "「ならば」は \\Rightarrow"),
    ("longrightarrow-if", "WARN", BOTH, r"\\Longrightarrow(?![A-Za-z])|⟹",
     "⟹ は教科書の「ならば」の記号でなく，式変形の矢印にも使わない", "「ならば」なら \\Rightarrow。式変形の矢印なら言葉（よって）でつなぐ"),
    ("iff", "WARN", MATH, r"\\(?:iff|Leftrightarrow|Longleftrightarrow)(?![A-Za-z])",
     "同値でない変形に ⇔ を書くと論理の誤りになる", "本当に同値なところだけに使い，ほかは「よって」でつなぐ"),
    ("forall-exists", "ERROR", BOTH, r"\\(?:forall|exists|nexists)(?![A-Za-z])|[∀∃]",
     "教科書にない記号（範囲外）", "「すべての…について」「…が存在する」と言葉で書く"),
    ("prod", "ERROR", BOTH, r"\\prod(?![A-Za-z])",
     "教科書にない記号（範囲外）", "積は書き並べる（$a_{1}a_{2}\\cdots a_{n}$，$n!$）"),
    ("binom", "ERROR", BOTH, r"\\[dt]?binom(?![A-Za-z])",
     "組合せの記号が教科書と違う", "組合せは {}_{n}\\mathrm{C}_{r}"),
    ("mathbb", "ERROR", BOTH, r"\\mathbb(?![A-Za-z])",
     "教科書にない記号（範囲外）", "「実数」などと言葉で書く"),
    ("logic", "ERROR", BOTH, r"\\(?:land|lor|lnot|neg|wedge|vee)(?![A-Za-z])",
     "教科書にない記号（範囲外）", "「かつ」「または」「…でない」"),
    ("langle", "ERROR", MATH, r"\\(?:langle|rangle)(?![A-Za-z])",
     "教科書にない記号（範囲外）", "内積は $\\vec{a}\\cdot\\vec{b}$"),
    ("Vert", "ERROR", MATH, r"\\Vert(?![A-Za-z])",
     "教科書にない記号（範囲外）", "ベクトルの大きさは絶対値記号（\\lvert \\rvert）"),
    ("bold-vector", "ERROR", BOTH, r"\\(?:mathbf|boldsymbol|bm)(?![A-Za-z])",
     "教科書のベクトルは矢印で書く", "ベクトルは \\vec{a}"),
    ("arc-trig", "ERROR", BOTH, r"\\arc(?:sin|cos|tan)(?![A-Za-z])|\\(?:sin|cos|tan)\s*\^\s*\{?\s*-\s*1",
     "逆三角関数は高校の範囲外", "角を文字でおく（「$\\tan\\alpha=2$ を満たす角 $\\alpha$」），積分は $x=\\tan\\theta$ などの置換積分"),
    ("hyperbolic", "ERROR", BOTH, r"\\(?:sinh|cosh|tanh|coth)(?![A-Za-z])",
     "双曲線関数は高校の範囲外", "$\\dfrac{e^{x}-e^{-x}}{2}$ をそのまま書く"),
    ("cot-sec-csc", "ERROR", BOTH, r"\\(?:cot|sec|csc)(?![A-Za-z])",
     "教科書にない記号（範囲外）", "$\\dfrac{1}{\\tan\\theta}$ などで書く"),
    ("ln", "ERROR", BOTH, r"\\ln(?![A-Za-z])",
     "教科書の自然対数は log（ln は使わない）", "自然対数は \\log"),
    ("exp", "ERROR", BOTH, r"\\exp(?![A-Za-z])",
     "教科書にない記号（範囲外）", "$e^{x}$ と書く"),
    ("floor-ceil", "ERROR", MATH, r"\\(?:lfloor|rfloor|lceil|rceil)(?![A-Za-z])",
     "教科書にない記号（範囲外）", "[x]（定義を添える），または言葉で書く"),
    ("partial-nabla", "ERROR", BOTH, r"\\(?:partial|nabla)(?![A-Za-z])",
     "偏微分・ナブラは高校の範囲外", "その解法ごと避ける（1文字を固定して考えるなど）"),
    ("landau", "ERROR", MATH, r"(?<![A-Za-z\\}])[oO]\s*\(\s*(?:[xhnt](?:\^\{?\d+\}?)?|1|\\d?frac\{1\}\{[nx]\})\s*\)",
     "ランダウの記号 o( )・O( ) は高校の範囲外（漸近展開に頼った論証になる）", "o( ) を使った展開をやめ，差をとった関数の増減・式変形・はさみうちの原理で示す"),
    ("complex-exp", "ERROR", BOTH, r"e\s*\^\s*\{\s*-?\s*i",
     "e^{iθ}（オイラーの公式）は高校の範囲外", "$e^{i\\theta}$ は使わず極形式（$\\cos\\theta+i\\sin\\theta$）"),
    ("nmid", "ERROR", MATH, r"\\nmid(?![A-Za-z])",
     "教科書にない記号（範囲外）", "「$b$ は $a$ の倍数」と言葉で書く"),
    ("gcd", "ERROR", MATH, r"\\(?:gcd|lcm)(?![A-Za-z])|\\mathrm\{lcm\}|\\operatorname\{lcm\}",
     "教科書にない記号（範囲外）", "「最大公約数」「最小公倍数」"),
    ("bmod", "ERROR", MATH, r"\\bmod(?![A-Za-z])",
     "教科書にない記号（範囲外）", "「$a$ を $b$ で割った余り」"),
    ("cond-prob", "ERROR", MATH, r"P\s*\(\s*[^()$]*?\\mid(?![A-Za-z])|P\s*\(\s*[A-Z]\s*\|\s*[A-Z]\s*\)",
     "条件付き確率の記号が教科書と違う", "条件付き確率は $P_{A}(B)$"),
    ("Pi-perm", "ERROR", MATH, r"\\Pi\s*_",
     "教科書にない記号（範囲外）", "重複順列は $n^{r}$"),
    ("max-min", "WARN", MATH, r"\\(?:max|min)(?![A-Za-z])",
     "max・min は教科書の本文の記号でない", "「最大値」「最小値」と言葉で書くか，意味を添える"),
    ("pmatrix", "ERROR", BOTH, r"\\begin\{[pbvBV]?matrix\}",
     "成分を縦に並べるのは行列の書き方で，高校のベクトルは横に並べる", "ベクトルの成分は $(a_{1},a_{2})$ と横に並べる"),
    ("mapsto", "ERROR", MATH, r"\\mapsto(?![A-Za-z])",
     "教科書にない記号（範囲外）", "「関数 $y=f(x)$」と書く"),
    ("approx", "ERROR", BOTH, r"\\(?:approx|simeq|sim)(?![A-Za-z])",
     "教科書の「ほぼ等しい」は ≒，分布は言葉で書く", "ほぼ等しいは \\fallingdotseq，分布は「…に従う」"),
    ("therefore", "ERROR", BOTH, r"\\(?:therefore|because)(?![A-Za-z])|[∴∵]",
     "∴ ∵ は答案の文でなく記号でつなぐことになる", "「よって」「…であるから」"),
    ("qed-square", "ERROR", MATH, r"\\(?:square|blacksquare|Box|qed)(?![A-Za-z])|[□■∎]",
     "教科書にない記号（範囲外）", "「（証明終）」"),
    ("defeq", "ERROR", MATH, r"\\triangleq(?![A-Za-z])|(?<![<>!=]):=",
     "教科書にない記号（範囲外）", "「…とおく」「…と定める」"),
    ("words-en", "ERROR", MATH, r"(?<![\\A-Za-z])(?:s\.t\.|iff|Q\.E\.D\.?|QED|w\.l\.o\.g\.?)(?![A-Za-z])",
     "英語の略語は答案の言葉でない", "「…を満たす」「…と同値」「（証明終）」"),
    ("phi", "ERROR", BOTH, r"\\phi(?![A-Za-z])|ϕ",
     "教科書の φ は \\varphi の字形（図とも合わせる）", "φ は \\varphi"),
    ("env", "ERROR", BOTH, r"\\begin\{(?:align|equation|eqnarray|gather|multline|flalign)\*?\}",
     "KaTeX・MathJax で描画できないか崩れる", "複数行は $$\\begin{aligned}…\\end{aligned}$$"),
    ("tag-label", "ERROR", BOTH, r"\\(?:tag|label|ref|eqref)(?![A-Za-z])",
     "KaTeX・MathJax で描画できないか崩れる", "式番号は「　$式$　……①」の形で数式の外に書く"),
    ("macro-def", "ERROR", BOTH, r"\\(?:newcommand|renewcommand|def|DeclareMathOperator)(?![A-Za-z])",
     "KaTeX・MathJax で描画できないか崩れる", "命令を定義せず毎回そのまま書く"),
    ("custom-macro", "ERROR", BOTH, r"\\(?:nCr|nPr|C|vector)(?![A-Za-z])",
     "KaTeX・MathJax で描画できないか崩れる", "標準の命令で書く（{}_{n}\\mathrm{C}_{r}，\\vec{a}）"),
    ("tabular", "ERROR", BOTH, r"\\begin\{tabular\}",
     "KaTeX・MathJax で描画できないか崩れる", "Markdown の表か \\begin{array}"),
    ("textcircled", "ERROR", BOTH, r"\\textcircled(?![A-Za-z])",
     "KaTeX・MathJax で描画できないか崩れる", "丸数字は数式の外に ① と書く"),
    ("mbox", "WARN", BOTH, r"\\(?:mbox|hbox)(?![A-Za-z])",
     "数式の中の長い文は字体と改行が本文とずれる", "説明文は地の文に出す"),
    ("vec-subscript", "ERROR", BOTH, r"\\vec\s*\{\s*\\?[A-Za-z]+\s*_",
     "矢印が添字まで伸びて教科書の形と違う", "添字は矢印の外（\\vec{e}_1）"),
    ("prime-power", "ERROR", BOTH, r"(?<!\})'\s*\^",
     "V'^{2} は描画でエラーになる", "プライムつきの2乗は {V'}^{2}"),
    ("vec-cross", "ERROR", BOTH, r"\\vec\s*\{[^{}]*\}\s*(?:_\{?[^{}\s]*\}?)?\s*\\times\s*\\vec",
     "外積は高校の範囲外", "数学は内積が 0 の連立方程式，物理は大きさとフレミングの左手の法則"),
    ("si-units", "ERROR", PHYS, r"\\(?:si|SI|unit|degree|celsius|ohm)(?![A-Za-z])",
     "siunitx の命令は KaTeX・MathJax で描画できない", "単位は \\mathrm{}，^{\\circ}，{}^{\\circ}\\mathrm{C}，\\Omega"),
    ("dot-derivative", "ERROR", PHYS, r"\\d?dot\s*\{\s*\\?[A-Za-z]",
     "導関数の記号は高校物理の教科書にない", "速度・加速度は $v$，$a$ と文字でおく"),
    ("d-dt", "ERROR", PHYS, r"\\[dt]?frac\s*\{\s*d\s*\\?[A-Za-z]*[^{}]*\}\s*\{\s*d\s*\\?[A-Za-z]",
     "微分の記号は高校物理の教科書にない", "変化の割合は $\\dfrac{\\Delta x}{\\Delta t}$（グラフの傾き）。単振動は $a=-\\omega^{2}x$ の形で読む"),
    ("integral", "ERROR", PHYS, r"\\(?:i*int|oint)(?![A-Za-z])",
     "積分は高校物理の教科書の方法でない", "グラフの面積で書く（$v$-$t$ グラフの面積が変位，$F$-$x$ グラフの面積が仕事）"),
]

# 数式の中だけを見る検査（コードの中は見ない）。id: (水準, 科目, なぜだめか, 何に直すか)
MATH_RULES = {
    "frac": ("ERROR", BOTH, "\\frac は文中で小さく組まれ，教科書の分数の大きさと違う",
        "分数は \\dfrac（\\frac は指数・添字の中だけ）"),
    "circled-in-math": ("ERROR", BOTH, "丸数字は KaTeX のフォントに無く，数式の中では警告が出て位置がずれる",
        "丸数字・丸囲み文字は数式の外に書く（KaTeX が警告を出す）"),
    "table-pipe": ("ERROR", BOTH, "表の中の | は列の区切りと衝突して表が崩れる",
        "表の中の数式に縦線 | を書かない（\\lvert x\\rvert）"),
    "text-long": ("WARN", BOTH, "数式の中の文は字体と改行が本文とずれる",
        "\\text{} に入れてよいのは「かつ」「または」程度の短い語だけ"),
    "text-unit": ("WARN", BOTH, "\\text{} の単位は字体が本文と違う",
        "点の名前・単位は \\mathrm{}（\\text{} にしない）"),
    "text-blank": ("ERROR", PHYS, "空欄の記号は量でないので式に入れない",
        "空欄の記号を数式に入れない（「アは $mg\\sin\\theta$」と文で書く）"),
    "displaystyle": ("WARN", BOTH, "文中の lim・Σ・∫ は小さく組まれて読みにくい",
        "文中の \\lim・\\sum・\\int には \\displaystyle"),
    "unit-italic": ("ERROR", PHYS, "単位が斜体になり量記号と区別できない",
        "単位は立体で数値との間に空白1つ（3.0\\ \\mathrm{m/s}）"),
    "unit-nospace": ("ERROR", PHYS, "数値と単位がくっつく",
        "数値と単位の間は空白1つ（3.0\\ \\mathrm{m/s}）"),
    "unit-maybe": ("WARN", PHYS, "単位が斜体になり量記号と区別できない",
        "1文字の単位なら \\mathrm{}（量記号との積なら問題ない）"),
}

# 形式・構成の検査。id: (水準, 科目, なぜだめか, 何に直すか)
FORM_RULES = {
    "dollar-unclosed": ("ERROR", BOTH, "$ が閉じていないと以降の本文が数式として崩れる",
        "$ の対応がとれていない（閉じ忘れ，または段落をまたいでいる）"),
    "display-blank": ("ERROR", BOTH, "$$ の中の空行で数式が切れて描画されない",
        "$$ の中に空行を入れない"),
    "paren-delim": ("ERROR", BOTH, "この答案の数式の区切りは $ に決めている（\\( \\) は環境によって描画されない）",
        "数式の区切りは $…$・$$…$$（\\( \\) と \\[ \\] は使わない）"),
    "code-wrap": ("ERROR", BOTH, "コードブロックの中では数式が描画されない",
        "全体をコードブロックで囲まない（数式が描画されなくなる）"),
    "bullet": ("ERROR", BOTH, "箇条書きは答案の文章でなく，推論のつながりが切れる",
        "解答本体に Markdown の箇条書きを使わない（文でつなぐか (i)(ii)・[1][2] で区切る）"),
    "answer-missing": ("ERROR", BOTH, "答案は独立した「**答**」の行で閉じる決まり",
        "独立した行の「**答**　…」がない"),
    "answer-missing-proof": ("WARN", MATH, "答案は「**答**」の行か（証明終）で閉じる決まり",
        "「**答**」の行がない（証明だけの問題でも，結論を **答** に書くか確かめる）"),
    "answer-inline": ("WARN", BOTH, "答が本文に埋もれて採点者が見つけにくい",
        "**答** が行の途中にある（独立した行にする）"),
    "after-answer-check": ("ERROR", BOTH, "答案は **答** で閉じ，検算や補足は載せない",
        "**答** の後の確認・検算・補足を消す"),
    "after-answer": ("WARN", BOTH, "答案は **答** で閉じる決まり",
        "最後の **答** の後の本文を消す（利用者への連絡なら --- で区切る）"),
    "kaitou-missing": ("WARN", BOTH, "答案は「**解答**」で始める決まり",
        "「**解答**」の行がない（既存の書式に合わせたのなら問題ない）"),
    "sections": ("WARN", BOTH, "求められない限り解答と答だけを書く決まり",
        "頼まれていない方針・解説・別解・参考は書かない（頼まれたなら問題ない）"),
    "eqno-format": ("ERROR", BOTH, "式番号の書式は1通りに決めている（丸数字を数式の外に置くため）",
        "式番号の書式は「　$式$　……①」（行頭に全角空白，文中数式，全角空白，「……」，番号）"),
    "eqno-paren-digit": ("ERROR", BOTH, "(1)(2) は小問の番号と紛れる",
        "式番号に (1)(2) を使わない（小問番号と紛れる）"),
    "eqno-mixed": ("WARN", BOTH, "1題の中で番号の系列が変わると参照が紛らわしい",
        "式番号の系列が1題の中で混ざっている"),
    "eqno-display-mix": ("WARN", BOTH, "番号つきの式だけ字下げで前後が中央寄せだと見た目がそろわない",
        "番号つきの式がある導出では，1行の式も「　$式$」の字下げにそろえる（$$ は複数行の aligned・cases だけ）"),
    "eqno-problem": ("WARN", BOTH, "問題文の番号と式番号が衝突する",
        "問題文に丸数字がある。選択肢・空欄・条件の番号なら式番号は (a)(b)… にする"),
    "memo": ("ERROR", BOTH, "検算は出力前に自分ですることで，答案の本文ではない",
        "検算・確認・作業メモを本文から消す（同値でない変形の後の確かめは答案の論理として書く）"),
    "memo-file": ("ERROR", BOTH, "作業の報告は答案の本文ではない",
        "図の保存・ファイル名・描画の確認などの作業メモを本文に書かない"),
    "memo-scope": ("ERROR", BOTH, "範囲外の方法は断っても書かない（名前だけの紹介もしない）",
        "その方法と断り書きを消し，範囲内の方法だけで書く"),
    "desu-masu": ("WARN", BOTH, "答案は「である」体",
        "文体は「である」体（指定があれば従う）。です・ます は利用者への連絡が混ざっていないかも確かめる"),
    "touten": ("WARN", BOTH, "教科書の句読点は「，」「。」",
        "句読点は「，」「。」（指定があれば従う）"),
    "alt-text": ("ERROR", BOTH, "代替テキストの記号は描画で崩れる",
        "画像の代替テキストは図の名前だけの平文（< $ | 式を入れない）"),
    "fig-number": ("WARN", BOTH, "問題の図と解答の図の番号が衝突する",
        "問題に図があるときは解答の図を「解図1」，問題の図を「問題の図1」と書く"),
    "congruence": ("WARN", MATH, "合同式は発展事項で，断りなく使うと範囲外",
        "合同式は発展。使うなら定義を書いてから（割った余りで分類する書き方が原則）"),
    "sufficient": ("WARN", MATH, "「〜であればよい」は十分条件しか示さない",
        "条件を求める問題では「〜となるための条件は」と書く"),
    "obvious": ("WARN", BOTH, "「自明」「明らか」は理由にならない",
        "根拠を書く"),
    "svg-missing": ("WARN", BOTH, "参照した図が無い",
        "答案が参照する SVG 図が見つからない"),
}

# ---------------------------------------------------------------------------------------------
# 範囲外の方法・用語（数式の外の地の文）。問題文（--problem）にある語は，問題文に合わせたものとして出さない
# (語の正規表現, 水準, 科目, なぜだめか, 何に直すか)
# ---------------------------------------------------------------------------------------------
WORDS = [
    (r"ロピタル", "ERROR", BOTH, "高校の教科書にない定理・解法（範囲外）",
     "式変形（約分・有理化・$\\dfrac{\\sin x}{x}$ の形を作る），はさみうちの原理，微分係数の定義で求める（$\\dfrac{\\sin x}{x}$ に使うのは循環論法）"),
    (r"テイラー(?:展開|の定理)?|マクローリン", "ERROR", BOTH, "高校の教科書にない定理・解法（範囲外）",
     "不等式は差をとった関数の増減（何回か微分する）で示し，極限は式変形・はさみうちの原理・微分係数の定義で求める"),
    (r"-\s*論法|[εδ]\s*-\s*[δN]\s*論法|イプシロン.?デルタ", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "「限りなく近づく」とはさみうちの原理"),
    (r"単調で有界", "WARN", MATH, "高校の教科書にない定理・解法（範囲外）",
     "極限値の候補 $\\alpha$ を求め，$\\lvert a_{n+1}-\\alpha\\rvert\\leqq r\\lvert a_{n}-\\alpha\\rvert$（$0<r<1$）を示してはさみうちの原理で結論する"),
    (r"外積", "ERROR", BOTH, "高校の教科書にない定理・解法（範囲外）",
     "数学は求めるベクトルを $(x,y,z)$ とおき内積が 0 の連立方程式を解く（面積は $\\dfrac{1}{2}\\sqrt{\\lvert\\vec{a}\\rvert^{2}\\lvert\\vec{b}\\rvert^{2}-(\\vec{a}\\cdot\\vec{b})^{2}}$）。物理は大きさとフレミングの左手の法則"),
    (r"行列式|逆行列|固有値|固有ベクトル|[1一]次変換", "ERROR", BOTH, "高校の教科書にない定理・解法（範囲外）",
     "連立方程式・加法定理・複素数平面"),
    (r"斜交座標", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "$s$，$t$ の条件として存在範囲を述べる"),
    (r"点と平面の距離|平面の方程式", "WARN", MATH, "教科書の本文にない（発展）",
     "発展扱い。垂線の足を垂直条件から求める"),
    (r"フェルマーの小定理|オイラーの定理", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "累乗の余りの周期を具体的に計算するか，二項定理で $(7+1)^{n}$ のように展開する"),
    (r"中国(?:式)?剰余定理", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "一方の条件を $n=3k+2$ と表して他方に代入し，1次不定方程式として解く"),
    (r"イェンセン|ジェンセン", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "相加平均と相乗平均の大小関係，差をとって微分"),
    (r"コーシー.?シュワル[ツッ]|シュワル[ツッ]の不等式", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "（左辺）$-$（右辺）を平方の和に変形して示す（内積の $\\lvert\\vec{a}\\cdot\\vec{b}\\rvert\\leqq\\lvert\\vec{a}\\rvert\\lvert\\vec{b}\\rvert$ から導いてもよい）"),
    (r"並べ替えの不等式|チェビシェフ", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "差をとって因数分解する"),
    (r"ラグランジュの未定乗数", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "条件式で1文字を消す，$x+y=k$ とおいて共有点をもつ条件にする，相加平均と相乗平均の大小関係，三角関数で置き換える"),
    (r"偏微分|重積分", "ERROR", BOTH, "高校の教科書にない定理・解法（範囲外）",
     "2変数は1つの文字を固定して他方の関数とみる（予選決勝法）。体積は断面積を積分する"),
    (r"パップス|ギュルダン", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "回転体の体積は $\\pi\\displaystyle\\int_{a}^{b}y^{2}\\,dx$ で計算する"),
    (r"バウムクーヘン", "WARN", MATH, "教科書の本文にない（発展）",
     "教科書の本文にない。$x$ を $y$ で表して $\\pi\\displaystyle\\int x^{2}\\,dy$ を計算するか置換積分する。使うなら導出を書く"),
    (r"傘型分割", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "軸に垂直な断面で積分する"),
    (r"逆三角関数", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "$x=\\tan\\theta$，$x=a\\sin\\theta$ とおく置換積分。角は「$\\tan\\alpha=2$ を満たす角 $\\alpha$」と定める"),
    (r"双曲線関数", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "$\\dfrac{e^{x}+e^{-x}}{2}$ をそのまま書く"),
    (r"オイラーの公式", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "極形式とド・モアブルの定理"),
    (r"微分方程式", "WARN", MATH, "発展事項（範囲外）",
     "発展扱い。問題が誘導していない限り使わない"),
    (r"微分方程式", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "運動方程式を $a=-\\omega^{2}x$ の形に直して角振動数 $\\omega$ の単振動と読み，周期は $T=\\dfrac{2\\pi}{\\omega}$"),
    (r"広義積分", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "$\\displaystyle\\lim_{t\\to\\infty}\\int_{1}^{t}f(x)\\,dx$ と定積分の極限として書く"),
    (r"ガンマ関数|ベータ関数|ウォリス", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "部分積分で漸化式を作る"),
    (r"トレミー|スチュワートの定理", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "余弦定理，円に内接する四角形の性質"),
    (r"包絡線", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "文字についての方程式が実数解をもつ条件（逆像法），または1文字を固定して値域を調べる（順像法）"),
    (r"ベイズ", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "条件付き確率の定義と乗法定理"),
    (r"不偏分散|\$?t\$?\s*分布|\$?p\$?\s*値", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "分散は $n$ で割る。検定は標準正規分布の棄却域"),
    (r"カタラン数|完全順列|スターリング数", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "数え上げるか漸化式を立てる"),
    (r"生成関数|母関数", "ERROR", MATH, "高校の教科書にない定理・解法（範囲外）",
     "漸化式，二項定理"),
    (r"ロルの定理", "WARN", MATH, "教科書により扱いが違う",
     "平均値の定理で書く"),
    (r"合同式", "WARN", MATH, "発展事項で，断りなく使うと範囲外",
     "発展。定義を書いてから使う"),
    (r"多項式", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "整式"),
    (r"線[形型]", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "1次（1次結合は「$s\\vec{a}+t\\vec{b}$ の形」）"),
    (r"ノルム", "ERROR", BOTH, "大学の用語で，教科書の言葉ではない",
     "大きさ"),
    (r"スカラー", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "実数"),
    (r"直交(?!座標)", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "垂直"),
    (r"正規化", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "同じ向きの単位ベクトルを求める"),
    (r"写像|単射|全射", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "関数，対応。内容を書く"),
    (r"一意", "ERROR", BOTH, "大学の用語で，教科書の言葉ではない",
     "ただ1つに"),
    (r"狭義単調", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "常に増加する（数学Ⅲでは「単調に増加する」）"),
    (r"凸関数|凹関数", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "下に凸，上に凸"),
    (r"上界|下界|有界", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "内容を書く（「$a_n<2$ がすべての $n$ で成り立つ」）"),
    (r"上限|下限", "WARN", MATH, "大学の用語で，教科書の言葉ではない",
     "数列の上限・下限の意味なら内容を書く"),
    (r"剰余(?!の定理)", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "余り，「$m$ で割った余り」"),
    (r"特性方程式|不動点", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "「$\\alpha=p\\alpha+q$ を満たす $\\alpha$」と式で書く"),
    (r"テレスコーピング", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "「途中の項が打ち消し合う」"),
    (r"一般性を失わ", "ERROR", BOTH, "大学の用語で，教科書の言葉ではない",
     "「対称性から $a\\leqq b$ としてよい」と理由を書く"),
    (r"全単射|逆写像", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "「1対1に対応する」，逆関数"),
    (r"同値類|剰余類", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "「$3$ で割った余りが同じ整数」"),
    (r"可換|結合的", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "「順序を変えてもよい」"),
    (r"閉包|開集合|近傍", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "使わない（「$x=a$ の近くで」）"),
    (r"連続微分可能|\$?C\^\{?1\}?\$?\s*級", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "「微分可能」「$f'(x)$ が連続」"),
    (r"収束半径|一様収束|絶対収束", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "使わない"),
    (r"極限の交換|項別微分", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "その解法を避ける"),
    (r"基底", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "「$s\\vec{a}+t\\vec{b}$ の形にただ1通りに表せる」"),
    (r"無限降下法", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "背理法として書き下す"),
    (r"適当な", "WARN", MATH, "大学の用語で，教科書の言葉ではない",
     "「ある実数 $k$ を用いて」"),
    (r"非自明|自明な解", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "「$x=y=0$ 以外の解」"),
    (r"退化", "WARN", MATH, "大学の用語で，教科書の言葉ではない",
     "「1点になる」「直線になる」と具体的に書く"),
    (r"オーダー|漸近的", "ERROR", MATH, "大学の用語で，教科書の言葉ではない",
     "使わない"),
    (r"高次の近似", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "$\\lvert x\\rvert\\ll1$ のとき $(1+x)^{n}\\fallingdotseq1+nx$"),
    (r"ナブラ|線積分|面積分", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "範囲外。その方法ごと避ける"),
    (r"慣性モーメント|回転の運動方程式|回転の運動エネルギー", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "剛体はつり合いだけ。問題文が与える関係式で解く"),
    (r"角運動量", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "面積速度一定の法則（ケプラーの第2法則）"),
    (r"換算質量|重心系", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "運動量保存の法則と力学的エネルギー保存の法則（または反発係数の式）"),
    (r"ラグランジアン|ハミルトニアン|仮想仕事", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "運動方程式とつり合いの式"),
    (r"コリオリ", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "静止した観測者から見て解く"),
    (r"有効ポテンシャル", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "力学的エネルギー保存の法則と $U=-G\\dfrac{Mm}{r}$"),
    (r"エントロピー", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "各過程の熱量から熱効率を計算する"),
    (r"マクスウェル分布|エネルギー等分配|等分配則", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "単原子分子理想気体の $U=\\dfrac{3}{2}nRT$"),
    (r"ファンデルワールス", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "範囲外"),
    (r"波動方程式", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "正弦波の式 $y=A\\sin2\\pi\\Bigl(\\dfrac{t}{T}-\\dfrac{x}{\\lambda}\\Bigr)$"),
    (r"波数", "WARN", PHYS, "高校物理の教科書にない方法（範囲外）",
     "問題文が使っていなければ $T$，$\\lambda$，$f$，$v$ で書く"),
    (r"フーリエ|群速度|分散関係", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "範囲外"),
    (r"レンズメーカー|球面収差|行列光学", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "範囲外"),
    (r"フレネルの式|反射率", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "反射での位相の変化だけを使う"),
    (r"ビオ.?サバール", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "右ねじの法則と直線電流・円形電流・ソレノイドの公式"),
    (r"アンペールの法則", "WARN", PHYS, "高校物理の教科書にない方法（範囲外）",
     "積分形は使わず，直線電流・円形電流・ソレノイドの公式で書く"),
    (r"ガウスの法則", "WARN", PHYS, "高校物理の教科書にない方法（範囲外）",
     "積分形は使わず，電気力線の本数（$4\\pi kQ$ 本）で書く"),
    (r"複素インピーダンス|フェーザ", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "電圧と電流の最大値の関係と位相，教科書の $Z$ の式"),
    (r"時定数", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "「スイッチを入れた直後」と「十分時間が経過した後」の2つの状態で論じる"),
    (r"マクスウェル方程式|変位電流|ポインティング", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "範囲外"),
    (r"電気影像|鏡像法", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "範囲外"),
    (r"磁気モーメント|磁気双極子", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "コイルの各辺が受ける力と，その力のモーメント"),
    (r"シュレーディンガー|シュレディンガー|波動関数|不確定性原理", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "ボーアの量子条件と振動数条件"),
    (r"崩壊定数", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "半減期の式 $N=N_{0}\\Bigl(\\dfrac{1}{2}\\Bigr)^{\\frac{t}{T}}$"),
    (r"(?<!逆)行列(?!式)", "ERROR", PHYS, "高校物理の教科書にない方法（範囲外）",
     "範囲外"),
    (r"熱力学第[1１]法則", "ERROR", PHYS, "教科書の用語と違う",
     "熱力学第一法則"),
    (r"エネルギー保存則|運動量保存則", "ERROR", PHYS, "教科書の用語と違う",
     "力学的エネルギー保存の法則，運動量保存の法則"),
    (r"キルヒホッフ則", "ERROR", PHYS, "教科書の用語と違う",
     "キルヒホッフの第1法則（電流），第2法則（電圧）"),
    (r"電荷保存", "ERROR", PHYS, "教科書の用語と違う",
     "電気量保存の法則"),
    (r"コンデンサ(?!ー)|キャパシタ", "ERROR", PHYS, "教科書の用語と違う",
     "コンデンサー"),
    (r"はねかえり係数|跳ね返り係数", "WARN", PHYS, "教科書の用語と違う",
     "反発係数（問題文が「はねかえり係数」ならそれに合わせる）"),
    (r"電界|磁界", "WARN", PHYS, "教科書の用語と違う",
     "電場，磁場（問題文が電界・磁界ならそれに合わせる）"),
    (r"ノーマルフォース|テンション|\bEOM\b", "ERROR", PHYS, "教科書の用語と違う",
     "垂直抗力，張力，運動方程式"),
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
        lvl, _subj, why, fix = table[rid] if rid in table else (level, None, None, note)
        self.findings.append({"level": level or lvl, "id": rid, "line": line, "message": note or message(why, fix),
                              "ref": None, "excerpt": _one_line(excerpt)})


def message(why, fix):
    """検査の出力の1行：なぜだめか → 何に直すか。"""
    return "{} → {}".format(why, fix) if why else fix


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
    for rid, level, subjects, pattern, why, fix in RULES:
        if subj not in subjects:
            continue
        for m in re.finditer(pattern, doc.clean):
            ln = doc.line_of(m.start())
            if (rid, ln) in seen:
                continue
            if rid == "cond-prob" and not _offset_in_math(doc, m.start()):
                continue
            seen.add((rid, ln))
            doc.findings.append({"level": level, "id": rid, "line": ln, "message": message(why, fix), "ref": None,
                                 "excerpt": m.group(0)})


def _offset_in_math(doc, off):
    return any(s <= off < e for s, e, _k, _b in doc.segments)


def _check_math(doc, subj):
    seen = set()

    def add(rid, ln, ex):
        if (rid, ln) in seen:
            return
        seen.add((rid, ln))
        level, subjects, why, fix = MATH_RULES[rid]
        if subj in subjects:
            doc.findings.append({"level": level, "id": rid, "line": ln, "message": message(why, fix), "ref": None,
                                 "excerpt": _one_line(ex)})

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
    for pattern, level, subjects, why, fix in WORDS:
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
                                 "message": "「{}」は{} → {}".format(word, why, fix), "ref": None,
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
            findings.append({"level": "WARN", "id": "svg-missing", "line": 0, "message": message(*FORM_RULES["svg-missing"][2:]),
                             "ref": None, "excerpt": rel})
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


RULES_HEAD = """# 検査の規則一覧（{subject}）

`scripts/hs_check.py rules --subject {subject}` の出力をそのまま置いたもの。手で直さない（規則を変えたら hs_check.py を直して作り直す）。
Python が使えず検査を実行できないときは，この一覧で答案を目で点検する（検査を実行したことにはならない）。
各行は「なぜだめか → 何に直すか」。ERROR は確実に直すもの，WARN は文脈で判断するもの。
"""


def rules_markdown(subject):
    """検査の規則一覧（Markdown）。"""
    out = [RULES_HEAD.format(subject=subject).rstrip(), ""]

    def esc(x):
        return x.replace("|", "\\|")

    out += ["## 記号・命令（本文のどこでも）", "", "| 水準 | 検査 | 書いたもの（正規表現） | なぜだめか → 何に直すか |", "|---|---|---|---|"]
    for rid, level, subjects, pattern, why, fix in RULES:
        if subject in subjects:
            out.append("| {} | {} | `{}` | {} |".format(level, rid, esc(pattern), esc(message(why, fix))))
    out += ["", "## 数式の中・形式・構成", "", "| 水準 | 検査 | なぜだめか → 何に直すか |", "|---|---|---|"]
    for table in (MATH_RULES, FORM_RULES):
        for rid, (level, subjects, why, fix) in table.items():
            if subject in subjects:
                out.append("| {} | {} | {} |".format(level, rid, esc(message(why, fix))))
    out += ["", "## 範囲外の方法・教科書にない用語（地の文。問題文にある語は出さない）", "",
            "| 水準 | 語（正規表現） | なぜだめか → 何に直すか |", "|---|---|---|"]
    for pattern, level, subjects, why, fix in WORDS:
        if subject in subjects:
            out.append("| {} | `{}` | {} |".format(level, esc(pattern), esc(message(why, fix))))
    out += ["", "## 作業メモ（本文に書かないもの）", "", "| 語（正規表現） | 検査 |", "|---|---|"]
    for pattern, rid in MEMO:
        out.append("| `{}` | {} |".format(esc(pattern), rid))
    return "\n".join(out) + "\n"


def cmd_rules(args):
    sys.stdout.write(rules_markdown(args.subject))
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
    p_rules = sub.add_parser("rules", help="規則の一覧を Markdown で出す（references/check-rules.md の元）")
    p_rules.add_argument("--subject", choices=("math", "physics"), required=True, help="科目")
    args = parser.parse_args(argv)
    if args.command == "rules":
        return cmd_rules(args)
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
