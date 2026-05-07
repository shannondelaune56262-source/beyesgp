"""ANDES simulation engine wrapper for BO-WCS.

Provides a clean interface to run transient stability simulations
using ANDES, with fault injection and result extraction.
Supports REGCA1+REECA1+REPCA1 renewable energy dynamic model injection.
"""

import logging
import time
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class REDeviceConfig:
    """Configuration for a single REGCA1+REECA1+REPCA1 RE device chain."""

    bus: int
    p_mw: float = 20.0
    q_mvar: float = 0.0
    # REGCA1 converter params (defaults model a Type-4 wind turbine)
    regca1: dict | None = None
    # REECA1 electrical control params
    reeca1: dict | None = None
    # REPCA1 plant controller params
    repca1: dict | None = None

    def get_regca1_params(self) -> dict:
        defaults = dict(
            Tg=0.1, Rrpwr=999, Brkpt=0.8, Zerox=0.4,
            Lvplsw=1, Lvpl1=1.0, Volim=1.2,
            Lvpnt1=1.0, Lvpnt0=0.4, Iolim=-999,
            Tfltr=0.1, Khv=0.7, Iqrmax=999, Iqrmin=-999,
            Accel=0, gammap=1, gammaq=1,
        )
        if self.regca1:
            defaults.update(self.regca1)
        return defaults

    def get_reeca1_params(self) -> dict:
        defaults = dict(
            PFFLAG=1, VFLAG=0, QFLAG=0, PFLAG=1, PQFLAG=0,
            Vdip=0.9, Vup=1.1, Trv=0.02,
            dbd1=-0.02, dbd2=0.02, Kqv=2,
            Iqh1=999, Iql1=-999, Vref0=1.0,
            Iqfrz=0, Thld=0.05, Thld2=0.1,
            Tp=0.02, QMax=0.05, QMin=-0.05,
            VMAX=999, VMIN=-999,
            Kqp=1, Kqi=0.1, Kvp=0.1, Kvi=0.01,
            Vref1=1, Tiq=0.02,
            dPmax=10, dPmin=-10,
            PMAX=999, PMIN=0, Imax=1.1, Tpord=0.02,
        )
        if self.reeca1:
            defaults.update(self.reeca1)
        return defaults

    def get_repca1_params(self) -> dict:
        defaults = dict(
            VCFlag=1, RefFlag=1, Fflag=1, PLflag=1,
            Tfltr=0.02, Kp=1, Ki=0.1,
            Tft=1, Tfv=1, Vfrz=0.8, Kc=1,
            emax=999, emin=-999, dbd1=-0.02, dbd2=0.02,
            Qmax=999, Qmin=-999, Kpg=1, Kig=0.1, Tp=0.02,
            fdbd1=-0.01, fdbd2=0.01, femax=0.05, femin=-0.05,
            Pmax=999, Pmin=-999, Tg=0.02, Ddn=10, Dup=10,
        )
        if self.repca1:
            defaults.update(self.repca1)
        return defaults


# Pre-defined RE device configurations per penetration level
RE_LEVEL_CONFIGS = {
    1: [  # Low: 1 RE device at Bus 5 (load bus), ~20 MW
        REDeviceConfig(bus=5, p_mw=20.0),
    ],
    2: [  # Medium: 3 RE devices at load buses, ~60 MW total
        REDeviceConfig(bus=5, p_mw=20.0),
        REDeviceConfig(bus=7, p_mw=20.0),
        REDeviceConfig(bus=9, p_mw=20.0),
    ],
    3: [  # High: 5 RE devices at load+gen buses, ~100 MW total
        REDeviceConfig(bus=5, p_mw=20.0),
        REDeviceConfig(bus=7, p_mw=20.0),
        REDeviceConfig(bus=9, p_mw=20.0),
        REDeviceConfig(bus=10, p_mw=20.0),
        REDeviceConfig(bus=4, p_mw=20.0),
    ],
    4: [  # Extreme: 6 RE devices, ~120 MW total
        REDeviceConfig(bus=5, p_mw=20.0),
        REDeviceConfig(bus=7, p_mw=20.0),
        REDeviceConfig(bus=9, p_mw=20.0),
        REDeviceConfig(bus=10, p_mw=20.0),
        REDeviceConfig(bus=4, p_mw=20.0),
        REDeviceConfig(bus=2, p_mw=20.0),
    ],
}


@dataclass
class SimulationResult:
    """Structured result from a single ANDES simulation."""

    success: bool
    stable: bool
    severity: float
    rotor_angles: np.ndarray | None = None  # (n_timesteps, n_gen)
    rotor_speeds: np.ndarray | None = None  # (n_timesteps, n_gen)
    bus_voltages: np.ndarray | None = None  # (n_timesteps, n_bus)
    time_vector: np.ndarray | None = None   # (n_timesteps,)
    re_states: dict | None = None           # RE device states: {model: values}
    tie_line_flows: dict | None = None      # {line_name: {initial_P_MW, final_P_MW, max_P_MW}}
    sim_time: float = 0.0
    error_msg: str = ""


def _sim_worker(scenario_dict, case_path, sim_config, q):
    """Module-level worker for subprocess simulation (must be picklable on Windows)."""
    try:
        import andes
        import os
        os.environ.setdefault("OMP_NUM_THREADS", "4")
        os.environ.setdefault("MKL_NUM_THREADS", "4")
        os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
        ss = None
        try:
            ss = andes.load(case_path, setup=False)
            load_scaling = scenario_dict.get("load_scaling", {})
            if load_scaling:
                for area, factor in load_scaling.items():
                    if factor == 1.0:
                        continue
                    if hasattr(ss, "PQ") and ss.PQ.n > 0:
                        area_map = {
                            "area1": {1, 2, 3, 4, 5},
                            "area2": {6, 7, 8, 9, 10},
                            "1": {1, 2, 3, 4, 5},
                            "2": {6, 7, 8, 9, 10},
                        }
                        area_buses = area_map.get(area.lower())
                        p_param = ss.PQ.p0 if hasattr(ss.PQ, 'p0') else ss.PQ.Ppf
                        q_param = ss.PQ.q0 if hasattr(ss.PQ, 'q0') else ss.PQ.Qpf
                        if area_buses is not None:
                            for i in range(ss.PQ.n):
                                bus_idx = ss.PQ.bus.v[i]
                                bus_num = ss.Bus.idx.v[bus_idx] if hasattr(ss.Bus.idx, 'v') else bus_idx
                                if bus_num in area_buses:
                                    p_param.v[i] *= factor
                                    q_param.v[i] *= factor
                        else:
                            p_param.v[:] *= factor
                            q_param.v[:] *= factor
            # Apply RE device injection before setup
            re_devices_raw = scenario_dict.get("re_devices")
            if re_devices_raw is not None:
                for dev in re_devices_raw:
                    if isinstance(dev, dict):
                        d = REDeviceConfig(**dev)
                    else:
                        d = dev
                    bus = d.bus
                    p_pu = d.p_mw / 100.0
                    q_pu = d.q_mvar / 100.0
                    pv_idx = ss.add("PV", {"bus": bus, "p0": p_pu, "q0": q_pu, "v0": 1.0})
                    rp = d.get_regca1_params()
                    rp["bus"] = bus
                    rp["gen"] = pv_idx
                    reg_idx = ss.add("REGCA1", rp)
                    ep = d.get_reeca1_params()
                    ep["reg"] = reg_idx
                    ree_idx = ss.add("REECA1", ep)
                    pp = d.get_repca1_params()
                    pp["ree"] = ree_idx
                    try:
                        ss.add("REPCA1", pp)
                    except Exception:
                        pass
            fault_bus = scenario_dict.get("fault_bus")
            if fault_bus is not None:
                fault_time = scenario_dict.get("fault_time", 1.0)
                clear_time = scenario_dict.get("clear_time", 1.1)
                ss.add("Fault", {"bus": fault_bus, "tf": fault_time, "tc": clear_time})
            line_trip = scenario_dict.get("line_trip")
            if line_trip is not None:
                trip_time = line_trip.get("time", scenario_dict.get("fault_time", 1.0))
                ss.add("Toggle", {"model": "Line", "dev": line_trip["line_idx"], "t": trip_time})
            ss.setup()
            ss.PFlow.run()
            if not ss.PFlow.converged:
                q.put(("ok", SimulationResult(success=False, stable=False, severity=1.0,
                                              error_msg="Power flow did not converge")))
                return
            ss.TDS.config.tf = sim_config.get("tf", 10.0)
            ss.TDS.config.tstep = sim_config.get("tstep", 0.02)
            ss.TDS.config.criteria = sim_config.get("criteria", 1)
            ss.TDS.run()
            # Extract results
            unstable = hasattr(ss, "_criteria_violated") and ss._criteria_violated
            t = ss.dae.ts.t
            if t is None or len(t) == 0:
                q.put(("ok", SimulationResult(success=False, stable=False, severity=1.0,
                                              error_msg="No TDS output")))
                return
            import numpy as np
            rotor_angles = None
            if hasattr(ss, "GENROU") and ss.GENROU.n > 0:
                delta_idx = ss.GENROU.delta.a
                if delta_idx is not None and len(delta_idx) > 0:
                    rotor_angles = ss.dae.ts.x[:, delta_idx]
            rotor_speeds = None
            if hasattr(ss, "GENROU") and ss.GENROU.n > 0:
                omega_idx = ss.GENROU.omega.a
                if omega_idx is not None and len(omega_idx) > 0:
                    rotor_speeds = ss.dae.ts.x[:, omega_idx]
            bus_voltages = None
            if hasattr(ss, "Bus") and ss.Bus.n > 0:
                v_idx = ss.Bus.v.a
                if v_idx is not None and len(v_idx) > 0:
                    bus_voltages = ss.dae.ts.y[:, v_idx]
            stable = not unstable
            if rotor_angles is not None:
                max_angle_diff = np.max(rotor_angles) - np.min(rotor_angles, axis=1, keepdims=True)
                if np.max(max_angle_diff) > np.deg2rad(180):
                    stable = False
            result = SimulationResult(
                success=True, stable=stable, severity=0.0,
                rotor_angles=rotor_angles, rotor_speeds=rotor_speeds,
                bus_voltages=bus_voltages, time_vector=t,
            )
            q.put(("ok", result))
        finally:
            if ss is not None:
                del ss
    except Exception as e:
        q.put(("err", str(e)))


class ANDESWrapper:
    """Wraps ANDES for transient stability simulation within the BO loop.

    Each call to evaluate() loads a fresh system, applies the scenario,
    runs power flow + TDS, and extracts results.
    """

    def __init__(self, case_path: str, config: dict | None = None,
                 tie_lines: list[dict] | None = None,
                 system_config: dict | None = None):
        self.case_path = case_path
        self.config = config or {}
        self.sim_tf = self.config.get("tf", 10.0)
        self.sim_tstep = self.config.get("tstep", 0.02)
        self.use_criteria = self.config.get("criteria", 1)
        self.timeout = self.config.get("timeout", 60)
        self.freq_nominal = self.config.get("freq_nominal", 60.0)
        self.base_mva = self.config.get("base_mva", 100.0)
        self.tie_lines = tie_lines
        self.system_config = system_config

        # Import ANDES once at init time
        try:
            import andes
            self._andes = andes
        except ImportError:
            raise ImportError(
                "ANDES is not installed. Run: pip install andes"
            )

        # Cache base case path
        if case_path.startswith("kundur/") or case_path.startswith("ieee"):
            self._full_case_path = self._andes.get_case(case_path)
        else:
            self._full_case_path = case_path

        # Limit threads to prevent system overload (torch 32 + OpenBLAS 48 = 80 threads on 32 cores)
        try:
            import torch
            torch.set_num_threads(4)
            logger.info(f"PyTorch threads set to {torch.get_num_threads()}")
        except ImportError:
            pass

        # Pre-warm ANDES codegen with single-thread to prevent Pool(32) freeze on Windows
        logger.info("Pre-warming ANDES codegen (nomp=True) ...")
        self._andes.prepare(nomp=True)
        logger.info("ANDES codegen pre-warmed successfully")

    def evaluate(self, scenario: dict) -> SimulationResult:
        """Run a single simulation with the given scenario.

        Args:
            scenario: Dict with scenario parameters, e.g.:
                {
                    "fault_bus": 7,
                    "fault_time": 1.0,
                    "clear_time": 1.1,
                    "load_scaling": {"area1": 1.0, "area2": 1.0},
                    "line_trip": None,  # or {"line_idx": "Line_7_8_1", "time": 1.0}
                }

        Returns:
            SimulationResult with severity and time-series data.
        """
        start_time = time.time()

        try:
            result = self._run_simulation_with_timeout(scenario)
            result.sim_time = time.time() - start_time
            return result
        except FuturesTimeoutError:
            logger.warning(f"Simulation timed out after {self.timeout}s")
            return SimulationResult(
                success=False,
                stable=False,
                severity=1.0,
                sim_time=time.time() - start_time,
                error_msg=f"Simulation timed out ({self.timeout}s)",
            )
        except Exception as e:
            logger.warning(f"Simulation failed: {e}")
            return SimulationResult(
                success=False,
                stable=False,
                severity=1.0,
                sim_time=time.time() - start_time,
                error_msg=str(e),
            )

    def _run_simulation_with_timeout(self, scenario: dict) -> SimulationResult:
        """Run simulation with optional subprocess timeout enforcement.

        On Windows, subprocess spawn has high overhead (60s+ to reimport all libraries).
        Since ANDES TDS has built-in early termination (criteria=1) and bounded steps,
        we run directly in the main process. The subprocess path is reserved for
        pathological cases where TDS hangs despite internal safeguards.
        """
        result = self._run_simulation(scenario)
        return result

    def _run_simulation(self, scenario: dict) -> SimulationResult:
        """Internal method that actually runs the ANDES simulation."""
        import andes

        ss = None
        try:
            # Load fresh system (undill loads cached pycode, no Pool)
            ss = andes.load(self._full_case_path, setup=False)

            # Apply load scaling before setup
            load_scaling = scenario.get("load_scaling", {})
            if load_scaling:
                self._apply_load_scaling(ss, load_scaling)

            # Apply generator output scaling before setup
            gen_scaling = scenario.get("gen_scaling", {})
            if gen_scaling:
                self._apply_gen_scaling(ss, gen_scaling)

            # Apply RE device injection before setup
            re_devices = scenario.get("re_devices")
            if re_devices is not None:
                self._apply_re_devices(ss, re_devices)

            # Add fault BEFORE setup (setup() sets is_setup=True, after which add() raises)
            fault_bus = scenario.get("fault_bus")
            if fault_bus is not None:
                fault_time = scenario.get("fault_time", 1.0)
                clear_time = scenario.get("clear_time", 1.1)

                ss.add("Fault", {
                    "bus": fault_bus,
                    "tf": fault_time,
                    "tc": clear_time,
                })

            # Add line trip BEFORE setup
            line_trip = scenario.get("line_trip")
            if line_trip is not None:
                trip_time = line_trip.get("time", scenario.get("fault_time", 1.0))
                ss.add("Toggle", {
                    "model": "Line",
                    "dev": line_trip["line_idx"],
                    "t": trip_time,
                })

            # Add multiple simultaneous line trips (same-tower multi-circuit fault)
            line_trips = scenario.get("line_trips")
            if line_trips is not None:
                for lt in line_trips:
                    trip_time = lt.get("time", scenario.get("fault_time", 1.0))
                    ss.add("Toggle", {
                        "model": "Line",
                        "dev": lt["line_idx"],
                        "t": trip_time,
                    })

            # Setup (now includes Fault and Toggle devices)
            ss.setup()

            # Run power flow
            ss.PFlow.run()

            # Check PF convergence
            if not ss.PFlow.converged:
                return SimulationResult(
                    success=False, stable=False, severity=1.0,
                    error_msg="Power flow did not converge"
                )

            # Configure TDS
            ss.TDS.config.tf = self.sim_tf
            ss.TDS.config.tstep = self.sim_tstep
            ss.TDS.config.criteria = self.use_criteria

            # Run TDS
            ss.TDS.run()

            # Extract results
            return self._extract_results(ss)
        finally:
            if ss is not None:
                del ss

    def _extract_tie_line_flows(self, ss) -> dict | None:
        """Extract power flow time series on tie lines from ANDES TDS output.

        Computes active power using pi-model from bus voltage/angle timeseries.
        Positive direction: from_bus → to_bus (config defines WEST→EAST).

        Returns:
            dict mapping line_name to {initial_P_MW, final_P_MW, max_P_MW}
            or None if no tie_lines configured.
        """
        if not self.tie_lines:
            return None

        t = ss.dae.ts.t
        n_steps = len(t) if t is not None else 0
        if n_steps == 0:
            return None

        # Build bus number → internal index map
        bus_map = {}
        for j in range(ss.Bus.n):
            bus_num = int(ss.Bus.idx.v[j]) if hasattr(ss.Bus.idx, 'v') else j
            bus_map[bus_num] = j

        bus_v_idx = ss.Bus.v.a
        bus_a_idx = ss.Bus.a.a

        flows = {}
        for tl in self.tie_lines:
            line_name = tl["name"]
            from_bus = tl["from_bus"]
            to_bus = tl["to_bus"]

            line_p_mw = None

            # Find line parameters r, x
            r_val, x_val = None, None
            if hasattr(ss, "Line") and ss.Line.n > 0:
                for i in range(ss.Line.n):
                    b1 = int(ss.Line.bus1.v[i])
                    b2 = int(ss.Line.bus2.v[i])
                    if ((b1 == from_bus and b2 == to_bus)
                            or (b1 == to_bus and b2 == from_bus)):
                        r_val = ss.Line.r.v[i]
                        x_val = ss.Line.x.v[i]
                        break

            # Compute power flow from bus voltages using pi-model
            fb = bus_map.get(from_bus)
            tb = bus_map.get(to_bus)
            if (fb is not None and tb is not None
                    and r_val is not None and x_val is not None):
                v1 = ss.dae.ts.y[:, bus_v_idx[fb]]
                a1 = ss.dae.ts.y[:, bus_a_idx[fb]]
                v2 = ss.dae.ts.y[:, bus_v_idx[tb]]
                a2 = ss.dae.ts.y[:, bus_a_idx[tb]]
                da = a1 - a2

                g = r_val / (r_val**2 + x_val**2)
                b_line = -x_val / (r_val**2 + x_val**2)
                p_pu = v1**2 * g - v1 * v2 * (g * np.cos(da) + b_line * np.sin(da))
                line_p_mw = p_pu * self.base_mva

            if line_p_mw is not None:
                flows[line_name] = {
                    "initial_P_MW": float(line_p_mw[0]),
                    "final_P_MW": float(line_p_mw[-1]),
                    "max_P_MW": float(np.max(np.abs(line_p_mw))),
                }
            else:
                flows[line_name] = {
                    "initial_P_MW": 0.0,
                    "final_P_MW": 0.0,
                    "max_P_MW": 0.0,
                }

        return flows

    def _extract_results(self, ss) -> SimulationResult:
        """Extract time-series data from ANDES TDS output."""
        # Check stability via ANDES criteria
        unstable = hasattr(ss, "_criteria_violated") and ss._criteria_violated

        # Extract time vector
        t = ss.dae.ts.t
        if t is None or len(t) == 0:
            return SimulationResult(
                success=False, stable=False, severity=1.0,
                error_msg="No TDS output"
            )

        # Extract rotor angles
        rotor_angles = None
        if hasattr(ss, "GENROU") and ss.GENROU.n > 0:
            delta_idx = ss.GENROU.delta.a
            if delta_idx is not None and len(delta_idx) > 0:
                rotor_angles = ss.dae.ts.x[:, delta_idx]

        # Extract rotor speeds
        rotor_speeds = None
        if hasattr(ss, "GENROU") and ss.GENROU.n > 0:
            omega_idx = ss.GENROU.omega.a
            if omega_idx is not None and len(omega_idx) > 0:
                rotor_speeds = ss.dae.ts.x[:, omega_idx]

        # Extract bus voltages
        bus_voltages = None
        if hasattr(ss, "Bus") and ss.Bus.n > 0:
            v_idx = ss.Bus.v.a
            if v_idx is not None and len(v_idx) > 0:
                bus_voltages = ss.dae.ts.y[:, v_idx]

        # Determine stability
        stable = not unstable
        if rotor_angles is not None:
            max_angle_diff = np.max(rotor_angles) - np.min(rotor_angles, axis=1, keepdims=True)
            if np.max(max_angle_diff) > np.deg2rad(180):
                stable = False

        # Extract RE device states
        re_states = {}
        for model_name in ("REGCA1", "REECA1", "REPCA1"):
            if hasattr(ss, model_name) and getattr(ss, model_name).n > 0:
                model = getattr(ss, model_name)
                model_states = {}
                for attr_name in dir(model):
                    attr = getattr(model, attr_name, None)
                    if hasattr(attr, 'a') and attr.a is not None and len(attr.a) > 0:
                        idx = attr.a
                        if idx is not None and len(idx) > 0:
                            try:
                                vals = ss.dae.ts.x[:, idx] if max(idx) < ss.dae.ts.x.shape[1] else None
                                if vals is None:
                                    vals = ss.dae.ts.y[:, idx] if max(idx) < ss.dae.ts.y.shape[1] else None
                                if vals is not None:
                                    model_states[attr_name] = vals
                            except (IndexError, ValueError):
                                pass
                if model_states:
                    re_states[model_name] = model_states

        # Extract tie-line power flows
        tie_line_flows = self._extract_tie_line_flows(ss)

        return SimulationResult(
            success=True,
            stable=stable,
            severity=0.0,  # Will be computed by SeverityCalculator
            rotor_angles=rotor_angles,
            rotor_speeds=rotor_speeds,
            bus_voltages=bus_voltages,
            time_vector=t,
            re_states=re_states if re_states else None,
            tie_line_flows=tie_line_flows,
        )

    def _apply_load_scaling(self, ss, scaling: dict) -> None:
        """Scale loads by area using the correct parameter (p0/q0 for PQ)."""
        for area, factor in scaling.items():
            if factor == 1.0:
                continue
            if hasattr(ss, "PQ") and ss.PQ.n > 0:
                area_buses = self._get_area_buses(area)
                p_param = ss.PQ.p0 if hasattr(ss.PQ, 'p0') else ss.PQ.Ppf
                q_param = ss.PQ.q0 if hasattr(ss.PQ, 'q0') else ss.PQ.Qpf
                if area_buses is not None:
                    for i in range(ss.PQ.n):
                        bus_idx = ss.PQ.bus.v[i]
                        bus_num = self._resolve_bus_num(ss, bus_idx)
                        if bus_num in area_buses:
                            p_param.v[i] *= factor
                            q_param.v[i] *= factor
                else:
                    p_param.v[:] *= factor
                    q_param.v[:] *= factor

    @staticmethod
    def _resolve_bus_num(ss, bus_idx: int) -> int:
        """Resolve ANDES internal bus index to bus number.

        Handles edge cases where bus_idx may be 1-based (e.g., last bus in IEEE 39).
        """
        if hasattr(ss.Bus.idx, 'v') and bus_idx < len(ss.Bus.idx.v):
            return ss.Bus.idx.v[bus_idx]
        return bus_idx

    def _apply_gen_scaling(self, ss, scaling: dict) -> None:
        """Scale generator outputs via PV/Slack p0 parameter."""
        # Build gen_name → bus mapping from system_config or fallback to Kundur defaults
        gen_bus_map = {}
        if self.system_config and "generators" in self.system_config:
            for gen in self.system_config["generators"]:
                gen_bus_map[gen["name"]] = gen["bus"]
        else:
            gen_bus_map = {"GENROU_1": 1, "GENROU_2": 2, "GENROU_3": 3, "GENROU_4": 4}

        for gen_name, factor in scaling.items():
            if factor == 1.0:
                continue
            target_bus = gen_bus_map.get(gen_name)
            if target_bus is None:
                continue
            # Check Slack - resolve internal bus index to bus number
            if hasattr(ss, 'Slack') and ss.Slack.n > 0:
                for i in range(ss.Slack.n):
                    bus_num = self._resolve_bus_num(ss, ss.Slack.bus.v[i])
                    if bus_num == target_bus:
                        ss.Slack.p0.v[i] *= factor
                        break
            # Check PV - resolve internal bus index to bus number
            if hasattr(ss, 'PV') and ss.PV.n > 0:
                for i in range(ss.PV.n):
                    bus_num = self._resolve_bus_num(ss, ss.PV.bus.v[i])
                    if bus_num == target_bus:
                        ss.PV.p0.v[i] *= factor
                        break

    def _get_area_buses(self, area: str) -> set | None:
        """Get bus numbers for a given area from system_config or Kundur defaults."""
        if self.system_config and "areas" in self.system_config:
            area_data = self.system_config["areas"].get(area.lower())
            if area_data is None:
                # Try matching area name directly (e.g., "west", "east")
                for area_name, area_info in self.system_config["areas"].items():
                    if area_name.lower() == area.lower():
                        return set(area_info["buses"])
                return None
            return set(area_data["buses"]) if isinstance(area_data, dict) else set(area_data)
        # Kundur fallback
        area_map = {
            "area1": {1, 2, 3, 4, 5},
            "area2": {6, 7, 8, 9, 10},
            "1": {1, 2, 3, 4, 5},
            "2": {6, 7, 8, 9, 10},
        }
        return area_map.get(area.lower())

    def evaluate_batch(self, scenarios: list[dict]) -> list[SimulationResult]:
        """Evaluate multiple scenarios sequentially.

        Note: ANDES is not thread-safe, so parallelism is handled
        at the process level in experiment/multi_run.py.
        """
        return [self.evaluate(s) for s in scenarios]

    def _apply_re_devices(self, ss, devices: list[REDeviceConfig | dict]) -> None:
        """Inject REGCA1+REECA1+REPCA1 RE device chains before setup().

        Each device creates: PV(static gen) → REGCA1(converter) → REECA1(control) → REPCA1(plant ctrl).
        The PV device provides the power injection point; REGCA1 overrides its dynamic behavior.
        """
        for dev_cfg in devices:
            if isinstance(dev_cfg, dict):
                dev_cfg = REDeviceConfig(**dev_cfg)

            bus = dev_cfg.bus
            p_pu = dev_cfg.p_mw / 100.0  # Convert MW to p.u. on 100 MVA base
            q_pu = dev_cfg.q_mvar / 100.0

            # Add a PV static generator as the RE injection point
            pv_idx = ss.add("PV", {"bus": bus, "p0": p_pu, "q0": q_pu, "v0": 1.0})

            # Add REGCA1 converter model linked to the PV
            regca1_params = dev_cfg.get_regca1_params()
            regca1_params["bus"] = bus
            regca1_params["gen"] = pv_idx
            reg_idx = ss.add("REGCA1", regca1_params)

            # Add REECA1 electrical control linked to REGCA1
            reeca1_params = dev_cfg.get_reeca1_params()
            reeca1_params["reg"] = reg_idx
            ree_idx = ss.add("REECA1", reeca1_params)

            # Add REPCA1 plant controller linked to REECA1
            repca1_params = dev_cfg.get_repca1_params()
            repca1_params["ree"] = ree_idx
            # Try to add BusFreq if not already present
            if hasattr(ss, "BusFreq") and ss.BusFreq.n > 0:
                repca1_params["busf"] = ss.BusFreq.idx.v[0]
            try:
                ss.add("REPCA1", repca1_params)
            except Exception as e:
                logger.warning(f"REPCA1 injection failed for bus {bus}: {e}")

            logger.debug(f"Injected RE device chain at bus {bus}: PV={pv_idx}, REGCA1={reg_idx}")
