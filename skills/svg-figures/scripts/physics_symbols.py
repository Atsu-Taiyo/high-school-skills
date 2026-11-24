"""Measured physics symbols in SVG coordinates (x right, y down)."""
from math import hypot


def diode_path(anode, cathode, half_width, through=False):
    """Outline from the base centre to the cathode bar. Leads end at these anchors."""
    ax, ay = anode
    bx, by = cathode
    length = hypot(bx - ax, by - ay)
    if length == 0 or half_width <= 0:
        raise ValueError("a diode needs two distinct anchors and positive width")
    nx, ny = (ay - by) * half_width / length, (bx - ax) * half_width / length
    shape = (f"M{ax+nx:.3f},{ay+ny:.3f} L{bx},{by} L{ax-nx:.3f},{ay-ny:.3f} Z "
             f"M{bx+nx:.3f},{by+ny:.3f} L{bx-nx:.3f},{by-ny:.3f}")
    return shape + (f" M{ax},{ay} L{bx},{by}" if through else "")


def earth_path(x, y, widths, pitch):
    """Horizontal earth bars, beginning at the conductor's endpoint."""
    return " ".join(f"M{x-w/2:g},{y+i*pitch:g} h{w:g}" for i, w in enumerate(widths))


def hatch_path(x, y, width, height, pitch, slope=-1):
    """Parallel straight hatches clipped to an axis-aligned block; slope is dy/dx."""
    if min(width, height, pitch) <= 0 or slope == 0:
        raise ValueError("positive dimensions and nonzero slope required")
    start = min(0, -height / slope)
    stop = width + max(0, -height / slope)
    lines = []
    while start <= stop:
        low, high = sorted((start, start + height / slope))
        a, b = max(0, low), min(width, high)
        if a < b:
            lines.append(f"M{x+a:.3f},{y+(a-start)*slope:.3f} "
                         f"L{x+b:.3f},{y+(b-start)*slope:.3f}")
        start += pitch
    return " ".join(lines)


def ladder_continuation(top, bottom, upper_stub, lower_stub):
    """Rail and two truncated stage branches. Apply the measured dash pattern to this path."""
    def point(p):
        return f"{p[0]:g},{p[1]:g}"

    return (f"M{point(top)} L{point(bottom)} M{point(top)} L{point(upper_stub)} "
            f"M{point(bottom)} L{point(lower_stub)}")


def detector_path(x, y, width, depth):
    """Photodetector with a horizontal receiving face centred at (x, y), and rounded back."""
    r = width / 2
    return f"M{x-r:g},{y:g} h{width:g} v{depth:g} a{r:g},{r:g} 0 0 1 {-width:g},0 Z"
