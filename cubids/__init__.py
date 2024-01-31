"""Top-level package for CuBIDS."""

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
from cubids.cubids import CuBIDS

__all__ = [
    "__copyright__",
    "__credits__",
    "__packagename__",
    "__version__",
    "CuBIDS",
    "cli",
    "config",
    "constants",
    "cubids",
    "metadata_merge",
    "utils",
    "validator",
    "workflows",
]
