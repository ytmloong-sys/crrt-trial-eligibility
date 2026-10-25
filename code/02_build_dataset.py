import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crrt_liberation.config import load_config
from crrt_liberation.cohort import build_dataset, export_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "config.yaml")
    if not args.export_only:
        build_dataset(cfg)
    out = export_dataset(cfg)
    print(f"Exported: {out}")


if __name__ == "__main__":
    main()
