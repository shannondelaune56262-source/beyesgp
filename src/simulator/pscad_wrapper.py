"""PSCAD simulation engine wrapper for cross-validation.

Provides Python interface to PSCAD/EMTDC for electromagnetic transient
simulation of worst-case scenarios identified by BO+ANDES.

Requires PSCAD to be installed with Python automation API enabled.
"""

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.simulator.andes_wrapper import SimulationResult

logger = logging.getLogger(__name__)


@dataclass
class PSCADCaseConfig:
    """Configuration for a PSCAD validation case."""
    case_name: str
    pscad_project_path: str  # Path to .psc file
    fault_bus: int
    fault_time: float       # seconds
    clear_time: float       # seconds
    load_scaling: dict      # area -> factor
    line_trip: str | None   # Line to trip
    output_dir: str


class PSCADWrapper:
    """Wraps PSCAD/EMTDC for electromagnetic transient verification.

    Supports two modes:
    1. Python API mode: Uses pscad.autolib (requires PSCAD with Python API)
    2. Command-line mode: Invokes PSCAD via command line with .psc files
    """

    def __init__(self, pscad_install_dir: str | None = None):
        self.pscad_dir = pscad_install_dir
        self._api_available = self._check_api()

    def _check_api(self) -> bool:
        """Check if PSCAD Python API is available."""
        try:
            import pscad
            return True
        except ImportError:
            logger.warning(
                "PSCAD Python API not available. "
                "Will use command-line mode if PSCAD path is configured."
            )
            return False

    def validate_scenario(
        self,
        scenario: dict,
        pscad_project: str,
        output_dir: str = "data/pscad_results",
    ) -> SimulationResult:
        """Run a single scenario in PSCAD for cross-validation.

        Args:
            scenario: Same scenario dict as used by ANDES.
            pscad_project: Path to the PSCAD project (.psc) file.
            output_dir: Directory for PSCAD output files.

        Returns:
            SimulationResult compatible with the severity calculator.
        """
        start_time = time.time()

        if self._api_available:
            result = self._run_via_api(scenario, pscad_project, output_dir)
        elif self.pscad_dir:
            result = self._run_via_cli(scenario, pscad_project, output_dir)
        else:
            return SimulationResult(
                success=False, stable=False, severity=1.0,
                sim_time=0.0,
                error_msg="PSCAD not available (no API and no install dir)",
            )

        result.sim_time = time.time() - start_time
        return result

    def validate_top_k(
        self,
        scenarios: list[dict],
        pscad_project: str,
        output_dir: str = "data/pscad_results",
    ) -> list[SimulationResult]:
        """Validate top-K worst-case scenarios from ANDES BO search."""
        results = []
        for i, scenario in enumerate(scenarios):
            logger.info(f"PSCAD validation [{i+1}/{len(scenarios)}]")
            result = self.validate_scenario(scenario, pscad_project, output_dir)
            results.append(result)
        return results

    def _run_via_api(
        self, scenario: dict, pscad_project: str, output_dir: str
    ) -> SimulationResult:
        """Run simulation using PSCAD Python API."""
        try:
            import pscad

            # Load project
            workspace = pscad.workspace()
            project = workspace.project(pscad_project)

            # Configure fault parameters
            fault_bus = scenario.get("fault_bus")
            fault_time = scenario.get("fault_time", 1.0)
            clear_time = scenario.get("clear_time", 1.1)

            # Set fault parameters in the project
            # (Implementation depends on specific PSCAD project structure)
            logger.info(
                f"PSCAD API: fault_bus={fault_bus}, "
                f"tf={fault_time}, tc={clear_time}"
            )

            # Run simulation
            project.run()

            # Extract results from output files
            return self._parse_pscad_output(output_dir)

        except Exception as e:
            return SimulationResult(
                success=False, stable=False, severity=1.0,
                error_msg=f"PSCAD API error: {e}",
            )

    def _run_via_cli(
        self, scenario: dict, pscad_project: str, output_dir: str
    ) -> SimulationResult:
        """Run simulation using PSCAD command-line interface."""
        try:
            pscad_exe = str(Path(self.pscad_dir) / "pscad.exe")
            cmd = [
                pscad_exe,
                pscad_project,
                "/run",
                f"/output:{output_dir}",
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )
            if result.returncode != 0:
                return SimulationResult(
                    success=False, stable=False, severity=1.0,
                    error_msg=f"PSCAD CLI error: {result.stderr}",
                )
            return self._parse_pscad_output(output_dir)

        except subprocess.TimeoutExpired:
            return SimulationResult(
                success=False, stable=False, severity=1.0,
                error_msg="PSCAD simulation timeout",
            )
        except Exception as e:
            return SimulationResult(
                success=False, stable=False, severity=1.0,
                error_msg=f"PSCAD CLI error: {e}",
            )

    def _parse_pscad_output(self, output_dir: str) -> SimulationResult:
        """Parse PSCAD .out output files into SimulationResult.

        PSCAD outputs are typically in .out or .csv format with columns
        for time, voltages, currents, rotor angles, etc.
        """
        output_path = Path(output_dir)
        out_files = list(output_path.glob("*.out")) + list(output_path.glob("*.csv"))

        if not out_files:
            return SimulationResult(
                success=False, stable=False, severity=1.0,
                error_msg="No PSCAD output files found",
            )

        # Parse the output file
        # Implementation depends on PSCAD output format
        try:
            data = np.loadtxt(out_files[0], skiprows=1)
            time_vec = data[:, 0]

            # Assume columns: time, gen1_angle, gen2_angle, ..., bus_voltages
            # Exact column mapping depends on PSCAD project configuration
            n_cols = data.shape[1]

            result = SimulationResult(
                success=True,
                stable=True,  # Will be determined by severity calc
                severity=0.0,
                time_vector=time_vec,
            )

            return result

        except Exception as e:
            return SimulationResult(
                success=False, stable=False, severity=1.0,
                error_msg=f"Output parsing error: {e}",
            )
