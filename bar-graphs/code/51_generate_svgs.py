#!/usr/bin/env python3
"""
51_generate_svgs.py — Grouped bar chart of the top-N cell types by
anatomical structure (AS). One group per cell type, one bar per AS,
bars colored by AS. Cell types are the top N by organ-wide cell count.

Reads:  config.yaml (organ / sex / side / tool)
        outputs/annotated organs/<organ>/json/<stem>_distribution.json
Writes: outputs/annotated organs/<organ>/svg/without-legend/<name>-without-legend.svg
            (exact physical size, default 1.384in square)
        outputs/annotated organs/<organ>/svg/with-legend/<name>-with-legend.svg
            (same chart with the AS swatch legend underneath)
"""

from __future__ import annotations

import json
import math
import sys
from html import escape
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared scripts"))
sys.path.insert(0, str(Path(__file__).parent))
from shared import load_config, resolve_glb_filename, canonicalize_cell_label
from palette import OTHER_COLOR

# =============================================================================
# DEFAULTS (every key can be overridden in config.yaml -> bar_graph)
# =============================================================================

TOP_N_CELL_TYPES = 5
WIDTH_IN, HEIGHT_IN, DPI = 1.384, 1.384, 300
SHOW_TITLE = True
SHOW_VALUES = False       # % label above each bar
OMIT_BELOW_PCT = 2.0      # skip bars under this within-AS %
MAX_LABEL_LINES = 8       # category labels truncated past this
LABEL_WRAP_CHARS = 12     # narrowest label wrap tried (characters per line)
LEGEND_COLUMNS = 1

# One text size for everything (title, axes, category labels, legend), in
# px at 300dpi, so all text matches.
FONT_PX = 9
GROUP_GAP_BARS = 1.5      # gap between cell-type sets, in bar widths; bars are sized to fill the plot
BAR_ALIGN = "center"     # drawn bars sit together in their set's slot: "center" or "left"
LEGEND_SWATCH_RATIO = 0.6 # legend square size relative to FONT_PX

# Optional per-organ override of the cell types plotted. Without an entry,
# an organ uses its top-N cell types by organ-wide count.
CELL_TYPE_OVERRIDES: Dict[str, List[str]] = {
    "heart": ["Atrial Cardiomyocyte", "pericyte", "fibroblast",
              "capillary endothelial cell", "Ventricular cardiomyocyte"],
}
# A5 AS color scheme: AS ranked by total cell count, highest first -> index 0.
AS_PALETTE: List[str] = [
    "#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3",
    "#fdb462", "#b3de69", "#fccde5", "#d9d9d9", "#bc80bd",
]

BG_COLOR    = "#FAF8F5"
TEXT_COLOR  = "#171616"
MUTED_COLOR = "#444444"
GRID_COLOR  = "#ACA8A8"
AXIS_COLOR  = "#444444"
# PostScript names first: Illustrator matches fonts by these (BentonSans-Book.ttf / BentonSans-Bold.ttf).
FONT_FAMILY = "BentonSans-Book, 'BentonSans Book', 'Benton Sans', Arial, Helvetica, sans-serif"
FONT_FAMILY_BOLD = "BentonSans-Bold, 'BentonSans Bold', 'Benton Sans', Arial, Helvetica, sans-serif"

# All pixel constants below are tuned for a 1.384in square at 300dpi and
# scale with the canvas.
REF_SIDE_PX = 1.384 * 300


# =============================================================================
# Settings / data
# =============================================================================

def canonical_pct_within_as(dist_data: dict, as_label: str) -> Dict[str, float]:
    """canonical cell label -> within-AS percentage (0-100)."""
    result: Dict[str, float] = {}
    for label, frac in dist_data["per_as_normalized"].get(as_label, {}).items():
        key = canonicalize_cell_label(label)
        result[key] = result.get(key, 0.0) + 100.0 * frac
    return result


def organ_counts(dist_data: dict) -> Dict[str, float]:
    counts: Dict[str, float] = {}
    for label, n in dist_data.get("organ_cell_counts", {}).items():
        key = canonicalize_cell_label(label)
        counts[key] = counts.get(key, 0.0) + n
    return counts


def pick_cell_types(dist_data: dict, top_n: int, override: List[str]) -> List[str]:
    counts = organ_counts(dist_data)
    if not override:
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        return [label for label, _n in ranked[:top_n]]
    by_lower = {k.lower(): k for k in counts}
    picked = []
    for name in override:
        key = by_lower.get(name.strip().lower())
        if key is None:
            print(f"  Warning: override cell type not found in organ: {name}")
        else:
            picked.append(key)
    return picked


def pick_as_labels(dist_data: dict) -> List[str]:
    """AS ordered by total cell count, highest first (matches color order)."""
    totals = dist_data.get("as_total_counts", {})
    labels = [a for a in dist_data["as_labels"] if a in dist_data.get("per_as_normalized", {})]
    return sorted(labels, key=lambda a: totals.get(a, 0.0), reverse=True)


def assign_as_colors(dist_data: dict, as_labels: List[str]) -> Dict[str, str]:
    """Color by AS rank in total cell count (highest first)."""
    totals = dist_data.get("as_total_counts", {})
    ranked = sorted(as_labels, key=lambda a: totals.get(a, 0.0), reverse=True)
    if len(ranked) > len(AS_PALETTE):
        print(f"  Warning: {len(ranked)} AS but only {len(AS_PALETTE)} colors; colors repeat.")
    return {a: AS_PALETTE[i % len(AS_PALETTE)] for i, a in enumerate(ranked)}


def apply_as_color_overrides(
    as_colors: Dict[str, str], overrides: Dict[str, str],
) -> Dict[str, str]:
    """Apply explicit AS colors while retaining palette colors as fallback."""
    for as_label, color in overrides.items():
        if as_label in as_colors:
            as_colors[as_label] = str(color)
    return as_colors


def build_groups(
    dist_data: dict, categories: List[str], as_labels: List[str],
) -> Dict[str, List[Tuple[str, float]]]:
    """category -> [(as_label, pct), ...] in as_labels order."""
    pct_by_as = {a: canonical_pct_within_as(dist_data, a) for a in as_labels}
    return {c: [(a, pct_by_as[a].get(c, 0.0)) for a in as_labels] for c in categories}


# =============================================================================
# SVG helpers
# =============================================================================

def wrap_text(text: str, max_width_px: float, font_size: float, ratio: float = 0.55) -> List[str]:
    max_chars = max(1, int(max_width_px / (font_size * ratio)))
    lines: List[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def upper_first(label: str) -> str:
    return label[:1].upper() + label[1:] if label else label


def svg_root(w_px: float, h_px: float, w_in: float, h_in: float) -> str:
    # Explicit "in" units: Illustrator reads unitless width/height as points.
    return (
        f'<svg viewBox="0 0 {w_px:.1f} {h_px:.1f}" width="{w_in:.4f}in" height="{h_in:.4f}in" '
        f'xmlns="http://www.w3.org/2000/svg" font-family="{FONT_FAMILY}">'
        f'<rect x="0" y="0" width="{w_px:.1f}" height="{h_px:.1f}" fill="{BG_COLOR}"/>'
    )


# =============================================================================
# Bar chart
# =============================================================================

def build_bar_body(
    groups: Dict[str, List[Tuple[str, float]]],
    categories: List[str],
    as_labels: List[str],
    as_colors: Dict[str, str],
    title: str,
) -> str:
    w_px, h_px = WIDTH_IN * DPI, HEIGHT_IN * DPI
    sc = min(w_px, h_px) / REF_SIDE_PX

    left_pad, right_pad = 38 * sc, 8 * sc
    bar_gap = 1 * sc
    font = FONT_PX * sc
    label_line_h = font * 1.15
    cos45 = 0.7071

    n_groups, n_bars = len(categories), len(as_labels)
    plot_w = w_px - left_pad - right_pad
    # Every set gets an equal slot wide enough for all AS bars; bars that
    # are drawn are packed together inside the slot (no empty gaps).
    # Bar width is solved so n slots plus (n-1) gaps of GROUP_GAP_BARS bar
    # widths exactly fill the plot width.
    drawn = {c: [(a, p) for a, p in groups[c] if p >= OMIT_BELOW_PCT] for c in categories}
    bar_w = max(0.5, (plot_w - n_groups * (n_bars - 1) * bar_gap) / (n_groups * n_bars + (n_groups - 1) * GROUP_GAP_BARS))
    group_w = n_bars * bar_w + (n_bars - 1) * bar_gap
    group_gap = GROUP_GAP_BARS * bar_w
    slot_xs = [left_pad + i * (group_w + group_gap) for i in range(n_groups)]
    group_ws, group_xs = [], []
    for slot_x, c in zip(slot_xs, categories):
        k = len(drawn[c])
        w = k * bar_w + max(0, k - 1) * bar_gap
        group_ws.append(w)
        group_xs.append(slot_x + (group_w - w) / 2 if BAR_ALIGN == "center" else slot_x)

    title_lines = wrap_text(title, w_px - 16 * sc, font) if SHOW_TITLE else []
    plot_top = (len(title_lines) * font * 1.3 + 8 * sc) if title_lines else 10 * sc

    def wrap_all(chars: int) -> Dict[str, List[str]]:
        out_w = {}
        for c in categories:
            lines = wrap_text(c, chars * font * 0.55, font)
            if len(lines) > MAX_LABEL_LINES:
                lines = lines[:MAX_LABEL_LINES]
                lines[-1] = lines[-1].rstrip() + "…"
            out_w[c] = lines
        return out_w

    def stack_for(w: Dict[str, List[str]]) -> float:
        return max(
            (max(len(l) for l in v) * font * 0.55 + (len(v) - 1) * label_line_h) * cos45 + font
            for v in w.values()
        )

    def anchor_x(gi: int, n_lines: int) -> float:
        center = slot_xs[gi] + group_w / 2
        return center - (n_lines - 1) * label_line_h * cos45 / 2 + font * 0.35

    def off_canvas(w: Dict[str, List[str]]) -> bool:
        # Rotated labels run down-left from their anchor; keep every line on canvas.
        for gi, c in enumerate(categories):
            v = w[c]
            for k, line in enumerate(v):
                end_x = anchor_x(gi, len(v)) + k * label_line_h * cos45
                start_x = end_x - len(line) * font * 0.55 * cos45
                if start_x < 2 * sc or end_x > w_px - 2 * sc:
                    return True
        return False

    # Pick the wrap width that gives the shortest label stack without
    # truncating labels or clipping the first one.
    best = None
    for chars in range(LABEL_WRAP_CHARS, max(31, LABEL_WRAP_CHARS + 1)):
        w = wrap_all(chars)
        truncated = any(l.endswith("…") for v in w.values() for l in v)
        if truncated or off_canvas(w):
            continue
        st = stack_for(w)
        if best is None or st < best[0]:
            best = (st, w)
    wrapped = best[1] if best else wrap_all(LABEL_WRAP_CHARS)
    label_stack = stack_for(wrapped)
    tick_gap = 5 * sc
    plot_bottom = h_px - (tick_gap + label_stack + 4 * sc)
    plot_h = plot_bottom - plot_top

    x0 = left_pad
    x1 = slot_xs[-1] + group_w
    max_pct = max((p for e in groups.values() for _a, p in e), default=0.0)
    axis_max = max(5.0, (int(max_pct / 5) + 1) * 5)

    def y_for(p: float) -> float:
        return plot_bottom - (p / axis_max) * plot_h

    out = []
    for i, line in enumerate(title_lines):
        out.append(
            f'<text x="{(x0 + x1) / 2:.1f}" y="{font * 1.1 + i * font * 1.3:.1f}" font-size="{font:.2f}" '
            f'font-family="{FONT_FAMILY_BOLD}" fill="{TEXT_COLOR}" text-anchor="middle">{escape(line)}</text>'
        )

    step = axis_max / 5
    for i in range(6):
        p = i * step
        y = y_for(p)
        out.append(f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x1:.1f}" y2="{y:.1f}" stroke="{GRID_COLOR}" stroke-width="{0.6 * sc:.2f}"/>')
        out.append(f'<text x="{x0 - 4 * sc:.1f}" y="{y + font * 0.35:.1f}" font-size="{font:.2f}" fill="{TEXT_COLOR}" text-anchor="end">{p:.0f}%</text>')
    # Keep the y-axis title clear of the tick values.
    ax_x, ax_y = 20 * sc, (plot_top + plot_bottom) / 2
    out.append(f'<text x="{ax_x:.1f}" y="{ax_y:.1f}" font-size="{font:.2f}" fill="{TEXT_COLOR}" text-anchor="middle" transform="rotate(-90 {ax_x:.1f} {ax_y:.1f})">Cells (%)</text>')
    out.append(f'<line x1="{x0:.1f}" y1="{plot_top:.1f}" x2="{x0:.1f}" y2="{plot_bottom:.1f}" stroke="{AXIS_COLOR}" stroke-width="{0.8 * sc:.2f}"/>')
    out.append(f'<line x1="{x0:.1f}" y1="{plot_bottom:.1f}" x2="{x1:.1f}" y2="{plot_bottom:.1f}" stroke="{AXIS_COLOR}" stroke-width="{0.8 * sc:.2f}"/>')

    for gi, cat in enumerate(categories):
        gx = group_xs[gi]
        for bi, (a, p) in enumerate(drawn[cat]):
            bx, by = gx + bi * (bar_w + bar_gap), y_for(p)
            out.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{plot_bottom - by:.1f}" fill="{as_colors[a]}"/>')
            if SHOW_VALUES:
                out.append(f'<text x="{bx + bar_w / 2:.1f}" y="{by - 2 * sc:.1f}" font-size="{font:.2f}" fill="{TEXT_COLOR}" text-anchor="middle">{p:.0f}</text>')
        lines = wrapped[cat]
        ax = anchor_x(gi, len(lines))
        ay = plot_bottom + tick_gap
        out.append(f'<g transform="translate({ax:.1f} {ay:.1f}) rotate(-45)">')
        for li, line in enumerate(lines):
            out.append(f'<text x="0" y="{font * 0.8 + li * label_line_h:.1f}" font-size="{font:.2f}" fill="{TEXT_COLOR}" text-anchor="end">{escape(line)}</text>')
        out.append("</g>")

    # Place the x-axis title below the complete rotated-label stack.
    x_axis_title_y = plot_bottom + tick_gap + label_stack + font * 1.35
    out.append(f'<text x="{(x0 + x1) / 2:.1f}" y="{x_axis_title_y:.1f}" font-size="{font:.2f}" fill="{TEXT_COLOR}" text-anchor="middle">Cell type</text>')

    return "".join(out), w_px, h_px


# =============================================================================
# Legend (separate file, one swatch per AS)
# =============================================================================

def build_legend_body(as_labels: List[str], as_colors: Dict[str, str]) -> Tuple[str, float, float]:
    font = FONT_PX
    cols = max(1, min(LEGEND_COLUMNS, len(as_labels)))
    rows = math.ceil(len(as_labels) / cols)
    names = [upper_first(a) for a in as_labels]
    pad, swatch, line_h = font * 0.6, font * LEGEND_SWATCH_RATIO, font * 1.5
    # Fill column by column so each column is only as wide as its own longest label.
    col_of = [i // rows for i in range(len(names))]
    col_w = [
        max(len(n) for n, c in zip(names, col_of) if c == ci) * font * 0.55 + swatch + font * 2.0
        for ci in range(max(col_of) + 1)
    ]
    col_x = [pad + sum(col_w[:ci]) for ci in range(len(col_w))]
    w_px = 2 * pad + sum(col_w) - font * 1.4
    h_px = 2 * pad + rows * line_h

    out = []
    for i, (a, name) in enumerate(zip(as_labels, names)):
        c, r = col_of[i], i % rows
        x, y = col_x[c], pad + r * line_h
        out.append(f'<rect x="{x:.1f}" y="{y + (line_h - swatch) / 2:.1f}" width="{swatch:.1f}" height="{swatch:.1f}" fill="{as_colors[a]}"/>')
        out.append(f'<text x="{x + swatch + font * 0.4:.1f}" y="{y + line_h / 2 + font * 0.35:.1f}" font-size="{font:.2f}" fill="{TEXT_COLOR}">{escape(name)}</text>')
    return "".join(out), w_px, h_px


def compose_svg(chart: Tuple[str, float, float], legend: Tuple[str, float, float] = None) -> str:
    """Chart alone, or chart with the legend centered underneath."""
    body, cw, ch = chart
    if legend is None:
        return svg_root(cw, ch, cw / DPI, ch / DPI) + body + "</svg>"
    lbody, lw, lh = legend
    gap = 10
    w, h = max(cw, lw), ch + gap + lh
    return (
        svg_root(w, h, w / DPI, h / DPI)
        + f'<g transform="translate({(w - cw) / 2:.1f} 0)">{body}</g>'
        + f'<g transform="translate({(w - lw) / 2:.1f} {ch + gap:.1f})">{lbody}</g>'
        + "</svg>"
    )


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    config = load_config(Path(__file__).parent.parent / "config.yaml")
    bar_graph_cfg = config.get("bar_graph", {}) or {}
    global WIDTH_IN, FONT_PX, HEIGHT_IN, MAX_LABEL_LINES, LABEL_WRAP_CHARS
    WIDTH_IN = float(bar_graph_cfg.get("width_in", WIDTH_IN))
    FONT_PX = float(bar_graph_cfg.get("font_px", FONT_PX))
    HEIGHT_IN = float(bar_graph_cfg.get("height_in", HEIGHT_IN))
    MAX_LABEL_LINES = int(bar_graph_cfg.get("max_label_lines", MAX_LABEL_LINES))
    LABEL_WRAP_CHARS = int(bar_graph_cfg.get("label_wrap_chars", LABEL_WRAP_CHARS))

    organ_name = config["organ"]["name"]
    organ_sex = config["organ"]["sex"]
    tool = config["filters"]["tool"]
    glb_filename = (config["organ"].get("glb_filename") or "").strip()
    organ_side = (config["organ"].get("side") or "").strip()
    if not glb_filename:
        glb_filename = resolve_glb_filename(organ_name, organ_sex, organ_side)
    stem = Path(glb_filename).stem

    base_folder = Path(config["output"]["amended_folder"]) / organ_name.lower()
    distribution_path = base_folder / "json" / f"{stem}_distribution.json"
    if not distribution_path.exists():
        raise FileNotFoundError(
            f"Distribution JSON not found: {distribution_path}. "
            "Run 20_fetch_cell_distribution.py first."
        )
    dist_data = json.loads(distribution_path.read_text(encoding="utf-8"))

    organ_key = organ_name.lower()
    categories = pick_cell_types(dist_data, TOP_N_CELL_TYPES, CELL_TYPE_OVERRIDES.get(organ_key, []))
    as_labels = pick_as_labels(dist_data)
    as_colors = assign_as_colors(dist_data, as_labels)
    as_colors = apply_as_color_overrides(
        as_colors,
        bar_graph_cfg.get("as_colors", {}) or {},
    )
    if not categories or not as_labels:
        raise ValueError("No cell types or anatomical structures to plot.")

    print(f"Cell types ({len(categories)}): {categories}")
    print(f"Anatomical structures ({len(as_labels)}): {as_labels}")

    groups = build_groups(dist_data, categories, as_labels)
    title = f"{organ_name.title()} — {tool.title()} — {organ_sex.title()}: cell type composition by AS"
    chart = build_bar_body(groups, categories, as_labels, as_colors, title)
    legend = build_legend_body(as_labels, as_colors)

    uberon_id = dist_data.get("uberon_id", "")
    name = "-".join(p for p in [stem, uberon_id, f"top{len(categories)}", tool.lower(), "bar-graph"] if p)
    name += str(bar_graph_cfg.get("output_suffix", ""))

    for folder, suffix, svg in (
        ("without-legend", "without-legend", compose_svg(chart)),
        ("with-legend", "with-legend", compose_svg(chart, legend)),
    ):
        out_path = base_folder / "svg" / folder / f"{name}-{suffix}.svg"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(svg, encoding="utf-8")
        print(f"Saved SVG: {out_path}")


if __name__ == "__main__":
    main()
