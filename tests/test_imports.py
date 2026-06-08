def test_core_modules_import():
    import bravo.config
    import bravo.report
    import bravo.front_office_memo
    import bravo.premium_figures
    import bravo.bsti_calibration
    import bravo.bsti_policy
    import bravo.bsti_transitions
    import bravo.bsti_validation
    import bravo.stress_index
    import bravo.stress_signals


def test_front_office_memo_builds_from_processed_outputs():
    from bravo.front_office_memo import build_front_office_memo

    memo = build_front_office_memo()

    assert "Decision read" in memo
    assert "Portfolio action snapshot" in memo
    assert "Risk committee agenda" in memo
    assert "Implementation warning" in memo
