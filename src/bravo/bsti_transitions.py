"""
BSTI persistence and transition diagnostics for BRAVO Lab.

This module tests whether the Brazil Stress Transmission Index behaves like a
governance signal rather than a random dashboard number.

It measures:

- state classification: normal, warning, stress
- state transition probabilities
- persistence of each warning state
- escalation from warning to stress
- dominant pressure-channel transitions

The objective is not prediction. The objective is portfolio governance:
understanding whether stress signals persist long enough to justify discussion,
review, or overlay action.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


STATE_ORDER = ["normal", "warning", "stress"]


def classify_bsti_state(
    bsti_score: float,
    warning_threshold: float = 15.0,
    stress_threshold: float = 33.0,
) -> str:
    """
    Classify a BSTI score into a governance state.
    """
    if pd.isna(bsti_score):
        return "missing"

    if bsti_score >= stress_threshold:
        return "stress"

    if bsti_score >= warning_threshold:
        return "warning"

    return "normal"


def prepare_bsti_state_table(
    bsti_table: pd.DataFrame,
    warning_threshold: float = 15.0,
    stress_threshold: float = 33.0,
) -> pd.DataFrame:
    """
    Add governance-state labels to a BSTI table.
    """
    if bsti_table.empty:
        return pd.DataFrame()

    if "bsti_0_100" not in bsti_table.columns:
        raise KeyError("BSTI table must contain a 'bsti_0_100' column.")

    output = bsti_table.copy()
    output = output.sort_index()

    output["bsti_state"] = output["bsti_0_100"].apply(
        lambda value: classify_bsti_state(
            value,
            warning_threshold=warning_threshold,
            stress_threshold=stress_threshold,
        )
    )

    output["previous_bsti_state"] = output["bsti_state"].shift(1)
    output["next_bsti_state"] = output["bsti_state"].shift(-1)
    output["state_changed"] = output["bsti_state"] != output["previous_bsti_state"]

    output["warning_threshold"] = warning_threshold
    output["stress_threshold"] = stress_threshold

    return output


def build_bsti_transition_matrix(
    state_table: pd.DataFrame,
    state_column: str = "bsti_state",
) -> pd.DataFrame:
    """
    Build long-form transition probabilities between BSTI states.
    """
    if state_table.empty:
        return pd.DataFrame()

    states = state_table[state_column].dropna()
    transitions = pd.DataFrame(
        {
            "from_state": states.shift(1),
            "to_state": states,
        }
    ).dropna()

    transitions = transitions[
        (transitions["from_state"] != "missing")
        & (transitions["to_state"] != "missing")
    ]

    if transitions.empty:
        return pd.DataFrame()

    counts = (
        transitions.groupby(["from_state", "to_state"])
        .size()
        .rename("transitions")
        .reset_index()
    )

    totals = counts.groupby("from_state")["transitions"].transform("sum")
    counts["probability"] = counts["transitions"] / totals

    counts["transition_label"] = (
        counts["from_state"].astype(str) + " -> " + counts["to_state"].astype(str)
    )

    return counts.sort_values(["from_state", "to_state"]).reset_index(drop=True)


def build_bsti_state_duration_summary(
    state_table: pd.DataFrame,
    state_column: str = "bsti_state",
) -> pd.DataFrame:
    """
    Summarize how long each BSTI state persists before changing.
    """
    if state_table.empty:
        return pd.DataFrame()

    data = state_table.copy()
    data = data[data[state_column] != "missing"].copy()

    if data.empty:
        return pd.DataFrame()

    data["episode_id"] = (data[state_column] != data[state_column].shift(1)).cumsum()

    rows = []

    for _, episode in data.groupby("episode_id"):
        state = episode[state_column].iloc[0]

        rows.append(
            {
                "state": state,
                "start_date": episode.index.min(),
                "end_date": episode.index.max(),
                "duration_observations": len(episode),
                "avg_bsti_0_100": episode["bsti_0_100"].mean(),
                "max_bsti_0_100": episode["bsti_0_100"].max(),
                "min_bsti_0_100": episode["bsti_0_100"].min(),
            }
        )

    episodes = pd.DataFrame(rows)

    summary_rows = []

    for state, group in episodes.groupby("state"):
        summary_rows.append(
            {
                "state": state,
                "episodes": len(group),
                "avg_duration_observations": group["duration_observations"].mean(),
                "median_duration_observations": group["duration_observations"].median(),
                "max_duration_observations": group["duration_observations"].max(),
                "avg_bsti_0_100": group["avg_bsti_0_100"].mean(),
                "max_bsti_0_100": group["max_bsti_0_100"].max(),
            }
        )

    summary = pd.DataFrame(summary_rows)

    if summary.empty:
        return summary

    return summary.sort_values(
        "state",
        key=lambda col: col.map({state: i for i, state in enumerate(STATE_ORDER)}),
    ).reset_index(drop=True)


def build_bsti_escalation_summary(
    state_table: pd.DataFrame,
    lookahead_observations: int = 3,
    state_column: str = "bsti_state",
) -> pd.DataFrame:
    """
    Test whether warning states escalate into stress within a lookahead window.

    The lookahead is measured in table observations, not calendar days, so it works
    for daily, weekly, or monthly BSTI tables.
    """
    if state_table.empty:
        return pd.DataFrame()

    data = state_table.copy()
    states = data[state_column].reset_index(drop=True)

    warning_indices = states[states == "warning"].index

    rows = []

    for idx in warning_indices:
        future = states.iloc[idx + 1 : idx + 1 + lookahead_observations]

        escalates = bool((future == "stress").any())

        rows.append(
            {
                "warning_observation_index": int(idx),
                "lookahead_observations": lookahead_observations,
                "escalates_to_stress": escalates,
                "next_state": states.iloc[idx + 1] if idx + 1 < len(states) else np.nan,
            }
        )

    events = pd.DataFrame(rows)

    if events.empty:
        return pd.DataFrame(
            [
                {
                    "warning_events": 0,
                    "lookahead_observations": lookahead_observations,
                    "escalation_rate": np.nan,
                    "stay_warning_or_stress_rate": np.nan,
                }
            ]
        )

    stay_warning_or_stress = events["next_state"].isin(["warning", "stress"]).mean()

    return pd.DataFrame(
        [
            {
                "warning_events": len(events),
                "lookahead_observations": lookahead_observations,
                "escalation_rate": events["escalates_to_stress"].mean(),
                "stay_warning_or_stress_rate": stay_warning_or_stress,
            }
        ]
    )


def build_bsti_pressure_channel_transition_summary(
    state_table: pd.DataFrame,
    channel_column: str = "dominant_pressure_channel",
) -> pd.DataFrame:
    """
    Summarize transitions between dominant pressure channels.
    """
    if state_table.empty or channel_column not in state_table.columns:
        return pd.DataFrame()

    channels = state_table[channel_column].fillna("unknown").astype(str)

    transitions = pd.DataFrame(
        {
            "from_channel": channels.shift(1),
            "to_channel": channels,
        }
    ).dropna()

    transitions = transitions[
        (transitions["from_channel"] != "unknown")
        & (transitions["to_channel"] != "unknown")
    ]

    if transitions.empty:
        return pd.DataFrame()

    counts = (
        transitions.groupby(["from_channel", "to_channel"])
        .size()
        .rename("transitions")
        .reset_index()
    )

    totals = counts.groupby("from_channel")["transitions"].transform("sum")
    counts["probability"] = counts["transitions"] / totals

    return counts.sort_values(
        ["from_channel", "probability"],
        ascending=[True, False],
    ).reset_index(drop=True)


def bsti_transition_interpretation(
    transition_matrix: pd.DataFrame,
    duration_summary: pd.DataFrame,
    escalation_summary: pd.DataFrame,
) -> str:
    """
    Produce a compact governance interpretation of BSTI persistence.
    """
    if transition_matrix.empty or duration_summary.empty:
        return (
            "BSTI transition diagnostics were not available. The index needs "
            "a valid state table before persistence can be interpreted."
        )

    stress_duration = duration_summary.loc[
        duration_summary["state"] == "stress",
        "avg_duration_observations",
    ]

    warning_duration = duration_summary.loc[
        duration_summary["state"] == "warning",
        "avg_duration_observations",
    ]

    avg_stress_duration = (
        float(stress_duration.iloc[0]) if not stress_duration.empty else np.nan
    )

    avg_warning_duration = (
        float(warning_duration.iloc[0]) if not warning_duration.empty else np.nan
    )

    escalation_rate = np.nan

    if not escalation_summary.empty and "escalation_rate" in escalation_summary.columns:
        escalation_rate = float(escalation_summary["escalation_rate"].iloc[0])

    return (
        f"BSTI transition read: warning episodes persisted for an average of "
        f"`{avg_warning_duration:.2f}` observations, while stress episodes "
        f"persisted for an average of `{avg_stress_duration:.2f}` observations. "
        f"The warning-to-stress escalation rate over the selected lookahead window "
        f"was `{escalation_rate:.2%}`. This helps distinguish a one-period stress "
        "flash from a governable warning state that may justify portfolio review, "
        "hedge discussion, or overlay-policy activation."
    )
