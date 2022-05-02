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

``CuBIDS`` is a workflow and software package designed to facilitate
reproducible curation of `BIDS <https://bids-specification.readthedocs.io/>`_ datasets.
We find it useful to break up the BIDS Dataset Curation process into four components. These components are
not necessarily linear, but all three must happen before running your data successfully through 
preprocessing pipelines and evenutally being able to use it for analyses.

  1. CuBIDS is a workflow and software package for curating BIDS data.
  2. CuBIDS summarizes the heterogeneity in a BIDS dataset. 
  3. CuBIDS prepares BIDS data for successful preprocessing pipeline runs.
  4. CuBIDS helps users perform metadata-based quality control. 

.. image:: _static/cubids_workflow.png
   :width: 600