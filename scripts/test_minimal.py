"""Minimal smoke test with detailed logging probes.

Tests the full pipeline step-by-step:
  1. Dependency imports
  2. Config loading
  3. ANDES system load + power flow
  4. Single fault scenario + TDS
  5. Result extraction + severity calculation
  6. Random search (3 evaluations)
  7. BO (2 init + 1 iteration) - most likely to hang

Usage:
  python scripts/test_minimal.py
"""

# ★ 限制线程数必须在所有 import 之前（torch/numpy/scipy 导入时读取这些变量）
import os
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"
os.environ["OPENBLAS_NUM_THREADS"] = "4"

import logging
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Configure logging to both console and file
log_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.DEBUG, format=log_fmt, datefmt="%H:%M:%S")
file_handler = logging.FileHandler("test_minimal.log", encoding="utf-8", mode="w")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(log_fmt, datefmt="%H:%M:%S"))
logging.getLogger().addHandler(file_handler)

logger = logging.getLogger("test_minimal")


_psutil_ok = False

def mem_mb():
    """Current process RSS in MB."""
    if _psutil_ok:
        import psutil
        return psutil.Process().memory_info().rss / 1024 / 1024
    return -1.0


def step(title):
    logger.info("=" * 60)
    logger.info(f"STEP: {title}")
    logger.info(f"Memory: {mem_mb():.0f} MB")
    logger.info("=" * 60)


def main():
    global _psutil_ok
    results = {}

    # ============================================================
    # Step 0: Dependency check
    # ============================================================
    step("0. Dependency imports + memory baseline")
    try:
        import psutil
        _psutil_ok = True
        logger.info(f"psutil OK, baseline RSS = {mem_mb():.0f} MB")
    except ImportError:
        logger.warning("psutil not installed, pip install psutil for memory tracking")

    t0 = time.time()

    try:
        import numpy as np
        logger.info(f"numpy {np.__version__}")
        import pandas as pd
        logger.info(f"pandas {pd.__version__}")
        import torch
        logger.info(f"torch {torch.__version__}")
        import botorch
        logger.info(f"botorch {botorch.__version__}")
        import gpytorch
        logger.info(f"gpytorch {gpytorch.__version__}")
        import andes
        logger.info(f"andes {andes.__version__}")
        import pymoo
        logger.info(f"pymoo {pymoo.__version__}")
    except ImportError as e:
        logger.error(f"Import failed: {e}")
        return
    results["imports_time"] = time.time() - t0
    logger.info(f"Imports done in {results['imports_time']:.1f}s, memory = {mem_mb():.0f} MB")

    # ============================================================
    # Step 1: Config loading
    # ============================================================
    step("1. Config loading")
    t1 = time.time()
    try:
        from src.utils.config import load_config
        config = load_config(base=True, test_system="kundur", experiment="exp1_kundur_2d")
        logger.info(f"Config loaded. experiment_name={config.get('experiment_name', 'N/A')}")
        logger.info(f"  optimizer: n_init={config.optimizer.n_init}, n_iter={config.optimizer.n_iter}")
        logger.info(f"  simulation: tf={config.simulation.tf}, timeout={config.simulation.timeout}")
        logger.info(f"  severity: w_angle={config.severity.w_angle}, w_freq={config.severity.w_freq}")
    except Exception as e:
        logger.error(f"Config failed: {e}\n{traceback.format_exc()}")
        return
    results["config_time"] = time.time() - t1
    logger.info(f"Config done in {results['config_time']:.2f}s")

    # ============================================================
    # Step 2: ANDES system load + power flow
    # ============================================================
    step("2. ANDES system load + power flow")
    t2 = time.time()
    try:
        case_path = andes.get_case("kundur/kundur_full.xlsx")
        logger.info(f"Case path: {case_path}")

        ss = andes.load(case_path, setup=False)
        logger.info(f"System loaded: {ss.Bus.n} buses, {ss.GENROU.n} gens")

        ss.setup()
        logger.info("System setup done")

        ss.PFlow.run()
        if ss.PFlow.converged:
            logger.info("Power flow CONVERGED")
        else:
            logger.error("Power flow DID NOT CONVERGE")
            return
    except Exception as e:
        logger.error(f"ANDES load/PF failed: {e}\n{traceback.format_exc()}")
        return
    results["andes_load_time"] = time.time() - t2
    logger.info(f"ANDES load+PF done in {results['andes_load_time']:.2f}s, memory = {mem_mb():.0f} MB")
    del ss
    logger.info(f"After del ss: memory = {mem_mb():.0f} MB")

    # ============================================================
    # Step 3: Single fault simulation via ANDESWrapper
    # ============================================================
    step("3. Single fault simulation via ANDESWrapper")
    t3 = time.time()
    try:
        from src.simulator.andes_wrapper import ANDESWrapper
        from src.simulator.scenario_builder import ScenarioBuilder

        system_config = load_config(test_system="kundur", base=False)
        builder = ScenarioBuilder(system_config, space_name="2d")
        logger.info(f"ScenarioBuilder: dim={builder.dim}, space=2d")

        wrapper = ANDESWrapper(
            case_path=system_config.system.case_path,
            config={"tf": 10.0, "tstep": 0.02, "criteria": 1, "timeout": 60},
        )
        logger.info("ANDESWrapper created")

        # Test a moderate fault: bus 7, clear at 0.15s
        x_test = np.array([0.6, 0.3])  # roughly bus 7, clear_time=0.185s
        scenario = builder.build(x_test)
        logger.info(f"Built scenario: {scenario}")

        sim_result = wrapper.evaluate(scenario)
        logger.info(
            f"Simulation result: success={sim_result.success}, "
            f"stable={sim_result.stable}, severity={sim_result.severity:.4f}, "
            f"time={sim_result.sim_time:.2f}s"
        )
        if sim_result.rotor_angles is not None:
            logger.info(f"  rotor_angles shape: {sim_result.rotor_angles.shape}")
        if sim_result.bus_voltages is not None:
            logger.info(f"  bus_voltages shape: {sim_result.bus_voltages.shape}")
    except Exception as e:
        logger.error(f"Single simulation failed: {e}\n{traceback.format_exc()}")
        return
    results["single_sim_time"] = time.time() - t3
    logger.info(f"Single sim done in {results['single_sim_time']:.2f}s, memory = {mem_mb():.0f} MB")

    # ============================================================
    # Step 4: Severity calculation
    # ============================================================
    step("4. Severity calculation")
    t4 = time.time()
    try:
        from src.objective.severity import SeverityCalculator

        sev_calc = SeverityCalculator(
            w_angle=config.severity.w_angle,
            w_freq=config.severity.w_freq,
            w_voltage=config.severity.w_voltage,
            angle_threshold=config.severity.angle_threshold,
            freq_nominal=config.severity.freq_nominal,
            freq_deviation=config.severity.freq_deviation,
        )
        severity = sev_calc.compute(sim_result)
        logger.info(f"Severity = {severity:.4f}")

        breakdown = sev_calc.compute_with_breakdown(sim_result)
        logger.info(f"Breakdown: {breakdown}")
    except Exception as e:
        logger.error(f"Severity calc failed: {e}\n{traceback.format_exc()}")
        return
    results["severity_time"] = time.time() - t4
    logger.info(f"Severity done in {results['severity_time']:.4f}s")

    # ============================================================
    # Step 5: Random search (3 evaluations only)
    # ============================================================
    step("5. Random search baseline (3 evaluations)")
    t5 = time.time()
    try:
        from src.baselines.random_search import RandomSearch

        eval_count = [0]

        def objective_probe(x):
            eval_count[0] += 1
            t_eval = time.time()
            scenario = builder.build(x)
            result = wrapper.evaluate(scenario)
            sev = sev_calc.compute(result)
            elapsed = time.time() - t_eval
            logger.info(
                f"  eval #{eval_count[0]}: x={[f'{v:.3f}' for v in x]}, "
                f"severity={sev:.4f}, eval_time={elapsed:.2f}s, mem={mem_mb():.0f}MB"
            )
            return sev

        searcher = RandomSearch(objective_probe, dim=2, n_evaluations=3, seed=42)
        best_x, best_y = searcher.optimize()
        convergence = searcher.get_convergence()
        logger.info(f"Random search best: severity={best_y:.4f}, convergence={convergence}")
    except Exception as e:
        logger.error(f"Random search failed: {e}\n{traceback.format_exc()}")
        return
    results["random_time"] = time.time() - t5
    logger.info(f"Random search (3 evals) done in {results['random_time']:.2f}s, memory = {mem_mb():.0f} MB")

    # ============================================================
    # Step 6: BO minimal (2 init + 1 iteration)
    # ============================================================
    step("6. BO minimal test (2 Sobol init + 1 BO iteration)")
    t6 = time.time()
    eval_count_bo = [0]
    try:
        from src.optimizer.bayesian_opt import BayesianOptimizer

        def objective_bo(x):
            eval_count_bo[0] += 1
            t_eval = time.time()
            scenario = builder.build(x)
            result = wrapper.evaluate(scenario)
            sev = sev_calc.compute(result)
            elapsed = time.time() - t_eval
            logger.info(
                f"  BO eval #{eval_count_bo[0]}: x={[f'{v:.3f}' for v in x]}, "
                f"severity={sev:.4f}, eval_time={elapsed:.2f}s, mem={mem_mb():.0f}MB"
            )
            return sev

        optimizer = BayesianOptimizer(
            objective_fn=objective_bo,
            dim=2,
            n_init=2,
            n_iter=1,
            acquisition="EI",
            kernel="matern52",
            seed=42,
        )

        logger.info("Starting BO.optimize()...")
        best_x_bo, best_y_bo = optimizer.optimize()
        conv = optimizer.get_convergence()
        logger.info(f"BO result: best_severity={best_y_bo:.4f}, convergence={conv}")
    except Exception as e:
        logger.error(f"BO failed: {e}\n{traceback.format_exc()}")
        return
    results["bo_time"] = time.time() - t6
    logger.info(f"BO (2+1 evals) done in {results['bo_time']:.2f}s, memory = {mem_mb():.0f} MB")

    # ============================================================
    # Step 7: ANDESWrapper memory leak check (5 sequential evals)
    # ============================================================
    step("7. Memory leak check (5 sequential evaluations)")
    t7 = time.time()
    try:
        rng = np.random.RandomState(99)
        mem_before = mem_mb()
        for i in range(5):
            x = rng.uniform(0, 1, size=2)
            scenario = builder.build(x)
            result = wrapper.evaluate(scenario)
            sev = sev_calc.compute(result)
            mem_now = mem_mb()
            logger.info(f"  leak-check #{i+1}: severity={sev:.4f}, RSS={mem_now:.0f}MB (delta={mem_now - mem_before:+.0f}MB)")
        mem_after = mem_mb()
        results["mem_leak_delta_mb"] = mem_after - mem_before
        logger.info(f"Memory after 5 evals: {mem_after:.0f} MB (delta = {mem_after - mem_before:+.0f} MB)")
    except Exception as e:
        logger.error(f"Memory leak check failed: {e}\n{traceback.format_exc()}")

    # ============================================================
    # Summary
    # ============================================================
    step("SUMMARY")
    logger.info("All steps passed!")
    logger.info(f"  Imports:        {results.get('imports_time', '?'):.1f}s")
    logger.info(f"  Config:         {results.get('config_time', '?'):.3f}s")
    logger.info(f"  ANDES load+PF:  {results.get('andes_load_time', '?'):.2f}s")
    logger.info(f"  Single sim:     {results.get('single_sim_time', '?'):.2f}s")
    logger.info(f"  Severity calc:  {results.get('severity_time', '?'):.4f}s")
    logger.info(f"  Random (3 ev):  {results.get('random_time', '?'):.2f}s")
    logger.info(f"  BO (2+1 ev):    {results.get('bo_time', '?'):.2f}s")
    logger.info(f"  Mem leak delta: {results.get('mem_leak_delta_mb', '?'):+.0f} MB over 5 evals")
    logger.info(f"  Final memory:   {mem_mb():.0f} MB")
    logger.info("Log saved to: test_minimal.log")


if __name__ == "__main__":
    main()
