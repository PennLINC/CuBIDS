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


def _compress_lists(df):
    """Compress lists in a DataFrame to strings."""
    for col in df.columns:
        if isinstance(df[col].values[0], list):
            df[col] = df[col].apply(lambda x: "|&|".join(x))
    return df


def _expand_lists(df):
    """Expand strings in a DataFrame to lists."""
    for col in df.columns:
        if isinstance(df[col].values[0], str):
            df[col] = df[col].apply(lambda x: x.split("|&|"))
    return df
