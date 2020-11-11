#!/usr/bin/env python

"""Tests for `bond` package."""
import sys
sys.path.append("..")
import os
import pytest
from pkg_resources import resource_filename as pkgrf
import shutil
from bond import BOnD
import os.path as op
from copy import deepcopy
import base64
from glob import glob

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
