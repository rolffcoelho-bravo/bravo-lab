"""
Premium figure layer for BRAVO Lab.

This module creates investment-committee-style visual evidence for the report.

The objective is not decorative plotting. The objective is premium quant/risk
communication:

- clear visual hierarchy
- institutional chart styling
- concise captions
- source notes
- risk-first interpretation
- reproducible figures from processed CSV outputs
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter


DEFAULT_PROCESSED_DIR = Path("data/processed")
DEFAULT_FIGURES_DIR = Path("reports/figures")


PALETTE = {
    "navy": "#0B1F33",
    "blue": "#1F5A99",
    "slate": "#5D6D7E",
    "gold": "#B8872D",
    "red": "#A23B3B",
    "green": "#2F7D5C",
    "gray": "#AAB2BD",
    "light": "#F5F7FA",
    "grid": "#D8DEE9",
}


STRATEGY_LABELS = {
    "passive_brazil_equity": "Passive Brazil equity",
    "covered_call": "Covered call",
    "collar": "Collar",
    "stress_aware_overlay": "Stress-aware overlay",
    "bsti_policy_overlay": "BSTI policy overlay",
}


STRATEGY_COLORS = {
    "passive_brazil_equity": PALETTE["slate"],
    "covered_call": PALETTE["gold"],
    "collar": PALETTE["green"],
    "stress_aware_overlay": PALETTE["blue"],
    "bsti_policy_overlay": PALETTE["navy"],
}


def _set_premium_theme() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#C7CED8",
            "axes.labelcolor": PALETTE["navy"],
            "xtick.color": "#34495E",
            "ytick.color": "#34495E",
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titleweight": "bold",
            "axes.titlesize": 13,
            "axes.labelsize": 9,
            "legend.fontsize": 8.5,
            "savefig.facecolor": "white",
            "savefig.edgecolor": "white",
        }
    )


def _read_csv(path: Path, index_col: int | None = 0) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        data = pd.read_csv(path, index_col=index_col)
    except Exception:
        return pd.DataFrame()

    if data.empty:
        return data

    try:
        index_text = pd.Series(data.index.astype(str))
        date_like_share = index_text.str.match(
            r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}"
        ).mean()

        if date_like_share >= 0.80:
            converted_index = pd.to_datetime(
                data.index,
                errors="coerce",
                format="%Y-%m-%d",
            )

            if converted_index.notna().sum() == len(converted_index):
                data.index = converted_index
    except Exception:
        pass

    return data


def _clean_numeric(data: pd.DataFrame) -> pd.DataFrame:
    output = data.copy()

    for column in output.columns:
        converted = pd.to_numeric(output[column], errors="coerce")

        if converted.notna().sum() > 0:
            output[column] = converted

    return output


def _format_pct(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{value:.2%}"


def _format_num(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{value:.2f}"


def _style_axes(ax, title: str, subtitle: str | None = None) -> None:
    ax.set_title(title, loc="left", pad=18, color=PALETTE["navy"])

    if subtitle:
        ax.text(
            0,
            1.015,
            subtitle,
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=9,
            color="#5A6775",
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis="y", color=PALETTE["grid"], linewidth=0.75, alpha=0.55)
    ax.tick_params(axis="both", labelsize=8.5)


def _add_source_note(fig, note: str) -> None:
    fig.text(
        0.01,
        0.01,
        note,
        ha="left",
        va="bottom",
        fontsize=7.5,
        color="#6B7280",
    )


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    # The executive dashboard uses manually positioned card axes.
    # Calling tight_layout on that figure creates harmless warning noise,
    # so layout is only tightened for standard chart figures.
    if "executive_risk_dashboard" not in path.name:
        fig.tight_layout(rect=[0, 0.035, 1, 1])

    fig.savefig(path, dpi=260, bbox_inches="tight")
    plt.close(fig)
    return path


def _cumulative_returns(returns: pd.DataFrame) -> pd.DataFrame:
    return (1.0 + returns.fillna(0.0)).cumprod() - 1.0


def _drawdown(returns: pd.DataFrame) -> pd.DataFrame:
    cumulative = (1.0 + returns.fillna(0.0)).cumprod()
    running_peak = cumulative.cummax()
    return cumulative / running_peak - 1.0


def build_executive_dashboard(processed_dir: Path, figures_dir: Path) -> Path | None:
    latest_bsti = _read_csv(
        processed_dir / "brazil_stress_transmission_index_latest.csv",
        index_col=None,
    )

    policy = _read_csv(
        processed_dir / "bsti_policy_decisions.csv",
    )

    comparison = _read_csv(
        processed_dir / "bsti_policy_comparison_summary.csv",
    )

    latest_score = np.nan
    latest_regime = "NA"
    latest_channel = "NA"

    if not latest_bsti.empty:
        latest_score = pd.to_numeric(
            latest_bsti.get("bsti_0_100", pd.Series([np.nan])),
            errors="coerce",
        ).iloc[-1]

        latest_regime = str(
            latest_bsti.get("bsti_regime", pd.Series(["NA"])).iloc[-1]
        )

        latest_channel = str(
            latest_bsti.get("dominant_pressure_channel", pd.Series(["NA"])).iloc[-1]
        )

    latest_policy = "NA"

    if not policy.empty and "selected_strategy" in policy.columns:
        latest_policy = str(policy["selected_strategy"].dropna().iloc[-1])

    best_ir = "NA"
    best_drawdown = "NA"

    if not comparison.empty:
        comparison = _clean_numeric(comparison)

        if "information_ratio" in comparison.columns:
            valid = comparison["information_ratio"].dropna()

            if not valid.empty:
                best_ir = str(valid.idxmax())

        if "max_drawdown" in comparison.columns:
            valid = comparison["max_drawdown"].dropna()

            if not valid.empty:
                best_drawdown = str(valid.idxmax())

    fig = plt.figure(figsize=(12, 6.6))
    fig.suptitle(
        "BRAVO Lab Executive Risk Dashboard",
        x=0.02,
        y=0.98,
        ha="left",
        fontsize=16,
        fontweight="bold",
        color=PALETTE["navy"],
    )

    fig.text(
        0.02,
        0.925,
        "Brazilian risk, allocation, volatility, options, and stress-transmission intelligence",
        ha="left",
        fontsize=9.5,
        color="#5A6775",
    )

    cards = [
        ("Latest BSTI", _format_num(latest_score), "Composite stress score, 0 to 100"),
        ("BSTI regime", latest_regime.replace("_", " ").title(), "Current transmission state"),
        ("Dominant channel", latest_channel.replace("_", " ").title(), "Main pressure source"),
        ("Policy action", latest_policy.replace("_", " ").title(), "Current overlay rule"),
        ("Best information ratio", best_ir.replace("_", " ").title(), "Highest active-risk efficiency"),
        ("Best drawdown profile", best_drawdown.replace("_", " ").title(), "Least severe max drawdown"),
    ]

    positions = [
        (0.02, 0.58),
        (0.35, 0.58),
        (0.68, 0.58),
        (0.02, 0.25),
        (0.35, 0.25),
        (0.68, 0.25),
    ]

    for (title, value, subtitle), (x, y) in zip(cards, positions):
        ax = fig.add_axes([x, y, 0.29, 0.23])
        ax.set_facecolor("#F8FAFC")

        for spine in ax.spines.values():
            spine.set_edgecolor("#D7DEE8")
            spine.set_linewidth(1.0)

        ax.set_xticks([])
        ax.set_yticks([])

        ax.text(
            0.04,
            0.78,
            title,
            transform=ax.transAxes,
            fontsize=9,
            color="#5A6775",
            fontweight="bold",
        )

        ax.text(
            0.04,
            0.43,
            str(value),
            transform=ax.transAxes,
            fontsize=16,
            color=PALETTE["navy"],
            fontweight="bold",
        )

        ax.text(
            0.04,
            0.16,
            subtitle,
            transform=ax.transAxes,
            fontsize=8,
            color="#687385",
        )

    _add_source_note(
        fig,
        "Source: BRAVO Lab processed outputs. Dashboard is generated automatically from reproducible CSV evidence files.",
    )

    return _save(fig, figures_dir / "00_executive_risk_dashboard.png")


def build_cumulative_performance_figure(processed_dir: Path, figures_dir: Path) -> Path | None:
    data = _read_csv(processed_dir / "bsti_policy_overlay_returns.csv")

    if data.empty:
        data = _read_csv(processed_dir / "overlay_return_table.csv")

    if data.empty:
        return None

    columns = [
        col
        for col in [
            "passive_brazil_equity",
            "covered_call",
            "collar",
            "stress_aware_overlay",
            "bsti_policy_overlay",
        ]
        if col in data.columns
    ]

    if not columns:
        return None

    cumulative = _cumulative_returns(data[columns])

    fig, ax = plt.subplots(figsize=(12, 6.7))

    for col in columns:
        ax.plot(
            cumulative.index,
            cumulative[col],
            linewidth=2.2 if col == "bsti_policy_overlay" else 1.75,
            color=STRATEGY_COLORS.get(col, PALETTE["gray"]),
            label=STRATEGY_LABELS.get(col, col.replace("_", " ").title()),
        )

    _style_axes(
        ax,
        "Cumulative performance path",
        "Strategy growth paths from periodic return series. The focus is path quality, not a single terminal number.",
    )

    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_ylabel("Cumulative return")
    ax.legend(frameon=False, loc="best")

    _add_source_note(
        fig,
        "Source: BRAVO Lab overlay return table and BSTI policy overlay returns.",
    )

    return _save(fig, figures_dir / "01_cumulative_performance.png")


def build_drawdown_figure(processed_dir: Path, figures_dir: Path) -> Path | None:
    data = _read_csv(processed_dir / "bsti_policy_overlay_returns.csv")

    if data.empty:
        data = _read_csv(processed_dir / "overlay_return_table.csv")

    if data.empty:
        return None

    columns = [
        col
        for col in [
            "passive_brazil_equity",
            "collar",
            "stress_aware_overlay",
            "bsti_policy_overlay",
        ]
        if col in data.columns
    ]

    if not columns:
        return None

    drawdown = _drawdown(data[columns])

    fig, ax = plt.subplots(figsize=(12, 6.7))

    for col in columns:
        ax.plot(
            drawdown.index,
            drawdown[col],
            linewidth=2.1 if col == "bsti_policy_overlay" else 1.7,
            color=STRATEGY_COLORS.get(col, PALETTE["gray"]),
            label=STRATEGY_LABELS.get(col, col.replace("_", " ").title()),
        )

    _style_axes(
        ax,
        "Drawdown control map",
        "Peak-to-trough losses by strategy. This is the visual test of whether protection improved the risk path.",
    )

    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_ylabel("Drawdown")
    ax.legend(frameon=False, loc="lower left")

    _add_source_note(
        fig,
        "Source: BRAVO Lab strategy return series. Drawdowns are calculated from cumulative strategy paths.",
    )

    return _save(fig, figures_dir / "02_drawdown_profile.png")


def build_bsti_signal_figure(processed_dir: Path, figures_dir: Path) -> Path | None:
    data = _read_csv(processed_dir / "brazil_stress_transmission_index.csv")

    if data.empty or "bsti_0_100" not in data.columns:
        return None

    fig, ax = plt.subplots(figsize=(12, 6.7))

    ax.fill_between(
        data.index,
        33,
        100,
        color=PALETTE["red"],
        alpha=0.08,
        label="Stress zone",
    )

    ax.fill_between(
        data.index,
        15,
        33,
        color=PALETTE["gold"],
        alpha=0.10,
        label="Warning zone",
    )

    ax.plot(
        data.index,
        data["bsti_0_100"],
        color=PALETTE["navy"],
        linewidth=2.1,
        label="BSTI",
    )

    ax.axhline(15.0, linewidth=1.1, linestyle="--", color=PALETTE["gold"], alpha=0.85)
    ax.axhline(33.0, linewidth=1.1, linestyle="--", color=PALETTE["red"], alpha=0.85)

    _style_axes(
        ax,
        "Brazil Stress Transmission Index",
        "Composite stress signal with warning and stress zones. The point is governance visibility, not point forecasting.",
    )

    ax.set_ylim(0, max(40, float(data["bsti_0_100"].max()) * 1.15))
    ax.set_ylabel("BSTI score, 0 to 100")
    ax.legend(frameon=False, loc="best")

    _add_source_note(
        fig,
        "Source: BRAVO Lab BSTI. Inputs include local Brazil risk, FX/VIX pressure, global risk, and external Brazil channels.",
    )

    return _save(fig, figures_dir / "03_bsti_signal.png")


def build_policy_selection_figure(processed_dir: Path, figures_dir: Path) -> Path | None:
    data = _read_csv(
        processed_dir / "bsti_policy_selection_summary.csv",
        index_col=None,
    )

    if data.empty or not {"selected_strategy", "share"}.issubset(data.columns):
        return None

    data = data.sort_values("share", ascending=True)

    fig, ax = plt.subplots(figsize=(10.8, 5.8))

    labels = data["selected_strategy"].str.replace("_", " ", regex=False).str.title()
    colors = [
        STRATEGY_COLORS.get(strategy, PALETTE["gray"])
        for strategy in data["selected_strategy"]
    ]

    ax.barh(labels, data["share"], color=colors)

    for i, value in enumerate(data["share"]):
        ax.text(
            value + 0.01,
            i,
            f"{value:.1%}",
            va="center",
            fontsize=8.5,
            color=PALETTE["navy"],
            fontweight="bold",
        )

    _style_axes(
        ax,
        "BSTI policy-selection mix",
        "How often the stress index chooses passive exposure, covered calls, or collars.",
    )

    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xlabel("Share of policy observations")
    ax.set_xlim(0, min(1.0, max(0.15, float(data["share"].max()) + 0.15)))

    _add_source_note(
        fig,
        "Source: BRAVO Lab BSTI policy decision table.",
    )

    return _save(fig, figures_dir / "04_bsti_policy_selection_mix.png")


def build_risk_return_map(processed_dir: Path, figures_dir: Path) -> Path | None:
    data = _read_csv(
        processed_dir / "bsti_policy_comparison_summary.csv",
    )

    if data.empty:
        data = _read_csv(processed_dir / "baseline_performance_summary.csv")

    required = {"annualized_return", "annualized_volatility"}

    if data.empty or not required.issubset(data.columns):
        return None

    data = _clean_numeric(data).dropna(subset=["annualized_return", "annualized_volatility"])

    if data.empty:
        return None

    fig, ax = plt.subplots(figsize=(10.8, 6.4))

    for strategy, row in data.iterrows():
        color = STRATEGY_COLORS.get(str(strategy), PALETTE["gray"])

        ax.scatter(
            row["annualized_volatility"],
            row["annualized_return"],
            s=95,
            color=color,
            edgecolor="white",
            linewidth=1.2,
            zorder=3,
        )

        ax.text(
            row["annualized_volatility"],
            row["annualized_return"],
            "  " + STRATEGY_LABELS.get(str(strategy), str(strategy).replace("_", " ").title()),
            fontsize=8.3,
            color=PALETTE["navy"],
            va="center",
        )

    _style_axes(
        ax,
        "Risk-return positioning map",
        "Annualized return versus annualized volatility. The better quadrant is higher return with lower volatility.",
    )

    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xlabel("Annualized volatility")
    ax.set_ylabel("Annualized return")

    _add_source_note(
        fig,
        "Source: BRAVO Lab policy comparison summary. This chart is descriptive, not a forecast.",
    )

    return _save(fig, figures_dir / "05_risk_return_map.png")


def build_transition_matrix_figure(processed_dir: Path, figures_dir: Path) -> Path | None:
    data = _read_csv(
        processed_dir / "bsti_transition_matrix.csv",
        index_col=None,
    )

    if data.empty or not {"from_state", "to_state", "probability"}.issubset(data.columns):
        return None

    pivot = data.pivot_table(
        index="from_state",
        columns="to_state",
        values="probability",
        fill_value=0.0,
    )

    order = [state for state in ["normal", "warning", "stress"] if state in pivot.index or state in pivot.columns]
    pivot = pivot.reindex(index=order, columns=order, fill_value=0.0)

    fig, ax = plt.subplots(figsize=(8.2, 6.5))

    image = ax.imshow(pivot.values, aspect="auto", vmin=0.0, vmax=1.0, cmap="Blues")

    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_xticklabels([str(x).title() for x in pivot.columns])
    ax.set_yticklabels([str(x).title() for x in pivot.index])

    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(
                j,
                i,
                f"{pivot.values[i, j]:.0%}",
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
                color=PALETTE["navy"],
            )

    _style_axes(
        ax,
        "BSTI state-transition matrix",
        "Probability of moving from one governance state to another in the next observation.",
    )

    ax.set_xlabel("To state")
    ax.set_ylabel("From state")

    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    colorbar.ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    colorbar.ax.tick_params(labelsize=8)

    _add_source_note(
        fig,
        "Source: BRAVO Lab BSTI transition diagnostics.",
    )

    return _save(fig, figures_dir / "06_bsti_transition_matrix.png")


def build_calibration_scores_figure(processed_dir: Path, figures_dir: Path) -> Path | None:
    data = _read_csv(
        processed_dir / "bsti_best_calibration_by_horizon.csv",
        index_col=None,
    )

    if data.empty:
        data = _read_csv(
            processed_dir / "bsti_calibration_grid.csv",
            index_col=None,
        )

    if data.empty or not {"horizon_days", "weight_scheme", "governance_score"}.issubset(data.columns):
        return None

    data = _clean_numeric(data)
    data = data.sort_values("governance_score", ascending=True).tail(10).copy()

    data["label"] = (
        data["weight_scheme"].astype(str).str.replace("_", " ", regex=False).str.title()
        + " | "
        + data["horizon_days"].astype(str)
        + "d"
    )

    fig, ax = plt.subplots(figsize=(11.5, 6.4))

    ax.barh(data["label"], data["governance_score"], color=PALETTE["blue"])

    for i, value in enumerate(data["governance_score"]):
        ax.text(
            value + 0.02,
            i,
            f"{value:.2f}",
            va="center",
            fontsize=8.5,
            color=PALETTE["navy"],
            fontweight="bold",
        )

    _style_axes(
        ax,
        "BSTI calibration scorecard",
        "Top calibration candidates by governance score across thresholds, channel weights, and forward-risk horizons.",
    )

    ax.set_xlabel("Governance score")

    _add_source_note(
        fig,
        "Source: BRAVO Lab BSTI calibration grid and best-by-horizon calibration summary.",
    )

    return _save(fig, figures_dir / "07_bsti_calibration_scores.png")


def build_report_figure_set(
    processed_dir: Path | str = DEFAULT_PROCESSED_DIR,
    figures_dir: Path | str = DEFAULT_FIGURES_DIR,
) -> OrderedDict[str, Path]:
    _set_premium_theme()

    processed_dir = Path(processed_dir)
    figures_dir = Path(figures_dir)

    builders = OrderedDict(
        [
            ("executive_dashboard", build_executive_dashboard),
            ("cumulative_performance", build_cumulative_performance_figure),
            ("drawdown_profile", build_drawdown_figure),
            ("bsti_signal", build_bsti_signal_figure),
            ("policy_selection", build_policy_selection_figure),
            ("risk_return_map", build_risk_return_map),
            ("transition_matrix", build_transition_matrix_figure),
            ("calibration_scores", build_calibration_scores_figure),
        ]
    )

    outputs: OrderedDict[str, Path] = OrderedDict()

    for name, builder in builders.items():
        path = builder(processed_dir, figures_dir)

        if path is not None:
            outputs[name] = path

    return outputs


def figure_markdown_gallery(figure_paths: dict[str, Path]) -> str:
    if not figure_paths:
        return "No premium figure files were generated for this report run."

    captions = OrderedDict(
        [
            (
                "executive_dashboard",
                (
                    "Executive risk dashboard",
                    "One-page visual summary of the current stress state, dominant channel, policy action, and active-risk leaders.",
                ),
            ),
            (
                "cumulative_performance",
                (
                    "Cumulative performance path",
                    "Shows whether the overlay logic improves the investment path through time, not only the final number.",
                ),
            ),
            (
                "drawdown_profile",
                (
                    "Drawdown control map",
                    "Tests whether the strategy actually reduces the left-tail pain investors care about.",
                ),
            ),
            (
                "bsti_signal",
                (
                    "Brazil Stress Transmission Index",
                    "Displays warning and stress zones so the stress signal becomes interpretable as a governance state.",
                ),
            ),
            (
                "policy_selection",
                (
                    "BSTI policy-selection mix",
                    "Shows how the model distributes portfolio actions across passive exposure, covered calls, and collars.",
                ),
            ),
            (
                "risk_return_map",
                (
                    "Risk-return positioning map",
                    "Places each strategy in annualized return versus annualized volatility space.",
                ),
            ),
            (
                "transition_matrix",
                (
                    "BSTI state-transition matrix",
                    "Shows whether the stress signal behaves like a persistent warning process or a random flash.",
                ),
            ),
            (
                "calibration_scores",
                (
                    "BSTI calibration scorecard",
                    "Ranks calibration candidates across thresholds, channel weights, and forward-risk horizons.",
                ),
            ),
        ]
    )

    lines = []

    for name, path in figure_paths.items():
        title, explanation = captions.get(
            name,
            (name.replace("_", " ").title(), "Generated visual evidence from BRAVO Lab processed outputs."),
        )

        relative_path = Path("figures") / path.name

        lines.append(f"### {title}")
        lines.append("")
        lines.append(f"![{title}]({relative_path.as_posix()})")
        lines.append("")
        lines.append(f"**Interpretation:** {explanation}")
        lines.append("")

    return "\n".join(lines).strip()
