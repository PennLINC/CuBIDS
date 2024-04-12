========================
CuBIDS: Curation of BIDS
========================

.. image:: https://img.shields.io/pypi/v/cubids.svg
    :target: https://pypi.python.org/pypi/cubids
    :alt: Latest Version

.. image:: https://img.shields.io/badge/Source%20Code-pennlinc%2Fcubids-purple
   :target: https://github.com/PennLINC/CuBIDS
   :alt: GitHub Repository

.. image:: https://readthedocs.org/projects/cubids/badge/?version=latest
    :target: https://cubids.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. image:: https://circleci.com/gh/PennLINC/CuBIDS.svg?style=svg
    :target: https://circleci.com/gh/PennLINC/CuBIDS
    :alt: Test Status

.. image:: https://codecov.io/gh/PennLINC/CuBIDS/branch/main/graph/badge.svg
   :target: https://app.codecov.io/gh/PennLINC/CuBIDS/tree/main
   :alt: Codecov

.. image:: https://img.shields.io/badge/NeuroImage-10.1016%2Fj.neuroimage.2022.119609-purple
   :target: https://doi.org/10.1016/j.neuroimage.2022.119609
   :alt: Publication DOI

.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.6514881.svg
   :target: https://doi.org/10.5281/zenodo.6514881
   :alt: Zenodo DOI

.. image:: https://img.shields.io/badge/License-MIT-green
   :target: https://opensource.org/licenses/MIT
   :alt: License


About
-----

``CuBIDS`` (Curation of BIDS) is a workflow and software package designed to facilitate
reproducible curation of neuroimaging `BIDS <https://bids-specification.readthedocs.io/>`_ datasets.
CuBIDS breaks down BIDS dataset curation into four main components and addresses each one using
various command line programs complete with version control capabilities.
These components are not necessarily linear but all are critical
in the process of preparing BIDS data for successful preprocessing and analysis pipeline runs.

  1.    CuBIDS facilitates the validation of BIDS data.
  2.    CuBIDS visualizes and summarizes the heterogeneity in a BIDS dataset.
  3.    CuBIDS helps users test pipelines on the entire parameter space of a BIDS dataset.
  4.    CuBIDS allows users to perform metadata-based quality control on their BIDS data.
  5.    CuBIDS helps users clean protected information in BIDS datasets,
        in order to prepare them for public sharing.

.. image:: https://github.com/PennLINC/CuBIDS/raw/main/docs/_static/cubids_workflow.png
   :width: 600

For full documentation, please visit our
`ReadTheDocs <https://cubids.readthedocs.io/en/latest/?badge=latest>`_.


Citing CuBIDS
-------------

If you use CuBIDS in your research, please cite the following paper:

    Covitz, S., Tapera, T. M., Adebimpe, A., Alexander-Bloch, A. F., Bertolero, M. A., Feczko, E.,
    ... & Satterthwaite, T. D. (2022).
    Curation of BIDS (CuBIDS): A workflow and software package for streamlining reproducible curation of large BIDS datasets.
    NeuroImage, 263, 119609.
    doi:10.1016/j.neuroimage.2022.119609.

Please also cite the Zenodo DOI for the version you used.
