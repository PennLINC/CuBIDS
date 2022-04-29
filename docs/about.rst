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
reproducible curation of BIDS datasets. This software helps users:

  1. Ensure data is BIDS-valid;
  2. Visualize and summarize heterogeneity of metadata in a BIDS dataset;
  3. Flexibly tailor heterogenous BIDS data for preprocessing pipeline runs;
  4. Perform metadata-based quality control.

.. image:: cubids_workflow.png
   :width: 600


Definitions
------------

Key Group
"""""""""

        * A unique set of `BIDS key-value pairs <https://bids-specification.readthedocs.io/en/stable/02-common-principles.html#file-name-structure>`_ , excluding the subject and session keys.
        * Derived from the filename
        * Example structure: ``acquisition-*_datatype-*_run-*_task-*_suffix`` 

Within a key group, all scanning parameters are expected to be identical.

Parameter (Param) Group
"""""""""""""""""""""""

        * The set of scans with identical critical imaging parameters. 
        * Defined within a Key Group
        * Numerically identified (e.g. 1, 2, etc.)

These parameters affect how BIDS Apps will configure their pipelines (e.g. fieldmap availability, multiband factor, etc).

Dominant Group
""""""""""""""
        * The Param Group that contains the highest number of scans in its Key Group.

Variant Group
"""""""""""""
        * Any Param Group that is non-dominant.

Rename Key Group
""""""""""""""""
        * Recommended new Key Group name for variant Param Group 

CuBIDS will suggest renaming any non-dominant Param Group to include ``VARIANT*`` in the acquisition field, where ``*`` is reason the Param Group varies from the dominant.
When ``cubids-apply`` is run, filenames will get renamed according to this auto-generated rename group.
In doing so, ``cubids-apply`` adds important information about a scan's variant metadata to the acquisition field of it's BIDS filename.

Examples
""""""""

A dominant resting state BOLD group:
        * Example Filename: ``sub-01_ses-A_task-rest_acq-singleband_bold.nii.gz``
        * Key Group: ``acquisition-singleband_datatype-func_suffix-bold_task-rest``
        * Param Group: ``1`` (Dominaint Group)

A variant resting state BOLD group
        * Example Filename: ``sub-02_ses-A_task-rest_acq-singleband_bold.nii.gz``
        * Key Group: ``acquisition-singleband_datatype-func_suffix-bold_task-rest``
        * Param Group: ``2`` (Variant Group)
        * Rename Key Group: ``acquisition-singlebandVARIANTNoFmap_datatype-func_suffix-bold_task-rest``

