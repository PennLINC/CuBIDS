"""Miscellaneous utility functions for CuBIDS.

This module provides various utility functions used throughout the CuBIDS package.
"""

import re
from pathlib import Path


def _get_container_type(image_name):
    """Get and return the container type.

    Parameters
    ----------
    image_name : :obj:`str`
        The name of the container image.

    Returns
    -------
    :obj:`str`
        The container type, either "docker" or "singularity".

    Raises
    ------
    :obj:`Exception`
        If the container type cannot be determined.
    """
    # If it's a file on disk, it must be a singularity image
    if Path(image_name).exists():
        return "singularity"

    # It needs to match a docker tag pattern to be docker
    if re.match(r"(?:.+\/)?([^:]+)(?::.+)?", image_name):
        return "docker"

    raise Exception("Unable to determine the container type of " + image_name)


def download_schema(version="latest", out_file=None):
    """Download the BIDS schema as a dereferenced JSON file.

    Parameters
    ----------
    version : :obj:`str`, optional
        The version of the schema to download.
        If not provided, the latest version will be downloaded.

    Returns
    -------
    :obj:`str`
        The path to the downloaded schema.
    """
    import json
    from urllib.request import urlopen

    out_file = out_file or Path("schema.json")

    schema_url = f"https://bids-specification.readthedocs.io/en/{version}/schema.json"

    # Check if the schema is available
    try:
        schema = urlopen(schema_url).read()
    except Exception as e:
        raise Exception(f"Unable to download schema from {schema_url}: {e}")

    with open(out_file, "wb") as f:
        json.dump(schema, f, indent=4, sort_keys=True)

    return out_file
