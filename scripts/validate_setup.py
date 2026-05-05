"""Validate ANDES installation and test case availability."""

import sys


def main():
    print("=" * 60)
    print("BO-WCS Environment Validation")
    print("=" * 60)

    errors = []

    # Check Python version
    print(f"\nPython: {sys.version}")

    # Check core dependencies
    deps = {
        "numpy": "numpy",
        "pandas": "pandas",
        "scipy": "scipy",
        "matplotlib": "matplotlib",
        "torch": "torch",
        "botorch": "botorch",
        "gpytorch": "gpytorch",
        "pymoo": "pymoo",
        "omegaconf": "omegaconf",
        "andes": "andes",
    }

    print("\n--- Dependencies ---")
    for name, import_name in deps.items():
        try:
            mod = __import__(import_name)
            version = getattr(mod, "__version__", "unknown")
            print(f"  [OK] {name}: {version}")
        except ImportError:
            print(f"  [MISSING] {name}")
            errors.append(name)

    # Check ANDES cases
    print("\n--- ANDES Test Cases ---")
    try:
        import andes
        cases = [
            ("Kundur 2-area", "kundur/kundur_full.xlsx"),
        ]
        for name, path in cases:
            try:
                full_path = andes.get_case(path)
                print(f"  [OK] {name}: {full_path}")
            except Exception as e:
                print(f"  [FAIL] {name}: {e}")
                errors.append(f"ANDES case: {name}")
    except ImportError:
        pass

    # Test ANDES simulation
    print("\n--- ANDES Quick Test ---")
    try:
        import andes
        import numpy as np

        ss = andes.load(andes.get_case("kundur/kundur_full.xlsx"))
        ss.setup()
        ss.PFlow.run()
        if ss.PFlow.converged:
            print("  [OK] Power flow converged")
        else:
            print("  [FAIL] Power flow did not converge")
            errors.append("ANDES power flow")

        # Quick TDS test
        ss.add("Fault", {"bus": 7, "tf": 1.0, "tc": 1.08})
        ss.TDS.config.tf = 5.0
        ss.TDS.run()

        t = ss.dae.ts.t
        if t is not None and len(t) > 0:
            print(f"  [OK] TDS completed ({len(t)} timesteps)")
            # Check rotor angles
            delta_idx = ss.GENROU.delta.a
            angles = ss.dae.ts.x[:, delta_idx]
            max_sep = np.rad2deg(np.max(angles) - np.min(angles, axis=1, keepdims=True).max())
            print(f"  [OK] Max rotor angle separation: {max_sep:.1f} deg")
        else:
            print("  [FAIL] No TDS output")
            errors.append("ANDES TDS")
    except Exception as e:
        print(f"  [FAIL] ANDES simulation error: {e}")
        errors.append("ANDES simulation")

    # Summary
    print("\n" + "=" * 60)
    if errors:
        print(f"FAILED: {len(errors)} issue(s) found:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED. Environment ready for experiments.")
        print("=" * 60)


if __name__ == "__main__":
    main()
