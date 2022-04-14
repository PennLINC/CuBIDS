=================
Full Walkthrough
=================

The CuBIDS workflow is currently being used in neuroimaging labs at a number of institutions 
including University of Pennsylvania, Children’s Hospital of Philadelphia, Child Mind Institute, 
and University of Minnesota’s Masonic Institute for the Developing Brain. To demonstrate the utility 
of CuBIDS, here we apply the software to a small example dataset that is included in the software’s 
GitHub repository for testing purposes. This dataset can be found at LINK TO TOY DATASET HERE!!!!!!!

Although DataLad is an optional dependency of CuBIDS, we use it in this example to demonstrate the 
version control curation capabilities of CuBIDS. For the purposes of this walkthrough, the path to this 
example dataset is ``~/BIDS_Dataset.`` 



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

Next, we copy the contents of our BIDS dataset into the newly created and currently empty DataLad 
dataset and save the changes. 

.. code-block:: console

    $ cp -r ~/BIDS_Dataset/* ~/BIDS_Dataset_Datalad
    $ datalad save -d ~/BIDS_Dataset_Datalad -m “checked dataset into datalad”


At this point, we can check our git history, which will display the version history of our dataset 
thus far, with the following command: 

.. code-block:: console

    $ git log --oneline

which will produce the following: 

.. image:: https://github.com/PennLINC/CuBIDS/blob/readthedocs-update/docs/_static/checked_dataset_into_datalad.png

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
Since we ran add-nifti-info with the –-use-datalad flag set, CuBIDS will automatically save the changes 
made to the dataset to the git log

INSERT SCREENSHOT HERE!!!!!!

Validation 
-----------

The next step in the CuBIDS workflow is to understand what BIDS validation errors may be present 
(using cubids-validate) as well as the structure, heterogeneity, and metadata errors present in the 
dataset (using cubids-group). Notably, neither of these two programs requires write access to the data, 
as each simply reads in the contents of the data and creates CSVs that parse the metadata and validation 
errors present. Validation can be accomplished by running the following command:

.. code-block:: console

    $ cubids-validate ~/BIDS_Dataset_Datalad ~/v0 --sequential




