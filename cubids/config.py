"""Functions for configuring CuBIDS."""

from pathlib import Path
import importlib.resources as pkg_resources
import yaml

def load_config(config_file):
    """Load a YAML file containing a configuration for param groups."""
    if config_file is None:
        config_file = Path(pkg_resources.files("cubids") / "data/config.yml")

    with config_file.open() as f:
        config = yaml.safe_load(f)

    return config
