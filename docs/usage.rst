==========================================
Commands & Actions
==========================================

Before we implement a ``CuBIDS`` workflow, let's define the terminology
and take a look at some of the commands available in the software.

More definitions
-----------------

.. _keygroup:

Key Group
~~~~~~~~~

A *Key Group* is a unique set of BIDS key-value pairs, excluding identifiers such as
subject and session. For example the files::

    bids-root/sub-1/ses-1/func/sub-1_ses-1_acq-mb_dir-PA_task-rest_bold.nii.gz
    bids-root/sub-1/ses-2/func/sub-1_ses-2_acq-mb_dir_PA_task-rest_bold.nii.gz
    bids-root/sub-2/ses-1/func/sub-2_ses-1_acq-mb_dir-PA_task-rest_bold.nii.gz

Would all share the same Key Group. If these scans were all acquired as a part of the same
study on the same scanner with exactly the same acquisition parameters, this
naming convention would suffice.

However, in large multi-scanner, multi-site, or longitudinal studies where acquisition
parameters change over time, it's possible that the same Key Group could comprise of
scans that differ in important ways.

``CuBIDS`` examines all acquisitions within a Key Group to see if there are any images
that differ in a set of important acquisition parameters. The subsets of consistent
acquisition parameter sets within a Key Group are called a :ref:`paramgroup`.


.. _paramgroup:

Parameter Group
~~~~~~~~~~~~~~~

Even though two images may belong to the same Key Group and are valid BIDS, they
may have images with different acquisition parameters. There is nothing fundamentally
wrong with this — the ``bids-validator`` will often simply flag these differences,
with a ``Warning``, but not necessarily suggest changes. That being said,
there can be detrimental consequences downstream if the different parameters cause the
same preprocessing pipelines to configure differently to images of the same Key Group.


.. _acquisitiongroup:

Acquisition Group
~~~~~~~~~~~~~~~~~~

We define an “Acquisition Group” as a collection of sessions across participants that contain the exact 
same set of Key and Parameter Groups. Since Key Groups are based on the BIDS filenames—and therefore both 
modality and acquisition specific—each BIDS session directory contains images that belong to a set of 
Parameter Groups. CuBIDS assigns each session––or set of Parameter Groups––to an Acquisition Group 
such that all sessions in an Acquisition Group possesses an identical set of scan acquisitions and 
metadata parameters across all image modalities present in the dataset. We find Acquisition Groups to be 
a particularly useful categorization of BIDS data, as they identify homogeneous sets of sessions (not 
individual scans) in a large dataset. They are also useful for expediting the testing of pipelines; if a 
BIDS App runs successfully on a single subject from each Acquisition Group, one can be confident that it 
will handle all combinations of scanning parameters in the entire dataset.

.. _summaryfile:

The ``_summary.csv`` File
~~~~~~~~~~~~~~~~~~~~~~~~~

This file contains all the detected Key Groups and Parameter Groups. It provides
an opportunity to evaluate your data and decide how to handle heterogeneity.

Below is an example ``_summary.csv`` of the run-1 DWI Key Group in the PNC [#f1]_. This
reflects the original data that has been converted to BIDS using a heuristic. It is
similar to what you will see when you first use this functionality:

.. csv-table:: Pre Apply Groupings
    :file: _static/PNC_pre_apply_summary_dwi_run1.csv
    :widths: 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 3
    :header-rows: 1


.. _filelistfile:

The ``_files.csv`` file
~~~~~~~~~~~~~~~~~~~~~~~~~

This file contains one row per imaging file in the BIDS directory. You won't need to edit this file
directly, but it keeps track of every file's assignment to Key and Parameter Groups.


.. _acqgroupcsv:

The ``_AcqGrouping.csv`` file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``_AcqGrouping.csv`` file organizes the dataset by session and tags each one with its Acquisition Group number.

.. _acqgrouptxt:

The ``_AcqGroupInfo.txt`` file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``_AcqGroupInfo.txt`` file lists all Key Groups that belong to a given Acquisition Group along with \
the number of sessions each group possesses.

Visualizing and summarizing metadata heterogenaity
----------------------------------------------------

Use ``cubids-group`` to generate your dataset's Key Groups and Parameter Groups:

.. code-block:: console

    $ cubids-group FULL/PATH/TO/BIDS/DIR FULL/PATH/TO/v0

This will output four files, including the summary and files CSVs described above, 
prefixed by the second argument ``v0``.

Appplying changes 
------------------

The ``cubids-apply`` program provides an easy way for users to manipulate their datasets. 
Specifically, ``cubids-apply`` can rename files according to the users’ specification in a tracked 
and organized way. Here, the summary.csv functions as an interface modifications; users can mark 
``Parameter Groups`` they want to rename (or delete) in a dedicated column of the summary.csv and 
pass that edited CSV as an argument to ``cubids-apply``.

Detecting Variant Groups
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Additionally, cubids-apply can automatically rename files in ``Variant Groups`` based on their 
scanning parameters that vary from those in their Key Groups’ Dominant Parameter Groups. Renaming 
is automatically suggested when the summary.csv is generated from a cubids-group run, with the suggested 
new name listed in the CSV’s “Rename Key Group” column. CuBIDS populates this column for all Variant 
Groups—e.g., every Parameter Group except the Dominant one. Specifically, CuBIDS will suggest renaming 
all non-dominant Parameter Group to include VARIANT* in their acquisition field where * is the reason 
the Parameter Group varies from the Dominant Group. For example, when CuBIDS encounters a Parameter 
Group with a repetition time that varies from the one present in the Dominant Group, it will automatically 
suggest renaming all scans in that Variant Group to include ``acquisition-VARIANTRepetitionTime`` in thier 
filenames. When the user runs ``cubids-apply``, filenames will get renamed according to the auto-generated 
names in the “Rename Key Group” column in the summary.csv

Deleting a mistake
~~~~~~~~~~~~~~~~~~~~~~

To remove files in a Parameter Group from your BIDS data, you simply set the ``MergeInto`` value
to ``0``. We see in our data that there is a strange scan that has a ``RepetitionTime`` of 12.3
seconds and is also variant with respect to EffectiveEchoSpacing and EchoTime. We elect to remove this scan from 
our dataset becasuse we do not want these parameters to affect our analyses.
To remove these files from your BIDS data, add a ``0`` to ``MergeInto`` and save the new CSV as ``v0_edited_summary.csv``

.. csv-table:: Pre Apply Groupings with Deletion Requested
    :file: _static/PNC_pre_apply_summary_dwi_run1_deletion.csv
    :widths: 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 3
    :header-rows: 1

In this example, users can apply the changes to BIDS data using the following command:

.. code-block:: console

    $ cubids-apply FULL/PATH/TO/BIDS/DIR FULL/PATH/TO/v0_edited_summary.csv FULL/PATH/TO/v0_files.csv FULL/PATH/TO/v1

The changes in ``v0_edited_summary.csv`` will be applied to the BIDS data
and the new Key and Parameter Groups will be saved to csv files starting with ``v1``.

Applying these changes we would see:

.. csv-table:: Post Apply Groupings
    :file: _static/PNC_post_apply_summary.csv
    :widths: 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 3
    :header-rows: 1
    
	
Command line tools
-------------------

With that brief introduction done, we can introduce the full gamut
of ``CuBIDS`` command line tools:

.. autofunction:: cubids.cli.cubids_add_nifti_info
.. autofunction:: cubids.cli.cubids_apply
.. autofunction:: cubids.cli.cubids_copy_exemplars
.. autofunction:: cubids.cli.cubids_datalad_save
.. autofunction:: cubids.cli.cubids_group
.. autofunction:: cubids.cli.cubids_print_metadata_fields
.. autofunction:: cubids.cli.cubids_purge
.. autofunction:: cubids.cli.cubids_remove_metadata_fields
.. autofunction:: cubids.cli.cubids_undo
.. autofunction:: cubids.cli.cubids_validate


Customizable configuration
---------------------------
``CuBIDS`` also features an optional, customizable, modality-specific configuration file. 
This file can be passed as an argument to cubids-group and cubids-apply using the ``–-config`` flag 
and allows users to customize grouping settings based on modality and parameter. Each ``Key Group`` 
is associated with one (and only one) modality, as BIDS filenames include modality-specific values 
as their suffixes. This easy-to-modify configuration file provides several benefits to curation. 
First, it allows users to add and remove metadata parameters from the set that determines groupings. 
This can be very useful if a user deems a specific metadata parameter irrelevant and wishes to collapse 
variation based on that parameter into a single Parameter Group. Second, the configuration file allows 
users to apply tolerances for parameters with numerical values. This functionality allows users to avoid 
very small differences in scanning parameters (i.e., a TR of 3.0s vs 3.0001s) being split into different 
``Parameter Groups``. Third, the configuration file allows users to determine which scanning parameters 
are listed in the acquisition field when auto-renaming is applied to ``Variant Groups``.


Exemplar testing
-----------------
In addition to facilitating curation of large, heterogeneous BIDS datasets, ``CuBIDS`` also prepares 
datasets for testing BIDS Apps. This portion of the ``CuBIDS`` workflow relies on the concept of the 
Acquisition Group: a set of sessions that have identical scan types and metadata across all imaging 
modalities present in the session set. Specifically, ``cubids-copy-exemplars`` copies one subject from each 
Acquisition Group into a separate directory, which we call an ``Exemplar Dataset``. Since the ``Exemplar Dataset`` 
contains one randomly selected subject from each unique Acquisition Group in the dataset, it will be a 
valid BIDS dataset that spans the entire metadata parameter space of the full study. If users run 
``cubids-copy-exemplars`` with the ``–-use-datalad`` flag, the program will ensure that the ``Exemplar Dataset`` 
is tracked and saved in ``DataLad``. If the user chooses to forgo this flag, the ``Exemplar Dataset`` 
will be a standard directory located on the filesystem. Once the ``Exemplar Dataset`` has been created, 
a user can test it with a BIDS App (e.g., fMRIPrep or QSIPrep) to ensure that each unique set of scanning 
parameters will pass through the pipelines successfully. Because BIDS Apps auto-configure workflows based 
on the metadata encountered, they will process all scans in each ``Acquisition Group`` in the same way. By 
first verifying that BIDS Apps perform as intended on the small sub-sample of participants present in the 
``Exemplar Dataset`` (that spans the full variation of the metadata), users can confidently move forward 
processing the data of the complete BIDS dataset. 


In the next section, we'll introduce ``DataLad`` and walk through a real example.

.. rubric:: Footnotes

.. [#f1] PNC: `The Philadelphia Developmental Cohort <https://www.med.upenn.edu/bbl/philadelphianeurodevelopmentalcohort.html>`_.