"""Configuration loading utilities using OmegaConf."""

from pathlib import Path
from omegaconf import OmegaConf, DictConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = PROJECT_ROOT / "configs"


def load_yaml(path: str | Path) -> DictConfig:
    """Load a single YAML config file."""
    return OmegaConf.load(path)


def load_config(
    base: bool = True,
    test_system: str | None = None,
    experiment: str | None = None,
) -> DictConfig:
    """Load and merge configuration files.

    Args:
        base: Whether to load base.yaml defaults.
        test_system: Name of test system config (e.g. 'kundur').
        experiment: Name of experiment config (e.g. 'exp1_kundur_2d').

    Returns:
        Merged OmegaConf DictConfig.
    """
    configs = []
    if base:
        configs.append(load_yaml(CONFIGS_DIR / "base.yaml"))
    if test_system:
        configs.append(load_yaml(CONFIGS_DIR / "test_systems" / f"{test_system}.yaml"))
    if experiment:
        configs.append(load_yaml(CONFIGS_DIR / "experiments" / f"{experiment}.yaml"))

    merged = OmegaConf.merge(*configs) if configs else OmegaConf.create()
    return merged
