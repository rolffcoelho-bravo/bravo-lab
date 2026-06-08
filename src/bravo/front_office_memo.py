"""
Front-office executive memo layer for BRAVO Lab.

This module turns the quantitative outputs into a concise portfolio-governance
memo.

The memo is designed for a portfolio manager, risk committee, allocator, or
front-office reviewer who needs to know:

- current risk state
- implied portfolio action
- whether the overlay helped
- what evidence supports the view
- what can break the conclusion
- what must be discussed before implementation
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_PROCESSED_DIR = Path("data/processed")


def _read_csv(path: Path, index_col: int | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path, index_col=index_col)
    except Exception:
        return pd.DataFrame()


def _read_indexed_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path, index_col=0)
    except Exception:
        return pd.DataFrame()


def _to_numeric(value) -> float:
    try:
        return float(value)
    except Exception:
        return np.nan


def _fmt_num(value) -> str:
    value = _to_numeric(value)

    if pd.isna(value):
        return "NA"

    return f"{value:.2f}"


def _fmt_pct(value) -> str:
    value = _to_numeric(value)

    if pd.isna(value):
        return "NA"

    return f"{value:.2%}"


def _clean_label(value: str) -> str:
    if value is None:
        return "NA"

    return str(value).replace("_", " ").title()


def _last_value(data: pd.DataFrame, column: str, fallback: str = "NA") -> str:
    if data.empty or column not in data.columns:
        return fallback

    values = data[column].dropna()

    if values.empty:
        return fallback

    return str(values.iloc[-1])


def _best_index(data: pd.DataFrame, column: str) -> str:
    if data.empty or column not in data.columns:
        return "NA"

    values = pd.to_numeric(data[column], errors="coerce").dropna()

    if values.empty:
        return "NA"

    return str(values.idxmax())


def _least_negative_index(data: pd.DataFrame, column: str) -> str:
    if data.empty or column not in data.columns:
        return "NA"

    values = pd.to_numeric(data[column], errors="coerce").dropna()

    if values.empty:
        return "NA"

    return str(values.idxmax())


def _row_for_strategy(data: pd.DataFrame, strategy: str) -> pd.Series:
    if data.empty:
        return pd.Series(dtype="object")

    if strategy in data.index:
        return data.loc[strategy]

    if "strategy" in data.columns:
        rows = data.loc[data["strategy"] == strategy]

        if not rows.empty:
            return rows.iloc[0]

    return pd.Series(dtype="object")


def _policy_action_read(policy_action: str) -> str:
    action = str(policy_action)

    if action == "collar":
        return (
            "The model is prioritizing downside definition. The committee should "
            "focus on protection cost, participation cap, and stress persistence."
        )

    if action == "covered_call":
        return (
            "The model is prioritizing income capture. The committee should check "
            "whether the upside sold is acceptable under the current stress state."
        )

    if action == "passive_brazil_equity":
        return (
            "The model is not demanding an option overlay. The committee should "
            "still monitor whether stress is beginning to migrate into warning state."
        )

    return (
        "The model does not produce a clean policy action. The committee should "
        "treat this as a data-quality or signal-governance issue."
    )


def build_front_office_memo(
    processed_dir: Path | str = DEFAULT_PROCESSED_DIR,
) -> str:
    """
    Build a front-office executive memo from processed BRAVO Lab outputs.
    """
    processed_dir = Path(processed_dir)

    latest_bsti = _read_csv(
        processed_dir / "brazil_stress_transmission_index_latest.csv",
        index_col=None,
    )

    policy_decisions = _read_indexed_csv(
        processed_dir / "bsti_policy_decisions.csv"
    )

    policy_comparison = _read_indexed_csv(
        processed_dir / "bsti_policy_comparison_summary.csv"
    )

    policy_selection = _read_csv(
        processed_dir / "bsti_policy_selection_summary.csv",
        index_col=None,
    )

    state_duration = _read_csv(
        processed_dir / "bsti_state_duration_summary.csv",
        index_col=None,
    )

    escalation = _read_csv(
        processed_dir / "bsti_escalation_summary.csv",
        index_col=None,
    )

    calibration = _read_csv(
        processed_dir / "bsti_best_calibration_by_horizon.csv",
        index_col=None,
    )

    bsti_score = _last_value(latest_bsti, "bsti_0_100")
    bsti_regime = _last_value(latest_bsti, "bsti_regime")
    dominant_channel = _last_value(latest_bsti, "dominant_pressure_channel")

    latest_policy_action = "NA"

    if not policy_decisions.empty and "selected_strategy" in policy_decisions.columns:
        latest_policy_action = str(policy_decisions["selected_strategy"].dropna().iloc[-1])

    policy_row = _row_for_strategy(policy_comparison, "bsti_policy_overlay")

    policy_active_return = policy_row.get("annualized_active_return", np.nan)
    policy_tracking_error = policy_row.get("tracking_error", np.nan)
    policy_information_ratio = policy_row.get("information_ratio", np.nan)
    policy_max_drawdown = policy_row.get("max_drawdown", np.nan)

    best_ir = _best_index(policy_comparison, "information_ratio")
    best_drawdown = _least_negative_index(policy_comparison, "max_drawdown")
    best_return = _best_index(policy_comparison, "annualized_return")

    dominant_policy_share = "NA"
    dominant_policy_name = "NA"

    if not policy_selection.empty and {"selected_strategy", "share"}.issubset(policy_selection.columns):
        clean_selection = policy_selection.copy()
        clean_selection["share"] = pd.to_numeric(clean_selection["share"], errors="coerce")
        clean_selection = clean_selection.dropna(subset=["share"])

        if not clean_selection.empty:
            dominant_row = clean_selection.sort_values("share", ascending=False).iloc[0]
            dominant_policy_name = str(dominant_row["selected_strategy"])
            dominant_policy_share = _fmt_pct(dominant_row["share"])

    warning_duration = "NA"
    stress_duration = "NA"

    if not state_duration.empty and {"state", "avg_duration_observations"}.issubset(state_duration.columns):
        warning_rows = state_duration.loc[state_duration["state"] == "warning"]
        stress_rows = state_duration.loc[state_duration["state"] == "stress"]

        if not warning_rows.empty:
            warning_duration = _fmt_num(warning_rows["avg_duration_observations"].iloc[0])

        if not stress_rows.empty:
            stress_duration = _fmt_num(stress_rows["avg_duration_observations"].iloc[0])

    escalation_rate = "NA"

    if not escalation.empty and "escalation_rate" in escalation.columns:
        escalation_rate = _fmt_pct(escalation["escalation_rate"].iloc[0])

    calibration_read = "NA"

    if not calibration.empty and {"horizon_days", "weight_scheme", "bsti_threshold", "governance_score"}.issubset(calibration.columns):
        clean_calibration = calibration.copy()
        clean_calibration["governance_score"] = pd.to_numeric(
            clean_calibration["governance_score"],
            errors="coerce",
        )
        clean_calibration = clean_calibration.dropna(subset=["governance_score"])

        if not clean_calibration.empty:
            top = clean_calibration.sort_values("governance_score", ascending=False).iloc[0]
            calibration_read = (
                f"{_clean_label(top['weight_scheme'])}, "
                f"{int(top['horizon_days'])}d horizon, "
                f"threshold {_fmt_num(top['bsti_threshold'])}, "
                f"governance score {_fmt_num(top['governance_score'])}"
            )

    action_read = _policy_action_read(latest_policy_action)

    lines = [
        "### Decision read",
        "",
        (
            f"BRAVO Lab currently reads Brazilian risk through a BSTI score of "
            f"**{_fmt_num(bsti_score)}**, classified as **{_clean_label(bsti_regime)}**, "
            f"with **{_clean_label(dominant_channel)}** as the dominant pressure channel. "
            f"The current BSTI policy action is **{_clean_label(latest_policy_action)}**."
        ),
        "",
        action_read,
        "",
        "### Portfolio action snapshot",
        "",
        "| Item | Current read |",
        "| --- | --- |",
        f"| Current BSTI score | {_fmt_num(bsti_score)} |",
        f"| Current BSTI regime | {_clean_label(bsti_regime)} |",
        f"| Dominant pressure channel | {_clean_label(dominant_channel)} |",
        f"| Current policy action | {_clean_label(latest_policy_action)} |",
        f"| Dominant historical policy choice | {_clean_label(dominant_policy_name)} ({dominant_policy_share}) |",
        f"| BSTI policy annualized active return | {_fmt_pct(policy_active_return)} |",
        f"| BSTI policy tracking error | {_fmt_pct(policy_tracking_error)} |",
        f"| BSTI policy information ratio | {_fmt_num(policy_information_ratio)} |",
        f"| BSTI policy max drawdown | {_fmt_pct(policy_max_drawdown)} |",
        "",
        "### Evidence stack",
        "",
        "| Question | Evidence read |",
        "| --- | --- |",
        f"| Which strategy had the best information ratio? | {_clean_label(best_ir)} |",
        f"| Which strategy had the best drawdown profile? | {_clean_label(best_drawdown)} |",
        f"| Which strategy had the highest annualized return? | {_clean_label(best_return)} |",
        f"| How persistent are warning states? | Average warning duration: {warning_duration} observations |",
        f"| How persistent are stress states? | Average stress duration: {stress_duration} observations |",
        f"| How often do warnings escalate? | Warning-to-stress escalation rate: {escalation_rate} |",
        f"| Which BSTI calibration is strongest? | {calibration_read} |",
        "",
        "### Risk committee agenda",
        "",
        "1. Confirm whether the current BSTI state is persistent or only a temporary pressure print.",
        "2. Check whether the implied policy action matches the committee's drawdown tolerance.",
        "3. Compare the BSTI policy overlay against passive equity, covered calls, collars, and the local stress-aware overlay.",
        "4. Review whether the selected action is justified after transaction costs, liquidity, taxes, and implementation constraints.",
        "5. Decide whether the stress state requires monitoring, hedge discussion, or actual overlay activation.",
        "",
        "### Implementation warning",
        "",
        (
            "This memo is a decision-support layer, not an investment recommendation. "
            "The evidence is generated from public market data, synthetic option-premium logic, "
            "transparent stress classification, and reproducible CSV outputs. Real B3 option-chain "
            "data, liquidity filters, tax effects, and portfolio mandate constraints must be added "
            "before production use."
        ),
    ]

    return "\n".join(lines)
