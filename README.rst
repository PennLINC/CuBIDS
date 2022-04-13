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

``CuBIDS`` is designed to facilitate the curation and sanity-checking of BIDS
datasets that live on a hard drive. Its has many functions that help curators
follow the Three Steps of Curation. These steps are


  1. Ensure the data is valid BIDS.
  2. Detect potentially multiple *parameter groups* within *key groups*
  3. Test preprocessing pipelines on an example of each *parameter group*.


Step 1: Ensure the data is valid BIDS
-------------------------------------

The CuBIDS class has a call to a containerized version of the BIDS Validator. The
output of the BIDS validator is collected and converted to a convenient Python object.
