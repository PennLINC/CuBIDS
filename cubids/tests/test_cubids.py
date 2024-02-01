"""This file contains unit tests for the CuBIDS class in the CuBIDS package."""

import pandas as pd
import pytest

from cubids.cubids import CuBIDS


@pytest.fixture
def cubids_instance():
    data_root = "/path/to/bids/dataset"
    return CuBIDS(data_root)


def _test_init_cubids(cubids_instance):
    assert cubids_instance.path == "/path/to/bids/dataset"
    assert cubids_instance.use_datalad is False
    assert cubids_instance.acq_group_level == "subject"
    assert cubids_instance.grouping_config is None
    assert cubids_instance.force_unlock is False


def _test_reset_bids_layout(cubids_instance):
    cubids_instance.reset_bids_layout()
    assert cubids_instance.layout is not None


def _test_create_cubids_code_dir(cubids_instance):
    cubids_instance.create_cubids_code_dir()
    assert cubids_instance.cubids_code_dir is True


def _test_init_datalad(cubids_instance):
    cubids_instance.init_datalad()
    assert cubids_instance.datalad_ready is True
    assert cubids_instance.datalad_handle is not None


def _test_add_nifti_info(cubids_instance):
    cubids_instance.add_nifti_info()
    # Add assertions here


def _test_datalad_save(cubids_instance):
    cubids_instance.datalad_save()
    # Add assertions here


def _test_is_datalad_clean(cubids_instance):
    assert cubids_instance.is_datalad_clean() is True


def _test_datalad_undo_last_commit(cubids_instance):
    cubids_instance.datalad_undo_last_commit()
    # Add assertions here


def _test_apply_tsv_changes(cubids_instance):
    summary_tsv = "/path/to/summary.tsv"
    files_tsv = "/path/to/files.tsv"
    new_prefix = "new_prefix"
    cubids_instance.apply_tsv_changes(summary_tsv, files_tsv, new_prefix)
    # Add assertions here


def _test_change_filename(cubids_instance):
    filepath = "/path/to/file.nii.gz"
    entities = {"subject": "sub-01", "session": "ses-01"}
    cubids_instance.change_filename(filepath, entities)
    # Add assertions here


def _test_copy_exemplars(cubids_instance):
    exemplars_dir = "/path/to/exemplars"
    exemplars_tsv = "/path/to/exemplars.tsv"
    min_group_size = 2
    cubids_instance.copy_exemplars(exemplars_dir, exemplars_tsv, min_group_size)
    # Add assertions here


def _test_purge(cubids_instance):
    scans_txt = "/path/to/scans.txt"
    cubids_instance.purge(scans_txt)
    # Add assertions here


def _test__purge_associations(cubids_instance):
    scans = ["scan-01", "scan-02"]
    cubids_instance._purge_associations(scans)
    # Add assertions here


def _test_get_nifti_associations(cubids_instance):
    nifti = "/path/to/file.nii.gz"
    associations = cubids_instance.get_nifti_associations(nifti)
    # Add assertions here


def _test__cache_fieldmaps(cubids_instance):
    cubids_instance._cache_fieldmaps()
    # Add assertions here


def _test_get_param_groups_from_key_group(cubids_instance):
    key_group = "group-01"
    param_groups = cubids_instance.get_param_groups_from_key_group(key_group)
    # Add assertions here


def _test_create_data_dictionary(cubids_instance):
    cubids_instance.create_data_dictionary()
    # Add assertions here


def _test_get_data_dictionary(cubids_instance):
    df = pd.DataFrame({"subject": ["sub-01", "sub-02"], "age": [25, 30]})
    data_dict = cubids_instance.get_data_dictionary(df)
    # Add assertions here


def _test_get_param_groups_dataframes(cubids_instance):
    param_groups_dataframes = cubids_instance.get_param_groups_dataframes()
    # Add assertions here


def _test_get_tsvs(cubids_instance):
    path_prefix = "/path/to/tsvs"
    tsvs = cubids_instance.get_tsvs(path_prefix)
    # Add assertions here


def _test_get_key_groups(cubids_instance):
    key_groups = cubids_instance.get_key_groups()
    # Add assertions here


def _test_change_metadata(cubids_instance):
    filters = {"subject": "sub-01"}
    metadata = {"age": 25}
    cubids_instance.change_metadata(filters, metadata)
    # Add assertions here


def _test_get_all_metadata_fields(cubids_instance):
    metadata_fields = cubids_instance.get_all_metadata_fields()
    # Add assertions here


def _test_remove_metadata_fields(cubids_instance):
    fields_to_remove = ["age", "sex"]
    cubids_instance.remove_metadata_fields(fields_to_remove)
    # Add assertions here


def _test_get_filenames(cubids_instance):
    filenames = cubids_instance.get_filenames()
    # Add assertions here


def _test_get_fieldmap_lookup(cubids_instance):
    fieldmap_lookup = cubids_instance.get_fieldmap_lookup()
    # Add assertions here


def _test_get_layout(cubids_instance):
    layout = cubids_instance.get_layout()
    # Add assertions here


def _test__validate_json(cubids_instance):
    cubids_instance._validate_json()
    # Add assertions here


def _test__update_json(cubids_instance):
    json_file = "/path/to/file.json"
    metadata = {"age": 25}
    cubids_instance._update_json(json_file, metadata)
    # Add assertions here


def _test__key_group_to_entities(cubids_instance):
    key_group = "group-01"
    entities = cubids_instance._key_group_to_entities(key_group)
    # Add assertions here


def _test__entities_to_key_group(cubids_instance):
    entities = {"subject": "sub-01", "session": "ses-01"}
    key_group = cubids_instance._entities_to_key_group(entities)
    # Add assertions here


def _test__file_to_key_group(cubids_instance):
    filename = "sub-01_ses-01_task-rest_bold.nii.gz"
    key_group = cubids_instance._file_to_key_group(filename)
    # Add assertions here


def _test__get_intended_for_reference(cubids_instance):
    scan = "sub-01_ses-01_task-rest_bold.nii.gz"
    reference = cubids_instance._get_intended_for_reference(scan)
    # Add assertions here


def _test__get_param_groups(cubids_instance):
    files = ["sub-01_ses-01_task-rest_bold.nii.gz", "sub-02_ses-01_task-rest_bold.nii.gz"]
    fieldmap_lookup = {"sub-01_ses-01_task-rest_bold.nii.gz": "fieldmap.nii.gz"}
    key_group_name = "group-01"
    grouping_config = {"group-01": {"modality": "bold"}}
    modality = "bold"
    keys_files = {"group-01": ["sub-01_ses-01_task-rest_bold.nii.gz"]}
    param_groups = cubids_instance._get_param_groups(
        files, fieldmap_lookup, key_group_name, grouping_config, modality, keys_files
    )
    # Add assertions here


def _test_round_params(cubids_instance):
    param_group_df = pd.DataFrame({"param": [0.123456789]})
    config = {"param": {"round": 3}}
    modality = "bold"
    rounded_params = cubids_instance.round_params(param_group_df, config, modality)
    # Add assertions here


def _test_get_sidecar_metadata(cubids_instance):
    json_file = "/path/to/file.json"
    metadata = cubids_instance.get_sidecar_metadata(json_file)
    # Add assertions here


def _test_format_params(cubids_instance):
    param_group_df = pd.DataFrame({"param": [0.123456789]})
    config = {"param": {"format": "{:.2f}"}}
    modality = "bold"
    formatted_params = cubids_instance.format_params(param_group_df, config, modality)
    # Add assertions here


def _test__order_columns(cubids_instance):
    df = pd.DataFrame({"b": [2], "a": [1]})
    ordered_df = cubids_instance._order_columns(df)
    # Add assertions here


def _test_img_to_new_ext(cubids_instance):
    img_path = "/path/to/image.nii.gz"
    new_ext = ".nii"
    new_img_path = cubids_instance.img_to_new_ext(img_path, new_ext)
    # Add assertions here


def _test_get_key_name(cubids_instance):
    path = "/path/to/file.nii.gz"
    key = "subject"
    key_name = cubids_instance.get_key_name(path, key)
    # Add assertions here
