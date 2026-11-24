"""Measure label boxes in Chrome for diagnostics, separately from the official render."""
import html
import json
import math
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

import numpy as np

from hsfig import SCRIPT, MIN_TEXT_PX
from lint_svg import is_atom_label_text
from math_diagnostics import math_issues, suggested_tex, text_runs


def measure_labels(chrome, svg, root, geometry, stage):
    elements = root.findall(".//{*}text")
    if not elements:
        return []
    w, h = geometry["intrinsic_size"]
    # A separate sandboxed document has the same intrinsic viewport as the img
    # in the screenshot. Source scripts and network requests stay disabled.
    inner = ('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" '
             'content="default-src \'none\'; style-src \'unsafe-inline\'">'
             f'<style>html,body{{margin:0}}body>svg{{display:block;width:{w}px;height:{h}px}}</style>'
             + re.sub(r"<\?xml[^?]*\?>", "", svg.read_text(encoding="utf-8-sig"), count=1))
    script = Path(__file__).with_name("measure_labels.js").read_text(encoding="utf-8")
    page = stage / "measure.html"
    page.write_text('<!doctype html><meta charset="utf-8"><pre id="boxes"></pre>'
                    f'<iframe sandbox="allow-same-origin" style="border:0;width:{w}px;height:{h}px" '
                    f'srcdoc="{html.escape(inner, quote=True)}"></iframe>'
                    f'<script>window.onload = () => {{ {script} }};</script>', encoding="utf-8")
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
           "--force-device-scale-factor=1", "--dump-dom", f"--user-data-dir={stage/'measure-profile'}"]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        cmd.append("--no-sandbox")
    # Some Chrome versions hang or exit nonzero during teardown *after* a
    # complete dump. Consume the completed measurement like the PNG renderer.
    dump = stage / "measure-dom.html"
    with dump.open("wb") as stream:
        proc = subprocess.Popen([*cmd, page.resolve().as_uri()], stdout=stream, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 45
            while proc.poll() is None and time.monotonic() < deadline:
                if dump.stat().st_size and dump.read_bytes()[-40:].rstrip().endswith(b"</html>"):
                    break
                time.sleep(.15)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
    match = re.search(r'<pre id="boxes">(.*?)</pre>', dump.read_text(encoding="utf-8"), re.S)
    if not match or not match[1]:
        raise ValueError("Chrome could not measure SVG text boxes")
    labels = json.loads(html.unescape(match[1]))
    vx, vy = geometry["origin"]
    ox, oy = geometry["origin_px"]
    sx, sy = geometry["px_per_unit"]
    for label in labels:
        x, y, width, height = label["bbox_px"]
        label["bbox_svg"] = [vx+(x-ox)/sx, vy+(y-oy)/sy, width/sx, height/sy]
        runs = text_runs(elements[label["index"]], label["size"], label["style"], label["family"])
        if "tex" in label:
            label["issues"] = []
        else:
            atom = label["chemistry"] and is_atom_label_text(label["current"])
            label["tex"] = suggested_tex(runs, atom=atom)
            label["issues"] = [msg for msg, _ in math_issues(runs, chem=atom)]
            if label["scaleY"] and any(r.script and r.size * label["scaleY"] < MIN_TEXT_PX - .05 for r in runs):
                label["suggested_size"] = max(label["size"], MIN_TEXT_PX / (SCRIPT * label["scaleY"]))
                label["issues"].append("添字・指数が描画時に12pxを下回る。原図と大きさ・基線を照合する")
    suggest_split_fractions(labels)
    return labels


def suggest_split_fractions(labels):
    """A trailing term above a close, horizontally overlapping short label
    can be a numerator accidentally left on the main expression's baseline.
    Ask to verify the crop before combining these two independently drawn texts.
    """
    for label in labels:
        term = re.search(r"([+−=])\s*([A-Za-z0-9]{1,4})\s*$", label["current"])
        if not term or not label["tex"].startswith("$"):
            continue
        x, y, w, h = label["bbox_px"]
        for other in labels:
            den = other["current"]
            if not re.fullmatch(r"[A-Za-z0-9]{1,3}", den):
                continue
            dx, dy, dw, dh = other["bbox_px"]
            if not (x+.5*w < dx+dw/2 <= x+w+2 and .18*h < dy-y < 1.4*h):
                continue
            prefix, found, _ = label["tex"][:-1].rpartition(term[2])
            if found:
                tex = prefix + r"\frac{" + term[2] + "}{" + den + "}$"
                label["tex"] = tex
                label["issues"].insert(0, f"縦分数の候補。{term[2]} が式の基線に残っている。下の「{den}」と括線を照合し、一緒に組む")
                break


def text_mask(labels, size, intrinsic):
    mask = np.zeros((size[1], size[0]), dtype=bool)
    for label in labels:
        x, y, w, h = label["bbox_px"]
        left, top = max(0, math.floor(x)), max(0, math.floor(y))
        right = max(0, math.ceil(min(x+w, intrinsic[0])))
        bottom = max(0, math.ceil(min(y+h, intrinsic[1])))
        mask[top:bottom, left:right] = True
    return mask


def feedback_label(region, labels, residual):
    x, y, w, h = region["bbox"]
    hits = []
    for label in labels:
        a, b, c, d = label["bbox_px"]
        left, top = max(0, math.floor(a)-x), max(0, math.floor(b)-y)
        right, bottom = min(w, math.ceil(a+c)-x), min(h, math.ceil(b+d)-y)
        if right > left and bottom > top:
            overlap = int(residual[top:bottom, left:right].sum())
            if overlap:
                hits.append((label, overlap))
    if not hits:
        return None
    # Prefer a concrete typography issue when it accounts for a substantial
    # portion of the text residual, not an incidental one-pixel intersection.
    peak = max(count for _, count in hits)
    label, _ = max((hit for hit in hits if hit[1] >= peak * .25),
                   key=lambda hit: (bool(hit[0]["issues"]), hit[1]))
    issue = "。".join(label["issues"]) or "文字付近に残差がある。クロップで字形・基線・位置を照合する"
    tex = label["tex"]
    anchor = shlex.quote(label["anchor"])
    size = label.get("suggested_size", label["size"])
    command = (f'python3 "$S/math_label.py" --x {label["x"]:g} --y {label["y"]:g} '
               f'--size {size:g} --anchor {anchor} -- {shlex.quote(tex)}')
    return dict(current=label["current"], bbox_svg=label["bbox_svg"], diagnosis=issue,
                tex=tex, command=command, transform=label["transform"])
