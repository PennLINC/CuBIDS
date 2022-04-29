=================
Full Walkthrough
=================

The CuBIDS workflow is currently being used in neuroimaging labs at a number of institutions 
including University of Pennsylvania, Children’s Hospital of Philadelphia, Child Mind Institute, 
and University of Minnesota’s Masonic Institute for the Developing Brain. The following walkthrough 
displays the process of curating a dataset using CuBIDS. To do so, we use an example dataset that is 
bundled with the software and can be found at https://github.com/PennLINC/CuBIDS/tree/main/cubids/testdata/BIDS_Dataset 


We have installed CuBIDS, DataLad, and the bids-validator inside a conda environment titled “test-env.” In this 
example, we use the bids-validator version 1.7.2. Using a different version of the validator may result in 
slightly different validation csv printouts. Throughout this example, we use DataLad for version 
control. 

Although DataLad is an optional dependency of CuBIDS, we use it in this example to demonstrate the 
version control curation capabilities of CuBIDS. For the purposes of this walkthrough, the path to this 
example dataset is ``~/BIDS_Dataset``


Identifying and removing PHI 
------------------------------------------

As a first step, we use CuBIDS to identify the metadata fields present in the dataset. 
This is accomplished with the following command:

.. code-block:: console

    $ cubids-print-metadata-fields ~/BIDS_Dataset

This command returns a total of 66 fields, including acquisition parameters and other metadata 
fields present in the dataset’s JSON sidecars. Some of these fields contain simulated protected 
health information (PHI) such as PatientName that we wish to remove. Completing this step prior 
to checking the BIDS dataset into DataLad is critical, as we must ensure PHI is not tracked as 
part of version control. To remove the PatientName field from the sidecars, we can use the command:

.. code-block:: console

    $ cubids-remove-metadata-fields ~/BIDS_Dataset –fields PatientName


Checking the BIDS dataset into DataLad
-------------------------------------------
Now that all PHI has been removed from the metadata, we are ready to check our dataset into DataLad. 
To do this, we run the following command:

.. code-block:: console

    $ datalad create -c text2git ~/BIDS_Dataset_Datalad

The creation of our DataLad dataset will be accordingly reflected in the dataset’s version control 
history, or “git log.” At any point in the CuBIDS workflow, we can view a summary of our dataset’s 
version history by running the following commands: 

.. code-block:: console 

    $ cd ~/CuBIDS_Test/BIDS_Dataset_DataLad
    $ git log --oneline

This command will write the following to the terminal: 

.. image:: _static/screenshot_1.png

Next, we copy the contents of our BIDS dataset into the newly created and currently empty DataLad 
dataset and save the changes. 

.. code-block:: console

    $ cp -r ~/BIDS_Dataset/* ~/BIDS_Dataset_Datalad

In addition to being able to access the version history of our data, any point in this workflow, we can 
also check the status of untracked (not yet saved) changes using the datalad status command, as seen 
below: 

.. code-block:: console 

    $ datalad status -d ~/CuBIDS_Test/BIDS_Dataset_DataLad

This command produces a description of the changes we have made to the data since the last commit 
(see below)

.. image:: _static/screenshot_2.png

The command above shows all files untracked, as we have copied the BIDS data into 
``~/CuBIDS_Test/BIDS_Dataset_DataLad`` but have not yet saved those changes. Our next step is to 
run save. It is best practice to provide a detailed commit message, for example:

.. code-block:: console

    $ datalad save -d ~/BIDS_Dataset_Datalad -m “checked dataset into datalad”

At this point, we can check our git history, which will display the version history of our dataset 
thus far, with the following command: 

.. code-block:: console

    $ git log --oneline

which will produce the following: 

.. image:: _static/screenshot_3.png

As seen above, the creation of our DataLad dataset is now reflected in the dataset’s version control 
history. Note that it is best practice to provide a detailed commit message with each change made to
the data. 


Adding NIfTI Information to JSON Sidecars
-------------------------------------------

Next, we seek to add new fields regarding our image parameters that are only reflected in the NIfTI 
header to our metadata; these include important details such as image dimensions, number of volumes, 
image obliquity, and voxel sizes. To do this, we run:

.. code-block:: console

    $ cubids-add-nifti-info ~/BIDS_Dataset_Datalad –-use-datalad

This command adds the NIfTI header information to the JSON sidecars and saves those changes. In order 
to ensure that this command has been executed properly, we can run ``cubids-print-metadata-fields`` 
once more, which reveals that NIfTI header information has been successfully included in the metadata. 
Since we ran ``cubids-add-nifti-info`` with the ``–-use-datalad`` flag set, CuBIDS will automatically save the changes 
made to the dataset to the git log as follows:


.. image:: _static/screenshot_4.png

Validation 
-----------

The next step in the CuBIDS workflow is to understand what BIDS validation errors may be present 
(using ``cubids-validate``) as well as the structure, heterogeneity, and metadata errors present in the 
dataset (using ``cubids-group``). Notably, neither of these two programs requires write access to the data, 
as each simply reads in the contents of the data and creates CSVs that parse the metadata and validation 
errors present. Validation can be accomplished by running the following command:

.. code-block:: console

    $ cubids-validate ~/BIDS_Dataset_Datalad ~/v0 --sequential

This command produces the following CSV: 

.. csv-table:: v0_validation.csv
   :file: _static/v0_validation.csv
   :widths: 10, 10, 10, 10, 10, 40, 10
   :header-rows: 1

The use of the sequential flag forces the validator to treat each participant as its own BIDS dataset. 
This initial validation run reveals that Phase Encoding Direction (PED) is not specified for one of the 
BOLD task-rest scans. We can clearly see that we either need to find the PED for this scan elsewhere and 
edit that sidecar to include it or remove that scan from the dataset, as this missing scanning parameter 
will render field map correction impossible. For the purpose of this demonstration, we elect to remove 
the scan. To do this, we run the following command: 

.. code-block:: console

    $ cubids-purge ~/CuBIDS_Test/BIDS_Dataset_DataLad ~/CuBIDS_Test/no_ped.txt --use-datalad 

Here, no_ped.txt is a text file containing the path to the dwi scan flagged in v0_validation.txt 
for missing PED which the user must create before running cubids-purge. We elect to use purge instead 
of simply removing the scan due to the fact that purge will ensure all associated files, including 
sidecars and IntendedFor references in the sidecars of fieldmaps, are also deleted. This change will 
be reflected in the git history.


.. image:: _static/screenshot_5.png


Returning again to ``v0_validation.csv``, we can also see that there is one DWI scan missing 
TotalReadoutTime, a metadata field necessary for certain pipelines. In this case, we determine 
that TotalReadoutTime (TRT) was erroneously omitted from the DWI sidecars. For the purpose of this 
example, we assume we are able to obtain the TRT value for this scan, by asking the scanner tech. 
Once we have this value, we manually add it to the sidecar for which it is missing. We then save the 
latest changes to the dataset with a detailed commit message as follows:

.. code-block:: console

    $ datalad save -d ~/CuBIDS_Test/BIDS_Dataset_DataLad -m "Added TotalReadoutTime to sub-03_ses-phdiff_acq-HASC55AP_dwi.nii.json"

This change will be reflected in the git history.

.. image:: _static/screenshot_6.png

To verify that there are no remaining validation errors, we rerun validation with the following command:

.. code-block:: console

    $ cubids-validate ~/CuBIDS_Test/BIDS_Dataset_DataLad ~/CuBIDS_Test/v1 --sequential

This command will produce no CSV output and instead print “No issues/warnings parsed, your dataset is 
BIDS valid” to the terminal, which indicates that the dataset is now free from BIDS validation errors 
and warnings.

Metadata Heterogenaity Parsing 
------------------------------

Along with parsing the BIDS validation errors in our dataset, it is important to understand the 
dataset’s structure, heterogeneity, and metadata errors. To accomplish these tasks, we use ``cubids-group``. 
Large datasets almost inevitably contain multiple validation and metadata errors. As such, it is 
typically useful to run both cubids-validate and cubids-group in parallel, as validation errors are 
better understood within the context of a dataset’s heterogeneity. Additionally, being able to see 
both the metadata errors—missing or incorrectly specified sidecar parameters—that grouping reveals, 
alongside BIDS errors the validator catches, gives users a more comprehensive view of the issues they 
will need to fix during the curation process. The command to run the grouping function is as follows:

.. code-block:: console

    $ cubids-group ~/CuBIDS_Test/BIDS_Dataset_DataLad ~/CuBIDS_Test/v0

This command will produce four tables that display the dataset’s heterogeneity in different ways. First, ``v0_summary.csv``
contains all detected Key and Parameter groups and provides a high-level overview of the heterogeneity in the entire 
dataset. Second, ``v0_files.csv`` maps each imaging file in the BIDS directory to a Key and 
Parameter group. Third, ``v0_AcqGrouping.csv`` maps each session in the dataset to an Acquisition Group. Finally, 
``v0_AcqGroupInfo.txt`` lists the set of scanning parameters present in each Acquisition Group.

The next step in the CuBIDS curation process is to examine ``v0_summary.csv``, which allows for automated metadata quality 
assurance (QA)––the identification of incomplete, incorrect, or unusable parameter groups based on acquisition fields such 
as dimension and voxel sizes, number of volumes, etc. While ``v0_validation.csv`` identified all BIDS validation errors present 
in the dataset, it will not identify several issues that might be present with the sidecars. Such issues include instances of 
erroneous metadata and missing sidecar fields, which may impact successful execution of BIDS Apps. 


.. csv-table:: v0_summary.csv
   :file: _static/v0_summary.csv
   :widths: 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4
   :header-rows: 1

Examining ``v0_summary.csv`` we can see that one DWI Parameter Group––``acquisition-HASC55AP_datatype-dwi_suffix-dwi__2``––contains 
only one scan (see “Counts” column) with only 10 volumes (see “NumVolumes” column). Since the majority of DWI scans in this dataset 
have 61 volumes, CuBIDS assigns this single scan to a “Non-Dominant”, or “Variant” Parameter Group and populates that Parameter 
Group’s “RenameKeyGroup” column in ``v0_summary.csv`` with ``acquisition-HASC55APVARIANTNumVolumes_datatype-dwi_suffix-dwi``. For the 
purpose of this demonstration, we elect to remove this scan because it does not have enough volumes to be usable for most analyses. 
To do this, we can either use ``cubids-purge``, or we can edit v0_summary.csv by adding “0” to the “MergeInto” column in the row 
(Parameter Group) we want to remove. This will ensure all scans in that Parameter Group (in this example, just one scan) are removed. 
We will then save this edited version of v0_summary.csv as v0_edited_summary.csv, which will be passed into ``cubids-apply`` in our next 
curation step. 

.. csv-table:: v0_edited_summary.csv
   :file: _static/v0_edited_summary.csv
   :widths: 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4
   :header-rows: 1

Applying Changes
-----------------

Now that all metadata issues have been remedied––both the validation an summary outputs appear problem-free––we are ready to 
rename our files based on their RenameKeyGroup values and apply the requested deletion in ``v0_edited_summary.csv``. The cubids-apply 
function renames scans in each Variant Parameter Group according to the metadata parameters with a flag “VARIANT”, which is useful 
because the user will then be able to see, in each scan’s filename, which metadata parameters associated with that scan vary from 
those in the acquisition’s Dominant Group. We execute ``cubids-apply`` with the following command:

.. code-block:: console

    $ cubids-apply ~/CuBIDS_Test/BIDS_Dataset_DataLad ~/CuBIDS_Test/v0_edited_summary.csv ~/CuBIDS_Test/v0_files.csv ~/CuBIDS_Test/v1 --use-datalad


Checking our git log, we can see that our changes from apply have been saved.

.. image:: _static/screenshot_7.png

As a final step, we can check the four grouping CSVs ``cubids-apply`` produces to ensure they look as 
expected––that all files with variant scanning parameters have been renamed to indicate the parameters 
that vary in the acquisition fields of their filenames.

Exemplar Testing
-----------------

At this stage, the curation of the dataset is complete; next is pre-processing. CuBIDS facilitates 
this subsequent step through the creation of an Exemplar Dataset: a subset of the full dataset that 
spans the full variation of acquisitions and parameters by including one subject from each Acquisition 
Group. By testing only one subject per Acquisition Group, users are able to pinpoint both the specific 
metadata values and scans that may be associated with pipeline failures; these acquisition groups could 
then be evaluated in more detail and flagged for remediation or exclusion. The Exemplar Dataset can 
easily be created with the ``cubids-copy-exemplars`` command, to which we pass in ``v2_AcqGrouping.csv``
––the post ``cubids-apply`` acquisition grouping csv.

.. code-block:: console

    $ cubids-copy-exemplars ~/CuBIDS_Test/BIDS_Dataset_DataLad ~/CuBIDS_Test/Exemplar_Dataset ~/v1_AcqGrouping.csv –-use-datalad

Once a preprocessing pipeline completes successfully on the Exemplars, the full dataset can be executed 
with confidence, as a pipeline’s behavior on the full range of metadata heterogeneity in the dataset 
will have already been discovered during exemplar testing. 



