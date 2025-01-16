"""Functions for configuring CuBIDS."""

from pathlib import Path
import importlib.resources
import yaml

def load_config(config_file):
    """Load a YAML file containing a configuration for param groups.

    Parameters
    ----------
    config_file : str or pathlib.Path, optional
        The path to the configuration file. If None, the default configuration file is used.

    Returns
    -------
    dict
        The configuration loaded from the YAML file.
    """
    if config_file is None:
        config_file = Path(importlib.resources.files("cubids") / "data/config.yml")

    with config_file.open() as f:
        config = yaml.safe_load(f)

    return config
