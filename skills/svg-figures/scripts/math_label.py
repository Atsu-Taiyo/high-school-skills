#!/usr/bin/env python3
"""Typeset a short TeX-like label at an SVG baseline (no external dependencies)."""
import argparse
import math
from xml.sax.saxutils import quoteattr

from hsfig import FONT, baseline_label

EXAMPLES = (
    r"$p_0+\frac{Mg}{S}$", r"$\mathrm{P}_{2N-1}$", r"$V_A=A\{V(z)-V_L\}$",
    "(張力 $T$)", r"$\vec{F}$", r"$\frac{1}{2}mv^2$",
)


def label_svg(text, x, y, size, anchor="start"):
    """Return an embeddable group. x and y are SVG units, y is the baseline."""
    if anchor not in ("start", "middle", "end"):
        raise ValueError("anchor must be start, middle or end")
    if not all(math.isfinite(v) for v in (x, y, size)) or size <= 0:
        raise ValueError("coordinates must be finite and size must be positive")
    body = baseline_label(text, x, y, size, anchor, strict=True)
    return (f'<g data-math-label={quoteattr(text)} font-family={quoteattr(FONT)} '
            f'data-label-placement="{x:g} {y:g} {size:g} {anchor}" font-style="normal">{body}</g>')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("text", nargs="?")
    p.add_argument("--list-examples", action="store_true")
    p.add_argument("--x", type=float, default=0)
    p.add_argument("--y", type=float, default=0)
    p.add_argument("--size", type=float, default=16)
    p.add_argument("--anchor", choices=("start", "middle", "end"), default="start")
    args = p.parse_args()
    if args.list_examples:
        print("\n".join(EXAMPLES))
    elif args.text is None:
        p.error("provide a label or --list-examples")
    else:
        try:
            print(label_svg(args.text, args.x, args.y, args.size, args.anchor))
        except ValueError as exc:
            p.error(str(exc))


if __name__ == "__main__":
    main()
