#!/usr/bin/env python3
"""Trace variable-width ink boundaries in original pixel coordinates.

Use with stroke_fidelity.ink_strength. Clear measured label regions on a COPY
of the strength image first; keep them in the scoring reference. Each layer
may have its own ink level and fill. A compound outline preserves the holes
in loops, open ends, and the observed width on both sides of a junction.
"""
import cv2
import numpy as np


def _outline(points, scale, tolerance):
    vertices = cv2.approxPolyDP(points, tolerance * scale, True).reshape(-1, 2)
    if len(vertices) < 3:
        vertices = points.reshape(-1, 2)
    if len(vertices) < 3:
        return ""
    vertices = (vertices + 0.5) / scale
    # Round only within a fraction of a source pixel of each measured vertex.
    prev = np.roll(vertices, 1, axis=0) - vertices
    nxt = np.roll(vertices, -1, axis=0) - vertices

    def handles(delta):
        distance = np.linalg.norm(delta, axis=1)
        fraction = np.minimum(0.36, 0.65 / np.maximum(distance, 1e-6))
        return vertices + delta * fraction[:, None]

    def point(pair):
        return f"{pair[0]:.2f},{pair[1]:.2f}"

    before, after = handles(prev), handles(nxt)
    path = [f"M{point(before[0])}"]
    for i, vertex in enumerate(vertices):
        if i:
            path.append(f"L{point(before[i])}")
        path.append(f"Q{point(vertex)} {point(after[i])}")
    return "".join(path) + "Z"


def trace_layer(strength, cutoff, min_area=1, tolerance=0.40):
    """Return one SVG path per ink island, with its interior cutouts."""
    from stroke_fidelity import reference_mask

    kept = reference_mask(strength, cutoff, min_area)
    # Retain edge intensities for interpolation, suppress remote noise islands.
    support = cv2.dilate(kept.astype(np.uint8), np.ones((3, 3), np.uint8))
    scale = 4
    fine = cv2.resize(strength * support, None, fx=scale, fy=scale,
                      interpolation=cv2.INTER_CUBIC)
    contours, tree = cv2.findContours((fine >= cutoff).astype(np.uint8),
                                      cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if tree is None:
        return
    for i, (_, _, child, parent) in enumerate(tree[0]):
        if parent >= 0:
            continue
        rings = [_outline(contours[i], scale, tolerance)]
        while child >= 0:
            rings.append(_outline(contours[child], scale, tolerance))
            child = tree[0, child, 0]
        path = "".join(rings)
        if path:
            yield path
