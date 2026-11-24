// The iframe blocks scripts in the input SVG. Measure after its layout is ready.
const doc = document.querySelector("iframe").contentDocument;
const svg = doc.querySelector("svg");
const labels = [];
const seen = new Set();
for (const [index, text] of Array.from(svg.querySelectorAll("text")).entries()) {
    if (!text.getNumberOfChars() || text.closest("defs, symbol, clipPath, marker, mask, pattern")) continue;
    const style = doc.defaultView.getComputedStyle(text);
    if (style.visibility !== "visible" || style.opacity === "0") continue;
    const group = text.closest("g[data-math-label][data-label-placement]");
    const target = group || text;
    if (seen.has(target)) continue;
    const {x, y, width, height} = target.getBoundingClientRect();
    if (!width || !height) continue;
    seen.add(target);
    const first = text.getStartPositionOfChar(0);
    const anchor = style.textAnchor;
    const start = text.x.baseVal.numberOfItems ? text.x.baseVal.getItem(0).value : first.x;
    const baseline = text.y.baseVal.numberOfItems ? text.y.baseVal.getItem(0).value : first.y;
    const size = parseFloat(style.fontSize);
    const ctm = text.getScreenCTM();
    const placement = group ? group.dataset.labelPlacement.split(" ") : [start, baseline, size, anchor];
    labels.push({index, bbox_px: [x, y, width, height], x: +placement[0], y: +placement[1],
        scaleY: Math.hypot(ctm.c, ctm.d), size: +placement[2], anchor: placement[3],
        style: style.fontStyle, family: style.fontFamily,
        chemistry: !!text.closest('[data-role="atom-label"], [data-role="chem-structure"], [data-chem="structure"]'),
        tex: group?.dataset.mathLabel, current: target.textContent.trim(),
        transform: target.getAttribute("transform")});
}
document.querySelector("pre").textContent = JSON.stringify(labels);
