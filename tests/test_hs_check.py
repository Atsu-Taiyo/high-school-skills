"""hs_check.py のテスト（標準ライブラリの unittest）。

    python3 -B -m unittest discover -s tests -v
"""
import hashlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
MATH_SCRIPT = os.path.join(SKILLS, "high-school-math-answers", "scripts", "hs_check.py")
PHYS_SCRIPT = os.path.join(SKILLS, "high-school-physics-answers", "scripts", "hs_check.py")

_spec = importlib.util.spec_from_file_location("hs_check", MATH_SCRIPT)
hs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hs)


def ids(text, subject="math", problem=None, level=None):
    found = hs.lint_text(text, subject, problem)
    return {f["id"] for f in found if level is None or f["level"] == level}


def answer(body):
    """**解答** と **答** で挟んだ最小の答案。"""
    return "**解答**\n\n" + body + "\n\n**答**　$x=2$\n"


GOOD_MATH = """**解答**

真数は正であるから

　$x>1$　……①

方程式を変形すると

　$\\log_{2}(x-1)(x+2)=\\log_{2}4$

よって

　$(x-1)(x+2)=4$

整理すると $x^{2}+x-6=0$ より $(x+3)(x-2)=0$ となり，$x=-3,\\ 2$ である。① より $x=2$ である。

**答**　$x=2$
"""

# 過去の評価で，画像だけを渡されたモデルが書いた答案の形（\\boxed，\\le，\\(，\\frac）
IMAGE_ONLY = """### (1)

\\(f(x)=x-1-\\log x\\) とおくと、
\\[
f'(x)=1-\\frac1x=\\frac{x-1}{x}.
\\]
よって \\(f(x)\\ge f(1)=0\\) だから、
\\[
\\boxed{\\log x\\le x-1}.
\\]
"""


class TestImageOnlyAnswer(unittest.TestCase):
    def test_detects_known_problems(self):
        found = ids(IMAGE_ONLY, level="ERROR")
        for rid in ("boxed", "ineq", "paren-delim", "frac", "answer-missing"):
            self.assertIn(rid, found)

    def test_good_answer_has_no_error(self):
        self.assertEqual(ids(GOOD_MATH, level="ERROR"), set())
        self.assertEqual(ids(GOOD_MATH), set())


class TestCommands(unittest.TestCase):
    def test_inequalities(self):
        self.assertIn("ineq", ids(answer("$a\\le b$ である。")))
        self.assertIn("ineq", ids(answer("$a\\geq b$ である。")))
        self.assertIn("ineq", ids(answer("$a≤b$ である。")))
        self.assertNotIn("ineq", ids(answer("$a\\leqq b$，$\\left(x\\right)\\geqq 0$ である。")))

    def test_implies_and_iff(self):
        self.assertIn("implies", ids(answer("$p\\implies q$")))
        self.assertNotIn("implies", ids(answer("$p\\Rightarrow q$")))
        self.assertIn("iff", ids(answer("$p\\iff q$"), level="WARN"))

    def test_symbols(self):
        for src, rid in [("\\forall x", "forall-exists"), ("\\exists x", "forall-exists"), ("\\prod a_k", "prod"),
                         ("\\binom{n}{r}", "binom"), ("\\phi", "phi"), ("\\ln x", "ln"), ("\\mathbb{R}", "mathbb"),
                         ("e^{i\\theta}", "complex-exp"), ("\\vec{a}\\times\\vec{b}", "vec-cross"),
                         ("P(B\\mid A)", "cond-prob"), ("\\vec{e_1}", "vec-subscript"), ("V'^{2}", "prime-power"),
                         ("\\therefore", "therefore"), ("a\\approx b", "approx"), ("f(x)=x+o(x)", "landau")]:
            self.assertIn(rid, ids(answer("$" + src + "$ である。")), src)
        ok = ids(answer("$\\varphi$，$2\\times 3$，$\\{x\\mid x>0\\}$，$P_{A}(B)$，${V'}^{2}$，$\\vec{e}_1$，"
                        "点 $\\mathrm{O}(0,0)$ である。"))
        self.assertFalse(ok & {"phi", "vec-cross", "cond-prob", "prime-power", "vec-subscript", "landau"}, ok)

    def test_environments(self):
        for src, rid in [("\\begin{align}a&=b\\end{align}", "env"), ("\\tag{1}", "tag-label"),
                         ("\\label{a}", "tag-label"), ("\\newcommand{\\R}{x}", "macro-def"), ("\\def\\a{1}", "macro-def")]:
            self.assertIn(rid, ids(answer("$$" + src + "$$")), src)
        self.assertNotIn("env", ids(answer("$$\\begin{aligned}a&=b\\\\&=c\\end{aligned}$$")))

    def test_code_is_ignored(self):
        self.assertNotIn("ineq", ids(answer("`\\le` は書かない。")))


class TestMath(unittest.TestCase):
    def test_frac(self):
        self.assertIn("frac", ids(answer("$\\frac{1}{2}$ である。")))
        self.assertIn("frac", ids(answer("$$y=\\frac{1}{x}$$")))
        for src in ("2^{\\frac{1}{n}}", "x^\\frac12", "a_{\\frac{n}{2}}", "e^{-\\frac{x}{2}}", "\\dfrac{1}{2}"):
            self.assertNotIn("frac", ids(answer("$" + src + "$ である。")), src)

    def test_circled_in_math(self):
        self.assertIn("circled-in-math", ids(answer("$x>1\\quad①$")))
        self.assertIn("circled-in-math", ids(answer("$\\text{①}$")))
        self.assertNotIn("circled-in-math", ids(GOOD_MATH))

    def test_table_pipe(self):
        table = "| $x$ | $|x|$ |\n|---|---|\n| $1$ | $1$ |"
        self.assertIn("table-pipe", ids(answer(table)))
        self.assertNotIn("table-pipe", ids(answer("| $x$ | $\\lvert x\\rvert$ |\n|---|---|")))
        self.assertNotIn("table-pipe", ids(answer("$|x|<1$ である。")))

    def test_text(self):
        self.assertNotIn("text-long", ids(answer("$x>0\\ \\text{かつ}\\ y>0$")))
        self.assertIn("text-long", ids(answer("$x>0\\ \\text{であるから両辺を割ると}$"), level="WARN"))

    def test_displaystyle(self):
        self.assertIn("displaystyle", ids(answer("$\\lim_{x\\to 0}f(x)$ である。")))
        self.assertNotIn("displaystyle", ids(answer("$\\displaystyle\\lim_{x\\to 0}f(x)$ である。")))
        self.assertNotIn("displaystyle", ids(answer("$$\\lim_{x\\to 0}f(x)$$")))

    def test_dollar(self):
        self.assertIn("dollar-unclosed", ids(answer("$x>1 である。\n\n次に")))
        self.assertIn("display-blank", ids(answer("$$\na=b\n\nc=d\n$$")))
        self.assertNotIn("dollar-unclosed", ids(answer("価格は \\$5 で，$x=1$ である。")))


class TestForm(unittest.TestCase):
    def test_answer_line(self):
        self.assertIn("answer-missing", ids("**解答**\n\n$x=2$ である。\n"))
        self.assertNotIn("answer-missing", ids(GOOD_MATH))
        self.assertNotIn("answer-missing", ids("**解答**\n\n$x=2$\n\n**答（2）**　$x=2$\n"))
        self.assertIn("answer-missing-proof", ids("**解答**\n\nよって成り立つ。（証明終）\n", level="WARN"))

    def test_after_answer(self):
        self.assertIn("after-answer-check", ids(GOOD_MATH + "\n（確認：$x=2$ を代入すると成り立つ）\n", level="ERROR"))
        self.assertIn("after-answer", ids(GOOD_MATH + "\nこの問題は難しい。\n", level="WARN"))
        sep = GOOD_MATH + "\n---\n\n検査：ERROR 0 件・WARN 0 件\n"
        self.assertFalse(ids(sep) & {"after-answer", "after-answer-check", "bullet", "desu-masu"})
        multi = "**解答**\n\n$x=1$ である。\n\n**答**\n\n$a<0$ のとき　最小値 $3$\n\n$a\\geqq 0$ のとき　最小値 $1$\n"
        self.assertNotIn("after-answer", ids(multi))

    def test_bullets(self):
        self.assertIn("bullet", ids(answer("- $x>0$ のとき\n- $x<0$ のとき")))
        self.assertIn("bullet", ids(answer("1. $x>0$ のとき")))
        self.assertNotIn("bullet", ids(answer("[1] $x>0$ のとき，$x=1$ である。")))
        self.assertNotIn("bullet", ids(answer("$$\n\\begin{aligned}\n- x &= 1\n\\end{aligned}\n$$")))

    def test_sections(self):
        for head in ("**方針**", "### 解説", "【別解】", "参考：$x=1$ でもよい。"):
            self.assertIn("sections", ids(answer(head + "\n\n$x=1$ である。"), level="WARN"), head)

    def test_eqno(self):
        self.assertNotIn("eqno-format", ids(GOOD_MATH))
        self.assertIn("eqno-format", ids(answer("$x>1$ ……①\n\n① より")))
        self.assertIn("eqno-format", ids(answer(" $x>1$ ……①\n\n① より")))
        self.assertIn("eqno-paren-digit", ids(answer("　$x>1$　……(1)")))
        self.assertNotIn("eqno-format", ids(answer("　$a=b$　すなわち　$c=d$　……②")))
        mixed = answer("　$x>1$　……①\n\n　$y>1$　……(a)")
        self.assertIn("eqno-mixed", ids(mixed, level="WARN"))
        mix_display = answer("　$x>1$　……①\n\nよって\n\n$$x=2$$\n\nである。")
        self.assertIn("eqno-display-mix", ids(mix_display, level="WARN"))
        # 小問が変われば別の導出（「(1)　…」の見出しでも区切る）
        two = answer("(1)　$x>0$ とおくと\n\n$$x=2$$\n\nである。\n\n(2)　次に\n\n　$y>1$　……①\n\n① より")
        self.assertNotIn("eqno-display-mix", ids(two))
        self.assertIn("eqno-problem", ids(GOOD_MATH, problem="次の ①〜④ から選べ。", level="WARN"))

    def test_memo(self):
        self.assertIn("memo", ids(answer("検算すると $x=2$ で成り立つ。")))
        self.assertIn("memo-file", ids(answer("図は fig1.svg に保存しました。")))
        self.assertIn("desu-masu", ids(answer("式番号は (a) にしています。"), level="WARN"))
        self.assertIn("touten", ids(answer("よって、$x=1$ である。"), level="WARN"))

    def test_code_wrap(self):
        self.assertIn("code-wrap", ids("```markdown\n" + GOOD_MATH + "```\n", level="ERROR"))

    def test_alt_and_figure_number(self):
        self.assertIn("alt-text", ids(answer("![解図1 $y=x^2$](fig1.svg)")))
        self.assertNotIn("alt-text", ids(answer("![解図1](fig1.svg)")))
        self.assertIn("fig-number", ids(answer("![図1](fig1.svg)"), problem="下の図のように", level="WARN"))
        self.assertNotIn("fig-number", ids(answer("![解図1](fig1.svg)\n\n問題の図1 より"), problem="図1のように"))

    def test_format_other_skips_markdown_checks(self):
        found = {f["id"] for f in hs.lint_text(IMAGE_ONLY, "math", None, "other")}
        self.assertNotIn("paren-delim", found)
        self.assertNotIn("answer-missing", found)
        self.assertIn("boxed", found)


class TestWords(unittest.TestCase):
    def test_math_words(self):
        for word in ("ロピタルの定理により", "テイラー展開すると", "外積を用いて", "多項式", "直交する", "一意に定まる"):
            self.assertIn("scope-word", ids(answer(word + "。"), level="ERROR"), word)
        for word in ("直交座標で", "剰余の定理により", "漸近線は"):
            self.assertNotIn("scope-word", ids(answer(word + "。")), word)

    def test_problem_terms_are_allowed(self):
        self.assertIn("scope-word", ids(answer("2つのベクトルは直交する。")))
        self.assertNotIn("scope-word", ids(answer("2つのベクトルは直交する。"), problem="直交する2つのベクトル"))

    def test_physics_words(self):
        self.assertIn("scope-word", ids(answer("慣性モーメントを $I$ とする。"), "physics", level="ERROR"))
        self.assertNotIn("scope-word", ids(answer("慣性モーメントを $I$ とする。"), "physics",
                                           problem="棒の慣性モーメントを I とする"))
        self.assertIn("scope-word", ids(answer("運動量保存則より"), "physics"))
        self.assertIn("scope-word", ids(answer("コンデンサの電気量"), "physics"))
        self.assertNotIn("scope-word", ids(answer("コンデンサーの電気量"), "physics"))
        self.assertIn("scope-word", ids(answer("電界の強さ"), "physics", level="WARN"))


class TestPhysics(unittest.TestCase):
    def test_units(self):
        p = "physics"
        self.assertEqual(ids(answer("$v=3.0\\ \\mathrm{m/s}$，$R=10\\ \\Omega$，$v_{\\mathrm{A}}=2.0\\ \\mathrm{m/s}$"), p)
                         & {"unit-italic", "unit-nospace"}, set())
        self.assertIn("unit-italic", ids(answer("$v=3.0\\ m/s$"), p))
        self.assertIn("unit-italic", ids(answer("$v=3.0 m/s$"), p))
        self.assertIn("unit-nospace", ids(answer("$v=3.0\\mathrm{m/s}$"), p))
        self.assertIn("unit-nospace", ids(answer("$Q=5.0\\times10^{2}\\mathrm{J}$"), p))
        self.assertNotIn("unit-italic", ids(answer("$2mv$，$v_{1}$"), p))
        self.assertIn("si-units", ids(answer("$\\SI{3}{m}$"), p))

    def test_derivatives(self):
        p = "physics"
        self.assertIn("d-dt", ids(answer("$v=\\dfrac{dx}{dt}$"), p))
        self.assertNotIn("d-dt", ids(answer("$v=\\dfrac{\\Delta x}{\\Delta t}$，$\\dfrac{d}{L}$"), p))
        self.assertIn("dot-derivative", ids(answer("$m\\ddot{x}=-kx$"), p))
        self.assertIn("integral", ids(answer("$W=\\int F\\,dx$"), p))
        self.assertNotIn("dot-derivative", ids(answer("$0.\\dot{3}$")))  # 数学の循環小数

    def test_blank_symbol(self):
        self.assertIn("text-blank", ids(answer("$\\text{ア}=mg\\sin\\theta$"), "physics"))
        self.assertNotIn("text-blank", ids(answer("アは $mg\\sin\\theta$ である。"), "physics"))


class TestExamplesInReferences(unittest.TestCase):
    """references/examples.md の見本（正本）に ERROR が出ないこと。"""

    def _examples(self, path):
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        for part in text.split("\n---\n"):
            if "**問題**" not in part:
                continue
            start = part.index("\n", part.index("**問題**"))
            body = re.split(r"\n\*\*この例で守っている点\*\*", part[start:])[0]
            yield part[:start], body

    def test_examples(self):
        for subject, rel in (("math", "high-school-math-answers"), ("physics", "high-school-physics-answers")):
            path = os.path.join(SKILLS, rel, "references", "examples.md")
            n = 0
            for problem, body in self._examples(path):
                n += 1
                errors = [f for f in hs.lint_text(body, subject, problem) if f["level"] == "ERROR"]
                self.assertEqual(errors, [], "{} の見本 {}".format(rel, n))
            self.assertGreater(n, 1)


class TestRulesAreTheSource(unittest.TestCase):
    """機械的に判定できる規則は hs_check.py が正本。SKILL.md・references に二重に書かない。"""

    def _read(self, rel):
        with open(os.path.join(SKILLS, rel), encoding="utf-8") as handle:
            return handle.read()

    def test_every_rule_says_why_and_fix(self):
        rows = [(r[0], r[4], r[5]) for r in hs.RULES] + [(k, v[2], v[3]) for k, v in hs.MATH_RULES.items()] + \
               [(k, v[2], v[3]) for k, v in hs.FORM_RULES.items()] + [(w[0], w[3], w[4]) for w in hs.WORDS]
        for rid, why, fix in rows:
            self.assertTrue(why and fix, rid)
            self.assertNotIn("\n", why + fix, rid)
            self.assertIn(" → ", hs.message(why, fix))

    def test_lint_messages_carry_why_and_fix(self):
        for f in hs.lint_text(IMAGE_ONLY, "math"):
            self.assertIn(" → ", f["message"], f["id"])

    def test_generated_rule_lists_are_current(self):
        for subject, rel in (("math", "high-school-math-answers"), ("physics", "high-school-physics-answers")):
            self.assertEqual(self._read(rel + "/references/check-rules.md"), hs.rules_markdown(subject),
                             "{}/references/check-rules.md が古い。hs_check.py rules --subject {} で作り直す".format(rel, subject))

    def test_skill_text_does_not_repeat_checked_rules(self):
        # 検査が教える記号・書式の細かい規則を SKILL.md に戻さない（二重管理の防止）
        for rel in ("high-school-math-answers/SKILL.md", "high-school-physics-answers/SKILL.md"):
            text = self._read(rel)
            for token in ("\\boxed", "\\leqq", "\\dfrac", "\\binom", "\\therefore", "……①"):
                self.assertNotIn(token, text, "{} に {}".format(rel, token))

    def test_skill_text_lists_forbidden_methods(self):
        # 解き方の禁止は書く前に知っている必要があるので，SKILL.md 本文に短い一覧で置く（版 D'）
        wants = {"high-school-math-answers/SKILL.md": ("ロピタル", "テイラー展開", "外積", "逆三角関数"),
                 "high-school-physics-answers/SKILL.md": ("微分方程式", "外積", "慣性モーメント", "ガウスの法則", "複素インピーダンス")}
        for rel, tokens in wants.items():
            text = self._read(rel)
            for token in tokens:
                self.assertIn(token, text, "{} に {} の禁止がない".format(rel, token))

    def test_descriptions_are_short(self):
        import re
        for rel in ("high-school-math-answers/SKILL.md", "high-school-physics-answers/SKILL.md"):
            desc = re.search(r"^description: (.*)$", self._read(rel), re.M).group(1)
            self.assertLessEqual(len(desc), 200, rel)
            self.assertIn("問題", desc)

    # 版 C までの references の表（forbidden.md 5節・notation.md 13節・notation-units.md 10節）にあった命令。
    # 表は hs_check.py に移したので，ここに固定して，どれも検査されることを確かめる。
    TOKENS = {
        "math": ["\\prod", "\\forall", "\\exists", "\\binom{n}{r}", "\\mathbb{R}", "\\land", "\\lor", "\\lnot",
                 "\\langle", "\\rangle", "\\Vert", "\\mathbf{a}", "\\boldsymbol{a}", "\\arcsin", "\\sinh", "\\cot",
                 "\\sec", "\\csc", "\\ln", "\\exp", "\\lfloor", "\\rfloor", "\\lceil", "\\rceil", "\\partial", "\\nabla",
                 "\\nmid", "\\gcd", "\\bmod", "\\max", "\\min", "\\begin{pmatrix}", "\\mapsto", "\\sim", "\\approx",
                 "\\therefore", "\\because", "\\square", "\\newcommand", "\\def", "\\renewcommand", "\\nCr", "\\C",
                 "\\bm", "\\vector", "\\begin{align}", "\\begin{equation}", "\\begin{eqnarray}", "\\label", "\\ref",
                 "\\eqref", "\\tag", "\\text{①}", "\\text{㋐}", "\\vec{e_1}", "\\phi", "\\begin{tabular}", "\\mbox",
                 "\\hbox", "\\textcircled{1}"],
        "physics": ["\\text{ア}=mg\\sin\\theta", "\\vec{v_A}", "\\si{}", "\\SI{}{}", "\\unit{}", "\\degree", "\\celsius",
                    "\\ohm", "\\bm{F}", "\\boldsymbol{F}", "\\mathbf{F}", "\\dot{x}", "\\ddot{x}", "\\approx", "\\simeq",
                    "\\sim"],
    }

    def test_former_reference_tables_are_covered(self):
        for subject, tokens in self.TOKENS.items():
            base = ids(answer("$x$ である。"), subject)
            for token in tokens:
                found = ids(answer("$" + token + "$ である。"), subject) - base
                self.assertTrue(found, "{} の {} を検査していない".format(subject, token))

    def test_rules_command(self):
        proc = subprocess.run([sys.executable, MATH_SCRIPT, "rules", "--subject", "physics"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("微分方程式", proc.stdout)


class TestCopies(unittest.TestCase):
    def test_physics_copy_is_identical(self):
        with open(MATH_SCRIPT, "rb") as a, open(PHYS_SCRIPT, "rb") as b:
            self.assertEqual(hashlib.sha256(a.read()).hexdigest(), hashlib.sha256(b.read()).hexdigest(),
                             "2つのスキルの scripts/hs_check.py は同じものにする")


class TestRunVerify(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state = os.path.join(self.tmp, "state")
        self.final = os.path.join(self.tmp, "answer.md")
        with open(self.final, "w", encoding="utf-8") as handle:
            handle.write(IMAGE_ONLY)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def cli(self, *args, stdin=None):
        proc = subprocess.run([sys.executable, MATH_SCRIPT] + list(args), input=stdin, capture_output=True,
                              text=True, cwd=self.tmp)
        return proc.returncode, proc.stdout

    def test_cycle(self):
        code, out = self.cli("run", "--subject", "math", "--final", self.final, "--state-dir", self.state)
        self.assertEqual(code, 0)
        first = out.splitlines()[0]
        self.assertIn("1回目", first)
        self.assertRegex(first, r"ERROR [1-9]\d* 件")
        self.assertIn("合格を示すものではありません", out)
        self.assertTrue(os.path.isfile(os.path.join(self.state, ".gitignore")))
        code, out = self.cli("verify", "--final", self.final, "--state-dir", self.state)
        self.assertEqual(code, 0, out)
        self.assertIn("合いました", out.splitlines()[0])
        with open(self.final, "w", encoding="utf-8") as handle:
            handle.write(GOOD_MATH)
        code, out = self.cli("verify", "--final", self.final, "--state-dir", self.state)
        self.assertEqual(code, 1)
        code, out = self.cli("run", "--subject", "math", "--final", self.final, "--state-dir", self.state)
        self.assertIn("2回目", out.splitlines()[0])
        self.assertIn("ERROR 0 件・WARN 0 件", out.splitlines()[0])
        code, out = self.cli("run", "--subject", "math", "--final", self.final, "--state-dir", self.state)
        self.assertIn("前回と同じ最終稿", out.splitlines()[0])
        # ファイルで run し，返す本文を標準入力で verify する
        code, out = self.cli("verify", "--final", "-", "--state-dir", self.state, stdin=GOOD_MATH)
        self.assertEqual(code, 0, out)

    def test_stdin_run(self):
        code, out = self.cli("run", "--subject", "math", "--final", "-", "--state-dir", self.state, stdin=GOOD_MATH)
        self.assertEqual(code, 0)
        code, out = self.cli("verify", "--final", "-", "--state-dir", self.state, stdin=GOOD_MATH + "\n\n")
        self.assertEqual(code, 0, out)
        code, out = self.cli("verify", "--final", "-", "--state-dir", self.state, stdin=GOOD_MATH + "追記\n")
        self.assertEqual(code, 1)

    def test_default_state_dir_is_git_top(self):
        os.makedirs(os.path.join(self.tmp, ".git"))
        sub = os.path.join(self.tmp, "a", "b")
        os.makedirs(sub)
        proc = subprocess.run([sys.executable, MATH_SCRIPT, "run", "--subject", "math", "--final", self.final],
                              capture_output=True, text=True, cwd=sub, env=dict(os.environ, HS_CHECK_STATE_DIR=""))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, ".hs-check", "state.json")))

    def test_lint_exit_code(self):
        code, _ = self.cli("lint", "--subject", "math", self.final)
        self.assertEqual(code, 1)
        code, _ = self.cli("lint", "--subject", "math", "-", stdin=GOOD_MATH)
        self.assertEqual(code, 0)

    def test_figures(self):
        svg = os.path.join(SKILLS, "svg-figures", "examples", "pulley.svg")
        shutil.copy(svg, os.path.join(self.tmp, "fig1.svg"))
        with open(self.final, "w", encoding="utf-8") as handle:
            handle.write(answer("![解図1](fig1.svg)\n\n解図1　滑車にはたらく力。"))
        code, out = self.cli("run", "--subject", "physics", "--final", self.final, "--state-dir", self.state)
        self.assertIn("lint_svg.py を実行した", out)
        with open(self.final, "w", encoding="utf-8") as handle:
            handle.write(answer("![解図1](missing.svg)"))
        code, out = self.cli("run", "--subject", "physics", "--final", self.final, "--state-dir", self.state)
        self.assertIn("svg-missing", out)

    def test_no_pycache(self):
        self.cli("lint", "--subject", "math", self.final)
        for d in (os.path.dirname(MATH_SCRIPT), os.path.dirname(PHYS_SCRIPT)):
            self.assertFalse(os.path.exists(os.path.join(d, "__pycache__")), d)

    def test_lint_output_lists_lines(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            hs.main(["lint", "--subject", "math", self.final])
        self.assertRegex(buf.getvalue(), r"ERROR\s+\d+行 \[boxed\]")


if __name__ == "__main__":
    unittest.main()
