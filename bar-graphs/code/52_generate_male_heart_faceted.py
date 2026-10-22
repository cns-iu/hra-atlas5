#!/usr/bin/env python3
"""Generate the male-heart counterpart of the A5 grouped-by-AS book SVG."""

from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared scripts"))
from shared import canonicalize_cell_label


AS_LABELS = [
    "right cardiac atrium",
    "left cardiac atrium",
    "heart right ventricle",
    "heart left ventricle",
    "interventricular septum",
]
AS_LABELS_FEMALE = AS_LABELS + [
    "Posteromedial head of posterior papillary muscle of left ventricle",
]
AS_COLORS = {
    "right cardiac atrium": "#fdb462",
    "left cardiac atrium": "#fb8072",
    "heart right ventricle": "#ffffb3",
    "heart left ventricle": "#8dd3c7",
    "interventricular septum": "#bebada",
    "Posteromedial head of posterior papillary muscle of left ventricle": "#80b1d3",
}
AS_NAMES = {
    "right cardiac atrium": "Right atrium",
    "left cardiac atrium": "Left atrium",
    "heart right ventricle": "Right ventricle",
    "heart left ventricle": "Left ventricle",
    "interventricular septum": "Interventricular septum",
    "Posteromedial head of posterior papillary muscle of left ventricle": "Posteromedial papillary muscle",
}

BG = "#FAF8F5"
TEXT = "#171616"
MUTED = "#444444"
GRID = "#ACA8A8"
WIDTH = 910.5543202511776
HEIGHT = 540.0
PHYSICAL_WIDTH_IN = 3.0352
PHYSICAL_HEIGHT_IN = 1.8000
# Match the liver SVG's actual plotting rectangle (not its overall canvas).
AXIS_X0 = 108.0
AXIS_X1 = 832.8
PLOT_TOP = 70.0
PLOT_BOTTOM = 365.0
AXIS_MAX = 50.0
BAR_WIDTH = 8.0
BAR_GAP = 1.0
FONT = "BentonSans-Book, 'BentonSans Book', 'Benton Sans', Arial, Helvetica, sans-serif"
FONT_BOLD = "BentonSans-Bold, 'BentonSans Bold', 'Benton Sans', Arial, Helvetica, sans-serif"
FONT_SIZE = 16.0


def wrap_label(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def categories_for(data: dict, as_labels: list[str]) -> list[str]:
    ordered: list[str] = []
    for as_label in as_labels:
        ranked = sorted(
            ((canonicalize_cell_label(k), 100.0 * v)
             for k, v in data["per_as_normalized"][as_label].items()),
            key=lambda item: item[1], reverse=True,
        )
        for label, _pct in ranked[:3]:
            if label not in ordered:
                ordered.append(label)
    return ordered


def pct_by_as(data: dict, as_labels: list[str]) -> dict[str, dict[str, float]]:
    return {
        as_label: {
            canonicalize_cell_label(k): 100.0 * v
            for k, v in data["per_as_normalized"][as_label].items()
        }
        for as_label in as_labels
    }


def build_svg(data: dict, as_labels: list[str], sex: str) -> str:
    categories = categories_for(data, as_labels)
    percentages = pct_by_as(data, as_labels)
    n_as = len(as_labels)
    n_groups = len(categories)
    is_female = sex.lower() == "female"
    axis_x0 = AXIS_X0
    axis_x1 = AXIS_X1
    canvas_height = HEIGHT
    physical_height = PHYSICAL_HEIGHT_IN
    x_axis_title_y = PLOT_BOTTOM + 83.0
    legend_y = 470.0
    legend_width = 500.0
    legend_col_offsets = (20.0, 180.0)
    y_title_x = 70.0
    if is_female:
        # Keep the female matrix compact, but move it right to clear the
        # y-axis title and leave room for the scale labels.
        axis_x0 = 200.0
        axis_x1 = axis_x0 + (AXIS_X1 - AXIS_X0) / 2.0
        canvas_height = 600.0
        physical_height = 2.0
        x_axis_title_y = 480.0
        legend_y = 520.0
        legend_width = 600.0
        legend_col_offsets = (20.0, 290.0)
        y_title_x = 155.0
    group_width = n_as * BAR_WIDTH + (n_as - 1) * BAR_GAP
    x0 = axis_x0
    x1 = axis_x1
    group_gap = (x1 - x0 - n_groups * group_width) / max(1, n_groups - 1)
    center = (x0 + x1) / 2.0

    max_pct = max(
        (percentages[a].get(c, 0.0) for a in as_labels for c in categories),
        default=1.0,
    )
    axis_max = AXIS_MAX

    def y_for(pct: float) -> float:
        return PLOT_BOTTOM - pct / axis_max * (PLOT_BOTTOM - PLOT_TOP)

    out = [
        f'<svg viewBox="0 0 {WIDTH:.4f} {canvas_height:.4f}" '
        f'width="{PHYSICAL_WIDTH_IN:.4f}in" height="{physical_height:.4f}in" '
        f'xmlns="http://www.w3.org/2000/svg" font-family="{FONT}">',
        f'<rect x="0" y="0" width="{WIDTH:.4f}" height="{canvas_height:.4f}" fill="{BG}"/>',
        f'<text x="{center:.1f}" y="30" font-size="{FONT_SIZE:.2f}" font-family="{FONT_BOLD}" font-weight="bold" fill="{TEXT}" text-anchor="middle">'
        f"Heart — Azimuth — {sex.title()}: cell type composition by AS</text>",
    ]

    for i in range(6):
        pct = i * axis_max / 5.0
        y = y_for(pct)
        out += [
            f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>',
            f'<text x="{x0 - 4}" y="{y + FONT_SIZE * 0.35:.1f}" font-size="{FONT_SIZE:.2f}" fill="{TEXT}" text-anchor="end">{pct:.0f}%</text>',
        ]
    mid_y = (PLOT_TOP + PLOT_BOTTOM) / 2.0
    out += [
        f'<text x="{y_title_x:.1f}" y="{mid_y:.1f}" font-size="{FONT_SIZE:.2f}" fill="{TEXT}" transform="rotate(-90 {y_title_x:.1f} {mid_y:.1f})" text-anchor="middle">Cells (%)</text>',
        f'<line x1="{x0}" y1="{PLOT_TOP}" x2="{x0}" y2="{PLOT_BOTTOM}" stroke="#444444" stroke-width="1.2"/>',
        f'<line x1="{x0}" y1="{PLOT_BOTTOM}" x2="{x1}" y2="{PLOT_BOTTOM}" stroke="#444444" stroke-width="1.2"/>',
    ]

    for gi, category in enumerate(categories):
        group_x = x0 + gi * (group_width + group_gap)
        for bi, as_label in enumerate(as_labels):
            pct = percentages[as_label].get(category, 0.0)
            if pct < 2.0:
                continue
            x = group_x + bi * (BAR_WIDTH + BAR_GAP)
            y = y_for(pct)
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{BAR_WIDTH:.0f}" height="{PLOT_BOTTOM-y:.1f}" fill="{AS_COLORS[as_label]}"/>')
        label_lines = wrap_label(category, 18)
        label_x = group_x + group_width / 2.0
        label_y = PLOT_BOTTOM + 5.0
        out.append(f'<g transform="translate({label_x:.1f} {label_y:.1f}) rotate(-45)">')
        for li, line in enumerate(label_lines):
            out.append(f'<text x="0" y="{FONT_SIZE * 0.8 + li * FONT_SIZE * 1.15:.1f}" font-size="{FONT_SIZE:.2f}" fill="{TEXT}" text-anchor="end">{escape(line.title())}</text>')
        out.append('</g>')

    out.append(f'<text x="{center:.1f}" y="{x_axis_title_y:.1f}" font-size="{FONT_SIZE:.2f}" fill="{TEXT}" text-anchor="middle">Cell type</text>')

    legend_rows = [as_labels[i:i + 2] for i in range(0, len(as_labels), 2)]
    # Center the legend box on the matrix's plotting area.
    legend_x = center - legend_width / 2.0
    legend_h = 16 + len(legend_rows) * 18
    out.append(f'<rect x="{legend_x:.1f}" y="{legend_y:.1f}" width="{legend_width:.1f}" height="{legend_h}" fill="{BG}" stroke="#dddddd" stroke-width="1"/>')
    col_x = [legend_x + legend_col_offsets[0], legend_x + legend_col_offsets[1]]
    for row, labels in enumerate(legend_rows):
        y = legend_y + 22 + row * 18
        for col, as_label in enumerate(labels):
            x = col_x[col]
            out += [
                f'<rect x="{x:.1f}" y="{y-10:.1f}" width="13" height="13" fill="{AS_COLORS[as_label]}" stroke="#999999" stroke-width="0.5"/>',
                f'<text x="{x+19:.1f}" y="{y:.1f}" font-size="{FONT_SIZE:.2f}" fill="{TEXT}" text-anchor="start">{escape(AS_NAMES[as_label])}</text>',
            ]
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    root = Path(__file__).parent.parent
    data_root = root.parent / "HRA" / "outputs" / "annotated organs" / "heart" / "json"
    out_root = root / "outputs" / "annotated organs" / "heart" / "svg" / "faceted"
    for sex, as_labels in (("female", AS_LABELS_FEMALE), ("male", AS_LABELS)):
        data_path = data_root / f"3d-vh-{sex[0]}-heart_distribution.json"
        out_path = out_root / f"3d-vh-{sex[0]}-heart-grouped-by-AS-book.svg"
        data = json.loads(data_path.read_text(encoding="utf-8"))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(build_svg(data, as_labels, sex), encoding="utf-8")
        print(f"Saved SVG: {out_path}")


if __name__ == "__main__":
    main()
