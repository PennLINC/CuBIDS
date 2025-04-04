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
   cubids.cubids.build_path


*******************************************
:mod:`cubids.workflows`: Workflow Functions
*******************************************

.. currentmodule:: cubids

.. autosummary::
   :toctree: generated/
   :template: function.rst

   workflows.validate
   workflows.bids_sidecar_merge
   workflows.group
   workflows.apply
   workflows.datalad_save
   workflows.undo
   workflows.copy_exemplars
   workflows.add_nifti_info
   workflows.add_file_collections
   workflows.purge
   workflows.remove_metadata_fields
   workflows.print_metadata_fields


**********************************************
:mod:`cubids.metadata_merge`: Merging Metadata
**********************************************

.. currentmodule:: cubids

.. autosummary::
   :toctree: generated/
   :template: function.rst

   metadata_merge.check_merging_operations
   metadata_merge.merge_without_overwrite
   metadata_merge.merge_json_into_json
   metadata_merge.get_acq_dictionary
   metadata_merge.group_by_acquisition_sets


***********************************
:mod:`cubids.validator`: Validation
***********************************

.. currentmodule:: cubids

.. autosummary::
   :toctree: generated/
   :template: function.rst

   validator.build_validator_call
   validator.build_subject_paths
   validator.run_validator
   validator.parse_validator_output
   validator.get_val_dictionary
