"""Run the full experimental suite."""

import os
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"
os.environ["OPENBLAS_NUM_THREADS"] = "4"

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.experiment.benchmark import Benchmark

log_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_fmt,
    datefmt="%H:%M:%S",
)

file_handler = logging.FileHandler("experiment.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(log_fmt, datefmt="%H:%M:%S"))
logging.getLogger().addHandler(file_handler)
logger = logging.getLogger(__name__)

EXPERIMENTS = [
    ("exp1_kundur_2d", "kundur"),
    ("exp2_kundur_4d", "kundur"),
    ("exp3_kundur_6d", "kundur"),
    ("exp4_ablation", "kundur"),
]


def main():
    n_workers = int(input("Number of parallel workers [2]: ") or "2")
    total_start = time.time()

    for exp_name, system in EXPERIMENTS:
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting experiment: {exp_name}")
        logger.info(f"{'='*60}")

        try:
            benchmark = Benchmark(
                experiment_name=exp_name,
                test_system=system,
                n_workers=n_workers,
            )
            benchmark.run()
            logger.info(f"Completed: {exp_name}")
        except Exception as e:
            logger.error(f"Failed: {exp_name}: {e}")
            continue

    total_time = time.time() - total_start
    logger.info(f"\nAll experiments completed in {total_time/3600:.1f} hours")


if __name__ == "__main__":
    main()
