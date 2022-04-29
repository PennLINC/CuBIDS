===============
CuBIDS Workflow
===============

Motivation
-------------

The Brain Imaging Data Structure (BIDS) is a simple and intuitive way to
organize and describe MRI data [#f1]_. Because of its ease of use, a wide array of
preprocessing and analysis tools and pipelines have been developed specifically
to operate on data curated in BIDS [#f2]_. These tools are able to automatically
self-configure to the user's BIDS dataset, which saves time and effort on the
part of the user. However, as datasets increase in size and complexity, it
can be dangerous to blindly run these pipelines without a careful understanding of
what's really in your BIDS data. Having knowledge of this potential **heterogeneity**
ahead of time gives researchers the ability to **predict pipeline configurations**,
**predict potential errors**, avoid running **unwanted or unusable data**, and **budget
their computational time and resources** effectively.

``CuBIDS`` is designed to facilitate the curation of such large, messy imaging data, so
that you can infer useful information from descriptive and accurate BIDS labels
before running pipelines *en masse*.

The big picture
---------------

We find it useful to break up the curation process into 3 stages. These stages are
not necessarily linear, but all three must happen before the ultimate goal: running
all your data through pipelines.

Here we want to

  1. Ensure the data are valid BIDS. This is done using the ``bids-validator`` package.
  2. Detect each :ref:`keygroup` and :ref:`paramgroup` in your BIDS data.
  3. Test pipelines on example data from each :ref:`paramgroup`.


Definitions
-----------

.. _keygroup:

Key Group
~~~~~~~~~

A *Key Group* is a unique set of BIDS key-value pairs exculding identifiers such as
subject and session. For example the files::

    bids-root/sub-1/ses-1/func/sub-1_ses-1_acq-mb_dir-PA_task-rest_bold.nii.gz
    bids-root/sub-1/ses-2/func/sub-1_ses-2_acq-mb_dir_PA_task-rest_bold.nii.gz
    bids-root/sub-2/ses-1/func/sub-2_ses-1_acq-mb_dir-PA_task-rest_bold.nii.gz

all share the same Key Group. If these scans were all acquired as a part of the same
study on the same scanner with exactly the same acquisition parameters, then this
naming convention works perfectly.

However, in multi-scanner, multi-site, or long-running studies where acquisition
parameters change over time, it's possible that the same Key Group will contain
scans that differ in important ways.

``CuBIDS`` examines all acquisitions within a Key Group to see if there are any images
that differ in a set of important acquisition parameters. The subsets of consistent
acquisition parameter sets within a Key Group are called a :ref:`paramgroup`.


.. _paramgroup:

Parameter Group
~~~~~~~~~~~~~~~

Even though two images may belong to the same Key Group and are valid BIDS, they
may have images with different acquisition parameters. There is nothing fundamentally
wrong with this, and normally will result in a warning from the ``bids-validator``,
but there can be big consequences if the different parameters cause different
preprocessing pipelines to be run on images of the same Key Group.


Detecting Key and Parameter Groups
----------------------------------

Given a BIDS directory, the Key Groups and Parameter Groups can be calculated using the
command line interface

.. code-block:: console

    $ cubids-group /bids/dir keyparam_original

This will produce two csv files prefixed by the second argument to ``cubids-group``.
You will find ``keyparam_original_summary.csv`` and ``keyparam_original_files.csv``.
These two files are a snapshot of your current BIDS layout.

The ``_summary.csv`` File
~~~~~~~~~~~~~~~~~~~~~~~~~

This file contains all the detected Key Groups and Parameter Groups. It also provides
an opportunity to evaluate your data to decide whether Key Groups should be merged
or whether a Parameter Group deserves to have its own Key Group (ie adding a unique
identifier to its BIDS name).

Here we look at some example Parameter Groups from the first DWI run in the PNC. This
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



The ``_files.csv`` File
~~~~~~~~~~~~~~~~~~~~~~~~~

This file contains one row per imaging file in the BIDS directory. You won't need to edit this file
directly, but it keeps track of every file's assignment to Key and Parameter Groups.



Modifying Key and Parameter Group Assignments
---------------------------------------------

Sometimes we see that there are important differences in acquisition parameters within a Key Group.
If these differences impact how a pipeline will process the data, it makes sense to assign the scans
in that Parameter Group to a different Key Group (i.e. assign them a different BIDS name). This can
be accomplished by editing the empty columns in the `_summary.csv` file produced by ``cubids-group``.

Once the columns have been edited you can apply the changes to BIDS data using

.. code-block:: console

    $ cubids-apply /bids/dir keyparam_edited new_keyparam_prefix

The changes in ``keyparam_edited_summary.csv`` will be applied to the BIDS data in ``/bids/dir``
and the new Key and Parameter groups will be saved to csv files starting with ``new_keyparam_prefix``.


Moving a Parameter Group to a New Key Group
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Continuing with the example data, we see one Parameter group that will have a very different run
through preprocessing: Parameter Group 6.


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

Dealing with Aberrant Parameter Groups
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Mistakes can happen when scanning and sometimes you will find some scans with different parameters
that you will not want to include in your study. Other times there will be an insignificant difference
where some data is missing from a Parameter Group and you'd like to copy the metadata from another
Parameter Group.

The ``MergeInto`` column can be used for either of these purposes.

Copying Incomplete metadata
^^^^^^^^^^^^^^^^^^^^^^^^^^^

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

This will copy the metadata from Parameter Group 3 into the metadata of Parameter Group 5. If we re-run
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
^^^^^^^^^^^^^^^^^^

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


.. rubric:: Footnotes

.. [#f1] See the `BIDS Specification <https://bids-specification.readthedocs.io>`_.
.. [#f2] See this list of amazing `BIDS apps <https://bids-apps.neuroimaging.io/>`_.