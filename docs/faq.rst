==========================
Frequently Asked Questions
==========================


--------------------------------------
Does CuBIDS work on all BIDS datasets?
--------------------------------------

CuBIDS relies on many hardcoded rules and data types,
so it may not work on all BIDS datasets.
Some datatypes, such as EEG or iEEG, are not yet supported,
nor are some configurations of supported datatypes, such as multi-echo fMRI.

If you encounter an issue, please open an issue on the CuBIDS GitHub repository.


-----------------------------------------------------
How do the developers determine what features to add?
-----------------------------------------------------

CuBIDS is primarily developed to curate large-scale datasets in order to be used by the PennLINC team.
This means that we will naturally prioritize features that are useful to us.
However, we are always open to suggestions and contributions from the community,
and will of course consider features that do not directly benefit us.

If you want to request support for a new modality or niche data feature,
please open an issue on the CuBIDS GitHub repository.
We are more likely to add support for a new feature if you can point us toward a dataset that we can use to test it.
