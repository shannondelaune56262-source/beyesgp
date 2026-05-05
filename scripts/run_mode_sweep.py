"""Generate 1000 operating modes and save to CSV."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.scenario.mode_generator import ModeGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    n_modes = 1000
    output_dir = Path("data/processed/mode_sweep")
    output_dir.mkdir(parents=True, exist_ok=True)

    gen = ModeGenerator(n_modes=n_modes, seed=42, method="lhs")
    df = gen.generate()

    csv_path = output_dir / "mode_definitions.csv"
    df.to_csv(csv_path)
    logger.info(f"Saved {len(df)} modes to {csv_path}")

    # Summary stats
    print("\n=== Mode Parameter Statistics ===")
    print(df.describe().round(4).to_string())
    print(f"\nDerived features:")
    for col in ["total_re_pct", "net_flow_proxy", "inertia_proxy", "stress_index"]:
        print(f"  {col}: mean={df[col].mean():.3f}, std={df[col].std():.3f}")

    # Parameter bounds check
    bounds = gen.get_param_bounds()
    for name, (lo, hi) in bounds.items():
        assert df[name].between(lo, hi).all(), f"{name} out of bounds!"
    print("\nAll parameters within bounds: OK")


if __name__ == "__main__":
    main()
