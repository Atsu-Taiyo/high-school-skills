#!/usr/bin/env python3
"""Score an unregistered Mode B SVG against the original printed crop."""
import argparse
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from fidelity_feedback import EXTRA, MATCH, MISSING, layout, write_feedback
from fidelity_labels import feedback_label, measure_labels, text_mask
from render_png import by_chrome, find_chrome
from stroke_fidelity import luminance, measure


def skeleton(mask):
    """Zhang–Suen thinning, including a white border around edge-touching ink."""
    ink = np.pad(mask, 1)
    center = ink[1:-1, 1:-1]
    ring = (ink[:-2, 1:-1], ink[:-2, 2:], ink[1:-1, 2:], ink[2:, 2:],
            ink[2:, 1:-1], ink[2:, :-2], ink[1:-1, :-2], ink[:-2, :-2])
    north, east, south, west = ring[::2]
    while True:
        changed = False
        for phase in (0, 1):
            count = sum(p.astype(np.uint8) for p in ring)
            rises = sum((~p & q).astype(np.uint8) for p, q in zip(ring, ring[1:] + ring[:1]))
            if phase == 0:
                protected = (north & east & south) | (east & south & west)
            else:
                protected = (north & east & west) | (north & south & west)
            remove = center & (count >= 2) & (count <= 6) & (rises == 1) & ~protected
            if remove.any():
                center[remove] = False
                changed = True
        if not changed:
            break
    # Parallel deletion can erase the last 2x2 block of an isolated dot.
    # Retain one central ink pixel in each otherwise vanished component.
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    present = np.bincount(labels[center], minlength=count)
    for label in np.flatnonzero(present[1:] == 0) + 1:
        x, y, w, h = stats[label, :4]
        yy, xx = np.nonzero(labels[y:y+h, x:x+w] == label)
        xx, yy = xx + x, yy + y
        cx, cy = centroids[label]
        i = np.argmin((xx - cx) ** 2 + (yy - cy) ** 2)
        center[yy[i], xx[i]] = True
    return center


def normalized(mask, radius):
    axis = np.arange(-radius, radius + 1, dtype=np.int64)
    disk = axis[:, None] ** 2 + axis ** 2 <= radius ** 2
    return cv2.dilate(skeleton(mask).astype(np.uint8), disk.astype(np.uint8)).astype(bool)


def iou(a, b):
    union = np.count_nonzero(a | b)
    return float(np.count_nonzero(a & b) / union) if union else None


def translation(reference, drawn):
    """Best local integer translation of SVG ink by overlap, with zero padding."""
    reach = 16
    search = np.pad(reference.astype(np.float32), reach)
    overlaps = np.rint(cv2.matchTemplate(search, drawn.astype(np.float32), cv2.TM_CCORR))
    y, x = np.nonzero(overlaps == overlaps.max())
    nearest = np.argmin((x - reach) ** 2 + (y - reach) ** 2)
    gain = int(overlaps.max() - overlaps[reach, reach])
    return int(x[nearest] - reach), int(y[nearest] - reach), gain


def suggested_shift(reference, drawn):
    dx, dy, _ = translation(reference, drawn)
    return dict(dx=dx, dy=dy, applied=False)


def regions(reference, drawn, limit, text_labels=()):
    """Group nearby normalized residuals, counting only actual mismatch pixels."""
    missing, extra = reference & ~drawn, drawn & ~reference
    mismatch = missing | extra
    grouped = cv2.dilate(mismatch.astype(np.uint8), np.ones((5, 5), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(grouped, connectivity=8)
    result = []
    for label in range(1, count):
        x, y, w, h = map(int, stats[label, :4])
        roi = np.s_[y:y+h, x:x+w]
        member = labels[roi] == label
        absent = int(np.count_nonzero(missing[roi] & member))
        added = int(np.count_nonzero(extra[roi] & member))
        bx, by, bw, bh = cv2.boundingRect((mismatch[roi] & member).astype(np.uint8))
        result.append(dict(label=label, bbox=[x+bx, y+by, bw, bh], area=absent+added,
                           missing_pixels=absent, extra_pixels=added,
                           kind="both" if absent and added else "missing" if absent else "extra"))
    result.sort(key=lambda r: (-r["area"], r["bbox"][1], r["bbox"][0]))
    selected = result[:limit]
    for i, region in enumerate(selected, 1):
        label = region.pop("label")
        if text_labels:
            x, y, w, h = region["bbox"]
            crop = np.s_[y:y+h, x:x+w]
            text = feedback_label(region, text_labels, mismatch[crop] & (labels[crop] == label))
            if text:
                region["label"] = text
        region.update(id=i, offset_px=None)
        if region["kind"] == "both":
            # Include the nearby matching ink in this component. A different
            # component inside its bounding rectangle must not vote for a move.
            x, y, w, h = stats[label, :4]
            roi = np.s_[y:y+h, x:x+w]
            support = labels[roi] == label
            dx, dy, gain = translation(reference[roi] & support, drawn[roi] & support)
            # Each new overlapping pixel resolves one missing and one extra pixel.
            if gain >= 4 and 2*gain >= 0.25*region["area"]:
                region.update(kind="shifted", offset_px=[dx, dy])
    return selected


def run(args):
    root = ET.parse(args.svg).getroot()
    if root.get("data-mode", "").upper() == "A":
        raise ValueError("handwritten Mode A figures are outside this scoring loop")
    out = args.out_dir
    names = ("render.png", "overlay.png", "score.json", "feedback.json", "feedback.md")
    inputs = {p.resolve() for p in (args.source, args.svg, args.text_mask) if p}
    if any((out / name).resolve() in inputs for name in names):
        raise ValueError("use an output directory separate from the input files")
    chrome = find_chrome()
    if not chrome:
        raise ValueError("Chrome or Chromium is required")
    out.mkdir(parents=True, exist_ok=True)
    with Image.open(args.source) as original:
        rgba = original.convert("RGBA")
        source_image = Image.new("RGB", original.size, "white")
        source_image.paste(rgba, mask=rgba.getchannel("A"))
        size = original.size
        raw_source = luminance(original) <= args.cutoff
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        stage = Path(tmp)
        by_chrome(chrome, args.svg, stage / "render.png", 1, viewport=size)
        with Image.open(stage / "render.png") as rendered:
            if rendered.size != size:
                raise ValueError(f"Chrome rendered {rendered.size}, expected {size}")
            rendered_image = rendered.convert("RGB")
            raw_drawn = luminance(rendered) <= args.cutoff
        raw = measure(raw_source, raw_drawn)
        ref, drawn = (normalized(mask, args.dilate) for mask in (raw_source, raw_drawn))
        score = iou(ref, drawn)
        if score is None:
            raise ValueError("both skeletons are empty")
        report = dict(iou_norm=score, iou_raw=raw["iou"], f1_1px=raw["f1_1px"],
                      cutoff=args.cutoff, dilate=args.dilate, render_size=list(size),
                      suggested_shift=suggested_shift(ref, drawn))
        geometry = layout(args.svg, root, size)
        try:
            labels = measure_labels(chrome, args.svg, root, geometry, stage)
        except (ValueError, OSError) as exc:
            labels = []
            report["text_diagnostic_error"] = str(exc)
        report["regions"] = regions(ref, drawn, args.max_regions, labels)
        mask = text_mask(labels, size, geometry["intrinsic_size"])
        report["iou_norm_text"] = iou(ref & mask, drawn & mask)
        report["iou_norm_notext"] = (None if "text_diagnostic_error" in report
                                      else iou(ref & ~mask, drawn & ~mask))
        report["text_mask_pixels"] = int(mask.sum())
        if args.text_mask:
            with Image.open(args.text_mask) as mask:
                if mask.size != size:
                    raise ValueError("text mask must have the source dimensions")
                keep = np.asarray(mask.convert("L")) < 128
            report["iou_norm_notext"] = iou(ref & keep, drawn & keep)
        overlay = np.full((*ref.shape, 3), 255, dtype=np.uint8)
        overlay[ref & drawn] = MATCH
        overlay[ref & ~drawn] = MISSING
        overlay[drawn & ~ref] = EXTRA
        write_feedback(stage, report, geometry, source_image, rendered_image, Image.fromarray(overlay))
        (stage / "score.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8")
        crops = out / "regions"
        new = {p.name for p in (stage / "regions").iterdir()}
        old = {p.name for p in crops.glob("region-*.png")
               if p.stem.removeprefix("region-").isdigit()}
        if crops.is_symlink() or any((crops / n).resolve() in inputs for n in old | new):
            raise ValueError("use an output directory separate from the input files")
        crops.mkdir(exist_ok=True)
        for n in new:
            (stage / "regions" / n).replace(crops / n)
        for n in old - new:
            (crops / n).unlink()
        for name in names:
            (stage / name).replace(out / name)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "svg", "out-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--cutoff", type=int, default=200)
    parser.add_argument("--dilate", type=int, default=2)
    parser.add_argument("--max-regions", type=int, default=12)
    parser.add_argument("--text-mask", type=Path, help="white excludes label regions from optional score")
    args = parser.parse_args()
    if not 0 <= args.cutoff <= 255 or min(args.dilate, args.max_regions) < 0:
        parser.error("cutoff must be 0..255, dilate and max-regions must be nonnegative")
    try:
        report = run(args)
    except (ValueError, OSError, RuntimeError, ET.ParseError) as exc:
        parser.exit(2, f"scoring error: {exc}\n")
    passed = report["iou_norm"] >= 0.90
    diagnostic = report["iou_norm_text"]
    text_score = f"{diagnostic:.6f}" if diagnostic is not None else "n/a"
    print(f"{'PASS' if passed else 'BELOW'} iou_norm={report['iou_norm']:.6f} "
          f"iou_raw={report['iou_raw']:.6f} f1_1px={report['f1_1px']:.6f} iou_norm_text={text_score} {args.out_dir}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
