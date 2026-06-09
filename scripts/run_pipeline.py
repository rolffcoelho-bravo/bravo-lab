from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_step(label: str, command: list[str]) -> None:
    print("\n" + "=" * 72)
    print(f"BRAVO PIPELINE STEP: {label}")
    print("=" * 72)
    print(" ".join(command))

    result = subprocess.run(command, cwd=ROOT)

    if result.returncode != 0:
        raise SystemExit(f"\nFAILED: {label} exited with code {result.returncode}")


def check_output(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"\nFAILED: expected {label} was not created: {path}")

    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"OK: {label} -> {path.relative_to(ROOT)} ({size_mb:.2f} MB)")


def main() -> None:
    print("\nBRAVO Lab full pipeline")
    print("Project root:", ROOT)

    run_step("Generate processed evidence, figures, and markdown reports", [
        sys.executable,
        "scripts/generate_report.py",
    ])

    check_output(ROOT / "reports" / "baseline_report.md", "baseline report")
    check_output(ROOT / "reports" / "front_office_memo.md", "front-office memo")
    check_output(ROOT / "reports" / "figures" / "00_executive_risk_dashboard.png", "executive dashboard figure")
    check_output(ROOT / "data" / "processed" / "bsti_policy_comparison_summary.csv", "BSTI policy comparison CSV")

    run_step("Generate final styled executive PDF", [
        sys.executable,
        "scripts/generate_institutional_pdf.py",
    ])

    check_output(ROOT / "reports" / "BRAVO_Lab_Executive_Report_v0.1.2.pdf", "final styled report")

    run_step("Run tests", [
        sys.executable,
        "-m",
        "pytest",
        "-q",
    ])

    print("\n" + "=" * 72)
    print("BRAVO PIPELINE FINISHED SUCCESSFULLY")
    print("=" * 72)
    print("Main report:")
    print("reports/BRAVO_Lab_Executive_Report_v0.1.2.pdf")


if __name__ == "__main__":
    main()

