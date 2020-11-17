#!/usr/bin/env python

"""Tests for `bond` package."""
import sys
import shutil
import json
from pkg_resources import resource_filename as pkgrf
sys.path.append("..")
import pytest
from bond import BOnD

TEST_DATA = pkgrf("bond", "testdata")

COMPLETE_KEY_GROUPS = [
    'acquisition-HASC55AP_datatype-dwi_suffix-dwi',
    'acquisition-v4_datatype-fmap_fmap-magnitude1_suffix-magnitude1',
    'acquisition-v4_datatype-fmap_fmap-magnitude2_suffix-magnitude2',
    'acquisition-v4_datatype-fmap_fmap-phasediff_suffix-phasediff',
    'datatype-anat_suffix-T1w',
    'datatype-fmap_direction-PA_fmap-epi_suffix-epi',
    'datatype-func_suffix-bold_task-rest']


def get_data(tmp_path):
    """Copy testing data to a local directory"""
    data_root = tmp_path / "testdata"
    shutil.copytree(TEST_DATA, str(data_root))
    return data_root


def test_keygroups(tmp_path):
    data_root = get_data(tmp_path)

    # Test the complete data
    complete_bod = BOnD(data_root / "complete")
    complete_misfit_fmaps = complete_bod._cache_fieldmaps()
    # There should be no unpaired fieldmaps
    assert len(complete_misfit_fmaps) == 0

    # Test that the correct key groups are found
    key_groups = complete_bod.get_key_groups()
    assert key_groups == COMPLETE_KEY_GROUPS

    # Test the incomplete
    ibod = BOnD(data_root / "inconsistent")
    inc_misfit_fmaps = ibod._cache_fieldmaps()
    assert len(inc_misfit_fmaps) == 1

    # There will still be the same number of key groups
    ikey_groups = ibod.get_key_groups()
    assert ikey_groups == COMPLETE_KEY_GROUPS


def test_csv_creation(tmp_path):
    """Test the Key Group and Parameter Group creation on sample data.
    """
    data_root = get_data(tmp_path)

    # Test the complete data
    complete_bod = BOnD(data_root / "complete")
    complete_misfit_fmaps = complete_bod._cache_fieldmaps()
    # There should be no unpaired fieldmaps
    assert len(complete_misfit_fmaps) == 0

    # Test that the correct key groups are found
    key_groups = complete_bod.get_key_groups()
    assert key_groups == COMPLETE_KEY_GROUPS

    # Get the CSVs from the complete data
    cfiles_df, csummary_df = \
        complete_bod.get_param_groups_dataframes()

    # Make sure we got all 21 of the files
    assert cfiles_df.shape[0] == 21

    # This data should have the same number of param
    # groups as key groups
    assert csummary_df.shape[0] == len(COMPLETE_KEY_GROUPS)

    # Test the incomplete
    ibod = BOnD(data_root / "inconsistent")
    inc_misfit_fmaps = ibod._cache_fieldmaps()
    assert len(inc_misfit_fmaps) == 1

    # There will still be the same number of key groups
    ikey_groups = ibod.get_key_groups()
    assert ikey_groups == COMPLETE_KEY_GROUPS

    # Get the CSVs from the inconsistent data
    ifiles_df, isummary_df = \
        ibod.get_param_groups_dataframes()

    # There are still 21 files
    assert ifiles_df.shape[0] == 21

    # But now there are more parameter groups
    assert isummary_df.shape[0] == 11


def test_change_key_groups(tmp_path):
    data_root = get_data(tmp_path)

    my_bond = BOnD(data_root)
    my_bond._cache_fieldmaps()
    my_bond.get_CSVs(str(tmp_path / "og_csv_dir"))


def _edit_a_json(json_file):
    """Open a json file, write somthing to it and save it to the same name."""
    with open(json_file, "r") as metadatar:
        metadata = json.load(metadatar)

    metadata["THIS_IS_A_TEST"] = True
    with open(json_file, "w") as metadataw:
        json.dump(metadata, metadataw)


def _get_json_string(json_path):
    with json_path.open("r") as f:
        content = "".join(f.readlines())
    return content


def test_datalad_integration(tmp_path):
    """Test that datalad works for basic file modification operations.
    """
    data_root = get_data(tmp_path)

    # Test that an uninitialized BOnD raises exceptions
    uninit_bond = BOnD(data_root / "complete", use_datalad=False)

    # Ensure an exception is raised if trying to use datalad without
    # initializing
    with pytest.raises(Exception):
        uninit_bond.is_datalad_clean()

    # initialize the datalad repository and try again
    uninit_bond.init_datalad()
    uninit_bond.datalad_save('Test save')
    assert uninit_bond.is_datalad_clean()

    # Now, the datalad repository is initialized and saved.
    # Make sure if we make a new BOnD object it recognizes that
    # the datalad status is OK
    complete_bod = BOnD(data_root / "complete", use_datalad=True)

    assert complete_bod.datalad_ready
    assert complete_bod.is_datalad_clean()

    # Test clean and revert functionality
    test_file = data_root / "complete" / "sub-03" / "ses-phdiff" \
        / "func" / "sub-03_ses-phdiff_task-rest_bold.json"

    # Edit a file and make sure that it's been detected by datalad
    original_content = _get_json_string(test_file)
    _edit_a_json(test_file)
    edited_content = _get_json_string(test_file)
    # Check that the file content has changed
    assert not original_content == edited_content
    # Check that datalad knows something has changed
    assert not uninit_bond.is_datalad_clean()
    assert not complete_bod.is_datalad_clean()

    # Test clear_untracked_changes
    uninit_bond.clear_untracked_changes()
    assert uninit_bond.is_datalad_clean()  # should be clean now
    cleaned_content = _get_json_string(test_file)
    assert cleaned_content == original_content

    # Test BOnD.datalad_save()
    _edit_a_json(test_file)
    edited_content = _get_json_string(test_file)
    # Check that the file content has changed
    assert not original_content == edited_content
    uninit_bond.datalad_save(message="TEST SAVE!")
    assert uninit_bond.is_datalad_clean()



"""
def test_fill_metadata(tmp_path):
    data_root = tmp_path / "testdata"
    shutil.copytree(TEST_DATA, str(data_root))
    data_root = op.join(bids_data + "/incomplete/fill-metadata")
    my_bond = bond.BOnD(data_root)
    # fill_metadata should add metadata elements to the json sidecar
    my_bond.fill_metadata(pattern="*acq-multiband_bold.nii.gz",
                          metadata={"EchoTime": 0.005})
    # get_metadata shold return a list of dictionaries that contain
    # metadata for
    # scans matching `pattern`
    for metadata in my_bond.get_metadata(pattern="*acq-multiband_bold"):
        assert metadata['EchoTime'] == 0.005

    # fill_metadata should add metadata elements to the json sidecar
    my_bond.fill_metadata(pattern="*acq-multiband_bold.nii.gz",
                          metadata={"EchoTime": 0.009})
    # get_metadata shold return a list of dictionaries that contain
    # metadata for
    # scans matching `pattern`
    for metadata in my_bond.get_metadata(pattern="*acq-multiband_bold"):
        assert metadata['EchoTime'] == 0.009


def test_detect_unique_parameter_sets(bids_data):
    data_root = op.join(bids_data + "/incomplete/multi_param_sets")
    my_bond = bond.BOnD(data_root)

    # Ground truth groups
    true_combinations = [
        {"EchoTime": 0.005, "PhaseEncodingDirection": "j"},
        {"EchoTime": 0.005, "PhaseEncodingDirection": "j-"}
    ]

    # Find param sets from the data on
    combinations = my_bond.find_param_sets(pattern="*_bold")

    assert len(true_combinations) == len(combinations)


def test_rename_files(tmp_path):
    data_root = tmp_path / "testdata"
    shutil.copytree(TEST_DATA, str(data_root))
    data_root = str(data_root / "complete")
    my_bond = bond.BOnD(data_root)

    original_suffix = "_run-01_bold"
    renamed_suffix = "_acq-multiband_run-01_bold"

    # Show that there are none of these files already there
    assert not glob("*" + renamed_suffix + "*")

    # Actually do the renaming
    my_bond.rename_files(original_suffix, renamed_suffix)

    # Show that these files are now there
    assert not glob("*" + renamed_suffix + "*")


def test_fieldmap_exists(bids_data):
    ok_data_root = op.join(bids_data + "/complete/fieldmaps")
    not_ok_data_root = op.join(bids_data + "/incomplete/fieldmaps")

    ok_bond = bond.BOnD(ok_data_root)
    assert ok_bond.fieldmaps_ok()

    not_ok_bond = bond.BOnD(not_ok_data_root)
    assert not not_ok_bond.fieldmaps_ok()
"""
