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


def load_schema(schema_file):
    """Load a JSON file containing the BIDS schema.

    Parameters
    ----------
    schema_file : str or pathlib.Path, optional
        The path to the schema file. If None, the default schema file is used.

    Returns
    -------
    dict
        The schema loaded from the YAML file.
    """
    import json

    if schema_file is None:
        schema_file = Path(importlib.resources.files("cubids") / "data/schema.json")

    with schema_file.open() as f:
        schema = json.load(f)

    print(
        f"Loading BIDS schema version: {schema['schema_version']}. "
        f"BIDS version: {schema['bids_version']}"
    )

    return schema
