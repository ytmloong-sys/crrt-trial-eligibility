import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crrt_liberation.analysis import run_analysis
from crrt_liberation.config import load_config


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "config.yaml")

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(Path(cfg["paths"]["data_dir"]) / "analysis_dataset.parquet"))
    parser.add_argument("--output", default=str(cfg["paths"]["output_dir"]))
    args = parser.parse_args()

    result = run_analysis(args.input, args.output, seed=cfg.get("seed", 20261019))
    print(result["primary"])


if __name__ == "__main__":
    main()
