from pathlib import Path


def test_report_artifacts_exist():
    required_files = [
        Path("reports/front_office_memo.md"),
        Path("reports/baseline_report.md"),
        Path("reports/README.md"),
        Path("reports/figures/00_executive_risk_dashboard.png"),
        Path("reports/figures/01_cumulative_performance.png"),
        Path("reports/figures/02_drawdown_profile.png"),
        Path("reports/figures/03_bsti_signal.png"),
        Path("reports/figures/04_bsti_policy_selection_mix.png"),
        Path("reports/figures/05_risk_return_map.png"),
        Path("reports/figures/06_bsti_transition_matrix.png"),
        Path("reports/figures/07_bsti_calibration_scores.png"),
    ]

    missing = [str(path) for path in required_files if not path.exists()]

    assert not missing, f"Missing report artifacts: {missing}"


def test_processed_evidence_files_exist():
    required_files = [
        Path("data/processed/brazil_stress_transmission_index.csv"),
        Path("data/processed/bsti_policy_comparison_summary.csv"),
        Path("data/processed/bsti_policy_decisions.csv"),
        Path("data/processed/bsti_state_table.csv"),
        Path("data/processed/bsti_transition_matrix.csv"),
        Path("data/processed/overlay_return_table.csv"),
    ]

    missing = [str(path) for path in required_files if not path.exists()]

    assert not missing, f"Missing processed evidence files: {missing}"


def test_front_office_memo_is_visible():
    text = Path("reports/front_office_memo.md").read_text(encoding="utf-8")

    assert "BRAVO Lab Front-Office Executive Memo" in text
    assert "Decision read" in text
    assert "Evidence stack" in text
    assert "Risk committee agenda" in text
