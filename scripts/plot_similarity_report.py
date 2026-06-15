#!/usr/bin/env python3
"""Render a similarity report from the FBI rules documentation CSV."""

from __future__ import annotations

import argparse
import csv
import html
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = REPO_ROOT / "json_rules" / "fbi_rules" / "documentation.csv"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "json_rules" / "fbi_rules" / "similarity_report.svg"


@dataclass(frozen=True)
class SimilarityRow:
    rule_id: str
    rule_path: str
    compare_path: str
    similarity: float

    @property
    def group(self) -> str:
        parts = Path(self.rule_path).parts
        return parts[2].replace("_", " ").title() if len(parts) > 2 else "Rules"

    @property
    def compare_name(self) -> str:
        return Path(self.compare_path).stem.replace("_", " ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a styled SVG plot of similarity values from documentation.csv."
    )
    parser.add_argument(
        "--csv-path",
        default=str(DEFAULT_CSV_PATH),
        help="Path to the documentation CSV file.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Path to the output SVG file.",
    )
    parser.add_argument(
        "--title",
        default="FBI Rule Similarity Overview",
        help="Chart title to render in the SVG.",
    )
    return parser.parse_args()


def load_rows(csv_path: Path) -> list[SimilarityRow]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for raw_row in reader:
            similarity_text = (raw_row.get("similarity_percentage") or "").strip()
            if not similarity_text:
                continue
            rows.append(
                SimilarityRow(
                    rule_id=(raw_row.get("rule_id") or "").strip(),
                    rule_path=(raw_row.get("rule_path") or "").strip(),
                    compare_path=(raw_row.get("compare_path") or "").strip(),
                    similarity=float(similarity_text),
                )
            )
    if not rows:
        raise ValueError(f"No similarity values found in {csv_path}")
    return sorted(rows, key=lambda row: row.similarity, reverse=True)


def escape(text: str) -> str:
    return html.escape(text, quote=True)


def blend_color(start: tuple[int, int, int], end: tuple[int, int, int], ratio: float) -> str:
    channel_values = [
        round(start[index] + (end[index] - start[index]) * ratio)
        for index in range(3)
    ]
    return "#" + "".join(f"{value:02x}" for value in channel_values)


def score_color(score: float) -> str:
    ratio = max(0.0, min(score / 100.0, 1.0))
    return blend_color((220, 94, 66), (54, 140, 98), ratio)


def render_svg(rows: list[SimilarityRow], title: str) -> str:
    chart_left = 280
    chart_width = 620
    bar_height = 36
    bar_gap = 18
    row_height = bar_height + bar_gap
    top_margin = 210
    bottom_margin = 70
    canvas_width = 1040
    canvas_height = top_margin + bottom_margin + row_height * len(rows)

    scores = [row.similarity for row in rows]
    average_score = mean(scores)
    summary = f"{len(rows)} rules, average similarity {average_score:.2f}%"

    average_x = chart_left + chart_width * (average_score / 100.0)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" '
            f'height="{canvas_height}" viewBox="0 0 {canvas_width} {canvas_height}">'
        ),
        "<defs>",
        (
            '<linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">'
            '<stop offset="0%" stop-color="#f5f1e8"/>'
            '<stop offset="100%" stop-color="#e5efe8"/>'
            "</linearGradient>"
        ),
        (
            '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">'
            '<feDropShadow dx="0" dy="6" stdDeviation="10" flood-opacity="0.12"/>'
            "</filter>"
        ),
        "</defs>",
        f'<rect width="{canvas_width}" height="{canvas_height}" fill="url(#bg)"/>',
        (
            '<rect x="30" y="26" width="980" height="150" rx="24" '
            'fill="#fffdf8" filter="url(#shadow)"/>'
        ),
        (
            '<text x="62" y="78" fill="#18312b" '
            'font-family="Avenir Next, Helvetica Neue, Arial, sans-serif" '
            'font-size="30" font-weight="700">'
            f"{escape(title)}</text>"
        ),
        (
            '<text x="62" y="112" fill="#56726a" '
            'font-family="Avenir Next, Helvetica Neue, Arial, sans-serif" '
            'font-size="16">'
            f"{escape(summary)}</text>"
        ),
        (
            '<text x="62" y="202" fill="#3a534e" '
            'font-family="Avenir Next, Helvetica Neue, Arial, sans-serif" '
            'font-size="14" font-weight="600">Similarity score</text>'
        ),
    ]

    for tick in range(0, 101, 20):
        x = chart_left + chart_width * (tick / 100.0)
        parts.append(
            (
                f'<line x1="{x:.2f}" y1="{top_margin - 18}" x2="{x:.2f}" '
                f'y2="{canvas_height - bottom_margin + 10}" stroke="#d4ddd7" '
                'stroke-dasharray="4 8" stroke-width="1"/>'
            )
        )
        parts.append(
            (
                f'<text x="{x:.2f}" y="{top_margin - 28}" text-anchor="middle" '
                'fill="#66827b" font-family="Avenir Next, Helvetica Neue, Arial, sans-serif" '
                f'font-size="13">{tick}%</text>'
            )
        )

    parts.append(
        (
            f'<line x1="{average_x:.2f}" y1="{top_margin - 10}" x2="{average_x:.2f}" '
            f'y2="{canvas_height - bottom_margin + 10}" stroke="#163f59" '
            'stroke-width="2.5"/>'
        )
    )
    parts.append(
        (
            f'<text x="{average_x + 10:.2f}" y="{top_margin - 14}" fill="#163f59" '
            'font-family="Avenir Next, Helvetica Neue, Arial, sans-serif" '
            f'font-size="13" font-weight="600">Average {average_score:.2f}%</text>'
        )
    )

    for index, row in enumerate(rows):
        y = top_margin + index * row_height
        width = chart_width * (row.similarity / 100.0)
        fill = score_color(row.similarity)
        parts.extend(
            [
                (
                    f'<text x="{chart_left - 16}" y="{y + 15}" text-anchor="end" '
                    'fill="#17322c" font-family="Avenir Next, Helvetica Neue, Arial, sans-serif" '
                    f'font-size="15" font-weight="700">{escape(row.rule_id)}</text>'
                ),
                (
                    f'<text x="{chart_left - 16}" y="{y + 34}" text-anchor="end" '
                    'fill="#6c7f79" font-family="Avenir Next, Helvetica Neue, Arial, sans-serif" '
                    f'font-size="12">{escape(row.group)} vs {escape(row.compare_name)}</text>'
                ),
                (
                    f'<rect x="{chart_left}" y="{y}" width="{chart_width}" height="{bar_height}" '
                    'rx="18" fill="#f1f3ef"/>'
                ),
                (
                    f'<rect x="{chart_left}" y="{y}" width="{width:.2f}" height="{bar_height}" '
                    f'rx="18" fill="{fill}"/>'
                ),
                (
                    f'<text x="{chart_left + width + 12:.2f}" y="{y + 24}" '
                    'fill="#18312b" font-family="Avenir Next, Helvetica Neue, Arial, sans-serif" '
                    f'font-size="15" font-weight="700">{row.similarity:.2f}%</text>'
                ),
            ]
        )

    parts.extend(["</svg>"])
    return "\n".join(parts)


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv_path).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    rows = load_rows(csv_path)
    svg = render_svg(rows, args.title)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    print(f"Wrote similarity plot to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
