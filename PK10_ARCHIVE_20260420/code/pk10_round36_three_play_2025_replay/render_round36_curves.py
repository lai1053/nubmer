#!/usr/bin/env python3
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "round36_outputs"


@dataclass(frozen=True)
class CurveSpec:
    label: str
    daily_path: Path
    color: str


@dataclass(frozen=True)
class StitchedCurveSpec:
    label: str
    daily_paths: tuple[Path, ...]
    color: str


CURVES = [
    CurveSpec(
        label="稳健版 intraday_1007",
        daily_path=OUTPUT_DIR / "three_play_intraday_1007_bankroll_1000_stake_10_m5_2025-01-01_2025-12-31_daily.csv",
        color="#2563eb",
    ),
    CurveSpec(
        label="进攻版 intraday_1037",
        daily_path=OUTPUT_DIR / "three_play_intraday_1037_bankroll_1000_stake_10_m5_2025-01-01_2025-12-31_daily.csv",
        color="#dc2626",
    ),
]


STITCHED_CURVES = [
    StitchedCurveSpec(
        label="稳健版 intraday_1007",
        daily_paths=(
            OUTPUT_DIR / "three_play_intraday_1007_bankroll_1000_stake_10_m5_2025-01-01_2025-12-31_daily.csv",
            OUTPUT_DIR / "three_play_intraday_1007_bankroll_11823_stake_10_m5_2026-01-01_2026-04-12_daily.csv",
        ),
        color="#2563eb",
    ),
    StitchedCurveSpec(
        label="进攻版 intraday_1037",
        daily_paths=(
            OUTPUT_DIR / "three_play_intraday_1037_bankroll_1000_stake_10_m5_2025-01-01_2025-12-31_daily.csv",
            OUTPUT_DIR / "three_play_intraday_1037_bankroll_17169_stake_10_m5_2026-01-01_2026-04-12_daily.csv",
        ),
        color="#dc2626",
    ),
]


def load_curve_paths(paths: tuple[Path, ...] | list[Path]) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    day_index = 0
    for path in paths:
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                day_index += 1
                rows.append(
                    {
                        "day_index": day_index,
                        "date": row["date"],
                        "bankroll_after_day": float(row["bankroll_after_day"]),
                        "drawdown_from_peak": float(row["drawdown_from_peak"]),
                        "total_real_pnl": float(row["total_real_pnl"]),
                    }
                )
    return rows


def load_curve(spec: CurveSpec) -> list[dict[str, float | int | str]]:
    return load_curve_paths((spec.daily_path,))


def load_stitched_curve(spec: StitchedCurveSpec) -> list[dict[str, float | int | str]]:
    return load_curve_paths(spec.daily_paths)


def x_scale(day_index: int, total_days: int, left: float, plot_w: float) -> float:
    if total_days <= 1:
        return left
    return left + (day_index - 1) * plot_w / (total_days - 1)


def y_scale(value: float, lo: float, hi: float, top: float, height: float) -> float:
    if hi == lo:
        return top + height / 2
    frac = (value - lo) / (hi - lo)
    return top + height - frac * height


def build_path(
    values: list[float],
    lo: float,
    hi: float,
    top: float,
    height: float,
    left: float,
    plot_w: float,
) -> str:
    total_days = len(values)
    parts: list[str] = []
    for idx, value in enumerate(values, start=1):
        x = x_scale(idx, total_days, left, plot_w)
        y = y_scale(value, lo, hi, top, height)
        parts.append(f"{'M' if idx == 1 else 'L'} {x:.2f} {y:.2f}")
    return " ".join(parts)


def add_grid(
    lines: list[str],
    left: float,
    top: float,
    plot_w: float,
    plot_h: float,
    lo: float,
    hi: float,
    day_labels: list[tuple[int, str]],
) -> None:
    lines.append(
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" rx="14" fill="#ffffff" stroke="#d1d5db"/>'
    )
    for i in range(5):
        frac = i / 4
        y = top + frac * plot_h
        value = hi - frac * (hi - lo)
        lines.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#e5e7eb" stroke-dasharray="4 4"/>'
        )
        lines.append(
            f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-size="12" fill="#6b7280">{value:.0f}</text>'
        )
    total_days = day_labels[-1][0]
    for day_index, label in day_labels:
        x = x_scale(day_index, total_days, left, plot_w)
        lines.append(
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#f3f4f6"/>'
        )
        lines.append(
            f'<text x="{x:.2f}" y="{top + plot_h + 20:.2f}" text-anchor="middle" font-size="12" fill="#6b7280">{label}</text>'
        )


def build_date_labels(
    rows: list[dict[str, float | int | str]],
    labels: list[tuple[str, str]],
) -> list[tuple[int, str]]:
    date_to_idx = {str(row["date"]): int(row["day_index"]) for row in rows}
    out: list[tuple[int, str]] = []
    for date_text, label in labels:
        day_index = date_to_idx.get(date_text)
        if day_index is not None:
            out.append((day_index, label))
    return out


def add_vertical_marker(
    lines: list[str],
    day_index: int,
    total_days: int,
    left: float,
    plot_w: float,
    top: float,
    plot_h: float,
    label: str,
) -> None:
    x = x_scale(day_index, total_days, left, plot_w)
    lines.append(
        f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#94a3b8" stroke-width="1.6" stroke-dasharray="6 6"/>'
    )
    lines.append(
        f'<text x="{x + 8:.2f}" y="{top + 18:.2f}" font-size="12" fill="#475569">{label}</text>'
    )


def build_comparison_svg(curves: list[tuple[CurveSpec, list[dict[str, float | int | str]]]]) -> Path:
    width = 1400
    height = 860
    left = 92
    right = 52
    top1 = 92
    panel_h = 260
    gap = 110
    top2 = top1 + panel_h + gap
    plot_w = width - left - right

    bankroll_values = [
        float(row["bankroll_after_day"])
        for _, rows in curves
        for row in rows
    ]
    drawdown_values = [
        float(row["drawdown_from_peak"])
        for _, rows in curves
        for row in rows
    ]
    bank_lo = min(bankroll_values)
    bank_hi = max(bankroll_values)
    dd_lo = min(drawdown_values)
    dd_hi = 0.0
    day_labels = [
        (1, "D1"),
        (32, "D32"),
        (91, "D91"),
        (182, "D182"),
        (274, "D274"),
        (365, "D365"),
    ]

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="92" y="42" font-size="28" font-weight="700" fill="#0f172a">Round36 两版本资金曲线（日维度）</text>',
        '<text x="92" y="68" font-size="14" fill="#475569">本金 1000 / 基投 10 / 大小马丁5层 + 单双固定1x + 和值独立马丁5层</text>',
    ]

    add_grid(lines, left, top1, plot_w, panel_h, bank_lo, bank_hi, day_labels)
    add_grid(lines, left, top2, plot_w, panel_h, dd_lo, dd_hi, day_labels)

    lines.append(f'<text x="{left}" y="{top1 - 16}" font-size="16" font-weight="600" fill="#0f172a">资金曲线</text>')
    lines.append(f'<text x="{left}" y="{top2 - 16}" font-size="16" font-weight="600" fill="#0f172a">回撤曲线</text>')

    legend_x = width - 280
    legend_y = 42
    for i, (spec, rows) in enumerate(curves):
        y = legend_y + i * 24
        lines.append(
            f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 30}" y2="{y}" stroke="{spec.color}" stroke-width="4" stroke-linecap="round"/>'
        )
        lines.append(
            f'<text x="{legend_x + 40}" y="{y + 4}" font-size="13" fill="#334155">{spec.label}</text>'
        )

        bankroll_path = build_path(
            [float(row["bankroll_after_day"]) for row in rows],
            bank_lo,
            bank_hi,
            top1,
            panel_h,
            left,
            plot_w,
        )
        drawdown_path = build_path(
            [float(row["drawdown_from_peak"]) for row in rows],
            dd_lo,
            dd_hi,
            top2,
            panel_h,
            left,
            plot_w,
        )
        lines.append(
            f'<path d="{bankroll_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        lines.append(
            f'<path d="{drawdown_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )

        final_row = rows[-1]
        final_x = x_scale(int(final_row["day_index"]), len(rows), left, plot_w)
        final_y = y_scale(float(final_row["bankroll_after_day"]), bank_lo, bank_hi, top1, panel_h)
        lines.append(
            f'<circle cx="{final_x:.2f}" cy="{final_y:.2f}" r="4.8" fill="{spec.color}" stroke="#ffffff" stroke-width="2"/>'
        )
        lines.append(
            f'<text x="{final_x + 10:.2f}" y="{final_y - 8:.2f}" font-size="12" fill="{spec.color}">{float(final_row["bankroll_after_day"]):.0f}</text>'
        )

    lines.append("</svg>")

    output_path = OUTPUT_DIR / "round36_two_version_daily_curve_comparison.svg"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def build_single_svg(spec: CurveSpec, rows: list[dict[str, float | int | str]]) -> Path:
    width = 1320
    height = 720
    left = 92
    right = 52
    top1 = 92
    panel_h = 220
    gap = 90
    top2 = top1 + panel_h + gap
    plot_w = width - left - right

    bankroll_values = [float(row["bankroll_after_day"]) for row in rows]
    drawdown_values = [float(row["drawdown_from_peak"]) for row in rows]
    bank_lo = min(bankroll_values)
    bank_hi = max(bankroll_values)
    dd_lo = min(drawdown_values)
    dd_hi = 0.0
    day_labels = [
        (1, "D1"),
        (32, "D32"),
        (91, "D91"),
        (182, "D182"),
        (274, "D274"),
        (365, "D365"),
    ]

    bank_path = build_path(bankroll_values, bank_lo, bank_hi, top1, panel_h, left, plot_w)
    dd_path = build_path(drawdown_values, dd_lo, dd_hi, top2, panel_h, left, plot_w)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<text x="92" y="42" font-size="28" font-weight="700" fill="#0f172a">{spec.label} 资金曲线（日维度）</text>',
        '<text x="92" y="68" font-size="14" fill="#475569">X 轴为 2025 年日序列，Y 轴分别为资金余额与相对峰值回撤</text>',
    ]
    add_grid(lines, left, top1, plot_w, panel_h, bank_lo, bank_hi, day_labels)
    add_grid(lines, left, top2, plot_w, panel_h, dd_lo, dd_hi, day_labels)
    lines.append(f'<text x="{left}" y="{top1 - 16}" font-size="16" font-weight="600" fill="#0f172a">资金曲线</text>')
    lines.append(f'<text x="{left}" y="{top2 - 16}" font-size="16" font-weight="600" fill="#0f172a">回撤曲线</text>')
    lines.append(
        f'<path d="{bank_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    lines.append(
        f'<path d="{dd_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
    )

    last_row = rows[-1]
    final_x = x_scale(int(last_row["day_index"]), len(rows), left, plot_w)
    final_y = y_scale(float(last_row["bankroll_after_day"]), bank_lo, bank_hi, top1, panel_h)
    lines.append(
        f'<circle cx="{final_x:.2f}" cy="{final_y:.2f}" r="4.8" fill="{spec.color}" stroke="#ffffff" stroke-width="2"/>'
    )
    lines.append(
        f'<text x="{final_x + 10:.2f}" y="{final_y - 8:.2f}" font-size="12" fill="{spec.color}">{float(last_row["bankroll_after_day"]):.0f}</text>'
    )
    lines.append("</svg>")

    output_name = f"{spec.daily_path.stem}_curve.svg"
    output_path = OUTPUT_DIR / output_name
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def build_overlay_svg(spec: CurveSpec, rows: list[dict[str, float | int | str]]) -> Path:
    width = 1320
    height = 620
    left = 92
    right = 78
    top = 96
    bottom = 84
    plot_w = width - left - right
    plot_h = height - top - bottom

    pnl_values = [float(row["total_real_pnl"]) for row in rows]
    bankroll_values = [float(row["bankroll_after_day"]) for row in rows]

    pnl_lo = min(min(pnl_values), 0.0)
    pnl_hi = max(max(pnl_values), 0.0)
    if pnl_lo == pnl_hi:
        pnl_hi = pnl_lo + 1.0

    bank_lo = min(bankroll_values)
    bank_hi = max(bankroll_values)
    if bank_lo == bank_hi:
        bank_hi = bank_lo + 1.0

    total_days = len(rows)
    day_labels = [
        (1, "D1"),
        (32, "D32"),
        (91, "D91"),
        (182, "D182"),
        (274, "D274"),
        (365, "D365"),
    ]
    zero_y = y_scale(0.0, pnl_lo, pnl_hi, top, plot_h)
    bar_step = plot_w / max(total_days, 1)
    bar_w = max(1.2, min(3.0, bar_step * 0.72))

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<text x="92" y="42" font-size="28" font-weight="700" fill="#0f172a">{spec.label} 日盈亏 + 资金曲线</text>',
        '<text x="92" y="68" font-size="14" fill="#475569">左轴为日盈亏，右轴为日终资金；柱状按天，折线为累计资金</text>',
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" rx="14" fill="#ffffff" stroke="#d1d5db"/>',
    ]

    for i in range(6):
        frac = i / 5
        y = top + frac * plot_h
        pnl_value = pnl_hi - frac * (pnl_hi - pnl_lo)
        bank_value = bank_hi - frac * (bank_hi - bank_lo)
        lines.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#e5e7eb" stroke-dasharray="4 4"/>'
        )
        lines.append(
            f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-size="12" fill="#6b7280">{pnl_value:.0f}</text>'
        )
        lines.append(
            f'<text x="{left + plot_w + 12}" y="{y + 4:.2f}" font-size="12" fill="#64748b">{bank_value:.0f}</text>'
        )

    lines.append(
        f'<line x1="{left}" y1="{zero_y:.2f}" x2="{left + plot_w}" y2="{zero_y:.2f}" stroke="#94a3b8" stroke-width="1.4"/>'
    )

    for day_index, label in day_labels:
        x = x_scale(day_index, total_days, left, plot_w)
        lines.append(
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#f3f4f6"/>'
        )
        lines.append(
            f'<text x="{x:.2f}" y="{top + plot_h + 22:.2f}" text-anchor="middle" font-size="12" fill="#6b7280">{label}</text>'
        )

    for row in rows:
        day_index = int(row["day_index"])
        pnl = float(row["total_real_pnl"])
        x = x_scale(day_index, total_days, left, plot_w)
        y = y_scale(pnl, pnl_lo, pnl_hi, top, plot_h)
        rect_x = x - bar_w / 2
        rect_y = min(y, zero_y)
        rect_h = max(1.0, abs(zero_y - y))
        fill = "#16a34a" if pnl >= 0 else "#dc2626"
        lines.append(
            f'<rect x="{rect_x:.2f}" y="{rect_y:.2f}" width="{bar_w:.2f}" height="{rect_h:.2f}" fill="{fill}" opacity="0.55"/>'
        )

    bankroll_path = build_path(
        bankroll_values,
        bank_lo,
        bank_hi,
        top,
        plot_h,
        left,
        plot_w,
    )
    lines.append(
        f'<path d="{bankroll_path}" fill="none" stroke="{spec.color}" stroke-width="3.0" stroke-linecap="round" stroke-linejoin="round"/>'
    )

    legend_x = width - 300
    legend_y = 42
    lines.append(
        f'<rect x="{legend_x}" y="{legend_y - 12}" width="12" height="12" fill="#16a34a" opacity="0.55"/>'
    )
    lines.append(
        f'<text x="{legend_x + 18}" y="{legend_y - 2}" font-size="12" fill="#334155">正日盈亏</text>'
    )
    lines.append(
        f'<rect x="{legend_x + 92}" y="{legend_y - 12}" width="12" height="12" fill="#dc2626" opacity="0.55"/>'
    )
    lines.append(
        f'<text x="{legend_x + 110}" y="{legend_y - 2}" font-size="12" fill="#334155">负日盈亏</text>'
    )
    lines.append(
        f'<line x1="{legend_x + 188}" y1="{legend_y - 6}" x2="{legend_x + 220}" y2="{legend_y - 6}" stroke="{spec.color}" stroke-width="3" stroke-linecap="round"/>'
    )
    lines.append(
        f'<text x="{legend_x + 228}" y="{legend_y - 2}" font-size="12" fill="#334155">资金曲线</text>'
    )

    last_row = rows[-1]
    final_x = x_scale(int(last_row["day_index"]), total_days, left, plot_w)
    final_y = y_scale(float(last_row["bankroll_after_day"]), bank_lo, bank_hi, top, plot_h)
    lines.append(
        f'<circle cx="{final_x:.2f}" cy="{final_y:.2f}" r="4.8" fill="{spec.color}" stroke="#ffffff" stroke-width="2"/>'
    )
    lines.append(
        f'<text x="{final_x + 10:.2f}" y="{final_y - 8:.2f}" font-size="12" fill="{spec.color}">{float(last_row["bankroll_after_day"]):.0f}</text>'
    )
    lines.append("</svg>")

    output_name = f"{spec.daily_path.stem}_pnl_overlay.svg"
    output_path = OUTPUT_DIR / output_name
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def build_stitched_comparison_svg(
    curves: list[tuple[StitchedCurveSpec, list[dict[str, float | int | str]]]]
) -> Path:
    width = 1440
    height = 860
    left = 92
    right = 52
    top1 = 92
    panel_h = 260
    gap = 110
    top2 = top1 + panel_h + gap
    plot_w = width - left - right

    bankroll_values = [
        float(row["bankroll_after_day"])
        for _, rows in curves
        for row in rows
    ]
    drawdown_values = [
        float(row["drawdown_from_peak"])
        for _, rows in curves
        for row in rows
    ]
    bank_lo = min(bankroll_values)
    bank_hi = max(bankroll_values)
    dd_lo = min(drawdown_values)
    dd_hi = 0.0
    day_labels = build_date_labels(
        curves[0][1],
        [
            ("2025-01-01", "2025-01"),
            ("2025-04-01", "2025-04"),
            ("2025-07-01", "2025-07"),
            ("2025-10-01", "2025-10"),
            ("2026-01-01", "2026-01"),
            ("2026-04-12", "2026-04-12"),
        ],
    )
    total_days = len(curves[0][1])
    year_switch_idx = next(
        int(row["day_index"]) for row in curves[0][1] if str(row["date"]) == "2026-01-01"
    )

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="92" y="42" font-size="28" font-weight="700" fill="#0f172a">Round36 两版本连续资金曲线</text>',
        '<text x="92" y="68" font-size="14" fill="#475569">区间 2025-01-01 到 2026-04-12，2026 段按承接 2025 年末资金继续滚动</text>',
    ]

    add_grid(lines, left, top1, plot_w, panel_h, bank_lo, bank_hi, day_labels)
    add_grid(lines, left, top2, plot_w, panel_h, dd_lo, dd_hi, day_labels)
    add_vertical_marker(lines, year_switch_idx, total_days, left, plot_w, top1, panel_h, "2026 续接起点")
    add_vertical_marker(lines, year_switch_idx, total_days, left, plot_w, top2, panel_h, "2026 续接起点")

    lines.append(f'<text x="{left}" y="{top1 - 16}" font-size="16" font-weight="600" fill="#0f172a">资金曲线</text>')
    lines.append(f'<text x="{left}" y="{top2 - 16}" font-size="16" font-weight="600" fill="#0f172a">回撤曲线</text>')

    legend_x = width - 280
    legend_y = 42
    for i, (spec, rows) in enumerate(curves):
        y = legend_y + i * 24
        lines.append(
            f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 30}" y2="{y}" stroke="{spec.color}" stroke-width="4" stroke-linecap="round"/>'
        )
        lines.append(
            f'<text x="{legend_x + 40}" y="{y + 4}" font-size="13" fill="#334155">{spec.label}</text>'
        )

        bankroll_path = build_path(
            [float(row["bankroll_after_day"]) for row in rows],
            bank_lo,
            bank_hi,
            top1,
            panel_h,
            left,
            plot_w,
        )
        drawdown_path = build_path(
            [float(row["drawdown_from_peak"]) for row in rows],
            dd_lo,
            dd_hi,
            top2,
            panel_h,
            left,
            plot_w,
        )
        lines.append(
            f'<path d="{bankroll_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        lines.append(
            f'<path d="{drawdown_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )

        final_row = rows[-1]
        final_x = x_scale(int(final_row["day_index"]), len(rows), left, plot_w)
        final_y = y_scale(float(final_row["bankroll_after_day"]), bank_lo, bank_hi, top1, panel_h)
        lines.append(
            f'<circle cx="{final_x:.2f}" cy="{final_y:.2f}" r="4.8" fill="{spec.color}" stroke="#ffffff" stroke-width="2"/>'
        )
        lines.append(
            f'<text x="{final_x + 10:.2f}" y="{final_y - 8:.2f}" font-size="12" fill="{spec.color}">{float(final_row["bankroll_after_day"]):.0f}</text>'
        )

    lines.append("</svg>")

    output_path = OUTPUT_DIR / "round36_two_version_continuous_2025-01-01_2026-04-12_curve_comparison.svg"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def build_stitched_single_svg(spec: StitchedCurveSpec, rows: list[dict[str, float | int | str]]) -> Path:
    width = 1360
    height = 720
    left = 92
    right = 52
    top1 = 92
    panel_h = 220
    gap = 90
    top2 = top1 + panel_h + gap
    plot_w = width - left - right

    bankroll_values = [float(row["bankroll_after_day"]) for row in rows]
    drawdown_values = [float(row["drawdown_from_peak"]) for row in rows]
    bank_lo = min(bankroll_values)
    bank_hi = max(bankroll_values)
    dd_lo = min(drawdown_values)
    dd_hi = 0.0
    day_labels = build_date_labels(
        rows,
        [
            ("2025-01-01", "2025-01"),
            ("2025-04-01", "2025-04"),
            ("2025-07-01", "2025-07"),
            ("2025-10-01", "2025-10"),
            ("2026-01-01", "2026-01"),
            ("2026-04-12", "2026-04-12"),
        ],
    )
    year_switch_idx = next(int(row["day_index"]) for row in rows if str(row["date"]) == "2026-01-01")

    bank_path = build_path(bankroll_values, bank_lo, bank_hi, top1, panel_h, left, plot_w)
    dd_path = build_path(drawdown_values, dd_lo, dd_hi, top2, panel_h, left, plot_w)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<text x="92" y="42" font-size="28" font-weight="700" fill="#0f172a">{spec.label} 连续资金曲线</text>',
        '<text x="92" y="68" font-size="14" fill="#475569">区间 2025-01-01 到 2026-04-12，2026 段按承接 2025 年末资金续算</text>',
    ]
    add_grid(lines, left, top1, plot_w, panel_h, bank_lo, bank_hi, day_labels)
    add_grid(lines, left, top2, plot_w, panel_h, dd_lo, dd_hi, day_labels)
    add_vertical_marker(lines, year_switch_idx, len(rows), left, plot_w, top1, panel_h, "2026 续接起点")
    add_vertical_marker(lines, year_switch_idx, len(rows), left, plot_w, top2, panel_h, "2026 续接起点")
    lines.append(f'<text x="{left}" y="{top1 - 16}" font-size="16" font-weight="600" fill="#0f172a">资金曲线</text>')
    lines.append(f'<text x="{left}" y="{top2 - 16}" font-size="16" font-weight="600" fill="#0f172a">回撤曲线</text>')
    lines.append(
        f'<path d="{bank_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    lines.append(
        f'<path d="{dd_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
    )

    last_row = rows[-1]
    final_x = x_scale(int(last_row["day_index"]), len(rows), left, plot_w)
    final_y = y_scale(float(last_row["bankroll_after_day"]), bank_lo, bank_hi, top1, panel_h)
    lines.append(
        f'<circle cx="{final_x:.2f}" cy="{final_y:.2f}" r="4.8" fill="{spec.color}" stroke="#ffffff" stroke-width="2"/>'
    )
    lines.append(
        f'<text x="{final_x + 10:.2f}" y="{final_y - 8:.2f}" font-size="12" fill="{spec.color}">{float(last_row["bankroll_after_day"]):.0f}</text>'
    )
    lines.append("</svg>")

    candidate_id = spec.label.split()[-1]
    output_path = OUTPUT_DIR / f"three_play_{candidate_id}_continuous_2025-01-01_2026-04-12_curve.svg"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def main() -> None:
    loaded = [(spec, load_curve(spec)) for spec in CURVES]
    stitched_loaded = [(spec, load_stitched_curve(spec)) for spec in STITCHED_CURVES]
    outputs = [build_comparison_svg(loaded)]
    outputs.append(build_stitched_comparison_svg(stitched_loaded))
    outputs.extend(build_single_svg(spec, rows) for spec, rows in loaded)
    outputs.extend(build_stitched_single_svg(spec, rows) for spec, rows in stitched_loaded)
    outputs.extend(build_overlay_svg(spec, rows) for spec, rows in loaded)
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
