"""Simulate local model monitoring for drift and operational signals."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config import (
    BATCH_INPUT_PATH,
    BATCH_PREDICTIONS_PATH,
    CATEGORICAL_FEATURES,
    MONITORING_CHARTS_DIR,
    MONITORING_MARKDOWN_PATH,
    MONITORING_REPORT_PATH,
    NUMERIC_FEATURES,
    TRAIN_DATA_PATH,
    ensure_directories,
    project_relative,
    require_file,
)
from src.data_preparation import ensure_feature_frame
from src.modeling import save_json, utc_now_iso


SVG_BLUE = "#2f6fed"
SVG_ORANGE = "#f59e0b"
SVG_GREEN = "#2f9e44"
SVG_AMBER = "#f08c00"
SVG_RED = "#d9480f"
SVG_GRID = "#e9ecef"
SVG_TEXT = "#222222"


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()


def _svg_text(x: float, y: float, text: str, size: int = 12, anchor: str = "start") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, sans-serif" '
        f'font-size="{size}" fill="{SVG_TEXT}" text-anchor="{anchor}">{html.escape(text)}</text>'
    )


def _write_svg(path: Path, width: int, height: int, body: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="white"/>',
            *body,
            "</svg>",
        ]
    )
    path.write_text(content, encoding="utf-8")


def _bar_color(value: float, warn: float, alert: float) -> str:
    if value >= alert:
        return SVG_RED
    if value >= warn:
        return SVG_AMBER
    return SVG_GREEN


def population_stability_index(expected: pd.Series, actual: pd.Series, buckets: int = 10) -> float:
    expected_values = pd.to_numeric(expected, errors="coerce").dropna().to_numpy(dtype=float)
    actual_values = pd.to_numeric(actual, errors="coerce").dropna().to_numpy(dtype=float)
    if len(expected_values) == 0 or len(actual_values) == 0:
        return 0.0

    quantiles = np.linspace(0.0, 1.0, buckets + 1)
    breakpoints = np.unique(np.quantile(expected_values, quantiles))
    if len(breakpoints) < 3:
        return 0.0

    expected_counts, _ = np.histogram(expected_values, bins=breakpoints)
    actual_counts, _ = np.histogram(actual_values, bins=breakpoints)
    expected_pct = np.maximum(expected_counts / max(expected_counts.sum(), 1), 1e-6)
    actual_pct = np.maximum(actual_counts / max(actual_counts.sum(), 1), 1e-6)
    return float(np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct)))


def numeric_drift_report(baseline: pd.DataFrame, current: pd.DataFrame) -> dict[str, Any]:
    report = {}
    for column in NUMERIC_FEATURES:
        baseline_values = pd.to_numeric(baseline[column], errors="coerce")
        current_values = pd.to_numeric(current[column], errors="coerce")
        baseline_mean = float(baseline_values.mean())
        current_mean = float(current_values.mean())
        baseline_std = float(baseline_values.std(ddof=0)) or 1.0
        mean_shift_std = abs(current_mean - baseline_mean) / max(baseline_std, 1e-8)
        psi = population_stability_index(baseline_values, current_values)
        report[column] = {
            "baseline_mean": baseline_mean,
            "current_mean": current_mean,
            "mean_shift_std": float(mean_shift_std),
            "psi": float(psi),
            "status": "alert" if psi >= 0.25 or mean_shift_std >= 1.5 else "ok",
        }
    return report


def categorical_drift_report(baseline: pd.DataFrame, current: pd.DataFrame) -> dict[str, Any]:
    report = {}
    for column in CATEGORICAL_FEATURES:
        baseline_dist = baseline[column].fillna("unknown").astype(str).value_counts(normalize=True)
        current_dist = current[column].fillna("unknown").astype(str).value_counts(normalize=True)
        categories = sorted(set(baseline_dist.index).union(current_dist.index))
        max_delta = max(abs(float(current_dist.get(category, 0.0) - baseline_dist.get(category, 0.0))) for category in categories)
        report[column] = {
            "max_distribution_delta": float(max_delta),
            "current_top_values": {str(k): float(v) for k, v in current_dist.head(5).to_dict().items()},
            "status": "alert" if max_delta >= 0.20 else "ok",
        }
    return report


def render_numeric_histogram(
    feature: str,
    baseline: pd.Series,
    current: pd.Series,
    output_path: Path,
    buckets: int = 12,
) -> None:
    baseline_values = pd.to_numeric(baseline, errors="coerce").dropna().to_numpy(dtype=float)
    current_values = pd.to_numeric(current, errors="coerce").dropna().to_numpy(dtype=float)
    if len(baseline_values) == 0 or len(current_values) == 0:
        return

    combined = np.concatenate([baseline_values, current_values])
    min_value = float(np.min(combined))
    max_value = float(np.max(combined))
    if min_value == max_value:
        min_value -= 0.5
        max_value += 0.5

    bins = np.linspace(min_value, max_value, buckets + 1)
    baseline_counts, _ = np.histogram(baseline_values, bins=bins)
    current_counts, _ = np.histogram(current_values, bins=bins)
    baseline_pct = baseline_counts / max(baseline_counts.sum(), 1)
    current_pct = current_counts / max(current_counts.sum(), 1)
    max_pct = float(max(baseline_pct.max(), current_pct.max(), 0.01))

    width, height = 900, 420
    left, right, top, bottom = 70, 30, 70, 70
    plot_width = width - left - right
    plot_height = height - top - bottom
    group_width = plot_width / buckets
    bar_width = group_width * 0.36

    body = [
        _svg_text(width / 2, 28, f"Numeric drift histogram: {feature}", 18, "middle"),
        _svg_text(width / 2, 50, "Baseline train distribution vs current batch distribution", 12, "middle"),
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="{SVG_TEXT}"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="{SVG_TEXT}"/>',
        f'<rect x="{left + 15}" y="58" width="12" height="12" fill="{SVG_BLUE}"/>',
        _svg_text(left + 32, 69, "baseline", 12),
        f'<rect x="{left + 115}" y="58" width="12" height="12" fill="{SVG_ORANGE}"/>',
        _svg_text(left + 132, 69, "current", 12),
    ]

    for idx in range(5):
        pct = max_pct * idx / 4
        y = top + plot_height - (pct / max_pct) * plot_height
        body.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="{SVG_GRID}"/>')
        body.append(_svg_text(left - 8, y + 4, f"{pct:.0%}", 10, "end"))

    for idx in range(buckets):
        x = left + idx * group_width + group_width * 0.12
        baseline_height = (baseline_pct[idx] / max_pct) * plot_height
        current_height = (current_pct[idx] / max_pct) * plot_height
        body.append(
            f'<rect x="{x:.1f}" y="{top + plot_height - baseline_height:.1f}" '
            f'width="{bar_width:.1f}" height="{baseline_height:.1f}" fill="{SVG_BLUE}" opacity="0.82"/>'
        )
        body.append(
            f'<rect x="{x + bar_width + 2:.1f}" y="{top + plot_height - current_height:.1f}" '
            f'width="{bar_width:.1f}" height="{current_height:.1f}" fill="{SVG_ORANGE}" opacity="0.82"/>'
        )
        if idx in {0, buckets // 2, buckets - 1}:
            label = f"{bins[idx]:.1f}"
            body.append(_svg_text(x, top + plot_height + 18, label, 10, "middle"))

    body.append(_svg_text(left + plot_width / 2, height - 20, "Feature value buckets", 12, "middle"))
    body.append(_svg_text(18, top + plot_height / 2, "Share of rows", 12, "middle"))
    _write_svg(output_path, width, height, body)


def render_categorical_bars(
    feature: str,
    baseline: pd.Series,
    current: pd.Series,
    output_path: Path,
    max_categories: int = 12,
) -> None:
    baseline_dist = baseline.fillna("unknown").astype(str).value_counts(normalize=True)
    current_dist = current.fillna("unknown").astype(str).value_counts(normalize=True)
    combined_rank = (baseline_dist.add(current_dist, fill_value=0.0)).sort_values(ascending=False)
    categories = list(combined_rank.head(max_categories).index)
    if not categories:
        return

    width = 980
    height = 110 + len(categories) * 42
    left, right, top = 190, 40, 72
    plot_width = width - left - right
    max_pct = max(float(baseline_dist.reindex(categories).fillna(0).max()), float(current_dist.reindex(categories).fillna(0).max()), 0.01)

    body = [
        _svg_text(width / 2, 28, f"Categorical drift bars: {feature}", 18, "middle"),
        _svg_text(width / 2, 50, "Baseline train share vs current batch share", 12, "middle"),
        f'<rect x="{left}" y="58" width="12" height="12" fill="{SVG_BLUE}"/>',
        _svg_text(left + 17, 69, "baseline", 12),
        f'<rect x="{left + 100}" y="58" width="12" height="12" fill="{SVG_ORANGE}"/>',
        _svg_text(left + 117, 69, "current", 12),
    ]

    for idx, category in enumerate(categories):
        y = top + idx * 42
        baseline_pct = float(baseline_dist.get(category, 0.0))
        current_pct = float(current_dist.get(category, 0.0))
        baseline_width = (baseline_pct / max_pct) * plot_width
        current_width = (current_pct / max_pct) * plot_width
        body.append(_svg_text(left - 10, y + 15, str(category), 11, "end"))
        body.append(f'<rect x="{left}" y="{y:.1f}" width="{baseline_width:.1f}" height="15" fill="{SVG_BLUE}" opacity="0.82"/>')
        body.append(f'<rect x="{left}" y="{y + 18:.1f}" width="{current_width:.1f}" height="15" fill="{SVG_ORANGE}" opacity="0.82"/>')
        body.append(_svg_text(left + baseline_width + 6, y + 12, f"{baseline_pct:.1%}", 10))
        body.append(_svg_text(left + current_width + 6, y + 30, f"{current_pct:.1%}", 10))

    _write_svg(output_path, width, height, body)


def render_psi_chart(numeric_report: dict[str, Any], output_path: Path) -> None:
    rows = sorted(
        ((feature, values["psi"], values["mean_shift_std"], values["status"]) for feature, values in numeric_report.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    width = 980
    height = 100 + len(rows) * 34
    left, right, top = 230, 40, 72
    plot_width = width - left - right
    max_value = max([row[1] for row in rows] + [0.25])

    body = [
        _svg_text(width / 2, 28, "PSI by numeric feature", 18, "middle"),
        _svg_text(width / 2, 50, "Higher PSI means stronger distribution shift", 12, "middle"),
        _svg_text(left + plot_width * (0.10 / max_value), 68, "0.10 watch", 10, "middle"),
        _svg_text(left + plot_width * (0.25 / max_value), 68, "0.25 alert", 10, "middle"),
    ]
    body.append(f'<line x1="{left + plot_width * (0.10 / max_value):.1f}" y1="{top - 8}" x2="{left + plot_width * (0.10 / max_value):.1f}" y2="{height - 25}" stroke="{SVG_AMBER}" stroke-dasharray="4 4"/>')
    body.append(f'<line x1="{left + plot_width * (0.25 / max_value):.1f}" y1="{top - 8}" x2="{left + plot_width * (0.25 / max_value):.1f}" y2="{height - 25}" stroke="{SVG_RED}" stroke-dasharray="4 4"/>')

    for idx, (feature, psi, shift, status) in enumerate(rows):
        y = top + idx * 34
        bar_width = (psi / max_value) * plot_width
        color = _bar_color(psi, warn=0.10, alert=0.25)
        body.append(_svg_text(left - 10, y + 15, feature, 11, "end"))
        body.append(f'<rect x="{left}" y="{y:.1f}" width="{bar_width:.1f}" height="18" fill="{color}" opacity="0.86"/>')
        body.append(_svg_text(left + bar_width + 6, y + 14, f"PSI={psi:.4f}, shift={shift:.3f}, {status}", 10))

    _write_svg(output_path, width, height, body)


def render_alert_heatmap(
    numeric_report: dict[str, Any],
    categorical_report: dict[str, Any],
    review_or_block_rate: float,
    output_path: Path,
) -> None:
    rows: list[tuple[str, float, float, float, float]] = []
    for feature, values in numeric_report.items():
        rows.append((feature, float(values["psi"]) / 0.25, float(values["mean_shift_std"]) / 1.5, 0.0, 0.0))
    for feature, values in categorical_report.items():
        rows.append((feature, 0.0, 0.0, float(values["max_distribution_delta"]) / 0.20, 0.0))
    rows.append(("review_or_block_rate", 0.0, 0.0, 0.0, review_or_block_rate / 0.40))

    columns = ["PSI", "Mean shift", "Cat delta", "Operational"]
    width = 860
    cell = 34
    left, top = 210, 86
    height = top + len(rows) * cell + 40
    body = [
        _svg_text(width / 2, 28, "Alert heatmap", 18, "middle"),
        _svg_text(width / 2, 50, "Intensity is relative to alert thresholds", 12, "middle"),
    ]

    for col_idx, column in enumerate(columns):
        body.append(_svg_text(left + col_idx * 130 + 55, top - 12, column, 11, "middle"))

    for row_idx, (feature, psi_score, shift_score, cat_score, op_score) in enumerate(rows):
        y = top + row_idx * cell
        body.append(_svg_text(left - 12, y + 22, feature, 11, "end"))
        for col_idx, score in enumerate([psi_score, shift_score, cat_score, op_score]):
            intensity = max(0.0, min(score, 1.0))
            if score >= 1.0:
                color = SVG_RED
            elif score >= 0.5:
                color = SVG_AMBER
            elif score > 0:
                color = SVG_GREEN
            else:
                color = "#f1f3f5"
            x = left + col_idx * 130
            body.append(f'<rect x="{x}" y="{y}" width="110" height="24" fill="{color}" opacity="{0.25 + 0.70 * intensity:.2f}" stroke="#ced4da"/>')
            body.append(_svg_text(x + 55, y + 17, f"{score:.2f}", 10, "middle"))

    _write_svg(output_path, width, height, body)


def generate_monitoring_charts(
    baseline_df: pd.DataFrame,
    current_df: pd.DataFrame,
    predictions_df: pd.DataFrame,
    numeric_report: dict[str, Any],
    categorical_report: dict[str, Any],
    review_or_block_rate: float,
    charts_dir: Path,
) -> dict[str, Any]:
    charts_dir.mkdir(parents=True, exist_ok=True)
    chart_paths: dict[str, Any] = {
        "numeric_histograms": {},
        "categorical_bars": {},
    }

    for feature in NUMERIC_FEATURES:
        path = charts_dir / f"numeric_{_slug(feature)}.svg"
        render_numeric_histogram(feature, baseline_df[feature], current_df[feature], path)
        if path.exists():
            chart_paths["numeric_histograms"][feature] = project_relative(path)

    for feature in CATEGORICAL_FEATURES:
        path = charts_dir / f"categorical_{_slug(feature)}.svg"
        render_categorical_bars(feature, baseline_df[feature], current_df[feature], path)
        if path.exists():
            chart_paths["categorical_bars"][feature] = project_relative(path)

    psi_path = charts_dir / "psi_by_feature.svg"
    render_psi_chart(numeric_report, psi_path)
    heatmap_path = charts_dir / "alert_heatmap.svg"
    render_alert_heatmap(numeric_report, categorical_report, review_or_block_rate, heatmap_path)

    chart_paths["psi_by_feature"] = project_relative(psi_path)
    chart_paths["alert_heatmap"] = project_relative(heatmap_path)
    chart_paths["charts_dir"] = project_relative(charts_dir)

    # Keep this read to make it explicit that charts are tied to predictions as well.
    _ = predictions_df[["fraud_probability", "risk_decision"]].head(1)
    return chart_paths


def render_monitoring_markdown(payload: dict[str, Any]) -> str:
    alert_lines = [f"- {alert}" for alert in payload["alerts"]] or ["- No alerts."]
    numeric_lines = [
        f"| {name} | {values['psi']:.4f} | {values['mean_shift_std']:.4f} | {values['status']} |"
        for name, values in payload["numeric_drift"].items()
    ]
    categorical_lines = [
        f"| {name} | {values['max_distribution_delta']:.4f} | {values['status']} |"
        for name, values in payload["categorical_drift"].items()
    ]
    chart_paths = payload.get("chart_paths", {})
    chart_lines = [
        f"- PSI ranking: `{chart_paths.get('psi_by_feature', 'n/a')}`",
        f"- Alert heatmap: `{chart_paths.get('alert_heatmap', 'n/a')}`",
        f"- Chart directory: `{chart_paths.get('charts_dir', 'n/a')}`",
    ]
    return "\n".join(
        [
            "# Monitoring Report",
            "",
            f"Created at: `{payload['created_at']}`",
            "",
            "## Operational Signals",
            "",
            f"- Baseline rows: `{payload['baseline_rows']}`",
            f"- Current rows: `{payload['current_rows']}`",
            f"- Average fraud probability: `{payload['average_fraud_probability']:.4f}`",
            f"- Review/block rate: `{payload['review_or_block_rate']:.4f}`",
            "",
            "## Alerts",
            "",
            *alert_lines,
            "",
            "## Visual Drift Charts",
            "",
            *chart_lines,
            "",
            "Open the SVG files in a browser to inspect baseline vs current distributions visually.",
            "",
            "## Numeric Drift",
            "",
            "| Feature | PSI | Mean shift std | Status |",
            "|---|---:|---:|---|",
            *numeric_lines,
            "",
            "## Categorical Drift",
            "",
            "| Feature | Max distribution delta | Status |",
            "|---|---:|---|",
            *categorical_lines,
            "",
            "## AWS Mapping",
            "",
            "This local report mirrors SageMaker Model Monitor plus CloudWatch metrics and alarms.",
        ]
    )


def run_monitoring(
    baseline_path: Path = TRAIN_DATA_PATH,
    current_path: Path = BATCH_INPUT_PATH,
    predictions_path: Path = BATCH_PREDICTIONS_PATH,
    report_path: Path = MONITORING_REPORT_PATH,
    markdown_path: Path = MONITORING_MARKDOWN_PATH,
    charts_dir: Path = MONITORING_CHARTS_DIR,
) -> dict[str, Any]:
    ensure_directories()
    require_file(baseline_path, "Run `make prepare` first.")
    require_file(current_path, "Run `make prepare` first.")
    require_file(predictions_path, "Run `make batch` first.")

    baseline_df = ensure_feature_frame(pd.read_csv(baseline_path))
    current_df = ensure_feature_frame(pd.read_csv(current_path))
    predictions_df = pd.read_csv(predictions_path)

    numeric = numeric_drift_report(baseline_df, current_df)
    categorical = categorical_drift_report(baseline_df, current_df)

    alerts = []
    for name, values in numeric.items():
        if values["status"] == "alert":
            alerts.append(f"Numeric drift alert for {name}: psi={values['psi']:.3f}, shift={values['mean_shift_std']:.3f}")
    for name, values in categorical.items():
        if values["status"] == "alert":
            alerts.append(f"Categorical drift alert for {name}: max_delta={values['max_distribution_delta']:.3f}")

    avg_probability = float(predictions_df["fraud_probability"].mean())
    review_or_block_rate = float(predictions_df["risk_decision"].isin(["review", "block"]).mean())
    if review_or_block_rate >= 0.40:
        alerts.append(f"High review/block rate: {review_or_block_rate:.3f}")

    chart_paths = generate_monitoring_charts(
        baseline_df=baseline_df,
        current_df=current_df,
        predictions_df=predictions_df,
        numeric_report=numeric,
        categorical_report=categorical,
        review_or_block_rate=review_or_block_rate,
        charts_dir=charts_dir,
    )

    payload = {
        "created_at": utc_now_iso(),
        "baseline_path": project_relative(baseline_path),
        "current_path": project_relative(current_path),
        "predictions_path": project_relative(predictions_path),
        "baseline_rows": int(len(baseline_df)),
        "current_rows": int(len(current_df)),
        "average_fraud_probability": avg_probability,
        "review_or_block_rate": review_or_block_rate,
        "numeric_drift": numeric,
        "categorical_drift": categorical,
        "alerts": alerts,
        "chart_paths": chart_paths,
        "aws_equivalent": "SageMaker Model Monitor + CloudWatch + EventBridge/SNS",
    }
    save_json(report_path, payload)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_monitoring_markdown(payload), encoding="utf-8")

    print(f"[monitor] wrote {report_path}")
    print(f"[monitor] alerts={len(alerts)}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local monitoring simulation.")
    parser.add_argument("--baseline-path", default=str(TRAIN_DATA_PATH))
    parser.add_argument("--current-path", default=str(BATCH_INPUT_PATH))
    parser.add_argument("--predictions-path", default=str(BATCH_PREDICTIONS_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_monitoring(
        baseline_path=Path(args.baseline_path),
        current_path=Path(args.current_path),
        predictions_path=Path(args.predictions_path),
    )


if __name__ == "__main__":
    main()
