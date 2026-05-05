"""CLI entry point for running a single experiment."""

import os
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"
os.environ["OPENBLAS_NUM_THREADS"] = "4"

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.experiment.benchmark import Benchmark


def main():
    parser = argparse.ArgumentParser(
        description="Run a BO-WCS experiment"
    )
    parser.add_argument(
        "experiment",
        choices=["exp1_kundur_2d", "exp2_kundur_4d", "exp3_kundur_6d", "exp4_ablation"],
        help="Experiment to run",
    )
    parser.add_argument(
        "--system", default="kundur", help="Test system (default: kundur)"
    )
    parser.add_argument(
        "--workers", type=int, default=2, help="Number of parallel workers (default: 2)"
    )
    parser.add_argument(
        "--output", default=None, help="Output directory"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable debug logging"
    )

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    log_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=level,
        format=log_fmt,
        datefmt="%H:%M:%S",
    )

    file_handler = logging.FileHandler("experiment.log", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(log_fmt, datefmt="%H:%M:%S"))
    logging.getLogger().addHandler(file_handler)

    benchmark = Benchmark(
        experiment_name=args.experiment,
        test_system=args.system,
        n_workers=args.workers,
    )

    results = benchmark.run(output_dir=args.output)
    print(f"\nResults saved to: data/processed/{args.experiment}/")


if __name__ == "__main__":
    main()
