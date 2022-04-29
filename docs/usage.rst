==========================================
Component Definitions, Commands, & Actions
==========================================

Before we implement a ``CuBIDS`` workflow, let's define the terminology
and take a look at some of the commands available in the software.

Definitions
-----------

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

.. _summaryfile:

The ``_summary.csv`` File
~~~~~~~~~~~~~~~~~~~~~~~~~

This file contains all the detected Key Groups and Parameter Groups. It provides
an opportunity to evaluate your data and decide how to handle heterogeneity. Key Groups
can be merged together, for example, or Parameter Groups can be extracted to their own Key Group.

Below is an example ``_summary.csv`` from the first DWI run in the PNC [#f1]_. This
reflects the original data that has been converted to BIDS using a heuristic. It is
similar to what you will see when you first use this functionality:


.. csv-table:: Parameter Group Summary Table
    :align: center
    :header: "Rename KeyGroup","Merge Into","KeyGroup","Param Group",Counts,"Fieldmap Key00","N Slice Times","Repetition Time"

    ,,datatype-dwi_run-1_suffix-dwi,1,1361,datatype-fmap_fmap-phase1_suffix-phase1,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,2,1,datatype-fmap_fmap-phase1_suffix-phase1,70,8.4
    ,,datatype-dwi_run-1_suffix-dwi,3,15,datatype-fmap_fmap-phasediff_suffix-phasediff,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,4,1,datatype-fmap_fmap-phase1_suffix-phase1,70,9
    ,,datatype-dwi_run-1_suffix-dwi,5,2,datatype-fmap_fmap-phasediff_suffix-phasediff,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,6,16,,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,7,2,datatype-fmap_fmap-phase1_suffix-phase1,46,8.1
    ,,datatype-dwi_run-1_suffix-dwi,8,1,datatype-fmap_fmap-phase1_suffix-phase1,70,12.3


.. _filelistfile:

The ``_files.csv`` File
~~~~~~~~~~~~~~~~~~~~~~~~~

This file contains one row per imaging file in the BIDS directory. You won't need to edit this file
directly, but it keeps track of every file's assignment to Key and Parameter Groups.

Commands & Actions
------------------

Group with the CLI
~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``cubids-group`` to generate your Key Groups and Parameter Groups:

.. code-block:: console

    $ cubids-group /bids/dir keyparam_original

This will output the two files above, prefixed by the second argument ``keyparam_original``.

Modifying Key and Parameter Group Assignments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If there are heterogenous Parameter groups within Key Groups, it may impact
how a pipeline will process the data. It makes sense to assign the scans
in these Parameter Groups to a different Key Group by assign them a new, unique
BIDS name. ``CuBIDS`` will automatically suggest appropriate BIDS-valid
names, but if you would like to modify or insert your own, this can be
accomplished by editing the ``RenameKeyGroup`` column in the `_summary.csv` file.

Apply Your Modifications with the CLI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once the column has been edited you can apply the changes to BIDS data using:

.. code-block:: console

    $ cubids-apply /bids/dir keyparam_edited_summary.csv new_keyparam_prefix

The changes in ``keyparam_edited_summary.csv`` will be applied to the BIDS data in ``/bids/dir``
and the new Key and Parameter groups will be saved to csv files starting with ``new_keyparam_prefix``.

Continuing with the example data, we see one Parameter group that will have a very different run
through preprocessing: Parameter Group 6:


.. csv-table:: Assign a New Key Group
    :align: center
    :header: "Rename KeyGroup","Merge Into","KeyGroup","Param Group",Counts,"Fieldmap Key00","N Slice Times","Repetition Time"

    ,,datatype-dwi_run-1_suffix-dwi,1,1361,datatype-fmap_fmap-phase1_suffix-phase1,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,2,1,datatype-fmap_fmap-phase1_suffix-phase1,70,8.4
    ,,datatype-dwi_run-1_suffix-dwi,3,15,datatype-fmap_fmap-phasediff_suffix-phasediff,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,4,1,datatype-fmap_fmap-phase1_suffix-phase1,70,9
    ,,datatype-dwi_run-1_suffix-dwi,5,2,datatype-fmap_fmap-phasediff_suffix-phasediff,70,8.1
    acquisition-NoSDC_datatype-dwi_run-1_suffix-dwi,,datatype-dwi_run-1_suffix-dwi,6,16,,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,7,2,datatype-fmap_fmap-phase1_suffix-phase1,46,8.1
    ,,datatype-dwi_run-1_suffix-dwi,8,1,datatype-fmap_fmap-phase1_suffix-phase1,70,12.3

By adding a value to the ``RenameKeyGroup`` column, all files in Parameter Group 6 will be renamed to match
that value. After being applied, there will be new Key Groups and Parameter Groups:

.. csv-table:: New Key Group Assigned
    :align: center
    :header: "Rename KeyGroup","Merge Into","KeyGroup","Param Group",Counts,"Fieldmap Key00","N Slice Times","Repetition Time"

    ,,datatype-dwi_run-1_suffix-dwi,1,1361,datatype-fmap_fmap-phase1_suffix-phase1,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,2,1,datatype-fmap_fmap-phase1_suffix-phase1,70,8.4
    ,,datatype-dwi_run-1_suffix-dwi,3,15,datatype-fmap_fmap-phasediff_suffix-phasediff,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,4,1,datatype-fmap_fmap-phase1_suffix-phase1,70,9
    ,,datatype-dwi_run-1_suffix-dwi,5,2,datatype-fmap_fmap-phasediff_suffix-phasediff,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,6,2,datatype-fmap_fmap-phase1_suffix-phase1,46,8.1
    ,,datatype-dwi_run-1_suffix-dwi,7,1,datatype-fmap_fmap-phase1_suffix-phase1,70,12.3
    ,,acquisition-NoSDC_datatype-dwi_run-1_suffix-dwi,1,16,,70,8.1

This way, we will know that any outputs with ``acq-NoSDC`` will not have had fieldmap-based distortion
correction applied.

Merge Parameter Groups
~~~~~~~~~~~~~~~~~~~~~~

Mistakes can happen when scanning and sometimes you will find some scans with different parameters
that you will not want to include in your study. Other times there will be an insignificant difference
where some data is missing from a Parameter Group and you'd like to copy the metadata from another
Parameter Group. The ``MergeInto`` column can be used for either of these purposes.

In the example data we see that Parameter Group 5 appears to be identical to Parameter Group 3.
The reason these were separated was because ``DwellTime`` was not included in the metadata for
Group 5. Since we collected the data and know that the protocol was identical for the scans in
Group 5, we can add ``3`` to the ``MergeInto`` column for Patameter Group 5.

.. csv-table:: Merge Parameter Groups
    :align: center
    :header: "Rename KeyGroup","Merge Into","KeyGroup","Param Group",Counts,"Fieldmap Key00","N Slice Times","Repetition Time"

    ,,datatype-dwi_run-1_suffix-dwi,1,1361,datatype-fmap_fmap-phase1_suffix-phase1,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,2,1,datatype-fmap_fmap-phase1_suffix-phase1,70,8.4
    ,,datatype-dwi_run-1_suffix-dwi,3,15,datatype-fmap_fmap-phasediff_suffix-phasediff,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,4,1,datatype-fmap_fmap-phase1_suffix-phase1,70,9
    ,3,datatype-dwi_run-1_suffix-dwi,5,2,datatype-fmap_fmap-phasediff_suffix-phasediff,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,6,16,,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,7,2,datatype-fmap_fmap-phase1_suffix-phase1,46,8.1
    ,,datatype-dwi_run-1_suffix-dwi,8,1,datatype-fmap_fmap-phase1_suffix-phase1,70,12.3

This will copy the metadata from Parameter Group 3 into the metadata of Parameter Group 5, such
that all the JSON sidecars belonging to files in Parameter Group 5 will have their scanning parameter data
overwritten to be identical to Parameter Group 3. If we re-run
the grouping function after these changes are applied, we should see something like:

.. csv-table:: Merge Parameter Groups
    :align: center
    :header: "Rename KeyGroup","Merge Into","KeyGroup","Param Group",Counts,"Fieldmap Key00","N Slice Times","Repetition Time"

    ,,datatype-dwi_run-1_suffix-dwi,1,1361,datatype-fmap_fmap-phase1_suffix-phase1,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,2,1,datatype-fmap_fmap-phase1_suffix-phase1,70,8.4
    ,,datatype-dwi_run-1_suffix-dwi,3,17,datatype-fmap_fmap-phasediff_suffix-phasediff,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,4,1,datatype-fmap_fmap-phase1_suffix-phase1,70,9
    ,,datatype-dwi_run-1_suffix-dwi,5,16,,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,6,2,datatype-fmap_fmap-phase1_suffix-phase1,46,8.1
    ,,datatype-dwi_run-1_suffix-dwi,7,1,datatype-fmap_fmap-phase1_suffix-phase1,70,12.3

The 2 scans from the former group 5 are now included in the count of Group 3.

Deleting a Mistake
~~~~~~~~~~~~~~~~~~~~~~

To remove files in a Parameter Group from your BIDS data, you simply set the ``MergeInto`` value
to ``0``. We see in our data that there is a strange scan that has a ``RepetitionTime`` of 12.3
seconds (Group 8) and a scan that has only 46 slices (Group 7). These scanning parameters are
different enough from all the other scans that it would be irresponsible to include them in
any final analysis. To remove these files from your BIDS data, add a ``0`` to ``MergeInto``:

.. csv-table:: Merge Parameter Groups
    :align: center
    :header: "Rename KeyGroup","Merge Into","KeyGroup","Param Group",Counts,"Fieldmap Key00","N Slice Times","Repetition Time"

    ,,datatype-dwi_run-1_suffix-dwi,1,1361,datatype-fmap_fmap-phase1_suffix-phase1,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,2,1,datatype-fmap_fmap-phase1_suffix-phase1,70,8.4
    ,,datatype-dwi_run-1_suffix-dwi,3,15,datatype-fmap_fmap-phasediff_suffix-phasediff,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,4,1,datatype-fmap_fmap-phase1_suffix-phase1,70,9
    ,,datatype-dwi_run-1_suffix-dwi,5,2,datatype-fmap_fmap-phasediff_suffix-phasediff,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,6,16,,70,8.1
    ,0,datatype-dwi_run-1_suffix-dwi,7,2,datatype-fmap_fmap-phase1_suffix-phase1,46,8.1
    ,0,datatype-dwi_run-1_suffix-dwi,8,1,datatype-fmap_fmap-phase1_suffix-phase1,70,12.3

Applying these changes we would see:

.. csv-table:: Merge Parameter Groups
    :align: center
    :header: "Rename KeyGroup","Merge Into","KeyGroup","Param Group",Counts,"Fieldmap Key00","N Slice Times","Repetition Time"

    ,,datatype-dwi_run-1_suffix-dwi,1,1361,datatype-fmap_fmap-phase1_suffix-phase1,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,2,1,datatype-fmap_fmap-phase1_suffix-phase1,70,8.4
    ,,datatype-dwi_run-1_suffix-dwi,3,15,datatype-fmap_fmap-phasediff_suffix-phasediff,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,4,1,datatype-fmap_fmap-phase1_suffix-phase1,70,9
    ,,datatype-dwi_run-1_suffix-dwi,5,2,datatype-fmap_fmap-phasediff_suffix-phasediff,70,8.1
    ,,datatype-dwi_run-1_suffix-dwi,6,16,,70,8.1


Command Line Tools
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



The Big Picture
---------------

We find it useful to break up the curation process into 3 stages. These stages are
not necessarily linear, but all three must happen before the ultimate goal: running
all your data through pipelines.

  1. Ensure the data are valid BIDS. This is done using the ``bids-validator`` package.
  2. Detect each :ref:`keygroup` and :ref:`paramgroup` in your BIDS data and modify as necessary.
  3. Test pipelines on example data from each :ref:`paramgroup`.

Recall the schematic:

.. image:: _static/cubids_workflow.png

In the next section, we'll introduce ``datalad`` and walk through a real example.

.. rubric:: Footnotes

.. [#f1] PNC: `The Philadelphia Developmental Cohort <https://www.med.upenn.edu/bbl/philadelphianeurodevelopmentalcohort.html>`_.