"""Diagnostic coordinates, images and edit hints for a completed fidelity score."""
import json
import re

from PIL import Image, ImageDraw, ImageFont

from render_png import svg_size


MISSING = (206, 91, 0)
EXTRA = (174, 45, 133)
MATCH = (0, 102, 108)
INK = (27, 43, 64)
INSTRUCTION = ("未達なら今回は上位1〜2件だけ直す。図全体に suggested_shift を適用せず、"
               "全体の線を引き直さない。公式の採点は毎回無補正。")


def layout(svg, root, viewport):
    """Invert the root viewBox transform inside the renderer's actual img box."""
    w, h = svg_size(svg)
    value = root.get("viewBox")
    vb = list(map(float, re.split(r"[\s,]+", value.strip()))) if value else None
    vx, vy, vw, vh = vb if vb else (0, 0, w, h)
    if vw <= 0 or vh <= 0:
        raise ValueError("viewBox dimensions must be positive")
    sx, sy = w / vw, h / vh
    left = top = 0.0
    aspect = (root.get("preserveAspectRatio") or "xMidYMid meet").split()
    if aspect[:1] == ["defer"]:
        aspect = aspect[1:]
    if aspect and aspect[0] != "none":
        scale = max(sx, sy) if aspect[1:] == ["slice"] else min(sx, sy)
        align = aspect[0]
        left = (w - vw * scale) * (1 if "xMax" in align else 0.5 if "xMid" in align else 0)
        top = (h - vh * scale) * (1 if "YMax" in align else 0.5 if "YMid" in align else 0)
        sx = sy = scale
    formula = ("画面とSVGが同寸で縦横をそのまま写すとき、user_x = vx + px * vw / viewport_w、"
               "user_y = vy + py * vh / viewport_h。寸法が違えば分母にはSVG固有寸法を使う。")
    mapping = (f"この図では x = {vx:g} + (px − {left:g}) / {sx:g}、"
               f"y = {vy:g} + (py − {top:g}) / {sy:g}。右・下が正。"
               "固有寸法の外には編集座標がない。境界をまたぐ矩形は内側だけを示す。")
    return dict(viewBox=vb, render_size=list(viewport), intrinsic_size=[w, h],
                origin=[vx, vy], origin_px=[left, top], px_per_unit=[sx, sy],
                formula=formula, mapping=mapping)


def locate(region, geometry):
    x, y, w, h = region["bbox"]
    iw, ih = geometry["intrinsic_size"]
    width = min(x + w, iw) - x
    height = min(y + h, ih) - y
    vx, vy = geometry["origin"]
    left, top = geometry["origin_px"]
    sx, sy = geometry["px_per_unit"]
    box = None
    canvas = "outside"
    if width > 0 and height > 0:
        box = [vx + (x-left)/sx, vy + (y-top)/sy, width/sx, height/sy]
        canvas = "inside" if (width, height) == (w, h) else "partial"
    # A translation across the img boundary cannot be made in this coordinate space.
    offset = region["offset_px"] if canvas == "inside" else None
    if offset is None and region["kind"] == "shifted":
        region["kind"] = "both"
    region.update(bbox_px=region["bbox"], bbox_svg=box, canvas=canvas, offset_px=offset,
                  offset_svg=[offset[0]/sx, offset[1]/sy] if offset else None)


def label_font():
    for face in ("/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "meiryo.ttc"):
        try:
            return ImageFont.truetype(face, 15), True
        except OSError:
            continue
    return ImageFont.load_default(), False


def save_crop(source, rendered, difference, region, dest, font, japanese):
    x, y, w, h = region["bbox"]
    box = (max(0, x-8), max(0, y-8), min(source.width, x+w+8), min(source.height, y+h+8))
    labels = ("原図", "SVG 描画", "差分") if japanese else ("Source", "SVG render", "Difference")
    cw, ch = box[2]-box[0], box[3]-box[1]
    zoom = 3 if max(cw, ch) <= 120 else 2 if max(cw, ch) <= 300 else 1
    panel = max(cw*zoom, 88)
    sheet = Image.new("RGB", (3*(panel+8)+8, ch*zoom+38), "#eff2f4")
    draw = ImageDraw.Draw(sheet)
    for i, (img, label) in enumerate(zip((source, rendered, difference), labels)):
        left = 8+i*(panel+8)
        draw.text((left, 5), label, font=font, fill=INK)
        crop = img.crop(box).resize((cw*zoom, ch*zoom), Image.Resampling.NEAREST)
        sheet.paste(crop, (left, 30))
    sheet.save(dest)


def save_overlay(difference, regions, dest, font, japanese):
    labels = (("橙　原図のみ／不足", "赤紫　SVGのみ／余分", "青緑　一致") if japanese
              else ("Missing (source only)", "Extra (SVG only)", "Match"))
    widths = [int(font.getlength(label))+36 for label in labels]
    size = (max(difference.width, sum(widths)), difference.height+36)
    sheet = Image.new("RGB", size, "white")
    sheet.paste(difference)
    draw = ImageDraw.Draw(sheet)
    boxes = []
    for region in regions:
        x, y, w, h = region["bbox"]
        draw.rectangle((x, y, x+w-1, y+h-1), outline=INK)
        boxes.append((x, y, w, h))
    badges = []
    for r, (x, y, w, h) in zip(regions, boxes):
        label = str(r["id"])
        bw, bh = int(font.getlength(label))+6, 19
        choices = [(x, y-bh), (x+w, y), (x-bw, y), (x, y+h), (x, y)]
        candidates = [(min(max(a, 0), sheet.width-bw), max(0, min(b, difference.height-bh)))
                      for a, b in choices]
        def overlaps(pos):
            a, b = pos
            return sum(max(0, min(a+bw, c+e)-max(a,c)) * max(0, min(b+bh, d+f)-max(b,d))
                       for c, d, e, f in badges + boxes)
        a, b = min(candidates, key=overlaps)
        draw.rectangle((a, b, a+bw-1, b+bh-1), fill=INK)
        draw.text((a+3, b), label, font=font, fill="white")
        badges.append((a, b, bw, bh))
    x, y = 8, difference.height+7
    for color, label, width in zip((MISSING, EXTRA, MATCH), labels, widths):
        draw.rectangle((x, y+3, x+12, y+15), fill=color)
        draw.text((x+19, y), label, font=font, fill=INK)
        x += width
    sheet.save(dest)


def numbers(values):
    return "[" + ", ".join(f"{v:.4f}".rstrip("0").rstrip(".") for v in values) + "]"


def hint(region):
    if region["canvas"] == "outside":
        return "SVGキャンバス外。原図とSVGの幅・高さを照合する。"
    if region["kind"] == "shifted":
        return f"ずれ。対応する線を約 {numbers(region['offset_svg'])} ユーザー単位だけ動かしてみる。"
    hints = {"missing": "不足。橙の位置に原図の線を足すか、近くの線をそこへ移す。",
             "extra": "余分。赤紫の線を消すか、原図の位置へ移す。",
             "both": "不足と余分が混在。原図とSVGの端点・字形を比べ、違う箇所だけ直す。"}
    prefix = "一部はキャンバス外。 " if region["canvas"] == "partial" else ""
    return prefix + hints[region["kind"]]


def write_feedback(stage, report, geometry, source, rendered, difference):
    font, japanese = label_font()
    save_overlay(difference, report["regions"], stage/"overlay.png", font, japanese)
    (stage/"regions").mkdir()
    scores = {key: report[key] for key in ("iou_norm", "iou_raw", "f1_1px")}
    passed = scores["iou_norm"] >= 0.90
    result = "合格" if passed else "未達"
    lines = [f"# Mode B　{result}（目標 iou_norm ≥ 0.90）", "",
             " ／ ".join(f"{k} {v:.6f}" for k, v in scores.items()), "",
             "合格。修正を終了する。" if passed else INSTRUCTION, "",
             f"viewBox {geometry['viewBox'] or 'なし（1単位＝1 px）'} ／ "
             f"描画画面 {numbers(geometry['render_size'])} px ／ SVG固有寸法 {numbers(geometry['intrinsic_size'])} px",
             geometry["formula"], geometry["mapping"], "",
             "## 修正候補（残差画素数の多い順）", "",
             "番号は overlay.png の枠と対応する。橙は不足、赤紫は余分、青緑は一致。矩形は [左, 上, 幅, 高さ]。", ""]
    if passed:
        lines[4] += " " + INSTRUCTION
    metric = report.get("iou_norm_text")
    diagnostic = f"{metric:.6f}" if metric is not None else "算出対象なし"
    lines.insert(3, f"文字領域の参考値 iou_norm_text {diagnostic}（合否は図全体の iou_norm で判定）")
    if report.get("text_diagnostic_error"):
        lines.insert(4, report["text_diagnostic_error"])
    for r in report["regions"]:
        locate(r, geometry)
        r["crop"] = f"regions/region-{r['id']:02d}.png"
        r["hint"] = hint(r)
        save_crop(source, rendered, difference, r, stage/r["crop"], font, japanese)
        bbox = numbers(r["bbox_svg"]) if r["bbox_svg"] else "対象外"
        offset = numbers(r["offset_svg"]) if r["offset_svg"] else "なし"
        lines.append(f"{r['id']}. **{r['kind']}**　bbox_svg {bbox} ／ 推定移動 {offset} ／ "
                     f"不足 {r['missing_pixels']} px・余分 {r['extra_pixels']} px　"
                     f"[クロップ]({r['crop']})　{r['hint']}")
        label = r.get("label")
        if label:
            lines.extend([f"   - 文字「{label['current']}」 bbox_svg {numbers(label['bbox_svg'])}。"
                          f"{label['diagnosis']}。推奨入力 `{label['tex']}`。",
                          "   - 同じ親要素内で置き換える。" +
                          (f" 元の変換 {label['transform']} を引き継ぐ。" if label["transform"] else ""),
                          "", "     ```sh", "     " + label["command"], "     ```", ""])
        elif (r["kind"] == "missing" and r["canvas"] == "inside"
              and 6 <= r["bbox"][3] <= 32 and 3 <= r["bbox"][2] <= 8*r["bbox"][3]):
            x, y, w, h = r["bbox_svg"]
            lines.append(f"   - 文字大の不足。対応する text は未検出。クロップで文字なら原図から"
                         f"推奨入力を読み取る（例: 変数 v の添字 0 は `$v_0$`）。"
                         f"原図の入力を LABEL に設定し、仮の基線・サイズを合わせる。"
                         f' `python3 "$S/math_label.py" --x {x:g} --y {y+h:g} --size {h:g} -- "$LABEL"`')
    if not report["regions"]:
        lines.append("表示対象の領域はありません。")
    feedback = dict(**scores, iou_norm_text=metric, passed=passed, target=0.90, **geometry,
                    instruction=INSTRUCTION, fixes=report["regions"])
    (stage/"feedback.json").write_text(json.dumps(feedback, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (stage/"feedback.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
