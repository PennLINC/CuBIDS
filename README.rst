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

``CuBIDS`` is designed to facilitate reproducible curation––checking and fixing––of BIDS
datasets. The main features of this software are

  1. Ensuring data is valid BIDS.
  2. Visualizing metadata heterogenaity present in a BIDS dataset
  3. Providing a platform for quality checking a datasets's metadata
  4. Test preprocessing pipelines on an example of each unique set of scanning parameters

.. image:: https://github.com/PennBBL/CuBIDS/raw/master/docs/_static/cubids_workflow.png

.. _preprocessing_def:

Validation
~~~~~~~~~~~~~~~

CuBIDS wraps the standard BIDS Validator to produce a validation csv 
