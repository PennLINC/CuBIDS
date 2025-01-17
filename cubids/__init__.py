"""Top-level package for CuBIDS.

This module initializes the CuBIDS package and imports its main submodules and attributes.

Submodules
----------
cli : module
    Command-line interface for CuBIDS.
config : module
    Configuration utilities for CuBIDS.
constants : module
    Constants used throughout the CuBIDS package.
cubids : module
    Core functionalities of the CuBIDS package.
metadata_merge : module
    Utilities for merging metadata in CuBIDS.
utils : module
    Utility functions for CuBIDS.
validator : module
    Validation utilities for CuBIDS.
workflows : module
    Workflows for CuBIDS operations.

Attributes
----------
__version__ : str
    The version of the CuBIDS package.
__packagename__ : str
    The name of the CuBIDS package.
__copyright__ : str
    The copyright information for the CuBIDS package.
__credits__ : str
    The credits for the CuBIDS package.
"""

from cubids import (
    cli,
    config,
    constants,
    cubids,
    metadata_merge,
    utils,
    validator,
    workflows,
)
from cubids.__about__ import __copyright__, __credits__, __packagename__, __version__

__all__ = [
    "__copyright__",
    "__credits__",
    "__packagename__",
    "__version__",
    "cli",
    "config",
    "constants",
    "cubids",
    "metadata_merge",
    "utils",
    "validator",
    "workflows",
]
