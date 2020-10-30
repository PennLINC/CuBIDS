=============
BOnD Workflow
=============

Curating MRI data using BIDS opens up a world of wonderful pipeline tools
to automatically and correctly preprocess (or more) your data. This software
is designed to help facilitate the BIDS curation of large, messy data so 
that you can be confident that your BIDS labels are descriptive and accurate
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

A *Key Group* is a unique set of BIDS key-value pairs exculding identifiers like 
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

``BOnD`` examines all acquisitions within a Key Group to see if there are any images
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


Use Cases
---------
