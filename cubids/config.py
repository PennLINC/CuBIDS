"""
Functions for configuring CuBIDS
"""

from pathlib import Path

import yaml
from pkg_resources import resource_filename as pkgrf


def load_config(config_file):
    """Loads a YAML file containing a configuration for param groups."""

    if config_file is None:
        config_file = Path(pkgrf("cubids", "data/config.yml"))

    with config_file.open() as f:
        config = yaml.safe_load(f)

    return config
