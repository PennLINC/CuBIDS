"""Miscellaneous utility functions for CuBIDS."""
import re
from pathlib import Path


def _get_container_type(image_name):
    """Get and return the container type."""
    # If it's a file on disk, it must be a singularity image
    if Path(image_name).exists():
        return "singularity"

    # It needs to match a docker tag pattern to be docker
    if re.match(r"(?:.+\/)?([^:]+)(?::.+)?", image_name):
        return "docker"

    raise Exception("Unable to determine the container type of " + image_name)
