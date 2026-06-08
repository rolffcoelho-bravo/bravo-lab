from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bravo.report import generate_baseline_report


if __name__ == "__main__":
    output = generate_baseline_report()
    print(f"BRAVO Lab report generated: {output}")
