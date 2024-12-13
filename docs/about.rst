==========
Background
==========

Motivation
----------

The Brain Imaging Data Structure (BIDS) is a simple and intuitive way to
organize and describe MRI data [#f1]_.
Because of its ease of use, a wide array of preprocessing and analysis tools and
pipelines have been developed specifically to operate on data curated in BIDS [#f2]_.
These tools are able to automatically self-configure to the user's BIDS dataset,
which saves time and effort on the part of the user.

However, as datasets increase in size and complexity,
it can be dangerous to blindly run these pipelines without a careful understanding of
what's really in your BIDS data.
Having knowledge of this potential **heterogeneity** ahead of time gives researchers
the ability to **predict pipeline configurations**, **predict potential errors**,
avoid running **unwanted or unusable data**,
and **budget their computational time and resources** effectively.

``CuBIDS`` is designed to facilitate the curation of large,
neuroimaging datasets so that users can infer useful information from descriptive and
accurate BIDS labels before running pipelines *en masse*.
``CuBIDS`` accomplishes this by summarizing BIDS data using :ref:`entityset`,
:ref:`paramgroup`, and :ref:`acquisitiongroup` categorizations in your data
(we'll explain what these are in more detail in the next section).

The image below demonstrates the ``CuBIDS`` workflow that we'll discuss on the next page.

.. image:: _static/cubids_workflow.png
   :width: 600

``CuBIDS`` also incorporates ``DataLad`` as an optional dependency for maintaining data provenance,
enhancing reproducibility, and supporting collaboration [#f3]_.


What CuBIDS Is Not
------------------

``CuBIDS`` is not designed to convert raw data into BIDS format.
For that, we recommend using `conversion tools <https://bids.neuroimaging.io/benefits.html#converters>`_.
``CuBIDS`` then takes over once you have a valid BIDS dataset,
prior to running any preprocessing or analysis pipelines, or to sharing the dataset.

.. note::

    CuBIDS _should_ work on BIDS-ish (not quite BIDS compliant, but in a similar format) datasets,
    but this is by no means guaranteed.


Examples
""""""""

Dominant Group resting state BOLD:

    *   Example Filename: ``sub-01_ses-A_task-rest_acq-singleband_bold.nii.gz``
    *   Entity Set: ``acquisition-singleband_datatype-func_suffix-bold_task-rest``
    *   Param Group: ``1`` (Dominant Group)

Variant Group resting state BOLD (all scans in this Param Group are missing a fieldmap)

    *   Example Filename: ``sub-02_ses-A_task-rest_acq-singleband_bold.nii.gz``
    *   Entity Set: ``acquisition-singleband_datatype-func_suffix-bold_task-rest``
    *   Param Group: ``2`` (Variant Group)
    *   Rename Entity Set: ``acquisition-singlebandVARIANTNoFmap_datatype-func_suffix-bold_task-rest``

These definitions are described in more detail in :doc:`glossary` and :doc:`usage`.

.. rubric:: Footnotes

.. [#f1] See the `BIDS Specification <https://bids-specification.readthedocs.io>`_.
.. [#f2] See this list of amazing `BIDS apps <https://bids-apps.neuroimaging.io/>`_.
.. [#f3] See `DataLad <https://www.datalad.org/>`_.
