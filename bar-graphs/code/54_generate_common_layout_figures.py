#!/usr/bin/env python3
"""Generate the requested kidney, liver, and heart figures on one shared layout."""

from __future__ import annotations

import importlib.util
import json
from html import escape
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location("bar_graph", HERE / "51_generate_svgs.py")
bar_graph = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(bar_graph)

# Shared canvas and plotting rectangle for every figure.
WIDTH = 910.5543
HEIGHT = 780.0
WIDTH_IN = 3.0352
HEIGHT_IN = 2.6000
# Half-width shared x-axis, centered in the common canvas.
X0, X1 = 274.1, 636.5
Y0, Y1 = 70.0, 365.0
Y_AXIS_TITLE_X = 221.1
Y_AXIS_MAX = 50.0
FONT_SIZE = 16.0
FONT = "BentonSans-Book, 'BentonSans Book', 'Benton Sans', Arial, Helvetica, sans-serif"
FONT_BOLD = "BentonSans-Bold, 'BentonSans Bold', 'Benton Sans', Arial, Helvetica, sans-serif"
BG = "#FAF8F5"
TEXT = "#171616"
GRID = "#ACA8A8"
AXIS = "#444444"

HEART_AS_COLORS = {
    "right cardiac atrium": "#fdb462",
    "left cardiac atrium": "#fb8072",
    "heart right ventricle": "#ffffb3",
    "heart left ventricle": "#8dd3c7",
    "interventricular septum": "#bebada",
    "Posteromedial head of posterior papillary muscle of left ventricle": "#80b1d3",
}
HEART_AS_NAMES = {
    "right cardiac atrium": "Right atrium",
    "left cardiac atrium": "Left atrium",
    "heart right ventricle": "Right ventricle",
    "heart left ventricle": "Left ventricle",
    "interventricular septum": "Interventricular septum",
    "Posteromedial head of posterior papillary muscle of left ventricle": "Posteromedial papillary muscle",
}


def wrap_label(text: str, max_chars: int = 34) -> list[str]:
    words = text.split()
    if len(words) <= 1:
        return [text]
    if len(" ".join(words)) <= max_chars:
        return [text]
    # Split once at the word boundary that best balances the two full lines.
    best = None
    for i in range(1, len(words)):
        left = " ".join(words[:i])
        right = " ".join(words[i:])
        score = max(len(left), len(right))
        if best is None or score < best[0]:
            best = (score, left, right)
    return [best[1], best[2]]


def svg_header(title: str) -> list[str]:
    return [
        f'<svg viewBox="0 0 {WIDTH:.4f} {HEIGHT:.4f}" width="{WIDTH_IN:.4f}in" height="{HEIGHT_IN:.4f}in" xmlns="http://www.w3.org/2000/svg" font-family="{FONT}">',
        f'<rect x="0" y="0" width="{WIDTH:.4f}" height="{HEIGHT:.4f}" fill="{BG}"/>',
        f'<text x="{(X0 + X1) / 2:.1f}" y="30" font-size="{FONT_SIZE:.2f}" font-family="{FONT_BOLD}" fill="{TEXT}" text-anchor="middle">{escape(title)}</text>',
    ]


def build_common_svg(title: str, categories: list[str], as_labels: list[str], percentages: dict[str, dict[str, float]], colors: dict[str, str], names: dict[str, str]) -> str:
    n_groups = len(categories)
    n_as = len(as_labels)
    bar_gap = 3.0
    group_gap = 8.0
    bar_width = max(
        4.0,
        (X1 - X0 - (n_groups - 1) * group_gap - n_groups * (n_as - 1) * bar_gap)
        / (n_groups * n_as),
    )
    group_width = n_as * bar_width + (n_as - 1) * bar_gap
    center = (X0 + X1) / 2.0

    def y_for(pct: float) -> float:
        return Y1 - pct / Y_AXIS_MAX * (Y1 - Y0)

    out = svg_header(title)
    for i in range(6):
        pct = i * Y_AXIS_MAX / 5.0
        y = y_for(pct)
        out += [
            f'<line x1="{X0:.1f}" y1="{y:.1f}" x2="{X1:.1f}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>',
            f'<text x="{X0 - 4:.1f}" y="{y + FONT_SIZE * 0.35:.1f}" font-size="{FONT_SIZE:.2f}" fill="{TEXT}" text-anchor="end">{pct:.0f}%</text>',
        ]
    mid_y = (Y0 + Y1) / 2.0
    out += [
        f'<text x="{Y_AXIS_TITLE_X:.1f}" y="{mid_y:.1f}" font-size="{FONT_SIZE:.2f}" fill="{TEXT}" text-anchor="middle" transform="rotate(-90 {Y_AXIS_TITLE_X:.1f} {mid_y:.1f})">Cells (%)</text>',
        f'<line x1="{X0:.1f}" y1="{Y0:.1f}" x2="{X0:.1f}" y2="{Y1:.1f}" stroke="{AXIS}" stroke-width="1.2"/>',
        f'<line x1="{X0:.1f}" y1="{Y1:.1f}" x2="{X1:.1f}" y2="{Y1:.1f}" stroke="{AXIS}" stroke-width="1.2"/>',
    ]

    label_bottom = Y1 + 5.0
    for gi, category in enumerate(categories):
        group_x = X0 + gi * (group_width + group_gap)
        for bi, as_label in enumerate(as_labels):
            pct = percentages[as_label].get(category, 0.0)
            if pct < 2.0:
                continue
            x = group_x + bi * (bar_width + bar_gap)
            y = y_for(pct)
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{Y1-y:.1f}" fill="{colors[as_label]}"/>')
        label_x = group_x + group_width / 2.0
        lines = wrap_label(category)
        out.append(f'<g transform="translate({label_x:.1f} {Y1 + 5:.1f}) rotate(-45)">')
        for li, line in enumerate(lines):
            baseline = FONT_SIZE * 0.8 + li * FONT_SIZE * 1.15
            out.append(f'<text x="0" y="{baseline:.1f}" font-size="{FONT_SIZE:.2f}" fill="{TEXT}" text-anchor="end">{escape(line.title())}</text>')
            # A rotated line extends downward according to its horizontal text length.
            label_bottom = max(label_bottom, Y1 + 5.0 + baseline + len(line) * FONT_SIZE * 0.55 * 0.7071)
        out.append('</g>')

    # Keep a common lower layout based on the longest label, with a small gap.
    x_axis_title_y = label_bottom + 1.0
    out.append(f'<text x="{center:.1f}" y="{x_axis_title_y:.1f}" font-size="{FONT_SIZE:.2f}" fill="{TEXT}" text-anchor="middle">Cell type</text>')
    legend_rows = [as_labels[i:i + 2] for i in range(0, len(as_labels), 2)]
    legend_x, legend_y, legend_w = max(0.0, center - 300.0), x_axis_title_y + 60.0, 600.0
    legend_h = 16 + len(legend_rows) * 18
    out.append(f'<rect x="{legend_x:.1f}" y="{legend_y:.1f}" width="{legend_w:.1f}" height="{legend_h}" fill="{BG}" stroke="#dddddd" stroke-width="1"/>')
    col_x = [legend_x + 20.0, legend_x + 290.0]
    for row, labels in enumerate(legend_rows):
        y = legend_y + 22 + row * 18
        for col, as_label in enumerate(labels):
            x = col_x[col]
            out += [
                f'<rect x="{x:.1f}" y="{y - 10:.1f}" width="13" height="13" fill="{colors[as_label]}" stroke="#999999" stroke-width="0.5"/>',
                f'<text x="{x + 19:.1f}" y="{y:.1f}" font-size="{FONT_SIZE:.2f}" fill="{TEXT}" text-anchor="start">{escape(names.get(as_label, as_label.title()))}</text>',
            ]
    out.append('</svg>')
    return "\n".join(out)


def render_distribution(path: Path, organ: str, sex: str, tool: str, out_dir: Path, suffix: str = "", color_overrides: dict[str, str] | None = None) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    categories = bar_graph.pick_cell_types(data, 5, bar_graph.CELL_TYPE_OVERRIDES.get(organ, []))
    as_labels = bar_graph.pick_as_labels(data)
    colors = bar_graph.assign_as_colors(data, as_labels)
    if color_overrides:
        colors = bar_graph.apply_as_color_overrides(colors, color_overrides)
    percentages = {a: {bar_graph.canonicalize_cell_label(k): 100.0 * v for k, v in data["per_as_normalized"][a].items()} for a in as_labels}
    title = f"{organ.title()} — {tool.title()} — {sex.title()}: cell type composition by AS"
    svg = build_common_svg(title, categories, as_labels, percentages, colors, {a: a.title() for a in as_labels})
    stem = path.name.removesuffix("_distribution.json")
    name = "-".join([stem, data.get("uberon_id", ""), "top5", tool.lower(), "bar-graph"]) + suffix
    for folder, end in (("without-legend", "without-legend"), ("with-legend", "with-legend")):
        target = out_dir / folder / f"{name}-{end}.svg"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(svg, encoding="utf-8")
        print(f"Saved SVG: {target}")


def render_heart(sex: str) -> None:
    data_path = ROOT.parent / "HRA" / "outputs" / "annotated organs" / "heart" / "json" / f"3d-vh-{sex[0]}-heart_distribution.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    as_labels = list(data["per_as_normalized"].keys())
    categories = []
    for a in as_labels:
        ranked = sorted(((bar_graph.canonicalize_cell_label(k), v) for k, v in data["per_as_normalized"][a].items()), key=lambda item: item[1], reverse=True)
        for label, _ in ranked[:3]:
            if label not in categories:
                categories.append(label)
    percentages = {a: {bar_graph.canonicalize_cell_label(k): 100.0 * v for k, v in data["per_as_normalized"][a].items()} for a in as_labels}
    colors = {a: HEART_AS_COLORS.get(a, "#d9d9d9") for a in as_labels}
    title = f"Heart — Azimuth — {sex.title()}: cell type composition by AS"
    svg = build_common_svg(title, categories, as_labels, percentages, colors, HEART_AS_NAMES)
    target = ROOT / "outputs" / "annotated organs" / "heart" / "svg" / "faceted" / f"3d-vh-{sex[0]}-heart-grouped-by-AS-book.svg"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(svg, encoding="utf-8")
    print(f"Saved SVG: {target}")


def main() -> None:
    a5 = ROOT / "outputs" / "annotated organs"
    hra = ROOT.parent / "HRA" / "outputs" / "annotated organs"
    for sex, side in (("female", "l"), ("female", "r"), ("male", "l"), ("male", "r")):
        stem = f"3d-vh-{sex[0]}-kidney-{side}"
        render_distribution(hra / "kidney" / "json" / f"{stem}_distribution.json", "kidney", sex, "azimuth", a5 / "kidney" / "svg")
    liver_colors = {
        "capsule of the liver": "#8dd3c7",
        "diaphragmatic surface of liver": "#ffffb3",
        "gastric impression of liver": "#bebada",
        "round ligament of liver": "#fb8072",
    }
    for sex in ("female", "male"):
        stem = f"3d-vh-{sex[0]}-liver"
        render_distribution(a5 / "liver" / "json" / f"{stem}_distribution.json", "liver", sex, "celltypist", a5 / "liver" / "svg", "-custom", liver_colors)
    render_heart("female")
    render_heart("male")


if __name__ == "__main__":
    main()
