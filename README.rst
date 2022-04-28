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
reproducible curation of BIDS datasets. This software includes the following 
functionalities:

  1. Ensures data is valid BIDS.
  2. Visualizes and summarizes the metadata heterogeneity in a BIDS dataset. 
  3. Prepares BIDS data for successful preprocessing pipeline runs.
  4. Helps users perform metadata-based quality control. 

.. image:: docs/_static/cubids_workflow.png


Definitions
------------

Key Group
        * A unique set of BIDS key-value pairs excluding identifiers such as subject and session.
        * Derived from the filename
        * Example structure: ``acquisition-*_datatype-*_run-*_task-*_suffix`` 
        * Within a key group, all scanning parameters are expected to be identical

Parameter (Param) Group
        * The set of scans with identical critical imaging parameters. 
        * Defined within a Key Group
        * Numerically identified (e.g. 1, 2, etc.)
        * These parameters affect how BIDS Apps will configure their pipelines (e.g. fieldmap availability, multiband factor, etc).

Dominant Group
        * The Param Group that contains the highest number of scans in its Key Group

Variant Group
        * Any Param Group that is non-dominant (>1)

Rename Key Group
        * The new Key Group name CuBIDS will assign to a non-dominant Param Group 
        * CuBIDS will suggest renaming any non-dominant Param Group to include VARIANT* in the acquisition field where * is reason the Param Group varies from the dominant
        * e.g. ``acquisition-VARIANTRepetitionTime``  
        * When ``cubids-apply`` is run, filenames will get renamed according to the auto-generated rename group.
        * In other words, ``cubids-apply`` adds information about a scan’s variant metadata to the acquisition field of it’s BIDS filename

Example 1
        * Filename: ``sub-01_ses-A_task-rest_acq-singleband_bold.nii.gz``
        * Key Group: ``acquisition-singleband_datatype-func_suffix-bold_task-rest``
        * Param Group: ``1`` (Dominaint Group)

Example 2
        * Filename: ``sub-02_ses-A_task-rest_acq-singleband_bold.nii.gz``
        * Key Group: ``acquisition-singleband_datatype-func_suffix-bold_task-rest``
        * Param Group: ``2`` (Variant Group)
        * Rename Key Group: ``acquisition-singlebandVARIANTNoFmap_datatype-func_suffix-bold_task-rest``

