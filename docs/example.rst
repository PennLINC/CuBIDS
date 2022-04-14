=================
Full Walkthrough
=================

The CuBIDS workflow is currently being used in neuroimaging labs at a number of institutions 
including University of Pennsylvania, Children’s Hospital of Philadelphia, Child Mind Institute, 
and University of Minnesota’s Masonic Institute for the Developing Brain. To demonstrate the utility 
of CuBIDS, here we apply the software to a small example dataset that is included in the software’s 
GitHub repository for testing purposes. This dataset can be found at LINK TO TOY DATASET HERE!!!!!!!

Although DataLad is an optional dependency of CuBIDS, we us it in this example to demonstrate the version 
control curation capabilities of CuBIDS. For the purposes of this walkthrough, the path to this 
example dataset is ``~/BIDS_Dataset.`` As a first step, we use CuBIDS to identify 
the metadata fields present in the dataset. This is accomplished with the following command:

.. code-block:: console

    $ cubids-print-metadata-fields ~/BIDS_Dataset




