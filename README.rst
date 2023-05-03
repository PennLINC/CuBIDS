========================
CuBIDS: Curation of BIDS
========================


.. image:: https://img.shields.io/pypi/v/cubids.svg
        :target: https://pypi.python.org/pypi/cubids

.. image:: https://circleci.com/gh/PennLINC/CuBIDS.svg?style=svg
        :target: https://circleci.com/gh/PennLINC/CuBIDS

.. image:: https://readthedocs.org/projects/cubids/badge/?version=latest
        :target: https://cubids.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

About
-----

Curation of BIDS, or ``CuBIDS``, is a workflow and software package designed to facilitate
reproducible curation of neuroimaging `BIDS <https://bids-specification.readthedocs.io/>`_ datasets.
CuBIDS breaks down BIDS dataset curation into four main components and addresses each one using 
various command line programs complete with version control capabilities. These components are not necessarily linear but all are critical 
in the process of preparing BIDS data for successful preprocessing and analysis pipeline runs. 

  1. CuBIDS facilitates the validation of BIDS data.
  2. CuBIDS visualizes and summarizes the heterogeneity in a BIDS dataset. 
  3. CuBIDS helps users test pipelines on the entire parameter space of a BIDS dataset.
  4. CuBIDS allows users to perform metadata-based quality control on their BIDS data.

.. image:: https://github.com/PennLINC/CuBIDS/raw/main/docs/_static/cubids_workflow.png
   :width: 600

For full documentation, please visit our `ReadTheDocs <https://cubids.readthedocs.io/en/latest/?badge=latest>`_ 