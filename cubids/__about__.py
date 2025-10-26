# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Base module variables for CuBIDS.

This module defines the base variables for the CuBIDS package, including version,
package name, copyright, credits, and URLs.

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
__url__ : str
    The URL for the CuBIDS package repository.
DOWNLOAD_URL : str
    The URL to download the CuBIDS package.
"""

try:
    from cubids._version import __version__
except ImportError:
    __version__ = "0+unknown"

__packagename__ = "CuBIDS"
__copyright__ = "Copyright 2023, The CuBIDS Developers"
__credits__ = (
    "Contributors: please check the ``.zenodo.json`` file at the top-level folder "
    "of the repository."
)
__url__ = "https://github.com/PennLINC/CuBIDS"

DOWNLOAD_URL = (
    f"https://github.com/PennLINC/{__packagename__}/archive/{__version__}.tar.gz"
)
