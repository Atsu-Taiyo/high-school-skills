#!/usr/bin/env python3
"""Mode A の意図仕様（<図>.intent.md）と SVG の照合。

lint_svg.py から呼ばれる。単独でも使える:
    python3 intent_check.py figure.svg [figure.intent.md]

仕様の書式は references/intent-template.md。見出し（## ）ごとに箇条書きで書く。
  ## 伝えたいこと        一文以上。何を示す図か。
  ## 対象と関係          式・対称・平行・等長・角・接点・交点など（箇条書き1件以上）
  ## 本質の印            各行の末尾に [hatch] [dashed] [open-point] [dot] [angle] [arrow] [caption] のどれか
  ## 文字                図に書く文字を `...` で囲んで1行1件（TeX 可）
  ## 読めない            判読できない文字は [?] を付けて書く。描かない。候補は 「...」 で書ける
  ## 歪みの補正 / ## 投影  任意（立体は投影を書く）
検査: 必須見出し、[印] の種類が SVG にあるか、`文字` が全部 SVG にあるか、
SVG に仕様にない文字（勝手な追加）がないか、[?] の候補を描いていないか。
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SVG = "{http://www.w3.org/2000/svg}"
REQUIRED = ("伝えたいこと", "対象と関係", "本質の印", "文字")
MARKS = ("hatch", "dashed", "open-point", "dot", "angle", "arrow", "caption")


def local(tag):
    return tag.split("}")[-1] if isinstance(tag, str) else ""


def norm(s: str) -> str:
    s = s.replace("\\circ", "°").replace("&lt;", "<").replace("&gt;", ">")
    s = re.sub(r"\\(mathrm|mathit|left|right|vec|hat|text|frac|sqrt|cdot|,|;|!)", lambda m: "√" if m.group(1) == "sqrt" else "", s)
    s = s.replace("−", "-").replace("–", "-").replace("〈", "<").replace("〉", ">").replace("＜", "<").replace("＞", ">")
    s = s.replace("\u2009", "").replace("\u00a0", "")
    return re.sub(r"[^0-9A-Za-zぁ-ヿ一-鿿°+\-=√α-ωΑ-Ω<>※]", "", s)


def parse_intent(text: str):
    sections, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s*(.+?)\s*$", line)
        if m:
            cur = re.sub(r"[（(].*$", "", m.group(1)).strip()
            sections.setdefault(cur, [])
        elif cur is not None and line.strip():
            sections[cur].append(line.strip())
    return sections


def items(lines):
    return [re.sub(r"^[-*・]\s*", "", ln) for ln in lines if re.match(r"^[-*・]\s*", ln)]


def svg_facts(root):
    texts, tex_labels, kinds = [], [], set()
    in_label = set()
    for g in root.iter():
        if g.get("data-math-label") is not None:
            tex_labels.append(g.get("data-math-label"))
            for t in g.iter(SVG + "text"):
                in_label.add(id(t))
    for t in root.iter(SVG + "text"):
        if id(t) not in in_label:
            s = "".join(t.itertext()).strip()
            if s:
                texts.append(s)
    for g in root.iter():
        if g.get("data-math-label") is not None:
            texts.append("".join("".join(t.itertext()) for t in g.iter(SVG + "text")))
    patterns = {p.get("id") for p in root.iter(SVG + "pattern")}
    for el in root.iter():
        tag = local(el.tag)
        st = (el.get("style") or "")
        fill = el.get("fill") or ""
        m = re.search(r"url\(#([^)]+)\)", fill + st)
        if (m and m.group(1) in patterns) or "hatch" in (el.get("class") or "") or el.get("data-role") == "hatch":
            kinds.add("hatch")
        if (el.get("stroke-dasharray") or "none") not in ("none", "") or "dasharray" in st:
            kinds.add("dashed")
        if tag == "circle":
            r = float(re.findall(r"[-\d.]+", el.get("r") or "0")[0] or 0)
            f = (el.get("fill") or "black").lower()
            if r <= 9 and f in ("white", "#fff", "#ffffff", "none"):
                kinds.add("open-point")
            elif r <= 7:
                kinds.add("dot")
        if tag == "path":
            d = el.get("d") or ""
            if re.search(r"[Aa]\s*[\d.]", d) or el.get("data-role") == "angle":
                kinds.add("angle")
        if el.get("data-role") == "angle":
            kinds.add("angle")
        if tag == "marker" or any(el.get(a) for a in ("marker-end", "marker-start")):
            kinds.add("arrow")
    return texts, tex_labels, kinds


def check(svg_path, intent_path=None):
    """(errors, warnings)。仕様ファイルが無いときは警告 1 件。"""
    svg_path = Path(svg_path)
    p = Path(intent_path) if intent_path else svg_path.with_suffix(".intent.md")
    if not p.exists():
        return [], [f"意図仕様 {p.name} が無い（描く前に伝えたいこと・対象と関係・本質の印・文字を書く。references/intent-template.md）"]
    sec = parse_intent(p.read_text(encoding="utf-8"))
    W = []
    for name in REQUIRED:
        if name not in sec or not sec[name]:
            W.append(f"意図仕様に「{name}」が無い、または空")
    if "伝えたいこと" in sec and sum(len(x) for x in sec["伝えたいこと"]) < 10:
        W.append("「伝えたいこと」が短すぎる（この図が何を示すかを一文で）")
    if "対象と関係" in sec and not items(sec["対象と関係"]):
        W.append("「対象と関係」に箇条書きが無い（式・対称・平行・交点などを書く）")
    try:
        root = ET.parse(svg_path).getroot()
    except ET.ParseError:
        return [], W
    texts, tex_labels, kinds = svg_facts(root)
    units = {norm(t) for t in texts} | {norm(t) for t in tex_labels}
    units.discard("")
    blob = "".join(norm(t) for t in texts) + "".join(norm(t) for t in tex_labels)

    def present(n):
        # 短い文字（1、2、O など）は単独の文字要素として存在することを求める（"120" の中の "1" は数えない）
        return n in units or (len(n) > 2 and n in blob)

    for it in items(sec.get("本質の印", [])):
        if "[?]" in it:
            continue
        tags = [t for t in MARKS if f"[{t}]" in it]
        if not tags:
            W.append(f"本質の印「{it[:30]}」に種類タグが無い（[hatch] [dashed] [open-point] [dot] [angle] [arrow] [caption]）")
        for t in tags:
            if t == "caption":
                m = re.search(r"[<〈＜]\s*図?[^>〉＞]*[>〉＞]", it)
                if m and not present(norm(m.group(0))):
                    W.append(f"仕様の図題「{m.group(0)}」が SVG に無い")
            elif t not in kinds:
                W.append(f"仕様の印 [{t}]「{it[:30]}」に対応するものが SVG に見当たらない")

    spec_labels = []
    for it in items(sec.get("文字", [])):
        for m in re.findall(r"`([^`]+)`", it):
            spec_labels.append(m)
    spec_blob = "".join(norm(s) for s in spec_labels)
    for s in spec_labels:
        n = norm(s)
        if n and not present(n):
            W.append(f"仕様の文字「{s}」が SVG に無い（薄い印・小さな添字も描く）")
    # 勝手な追加: SVG の文字が仕様に無い
    for t in texts:
        n = norm(t)
        if n and n not in spec_blob:
            W.append(f"SVG の文字「{t}」が意図仕様の「文字」に無い（書いていない文字を足していないか）")
    # [?] の候補を描いていないか
    for it in items(sec.get("読めない", [])):
        for cand in re.findall(r"[「`]([^」`]+)[」`]", it):
            n = norm(cand)
            if n and present(n) and n not in spec_blob:
                W.append(f"判読できない印の候補「{cand}」を描いている（[?] は描かず、仕様に残す）")
    return [], W


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    E, Wn = check(*sys.argv[1:3])
    for m in Wn:
        print(f"WARN  {m}")
    print("OK" if not Wn else "")
    sys.exit(1 if Wn else 0)
