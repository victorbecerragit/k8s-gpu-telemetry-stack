#!/usr/bin/env python3
"""Render demo snapshots into dependency-free SVG charts.

Reads a snapshot produced by ``collect-demo-metrics.py`` and writes one SVG per
metric plus a fleet-summary card. Pure standard library — no matplotlib, no
network access — so it runs in CI and on minimal hosts.

Usage:
    python3 scripts/render-demo-charts.py \
        --input demo/snapshots/example.json \
        --output-dir docs/images
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timezone
from typing import Any

# -- Theme ------------------------------------------------------------------
BG = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
GRID = "#21262d"
ACCENT = "#58a6ff"
PALETTE = ["#58a6ff", "#3fb950", "#d29922", "#f85149", "#bc8cff", "#39c5cf"]

WIDTH = 900
HEIGHT = 340
PAD_L, PAD_R, PAD_T, PAD_B = 64, 24, 52, 44


def esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def nice_ceiling(value: float) -> float:
    """Round a max value up to a readable axis bound."""
    if value <= 0:
        return 1.0
    exp = math.floor(math.log10(value))
    base = 10**exp
    for mult in (1, 2, 2.5, 5, 10):
        if value <= base * mult:
            return base * mult
    return base * 10


def fmt_num(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 10:
        return f"{value:.0f}"
    if abs(value) >= 1:
        return f"{value:.1f}"
    return f"{value:.2f}"


def line_chart(
    title: str,
    unit: str,
    series: list[dict[str, Any]],
    subtitle: str = "",
    synthetic: bool = False,
) -> str:
    """Build a multi-series line chart as an SVG string."""
    plot_w = WIDTH - PAD_L - PAD_R
    plot_h = HEIGHT - PAD_T - PAD_B

    all_points = [p for s in series for p in s["points"]]
    if not all_points:
        return empty_chart(title, unit, subtitle, synthetic)

    t_min = min(p["t"] for p in all_points)
    t_max = max(p["t"] for p in all_points)
    v_max = nice_ceiling(max(p["v"] for p in all_points))
    v_min = 0.0
    t_span = max(t_max - t_min, 1.0)

    def x_of(t: float) -> float:
        return PAD_L + (t - t_min) / t_span * plot_w

    def y_of(v: float) -> float:
        return PAD_T + plot_h - (v - v_min) / (v_max - v_min) * plot_h

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        f'aria-label="{esc(title)}">'
    )
    parts.append(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}" rx="10"/>')
    parts.append(
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" '
        f'fill="none" stroke="{BORDER}" rx="10"/>'
    )

    # Title + subtitle
    parts.append(
        f'<text x="{PAD_L}" y="30" fill="{TEXT}" font-family="ui-sans-serif,'
        f'Segoe UI,Helvetica,Arial" font-size="16" font-weight="600">{esc(title)}</text>'
    )
    if subtitle:
        parts.append(
            f'<text x="{WIDTH - PAD_R}" y="30" fill="{MUTED}" text-anchor="end" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo" font-size="11">'
            f"{esc(subtitle)}</text>"
        )

    # Horizontal grid + y labels
    for i in range(5):
        frac = i / 4
        y = PAD_T + plot_h - frac * plot_h
        val = v_min + frac * (v_max - v_min)
        parts.append(
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L + plot_w}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{PAD_L - 10}" y="{y + 4:.1f}" fill="{MUTED}" text-anchor="end" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo" font-size="10">'
            f"{fmt_num(val)}</text>"
        )

    # X labels (start / mid / end)
    for frac in (0.0, 0.5, 1.0):
        t = t_min + frac * t_span
        x = PAD_L + frac * plot_w
        label = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%H:%M")
        anchor = "start" if frac == 0 else ("end" if frac == 1 else "middle")
        parts.append(
            f'<text x="{x:.1f}" y="{PAD_T + plot_h + 20}" fill="{MUTED}" '
            f'text-anchor="{anchor}" font-family="ui-monospace,SFMono-Regular,Menlo" '
            f'font-size="10">{label}</text>'
        )

    # Axis unit
    parts.append(
        f'<text x="{PAD_L - 10}" y="{PAD_T - 12}" fill="{MUTED}" text-anchor="end" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo" font-size="10">{esc(unit)}</text>'
    )

    # Series
    for idx, s in enumerate(series):
        color = PALETTE[idx % len(PALETTE)]
        pts = sorted(s["points"], key=lambda p: p["t"])
        if len(pts) == 1:
            x, y = x_of(pts[0]["t"]), y_of(pts[0]["v"])
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>')
            continue
        d = " ".join(
            f'{"M" if i == 0 else "L"}{x_of(p["t"]):.1f},{y_of(p["v"]):.1f}'
            for i, p in enumerate(pts)
        )
        parts.append(
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )
        # Area fill
        area = (
            f"M{x_of(pts[0]['t']):.1f},{PAD_T + plot_h:.1f} "
            + " ".join(f"L{x_of(p['t']):.1f},{y_of(p['v']):.1f}" for p in pts)
            + f" L{x_of(pts[-1]['t']):.1f},{PAD_T + plot_h:.1f} Z"
        )
        parts.append(f'<path d="{area}" fill="{color}" opacity="0.10"/>')

    # Legend
    legend_y = HEIGHT - 12
    x_cursor = PAD_L
    for idx, s in enumerate(series[:6]):
        color = PALETTE[idx % len(PALETTE)]
        parts.append(
            f'<rect x="{x_cursor}" y="{legend_y - 8}" width="10" height="3" '
            f'rx="1.5" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{x_cursor + 16}" y="{legend_y - 3}" fill="{MUTED}" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo" font-size="10">'
            f"{esc(s['label'])}</text>"
        )
        x_cursor += 26 + 7 * len(str(s["label"]))

    if synthetic:
        parts.append(synthetic_badge(y=PAD_T + 6))

    parts.append("</svg>")
    return "\n".join(parts)


def synthetic_badge(y: int | None = None) -> str:
    """Watermark marking a chart as illustrative, not captured telemetry."""
    badge_w, badge_h = 152, 20
    x = WIDTH - PAD_R - badge_w
    if y is None:
        y = HEIGHT - 58
    return (
        f'<g><rect x="{x}" y="{y}" width="{badge_w}" height="{badge_h}" '
        f'rx="10" fill="#d29922" opacity="0.16"/>'
        f'<text x="{x + badge_w / 2}" y="{y + 14}" fill="#d29922" '
        f'text-anchor="middle" font-family="ui-monospace,SFMono-Regular,Menlo" '
        f'font-size="10" font-weight="600">ILLUSTRATIVE DATA</text></g>'
    )


def empty_chart(title: str, unit: str, subtitle: str = "", synthetic: bool = False) -> str:
    """Placeholder shown when a metric has no data."""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{esc(title)}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}" rx="10"/>',
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" '
        f'fill="none" stroke="{BORDER}" rx="10"/>',
        f'<text x="{PAD_L}" y="30" fill="{TEXT}" font-family="ui-sans-serif,'
        f'Segoe UI,Helvetica,Arial" font-size="16" font-weight="600">{esc(title)}</text>',
        f'<text x="{WIDTH / 2}" y="{HEIGHT / 2}" fill="{MUTED}" text-anchor="middle" '
        f'font-family="ui-sans-serif,Segoe UI,Helvetica,Arial" font-size="13">'
        f"No data captured for this metric</text>",
        f'<text x="{WIDTH / 2}" y="{HEIGHT / 2 + 22}" fill="{MUTED}" '
        f'text-anchor="middle" font-family="ui-monospace,SFMono-Regular,Menlo" '
        f'font-size="11">{esc(subtitle or unit)}</text>',
    ]
    if synthetic:
        parts.append(synthetic_badge(y=HEIGHT - 34))
    parts.append("</svg>")
    return "\n".join(parts)


def summary_card(snapshot: dict[str, Any]) -> str:
    """Render the four fleet KPIs as a single card."""
    summary = snapshot.get("summary", {})
    synthetic = bool(snapshot.get("synthetic"))
    order = [
        "avg_sm_utilization",
        "vram_utilization",
        "max_temperature",
        "xid_errors_1h",
    ]
    card_w, card_h = WIDTH, 200
    gap = 16
    inner_w = (card_w - PAD_L - PAD_R - gap * 3) / 4

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{card_w}" height="{card_h}" '
        f'viewBox="0 0 {card_w} {card_h}" role="img" aria-label="Fleet summary">',
        f'<rect width="{card_w}" height="{card_h}" fill="{BG}" rx="10"/>',
        f'<rect x="0.5" y="0.5" width="{card_w - 1}" height="{card_h - 1}" '
        f'fill="none" stroke="{BORDER}" rx="10"/>',
        f'<text x="{PAD_L}" y="30" fill="{TEXT}" font-family="ui-sans-serif,'
        f'Segoe UI,Helvetica,Arial" font-size="16" font-weight="600">'
        f"Fleet Summary</text>",
        f'<text x="{card_w - PAD_R}" y="30" fill="{MUTED}" text-anchor="end" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo" font-size="11">'
        f"{esc(snapshot.get('cluster', 'unknown'))}</text>",
    ]

    for i, key in enumerate(order):
        item = summary.get(key, {})
        value = item.get("value")
        unit = item.get("unit", "")
        title = item.get("title", key)
        x = PAD_L + i * (inner_w + gap)
        y = 52
        parts.append(
            f'<rect x="{x:.1f}" y="{y}" width="{inner_w:.1f}" height="96" '
            f'fill="{PANEL}" stroke="{BORDER}" rx="8"/>'
        )
        parts.append(
            f'<text x="{x + 14:.1f}" y="{y + 24}" fill="{MUTED}" '
            f'font-family="ui-sans-serif,Segoe UI,Helvetica,Arial" font-size="11">'
            f"{esc(title)}</text>"
        )
        display = "n/a" if value is None else fmt_num(value)
        color = ACCENT
        if key == "max_temperature" and value is not None and value > 85:
            color = "#f85149"
        if key == "xid_errors_1h" and value:
            color = "#f85149"
        parts.append(
            f'<text x="{x + 14:.1f}" y="{y + 62}" fill="{color}" '
            f'font-family="ui-sans-serif,Segoe UI,Helvetica,Arial" font-size="28" '
            f'font-weight="600">{esc(display)}</text>'
        )
        parts.append(
            f'<text x="{x + 14:.1f}" y="{y + 82}" fill="{MUTED}" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo" font-size="11">'
            f"{esc(unit)}</text>"
        )

    if synthetic:
        parts.append(synthetic_badge(y=card_h - 34))

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Snapshot JSON path")
    parser.add_argument("--output-dir", default="docs/images")
    args = parser.parse_args()

    with open(args.input) as f:
        snapshot = json.load(f)

    os.makedirs(args.output_dir, exist_ok=True)

    generated = snapshot.get("generated_at", "")
    if generated:
        try:
            stamp = datetime.fromisoformat(generated).strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            stamp = generated
    else:
        stamp = ""

    written: list[str] = []
    synthetic = bool(snapshot.get("synthetic"))

    path = os.path.join(args.output_dir, "fleet-summary.svg")
    with open(path, "w") as f:
        f.write(summary_card(snapshot))
    written.append(path)

    for key, meta in snapshot.get("series", {}).items():
        svg = line_chart(
            meta.get("title", key),
            meta.get("unit", ""),
            meta.get("series", []),
            subtitle=stamp,
            synthetic=synthetic,
        )
        path = os.path.join(args.output_dir, f"{key.replace('_', '-')}.svg")
        with open(path, "w") as f:
            f.write(svg)
        written.append(path)

    for path in written:
        print(f"wrote {path}")
    if synthetic:
        print("note: snapshot is synthetic; charts are watermarked ILLUSTRATIVE DATA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
