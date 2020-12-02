#!/usr/bin/env python

"""Tests for `bond` package."""
import sys
sys.path.append("..")
import shutil
from copy import deepcopy
import hashlib
import json
from pkg_resources import resource_filename as pkgrf
import pytest
from bond import BOnD
from bond.validator import (build_validator_call,
                       run_validator, parse_validator_output)
from bond.metadata_merge import merge_without_overwrite
from math import nan
import csv
import os
import filecmp
import nibabel as nb
import numpy as np
import pandas as pd


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


def test_csv_merge_changes(tmp_path):
    data_root = get_data(tmp_path)
    bod = BOnD(data_root / "inconsistent", use_datalad=True)
    bod.datalad_save()
    assert bod.is_datalad_clean()

    csv_prefix = str(tmp_path / "originals")
    bod.get_CSVs(csv_prefix)
    summary_csv = csv_prefix + "_summary.csv"

    # give csv with no changes (make sure it does nothing)
    bod.apply_csv_changes(str(tmp_path / "originals_summary.csv"),
                          str(tmp_path / "originals_files.csv"),
                          str(tmp_path / "unmodified"))

    assert file_hash(tmp_path / "originals_summary.csv") == \
           file_hash(tmp_path / "unmodified_summary.csv")

    summary_df = pd.read_csv(summary_csv)

    # Find the dwi with no FlipAngle
    fa_nan_dwi_row, = np.flatnonzero(
        np.isnan(summary_df.FlipAngle) &
        summary_df.KeyGroup.str.fullmatch(
            "acquisition-HASC55AP_datatype-dwi_suffix-dwi"))
    # Find the dwi with and EchoTime ==
    complete_dwi_row, = np.flatnonzero(
        summary_df.KeyGroup.str.fullmatch(
            "acquisition-HASC55AP_datatype-dwi_suffix-dwi") &
        (summary_df.FlipAngle == 90.) &
        (summary_df.EchoTime > 0.05))
    cant_merge_echotime_dwi_row, = np.flatnonzero(
        summary_df.KeyGroup.str.fullmatch(
            "acquisition-HASC55AP_datatype-dwi_suffix-dwi") &
        (summary_df.FlipAngle == 90.) &
        (summary_df.EchoTime < 0.05))

    # Set a legal MergeInto value. This effectively fills in data
    # where there was previously as missing FlipAngle
    summary_df.loc[fa_nan_dwi_row, "MergeInto"] = summary_df.ParamGroup[
        complete_dwi_row]

    valid_csv_prefix = csv_prefix + "_valid"
    summary_df.to_csv(valid_csv_prefix + "_summary.csv", index=False)

    bod.apply_csv_changes(valid_csv_prefix + "_summary.csv",
                          str(tmp_path / "originals_files.csv"),
                          str(tmp_path / "ok_modified"))

    assert not file_hash(tmp_path / "originals_summary.csv") == \
           file_hash(tmp_path / "ok_modified_summary.csv")

    # Add an illegal merge to MergeInto
    summary_df.loc[cant_merge_echotime_dwi_row, "MergeInto"] = summary_df.ParamGroup[
        complete_dwi_row]
    invalid_csv_file = csv_prefix + "_invalid_summary.csv"
    summary_df.to_csv(valid_csv_prefix + "_invalid_summary.csv", index=False)

    with pytest.raises(Exception):
        bod.apply_csv_changes(invalid_csv_file,
                              str(tmp_path / "originals_files.csv"),
                              str(tmp_path / "ok_modified"))


def test_merge_without_overwrite():
    meta1 = {
        'ManualCheck': 1.0,
        'RenameKeyGroup': np.nan,
        'MergeInto': 2.0,
        'KeyGroup': 'datatype-func_suffix-bold_task-rest',
        'ParamGroup': 12,
        'Counts': 2,
        'DwellTime': 2.6e-06,
        'EchoTime': 0.03,
        'EffectiveEchoSpacing': 0.000580013,
        'FieldmapKey00': 'acquisition-fMRI_datatype-fmap_direction-AP_fmap-epi_suffix-epi',
        'FieldmapKey01': 'acquisition-fMRI_datatype-fmap_direction-PA_fmap-epi_run-1_suffix-epi',
        'FieldmapKey02': 'acquisition-fMRI_datatype-fmap_direction-PA_fmap-epi_run-2_suffix-epi',
        'FieldmapKey03': np.nan,
        'FieldmapKey04': np.nan,
        'FieldmapKey05': np.nan,
        'FieldmapKey06': np.nan,
        'FieldmapKey07': np.nan,
        'FlipAngle': 31.0,
        'IntendedForKey00': np.nan,
        'IntendedForKey01': np.nan,
        'IntendedForKey02': np.nan,
        'IntendedForKey03': np.nan,
        'IntendedForKey04': np.nan,
        'IntendedForKey05': np.nan,
        'IntendedForKey06': np.nan,
        'IntendedForKey07': np.nan,
        'IntendedForKey08': np.nan,
        'IntendedForKey09': np.nan,
        'MultibandAccelerationFactor': 6.0,
        'NSliceTimes': 60,
        'ParallelReductionFactorInPlane': np.nan,
        'PartialFourier': 1.0,
        'PhaseEncodingDirection': 'j-',
        'RepetitionTime': 0.8,
        'TotalReadoutTime': 0.0481411}

    # Set a conflicting imaging param in the dest group
    meta_overwrite = deepcopy(meta1)
    meta_overwrite["FlipAngle"] = 62.0
    bad_merge = merge_without_overwrite(meta1, meta_overwrite)
    assert not bad_merge

    # Suppose "PartialFourier" is missing in the dest group
    meta_ok = deepcopy(meta1)
    meta_ok["PartialFourier"] = np.nan
    ok_merge = merge_without_overwrite(meta1, meta_ok)
    assert ok_merge
    assert ok_merge["PartialFourier"] == meta1["PartialFourier"]

    # Suppose the same, but there is a different number of slice times
    slices_bad = deepcopy(meta1)
    slices_bad["PartialFourier"] = np.nan
    slices_bad["NSliceTimes"] = meta1["NSliceTimes"] + 5
    bad_slice_merge = merge_without_overwrite(meta1, slices_bad)
    assert not bad_slice_merge


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


def test_apply_csv_changes(tmp_path):
    # set up like narrative of user using this
    # similar to test csv creation
    # open the csv, rename a key group
    # save csv
    # call change key groups
    # give csv with no changes (make sure it does nothing)
    # make sure files you wanted to rename exist in the bids dir

    data_root = get_data(tmp_path)
    complete_bond = BOnD(data_root / "complete", use_datalad=True)
    complete_bond.datalad_save()

    complete_bond.get_CSVs(str(tmp_path / "originals"))

    # give csv with no changes (make sure it does nothing)
    complete_bond.apply_csv_changes(str(tmp_path / "originals"),
                                    str(tmp_path / "modified1"))

    og_path = tmp_path / "originals_summary.csv"
    with og_path.open("r") as f:
        og_content = "".join(f.readlines())

    mod1_path = tmp_path / "modified1_summary.csv"
    with mod1_path.open("r") as f:
        mod1_content = "".join(f.readlines())

    assert og_content == mod1_content

    # edit the csv, add a RenameKeyGroup
    _edit_csv(str(tmp_path / "originals_summary.csv"))
    complete_bond.apply_csv_changes(str(tmp_path / "originals"),
                                    str(tmp_path / "modified2"))

    mod2_path = tmp_path / "modified2_summary.csv"
    with mod2_path.open("r") as f:
        mod2_content = "".join(f.readlines())

    assert og_content != mod2_content


def _edit_csv(summary_csv):
    r = csv.reader(open(summary_csv))
    lines = list(r)

    # adds a new key group to the RenameKeyGroup columm
    lines[2][3] = \
        "acquisition-v5_datatype-fmap_fmap-magnitude1_suffix-magnitude1"

    writer = csv.writer(open(summary_csv, 'w'))
    writer.writerows(lines)

    # add new key group name to RenameKeyGroup column


def _edit_a_json(json_file):
    """Open a json file, write somthing to it and save it to the same name."""
    with open(json_file, "r") as metadatar:
        metadata = json.load(metadatar)

    metadata["THIS_IS_A_TEST"] = True
    with open(json_file, "w") as metadataw:
        json.dump(metadata, metadataw)


def _edit_a_nifti(nifti_file):
    img = nb.load(nifti_file)
    new_img = nb.Nifti1Image(np.random.rand(*img.shape),
                             affine=img.affine,
                             header=img.header)
    new_img.to_filename(nifti_file)


def file_hash(file_name):
    with open(str(file_name), 'rb') as fcheck:
        data = fcheck.read()
    return hashlib.md5(data).hexdigest()


def _get_json_string(json_path):
    with json_path.open("r") as f:
        content = "".join(f.readlines())
    return content


def test_remove_fields(tmp_path):
    """Test that we metadata fields are detected and removed."""
    data_root = get_data(tmp_path)
    bod = BOnD(data_root, use_datalad=False)

    # Get the metadata fields
    metadata_fields = bod.get_all_metadata_fields()
    assert metadata_fields

    # Simulate some fields we might want to remove
    fields_to_remove = ["DeviceSerialNumber", "AcquisitionTime",
                        "InstitutionAddress", "InstitutionName",
                        "StationName", "NotARealField"]

    bod.remove_metadata_fields(fields_to_remove)
    new_fields = bod.get_all_metadata_fields()
    assert not set(new_fields).intersection(fields_to_remove)


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
    test_binary = data_root / "complete" / "sub-03" / "ses-phdiff" \
        / "func" / "sub-03_ses-phdiff_task-rest_bold.nii.gz"

    # Try editing a locked file - it should fail
    with pytest.raises(Exception):
        _edit_a_nifti(test_binary)

    # Unlock the files so we can access their content
    complete_bod.datalad_handle.unlock(test_binary)
    complete_bod.datalad_handle.unlock(test_file)

    # Get the contents of the original files
    original_content = _get_json_string(test_file)
    original_binary_content = file_hash(test_binary)

    # Edit the files
    _edit_a_nifti(test_binary)
    _edit_a_json(test_file)

    # Get the edited content
    edited_content = _get_json_string(test_file)
    edited_binary_content = file_hash(test_binary)

    # Check that the file content has changed
    assert not original_content == edited_content
    assert not original_binary_content == edited_binary_content

    # Check that datalad knows something has changed
    assert not uninit_bond.is_datalad_clean()
    assert not complete_bod.is_datalad_clean()

    # Attempt to undo a change before checking in changes
    with pytest.raises(Exception):
        uninit_bond.datalad_undo_last_commit()

    # Perform a save
    uninit_bond.datalad_save(message="TEST SAVE!")
    assert uninit_bond.is_datalad_clean()

    # Now undo the most recent save
    uninit_bond.datalad_undo_last_commit()

    # Unlock the restored files so we can access their content
    complete_bod.datalad_handle.unlock(test_binary)
    complete_bod.datalad_handle.unlock(test_file)

    # Get the contents of the original files
    restored_content = _get_json_string(test_file)
    restored_binary_content = file_hash(test_binary)

    # Check that the file content has returned to its original state
    assert original_content == restored_content
    assert original_binary_content == restored_binary_content


def _remove_a_json(json_file):

    os.remove(json_file)


def test_validator(tmp_path):

    data_root = get_data(tmp_path)

    # test the validator in valid dataset
    call = build_validator_call(str(data_root) + "/complete")
    ret = run_validator(call)

    assert ret.returncode == 0

    parsed = parse_validator_output(ret.stdout.decode('UTF-8'))

    assert parsed.shape[1] < 1

    # bungle some data and test

    # get data
    test_file = data_root / "complete" / "sub-03" / "ses-phdiff" \
        / "func" / "sub-03_ses-phdiff_task-rest_bold.json"
    test_binary = data_root / "complete" / "sub-03" / "ses-phdiff" \
        / "func" / "sub-03_ses-phdiff_task-rest_bold.nii.gz"

    # Edit the files
    _edit_a_nifti(test_binary)
    _remove_a_json(test_file)

    call = build_validator_call(str(data_root) + "/complete")
    ret = run_validator(call)

    assert ret.returncode == 1

    parsed = parse_validator_output(ret.stdout.decode('UTF-8'))

    assert parsed.shape[1] > 1


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

"""
