from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

CANONICAL = REPORTS / "BRAVO_Lab_Executive_Report_v0.1.2.pdf"

LEGACY_SOURCES = [
    REPORTS / "BRAVO_Lab_Executive_Report_v0.1.2_FINAL_LOCKED.pdf",
    REPORTS / "BRAVO_Lab_Executive_Report_v0.1.2_styled.pdf",
    REPORTS / "BRAVO_Lab_Executive_Report_v0.1.2_styled16.pdf",
    REPORTS / "BRAVO_Lab_Executive_Report_v0.1.2_styled15.pdf",
    REPORTS / "BRAVO_Lab_Executive_Report_v0.1.2_styled10.pdf",
]

def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)

    if CANONICAL.exists() and CANONICAL.stat().st_size > 100_000:
        print(f"Canonical PDF already exists: {CANONICAL}")
        return 0

    for source in LEGACY_SOURCES:
        if source.exists() and source.stat().st_size > 100_000:
            shutil.copy2(source, CANONICAL)
            print(f"Canonical PDF created: {CANONICAL}")
            print(f"Source PDF: {source.name}")
            return 0

    print("ERROR: No valid source PDF found to create canonical BRAVO report.", file=sys.stderr)
    print(f"Expected canonical: {CANONICAL}", file=sys.stderr)
    print("Checked sources:", file=sys.stderr)
    for source in LEGACY_SOURCES:
        print(f" - {source}", file=sys.stderr)
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
