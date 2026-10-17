"""Text contrast in a rendered page (WCAG 2.1 AA, success criterion 1.4.3), measured in the browser.

Every visible text element is compared with its effective background: the colours of the element and its ancestors,
composited from the page up. Large text (at least 24 px, or 18.66 px bold) needs 3:1, other text 4.5:1. Text over a
background image (the hatched "no reading" swatch, the loading shimmer) and disabled controls are skipped, as WCAG
allows for inactive controls. Chart text is drawn on a canvas and is checked in the screenshots instead.
"""

from __future__ import annotations

_SCRIPT = r"""
() => {
  const parse = (c) => {
    const m = /rgba?\(([^)]+)\)/.exec(c || "");
    if (!m) return null;
    const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number);
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  };
  const over = (top, bottom) => [0, 1, 2].map((i) => top[i] * top[3] + bottom[i] * (1 - top[3])).concat([1]);
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const background = (el) => {
    const layers = [];
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== "none") return null;
      const c = parse(cs.backgroundColor);
      if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; }
    }
    let acc = [255, 255, 255, 1];
    for (let i = layers.length - 1; i >= 0; i--) acc = over(layers[i], acc);
    return acc;
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) return false;
    if (el.closest("[hidden], .sr-only, button:disabled, option")) return false;
    return el.checkVisibility ? el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) : true;
  };
  const els = new Set(document.querySelectorAll("select, input:not([type=file]):not([type=radio]):not([type=checkbox])"));
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (n.textContent.trim() && n.parentElement) els.add(n.parentElement);
  }
  const fails = [];
  for (const el of els) {
    if (!visible(el)) continue;
    const cs = getComputedStyle(el);
    const bg = background(el);
    const fg0 = parse(cs.color);
    if (!bg || !fg0) continue;
    let opacity = 1;
    for (let e = el; e; e = e.parentElement) opacity *= Number(getComputedStyle(e).opacity);
    const fg = over([fg0[0], fg0[1], fg0[2], fg0[3] * opacity], bg);
    const size = parseFloat(cs.fontSize), bold = Number(cs.fontWeight) >= 700;
    const need = size >= 24 || (size >= 18.66 && bold) ? 3 : 4.5;
    const got = ratio(fg, bg);
    if (got + 1e-6 < need) {
      const text = (el.value || el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 60);
      fails.push(`${got.toFixed(2)}:1 < ${need}:1  "${text}"  (${cs.color} on rgb(${bg.slice(0, 3).map(Math.round)}), ${size}px)`);
    }
  }
  return fails;
}
"""


def contrast_failures(page) -> list[str]:
    """Every visible text element on the page whose contrast is below WCAG AA, as readable lines."""
    return page.evaluate(_SCRIPT)
