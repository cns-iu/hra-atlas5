#!/usr/bin/env python3
"""Regenerate the requested kidney and liver bar graphs with shared styling."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location("bar_graph", HERE / "51_generate_svgs.py")
bar_graph = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(bar_graph)


FONT_PX = 16.0
WIDTH_IN = 2.2
HEIGHT_IN = 2.4
MAX_LABEL_LINES = 8
LABEL_WRAP_CHARS = 16


def render(dist_path: Path, organ: str, sex: str, tool: str, out_dir: Path,
           output_suffix: str = "", as_colors: dict[str, str] | None = None) -> None:
    data = json.loads(dist_path.read_text(encoding="utf-8"))
    bar_graph.WIDTH_IN = WIDTH_IN
    bar_graph.HEIGHT_IN = HEIGHT_IN
    bar_graph.FONT_PX = FONT_PX
    bar_graph.MAX_LABEL_LINES = MAX_LABEL_LINES
    bar_graph.LABEL_WRAP_CHARS = LABEL_WRAP_CHARS
    # Keep the requested 16px typography while widening the plotting area.
    bar_graph.REF_SIDE_PX = min(WIDTH_IN * bar_graph.DPI, HEIGHT_IN * bar_graph.DPI)

    categories = bar_graph.pick_cell_types(
        data,
        bar_graph.TOP_N_CELL_TYPES,
        bar_graph.CELL_TYPE_OVERRIDES.get(organ, []),
    )
    as_labels = bar_graph.pick_as_labels(data)
    colors = bar_graph.assign_as_colors(data, as_labels)
    if as_colors:
        colors = bar_graph.apply_as_color_overrides(colors, as_colors)
    groups = bar_graph.build_groups(data, categories, as_labels)
    title = f"{organ.title()} — {tool.title()} — {sex.title()}: cell type composition by AS"
    chart = bar_graph.build_bar_body(groups, categories, as_labels, colors, title)
    legend = bar_graph.build_legend_body(as_labels, colors)
    uberon_id = data.get("uberon_id", "")
    stem = dist_path.name.removesuffix("_distribution.json")
    name = "-".join(p for p in [stem, uberon_id, f"top{len(categories)}", tool.lower(), "bar-graph"] if p)
    name += output_suffix

    for folder, suffix, svg in (
        ("without-legend", "without-legend", bar_graph.compose_svg(chart)),
        ("with-legend", "with-legend", bar_graph.compose_svg(chart, legend)),
    ):
        path = out_dir / folder / f"{name}-{suffix}.svg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8")
        print(f"Saved SVG: {path}")


def main() -> None:
    a5 = ROOT / "outputs" / "annotated organs"
    hra = ROOT.parent / "HRA" / "outputs" / "annotated organs"

    # The HRA source contains all four sex/side kidney distributions, including
    # female right kidney, which is not present in the A5 amended JSON folder.
    for sex, side in (("female", "l"), ("female", "r"), ("male", "l"), ("male", "r")):
        stem = f"3d-vh-{sex[0]}-kidney-{side}"
        render(
            hra / "kidney" / "json" / f"{stem}_distribution.json",
            "kidney", sex, "azimuth", a5 / "kidney" / "svg",
        )

    liver_colors = {
        "capsule of the liver": "#8dd3c7",
        "diaphragmatic surface of liver": "#ffffb3",
        "gastric impression of liver": "#bebada",
        "round ligament of liver": "#fb8072",
    }
    for sex in ("female", "male"):
        stem = f"3d-vh-{sex[0]}-liver"
        render(
            a5 / "liver" / "json" / f"{stem}_distribution.json",
            "liver", sex, "celltypist", a5 / "liver" / "svg",
            output_suffix="-custom", as_colors=liver_colors,
        )


if __name__ == "__main__":
    main()
