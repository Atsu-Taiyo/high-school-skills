#!/usr/bin/env python3
"""Extract a reference ink mask, or compare a registered black-on-white render.

IoU = |R & V| / |R | V| at the original pixel resolution. R is the reviewed
source mask (white = ink). V is the SVG render composited on white, luminance
<= the render cutoff. F1@1px is the harmonic mean of the fractions of V and R
within Euclidean distance <= 1 pixel of the opposite mask. All glyphs count.
Neither metric translates, warps, dilates the measured areas for IoU, nor
counts matching blank paper. Dependencies: Pillow, NumPy, OpenCV.
"""
import argparse
import json

import cv2
import numpy as np
from PIL import Image


def luminance(image):
    rgba = image.convert("RGBA")
    white = Image.new("RGBA", rgba.size, "white")
    return np.asarray(Image.alpha_composite(white, rgba).convert("L"))


def ink_strength(image, light_ink=False, window=13):
    """Contrast from a local background envelope. Output increases with ink."""
    if window < 3 or window % 2 == 0:
        raise ValueError("background window must be odd and >= 3 px")
    gray = luminance(image)
    if light_ink:
        gray = 255 - gray
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (window, window))
    background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    return cv2.subtract(background, gray)


def reference_mask(strength, cutoff, min_area):
    if not 1 <= cutoff <= 255 or min_area < 1:
        raise ValueError("cutoff must be 1..255 and min-area >= 1")
    _, labels, stats, _ = cv2.connectedComponentsWithStats(
        (strength >= cutoff).astype(np.uint8), connectivity=8)
    keep = stats[:, cv2.CC_STAT_AREA] >= min_area
    keep[0] = False
    return keep[labels]


def measure(reference, drawn):
    if reference.shape != drawn.shape:
        raise ValueError("mask and render must have identical native dimensions")
    if not reference.any():
        raise ValueError("reference mask contains no ink")
    intersection = (reference & drawn).sum()
    union = (reference | drawn).sum()

    def covered(source, target):
        if not source.any() or not target.any():
            return 0.0
        distance = cv2.distanceTransform((~target).astype(np.uint8),
                                         cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        return float((distance[source] <= 1.0).mean())

    precision, recall = covered(drawn, reference), covered(reference, drawn)
    return dict(iou=float(intersection / union),
                f1_1px=2 * precision * recall / (precision + recall) if precision + recall else 0,
                precision_1px=precision, recall_1px=recall,
                reference_pixels=int(reference.sum()), render_pixels=int(drawn.sum()))


def compare(original, mask_image, rendered, overlay_path, render_cutoff=200):
    if not 0 <= render_cutoff <= 255:
        raise ValueError("render cutoff must be 0..255")
    if original.size != mask_image.size or original.size != rendered.size:
        raise ValueError("original, mask and PNG must have the same crop and dimensions")
    mask = np.asarray(mask_image.convert("L"))
    if not np.all((mask == 0) | (mask == 255)):
        raise ValueError("reference mask must be binary (255 for ink, 0 for background)")
    reference = mask == 255
    drawn = luminance(rendered) <= render_cutoff
    scores = measure(reference, drawn)
    # Keep the actual photograph beneath the exact (zero-tolerance) residuals.
    base = np.asarray(Image.blend(original.convert("RGB"),
                                  Image.new("RGB", original.size, "white"), 0.62)).copy()
    base[reference & ~drawn] = (206, 91, 0)
    base[drawn & ~reference] = (174, 45, 133)
    base[reference & drawn] = (0, 102, 108)
    Image.fromarray(base).save(overlay_path)
    return scores


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    mask = actions.add_parser("mask", help="make white-ink-on-black reference mask")
    mask.add_argument("original")
    mask.add_argument("output")
    mask.add_argument("--light-ink", action="store_true", help="chalk on a dark board")
    mask.add_argument("--window", type=int, default=13, help="background window in pixels")
    mask.add_argument("--cutoff", type=int, required=True, help="minimum local contrast (1..255)")
    mask.add_argument("--min-area", type=int, default=1, help="smallest retained component in pixels")
    score = actions.add_parser("score", help="score the rendered PNG against a fixed reference")
    for name in ("original", "mask", "render", "overlay"):
        score.add_argument(name)
    score.add_argument("--render-cutoff", type=int, default=200)
    args = parser.parse_args()
    with Image.open(args.original) as original:
        if args.action == "mask":
            ink = ink_strength(original, args.light_ink, args.window)
            ref = reference_mask(ink, args.cutoff, args.min_area)
            Image.fromarray(ref.astype(np.uint8) * 255).save(args.output)
        else:
            with Image.open(args.mask) as ref, Image.open(args.render) as render:
                print(json.dumps(compare(original, ref, render, args.overlay, args.render_cutoff),
                                 indent=2))


if __name__ == "__main__":
    main()
