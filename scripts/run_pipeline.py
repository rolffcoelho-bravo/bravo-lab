from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

CANONICAL_REPORT = ROOT / "reports" / "BRAVO_Lab_Executive_Report_v0.1.2.pdf"

GENERATED_PATHS_TO_RESTORE = [
    "data/processed",
    "reports/baseline_report.md",
    "reports/front_office_memo.md",
    "reports/figures",
]


def run_command(args: list[str], step_name: str) -> None:
    print()
    print("=" * 72)
    print(f"BRAVO PIPELINE STEP: {step_name}")
    print("=" * 72)
    print(" ".join(args))

    result = subprocess.run(args, cwd=ROOT)

    if result.returncode != 0:
        raise SystemExit(f"\nFAILED: {step_name}")


def check_output(path: Path, label: str, min_size: int = 1) -> None:
    if not path.exists():
        raise SystemExit(f"\nFAILED: expected {label} was not created: {path}")

    size = path.stat().st_size

    if size < min_size:
        raise SystemExit(f"\nFAILED: expected {label} is too small: {path}")

    print(f"OK: {label} -> {path.relative_to(ROOT)} ({size / 1_000_000:.2f} MB)")


def git_porcelain() -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def restore_generated_outputs() -> None:
    subprocess.run(
        ["git", "restore", *GENERATED_PATHS_TO_RESTORE],
        cwd=ROOT,
        check=False,
    )


def open_final_pdf() -> None:
    """Open the final PDF report at the end of a successful local pipeline run."""
    if sys.platform.startswith("win"):
        import os
        os.startfile(CANONICAL_REPORT)
    elif sys.platform == "darwin":
        subprocess.run(["open", str(CANONICAL_REPORT)], check=False)
    else:
        subprocess.run(["xdg-open", str(CANONICAL_REPORT)], check=False)

def main() -> int:
    print("BRAVO Lab full pipeline")
    print(f"Project root: {ROOT}")

    if git_porcelain():
        print()
        print("FAILED: working tree is not clean before running the pipeline.")
        print("Run git status, commit or restore changes, then run the pipeline again.")
        return 1

    run_command(
        [PYTHON, "scripts/generate_report.py"],
        "Generate processed evidence, figures, and markdown reports",
    )

    check_output(ROOT / "reports" / "baseline_report.md", "baseline report", min_size=5_000)
    check_output(ROOT / "reports" / "front_office_memo.md", "front-office memo", min_size=500)
    check_output(ROOT / "reports" / "figures" / "00_executive_risk_dashboard.png", "executive dashboard figure", min_size=50_000)
    check_output(ROOT / "data" / "processed" / "bsti_policy_comparison_summary.csv", "BSTI policy comparison CSV", min_size=100)

    run_command(
        [PYTHON, "scripts/generate_institutional_pdf.py"],
        "Generate final canonical executive PDF",
    )

    check_output(CANONICAL_REPORT, "final canonical report", min_size=100_000)

    run_command(
        [PYTHON, "-m", "pytest", "-q"],
        "Run tests",
    )

    restore_generated_outputs()

    remaining_changes = git_porcelain()

    print()
    print("=" * 72)
    print("BRAVO PIPELINE FINISHED SUCCESSFULLY")
    print("=" * 72)
    print("Main report:")
    print("reports/BRAVO_Lab_Executive_Report_v0.1.2.pdf")

    if remaining_changes:
        print()
        print("WARNING: pipeline passed, but non-generated files changed:")
        print(remaining_changes)
        return 1

    print()
    print("Git working tree remains clean after full pipeline run.")
    print("\nOpening final PDF report...")
    open_final_pdf()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

