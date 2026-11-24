"""Read visible SVG text runs and suggest typesetting for short figure labels."""
import re
from dataclasses import dataclass
from itertools import groupby

from hsfig import parse_label

JAPANESE = re.compile(r"[ぁ-ヿ㐀-鿿々]")
MATH_FACE = re.compile(r"\bmath\b|mathjax|katex|stix two math|stixgeneral", re.I)
SUBSCRIPT = re.compile(r"(?<![A-Za-z])([A-Za-zΑ-ω])(\d+)(?![A-Za-z\d])|(?<![A-Za-z])V([AL])(?![A-Za-z])")
CAPTION = re.compile(r"図\s*\d+(?:\s*[-－―–]\s*\d+)+")
OPERAND = r"(?:[A-Za-zΑ-ω]{1,2}|[A-Za-zΑ-ω]?\d+(?:\.\d+)?)"
MINUS = re.compile(rf"(?<![A-Za-zΑ-ω\d])(?:{OPERAND}|\))?\s*-\s*(?:{OPERAND}(?![A-Za-zΑ-ω\d])|\()")
NUM = r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"


def prop(el, name):
    """インライン style を提示属性に優先する。"""
    matches = re.findall(r"(?:^|;)\s*" + re.escape(name) + r"\s*:\s*([^;]+)", el.get("style") or "")
    if matches:
        return matches[-1].strip()
    v = el.get(name)
    return v.strip() if v is not None else None


def length(v, default=0.0):
    m = re.match(r"\s*(" + NUM + r")\s*([a-z%]*)", v or "")
    if not m:
        return default
    k = {"": 1, "px": 1, "pt": 96 / 72, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96}.get(m.group(2))
    return float(m.group(1)) * k if k else default


def font_px(v, parent):
    if not v:
        return parent
    v = v.strip()
    if v.endswith("%"):
        return parent * float(v[:-1]) / 100
    if v.endswith("em"):
        return parent * float(v[:-2])
    return length(v, parent)


@dataclass
class Run:
    text: str
    size: float
    style: str
    family: str
    script: str


def text_runs(el, size, style="", family=""):
    """Track dy between siblings, including absolute baselines on individual tspans."""
    baseline = None
    y = 0.
    runs = []

    def visit(node, fs, face, fonts, shift):
        nonlocal baseline, y
        if prop(node, "display") == "none" or prop(node, "visibility") == "hidden":
            return
        if node is not el:
            fs = font_px(prop(node, "font-size"), fs)
        face = prop(node, "font-style") or face
        fonts = prop(node, "font-family") or fonts
        shift = prop(node, "baseline-shift") or shift
        if node.get("y"):
            y = font_px(node.get("y").split()[0], 0)
        y += font_px(node.get("dy", "0").split()[0], fs)

        def append(content):
            nonlocal baseline
            if content:
                if baseline is None and content.strip():
                    baseline = y if node is el or not el.get("y") else font_px(el.get("y"), 0)
                delta = y - (y if baseline is None else baseline)
                script = shift if shift in ("sub", "super") else ""
                if not script and fs < size * .96 and abs(delta) > .04 * size:
                    script = "sub" if delta > 0 else "super"
                runs.append(Run(content, fs, face, fonts, script))
        append(node.text)
        for child in node:
            if child.tag.rsplit("}", 1)[-1] in ("tspan", "textPath", "a"):
                visit(child, fs, face, fonts, shift)
            append(child.tail)

    visit(el, size, style, family, "")
    return runs


def math_issues(runs, *, generated=False, chem=False):
    """(message, definite) pairs. Ambiguous notation remains a warning."""
    content = "".join(r.text for r in runs)
    math = CAPTION.sub("", content)
    issues = []
    if "^" in math or "_" in math:
        issues.append(("添字・指数の ^ または _ が文字として残っている", bool(re.search(r"[_^]\{[^{}]+\}|(?:^|[^A-Za-z])(?:[A-Za-z]|\d+)[_^][A-Za-z\d](?:$|[^A-Za-z])", math))))
    if re.search(r"[{}]", math) and re.search(r"[A-Za-zΑ-ω\d=]", math) and not generated:
        issues.append((r"波括弧が見える。組版のグループか、原図にある区切り記号（\{ と \}）かを照合する", False))
    if MINUS.search(math) and not chem:
        issues.append(("数式の ASCII ハイフンをマイナス（−）にする", False))
    if any(JAPANESE.search(r.text) and (r.style.startswith(("italic", "oblique")) or MATH_FACE.search(r.family))
           for r in runs):
        issues.append(("和文に斜体・数式書体が及んでいる。変数だけを数式にする", True))
    baseline_chunks = ("".join(r.text for r in group)
                       for script, group in groupby(runs, lambda r: r.script) if not script)
    if not chem and any(SUBSCRIPT.search(s) for s in baseline_chunks):
        issues.append(("添字が付いていない可能性がある。原図で添字の位置を確認する", False))
    if any(r.style.startswith(("italic", "oblique")) and re.search(r"[0-9−]", r.text) for r in runs):
        issues.append(("数字・マイナスまで斜体になっている。変数だけを斜体にする", False))
    if re.search(r"[A-Za-z\d]+\s*/\s*[A-Za-z\d]+", math) and not chem:
        issues.append(("斜線の分数か単位かを照合し、縦分数なら分子・括線・分母を組む", False))
    return issues


def suggested_tex(runs, *, atom=False):
    """Reconstruct visible scripts and keep prose/caption punctuation intact."""
    content = "".join(r.text for r in runs).strip()
    if atom:
        parts = []
        for script, group in groupby(runs, lambda r: r.script):
            part = "".join(r.text for r in group)
            if script:
                marker = "_" if script == "sub" else "^"
                parts.append("$" + marker + r"{\mathrm{" + part + "}}$")
            else:
                parts.append(part)
        return "".join(parts)
    if content.startswith("$") and content.endswith("$") and len(content) >= 2:
        try:
            parse_label(content, strict=True)
            return content
        except ValueError:
            pass
    if CAPTION.search(content):
        return content
    if JAPANESE.search(content):
        return re.sub(r"(?<![A-Za-zΑ-ω])[A-Za-zΑ-ω](?![A-Za-zΑ-ω])", lambda m: "$" + m[0] + "$", content)
    if not any(r.script or r.style.startswith(("italic", "oblique")) for r in runs) and not re.search(
            r"[_^=+−{}\d/]|^V[AL]$", content):
        return content
    parts = []
    for script, group in groupby(runs, lambda r: r.script):
        group = list(group)
        s = "".join(r.text for r in group).strip().replace("−", "-").replace("′", "'")
        if not s:
            continue
        # Visible braces in an equation can be intentional delimiters. Preserve
        # those while retaining TeX argument braces on literal _ and ^ markers.
        if not re.search(r"[_^]\{", s):
            s = s.replace("{", r"\{").replace("}", r"\}")
        if script:
            parts.append(("_" if script == "sub" else "^") + (s if len(s) == 1 else "{" + s + "}"))
        else:
            s = SUBSCRIPT.sub(lambda m: ((r"\mathrm{P}" if m[1] == "P" else m[1]) + "_{" + m[2] + "}")
                              if m[1] else "V_" + m[3], s)
            if s == "P" and group[0].style not in ("italic", "oblique"):
                s = r"\mathrm{P}"
            s = re.sub(r"([A-Za-z\d]+)/([A-Za-z\d]+)", r"\\frac{\1}{\2}", s)
            parts.append(s)
    tex = "$" + "".join(parts).replace("\u2009", "").replace(" ", "") + "$"
    try:
        parse_label(tex, strict=True)
    except ValueError:
        return content
    return tex
