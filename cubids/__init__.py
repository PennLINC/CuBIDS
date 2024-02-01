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
