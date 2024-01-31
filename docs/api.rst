.. include:: links.rst

===
API
===

*********************************
:mod:`cubids.cubids`: Main Module
*********************************

.. currentmodule:: cubids

.. autosummary::
   :toctree: generated/
   :template: class.rst

   cubids.cubids.CuBIDS


*******************************************
:mod:`cubids.workflows`: Workflow Functions
*******************************************

.. currentmodule:: cubids

.. autosummary::
   :toctree: generated/
   :template: function.rst

   cubids.workflows.validate
   cubids.workflows.bids_sidecar_merge
   cubids.workflows.group
   cubids.workflows.apply
   cubids.workflows.datalad_save
   cubids.workflows.undo
   cubids.workflows.copy_exemplars
   cubids.workflows.add_nifti_info
   cubids.workflows.purge
   cubids.workflows.remove_metadata_fields
   cubids.workflows.print_metadata_fields


**********************************************
:mod:`cubids.metadata_merge`: Merging Metadata
**********************************************

.. currentmodule:: cubids

.. autosummary::
   :toctree: generated/
   :template: function.rst

   cubids.metadata_merge.check_merging_operations
   cubids.metadata_merge.merge_without_overwrite
   cubids.metadata_merge.merge_json_into_json
   cubids.metadata_merge.get_acq_dictionary
   cubids.metadata_merge.group_by_acquisition_sets


***********************************
:mod:`cubids.validator`: Validation
***********************************

.. currentmodule:: cubids

.. autosummary::
   :toctree: generated/
   :template: function.rst

   cubids.validate.build_validator_call
   cubids.validate.build_subject_paths
   cubids.validate.run_validator
   cubids.validate.parse_validator_output
   cubids.validate.get_val_dictionary
