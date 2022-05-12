#!/usr/bin/env python

"""Tests for `cubids` package."""
import sys
sys.path.append("..")
import shutil
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from pkg_resources import resource_filename as pkgrf
import pytest
from cubids import CuBIDS
from cubids.validator import (build_validator_call,
                       run_validator, parse_validator_output)
from cubids.metadata_merge import (
    merge_without_overwrite, merge_json_into_json)
from math import nan
import subprocess
import csv
import os
import filecmp
import nibabel as nb
import numpy as np
import pandas as pd
import subprocess

TEST_DATA = pkgrf("cubids", "testdata")

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


def test_ok_json_merge(tmp_path):
    data_root = get_data(tmp_path)

    # Test that a successful merge can happen
    dest_json = data_root / "inconsistent" / "sub-02" / \
        "ses-phdiff" / "dwi" / "sub-02_ses-phdiff_acq-HASC55AP_dwi.json"
    orig_dest_json_content = _get_json_string(dest_json)
    source_json = data_root / "inconsistent" / "sub-03" / \
        "ses-phdiff" / "dwi" / "sub-03_ses-phdiff_acq-HASC55AP_dwi.json"

    merge_return = merge_json_into_json(source_json, dest_json)
    assert merge_return == 0
    assert not _get_json_string(dest_json) == orig_dest_json_content


def test_ok_json_merge_cli(tmp_path):
    data_root = get_data(tmp_path)

    # Test that a successful merge can happen
    dest_json = data_root / "inconsistent" / "sub-02" / \
        "ses-phdiff" / "dwi" / "sub-02_ses-phdiff_acq-HASC55AP_dwi.json"
    orig_dest_json_content = _get_json_string(dest_json)
    source_json = data_root / "inconsistent" / "sub-03" / \
        "ses-phdiff" / "dwi" / "sub-03_ses-phdiff_acq-HASC55AP_dwi.json"

    merge_proc = subprocess.run(
        ['bids-sidecar-merge', str(source_json), str(dest_json)])
    assert merge_proc.returncode == 0
    assert not _get_json_string(dest_json) == orig_dest_json_content

def test_get_param_groups(tmp_path):
    data_root = get_data(tmp_path)
    bod = CuBIDS(data_root / "inconsistent", use_datalad=True)
    csv_prefix = str(tmp_path / "csvs")
    key_groups = bod.get_key_groups()
    bod._cache_fieldmaps()

    for key_group in key_groups:
        ret = bod.get_param_groups_from_key_group(key_group)
        assert sum(ret[1].Counts) == ret[1].loc[0, 'KeyGroupCount']

def test_copy_exemplars(tmp_path):
    data_root = get_data(tmp_path)
    bod = CuBIDS(data_root / "complete", use_datalad=True)
    csv_prefix = str(tmp_path / "csvs")
    bod.get_CSVs(csv_prefix)
    acq_group_csv = csv_prefix + "_AcqGrouping.csv"
    print("ACQ GROUP PATH: ", acq_group_csv)
    exemplars_dir = str(tmp_path / "exemplars")
    print('EXEMPLARS DIR: ', exemplars_dir)
    df = pd.read_csv(acq_group_csv)

    bod.copy_exemplars(exemplars_dir, acq_group_csv, min_group_size=1)

    # check exemplar dir got created and has the correct number of subs
    cntr = 0
    for path in Path(exemplars_dir).glob("sub-*"):
        cntr += 1
    assert cntr == len(df.drop_duplicates(subset=["AcqGroup"]))

    # check that dataset_description.json got added
    assert Path(exemplars_dir + '/dataset_description.json').exists()

def test_purge_no_datalad(tmp_path):
    data_root = get_data(tmp_path)
    scans = []
    scan_name = data_root / "complete" / "sub-03" / "ses-phdiff" \
        / "func" / "sub-03_ses-phdiff_task-rest_bold.nii.gz"
    json_name = data_root / "complete" / "sub-03" / "ses-phdiff" \
        / "func" / "sub-03_ses-phdiff_task-rest_bold.json"
    scans.append(scan_name)
    scans.append(data_root / "complete" / "sub-01" / "ses-phdiff/dwi/sub-01_ses-phdiff_acq-HASC55AP_dwi.nii.gz")

    # create and save .txt with list of scans
    purge_path = str(tmp_path / "purge_scans.txt")
    with open(purge_path, 'w') as filehandle:
        for listitem in scans:
            filehandle.write('%s\n' % listitem)
    bod = CuBIDS(data_root / "complete", use_datalad=False)

    assert Path(scan_name).exists()
    assert Path(json_name).exists()

    # Check that IntendedFor purge worked
    with open(str(data_root / "complete" / "sub-01" / "ses-phdiff" / "fmap" / "sub-01_ses-phdiff_acq-v4_phasediff.json")) as f:
        j_dict = json.load(f)

    assert "ses-phdiff/dwi/sub-01_ses-phdiff_acq-HASC55AP_dwi.nii.gz" in j_dict.values()
    assert isinstance(j_dict['IntendedFor'], str)
    # PURGE
    bod.purge(purge_path)

    with open(str(data_root / "complete" / "sub-01" / "ses-phdiff" / "fmap" / "sub-01_ses-phdiff_acq-v4_phasediff.json")) as f:
        purged_dict = json.load(f)

    assert not Path(scan_name).exists()
    assert not Path(json_name).exists()
    assert "ses-phdiff/dwi/sub-01_ses-phdiff_acq-HASC55AP_dwi.nii.gz" not in purged_dict.values()
    assert isinstance(purged_dict['IntendedFor'], list)
    assert purged_dict['IntendedFor'] == []

def test_purge(tmp_path):
    data_root = get_data(tmp_path)
    scans = []
    scan_name = data_root / "complete" / "sub-03" / "ses-phdiff" \
        / "func" / "sub-03_ses-phdiff_task-rest_bold.nii.gz"
    json_name = data_root / "complete" / "sub-03" / "ses-phdiff" \
        / "func" / "sub-03_ses-phdiff_task-rest_bold.json"
    scans.append(scan_name)
    purge_path = str(tmp_path / "purge_scans.txt")

    with open(purge_path, 'w') as filehandle:
        for listitem in scans:
            filehandle.write('%s\n' % listitem)
    bod = CuBIDS(data_root / "complete", use_datalad=True)
    bod.datalad_save()

    assert bod.is_datalad_clean()
    assert Path(scan_name).exists()
    assert Path(json_name).exists()

    # create and save .txt with list of scans
    bod.purge(purge_path)

    assert not Path(scan_name).exists()
    assert not Path(json_name).exists()


def test_bad_json_merge(tmp_path):
    data_root = get_data(tmp_path)

    # Test that a successful merge can happen
    dest_json = data_root / "inconsistent" / "sub-02" / \
        "ses-phdiff" / "dwi" / "sub-02_ses-phdiff_acq-HASC55AP_dwi.json"
    orig_dest_json_content = _get_json_string(dest_json)
    invalid_source_json = data_root / "inconsistent" / "sub-01" / \
        "ses-phdiff" / "dwi" / "sub-01_ses-phdiff_acq-HASC55AP_dwi.json"

    assert merge_json_into_json(invalid_source_json, dest_json) > 0
    assert _get_json_string(dest_json) == orig_dest_json_content


def test_bad_json_merge_cli(tmp_path):
    data_root = get_data(tmp_path)

    # Test that a successful merge can happen
    dest_json = data_root / "inconsistent" / "sub-02" / \
        "ses-phdiff" / "dwi" / "sub-02_ses-phdiff_acq-HASC55AP_dwi.json"
    orig_dest_json_content = _get_json_string(dest_json)
    invalid_source_json = data_root / "inconsistent" / "sub-01" / \
        "ses-phdiff" / "dwi" / "sub-01_ses-phdiff_acq-HASC55AP_dwi.json"

    merge_proc = subprocess.run(
        ['bids-sidecar-merge', str(invalid_source_json), str(dest_json)])
    assert merge_proc.returncode > 0
    assert _get_json_string(dest_json) == orig_dest_json_content

def test_add_nifti_info_datalad(tmp_path):
    data_root = get_data(tmp_path)
    bod = CuBIDS(data_root / "complete", use_datalad=True, force_unlock=True)
    csv_prefix = str(tmp_path / "csvs")
    bod.get_CSVs(csv_prefix)
    summary_csv = csv_prefix + "_summary.csv"
    summary_df = pd.read_csv(summary_csv)
    l_cols = summary_df.columns.tolist()
    assert 'NumVolumes' not in l_cols
    assert 'Obliquity' not in l_cols

    # now add nifti info
    bod.add_nifti_info()
    nifti_csv_prefix = str(tmp_path / "nifti_csvs")
    bod.get_CSVs(nifti_csv_prefix)
    nifti_summary_csv = nifti_csv_prefix + "_summary.csv"
    nifti_summary_df = pd.read_csv(nifti_summary_csv)
    nifti_l_cols = nifti_summary_df.columns.tolist()
    assert 'NumVolumes' in nifti_l_cols
    assert 'Obliquity' in nifti_l_cols
    assert 'ImageOrientation' in nifti_l_cols

def test_add_nifti_info_no_datalad(tmp_path):
    data_root = get_data(tmp_path)
    bod = CuBIDS(data_root / "complete", use_datalad=False, force_unlock=False)
    bod.add_nifti_info()
    csv_prefix = str(tmp_path / "csvs")
    bod.get_CSVs(csv_prefix)
    summary_csv = csv_prefix + "_summary.csv"
    summary_df = pd.read_csv(summary_csv)
    l_cols = summary_df.columns.tolist()
    assert 'NumVolumes' in l_cols
    assert 'Obliquity' in l_cols

#TODO: add tests that return an error for invalid merge
def test_csv_merge_no_datalad(tmp_path):
    data_root = get_data(tmp_path)
    bod = CuBIDS(data_root / "inconsistent", use_datalad=False)

    # Get an initial grouping summary and files list
    csv_prefix = str(tmp_path / "originals")
    bod.get_CSVs(csv_prefix)
    original_summary_csv = csv_prefix + "_summary.csv"
    original_files_csv = csv_prefix + "_files.csv"

    # give csv with no changes (make sure it does nothing)
    bod.apply_csv_changes(original_summary_csv,
                          original_files_csv,
                          str(tmp_path / "unmodified"))

    # these will not actually be equivalent because of the auto renames
    assert file_hash(original_summary_csv) != \
           file_hash(tmp_path / "unmodified_summary.csv")

    # Find the dwi with no FlipAngle
    summary_df = pd.read_csv(original_summary_csv)
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

    valid_csv_file = csv_prefix + "_valid_summary.csv"
    summary_df.to_csv(valid_csv_file, index=False)

    # about to apply merges!

    bod.apply_csv_changes(valid_csv_file,
                          original_files_csv,
                          str(tmp_path / "ok_modified"))

    assert not file_hash(original_summary_csv) == \
           file_hash(tmp_path / "ok_modified_summary.csv")

    # Add an illegal merge to MergeInto
    summary_df.loc[cant_merge_echotime_dwi_row, "MergeInto"] = summary_df.ParamGroup[
        complete_dwi_row]
    invalid_csv_file = csv_prefix + "_invalid_summary.csv"
    summary_df.to_csv(invalid_csv_file, index=False)

    with pytest.raises(Exception):
        bod.apply_csv_changes(invalid_csv_file,
                              str(tmp_path / "originals_files.csv"),
                              str(tmp_path / "ok_modified"))

def test_csv_merge_changes(tmp_path):
    data_root = get_data(tmp_path)
    bod = CuBIDS(data_root / "inconsistent", use_datalad=True)
    bod.datalad_save()
    assert bod.is_datalad_clean()

    # Get an initial grouping summary and files list
    csv_prefix = str(tmp_path / "originals")
    bod.get_CSVs(csv_prefix)
    original_summary_csv = csv_prefix + "_summary.csv"
    original_files_csv = csv_prefix + "_files.csv"

    # give csv with no changes (make sure it does nothing except rename)
    bod.apply_csv_changes(original_summary_csv,
                          original_files_csv,
                          str(tmp_path / "unmodified"))
    orig = pd.read_csv(original_summary_csv)
    # TEST RenameKeyGroup column got populated CORRECTLY
    for row in range(len(orig)):
        if orig.loc[row, 'ParamGroup'] != 1:
            assert str(orig.loc[row, 'RenameKeyGroup']) != 'nan'

    # TESTING RENAMES GOT APPLIED
    applied = pd.read_csv(str(tmp_path / "unmodified_summary.csv"))

    applied_f = pd.read_csv(str(tmp_path / "unmodified_files.csv"))
    odd = []
    for row in range(len(applied_f)):
        if 'VARIANT' in applied_f.loc[row, 'FilePath'] and 'VARIANT' not in applied_f.loc[row, 'KeyParamGroup']:
            odd.append((applied_f.loc[row, 'FilePath']))

    occurrences = {}
    for row in range(len(applied_f)):
        if applied_f.loc[row, 'FilePath'] in odd:
            if applied_f.loc[row, 'FilePath'] in occurrences.keys():
                occurrences[applied_f.loc[row, 'FilePath']].append(applied_f.loc[row, 'KeyParamGroup'])
            else:
                occurrences[applied_f.loc[row, 'FilePath']] = [applied_f.loc[row, 'KeyParamGroup']]

    assert len(orig) == len(applied)

    renamed = True
    new_keys = applied['KeyGroup'].tolist()
    for row in range(len(orig)):
        if orig.loc[row, 'Modality'] != 'fmap':
            if str(orig.loc[row, 'RenameKeyGroup']) != 'nan' \
                    and str(orig.loc[row, 'RenameKeyGroup']) not in new_keys:
                print(orig.loc[row, 'RenameKeyGroup'])
                renamed = False

    assert renamed == True

    # will no longer be equal because of auto rename!
    assert file_hash(original_summary_csv)!= \
           file_hash(tmp_path / "unmodified_summary.csv")

    # Find the dwi with no FlipAngle
    summary_df = pd.read_csv(original_summary_csv)
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

    valid_csv_file = csv_prefix + "_valid_summary.csv"
    summary_df.to_csv(valid_csv_file, index=False)

    # about to merge
    bod.apply_csv_changes(valid_csv_file,
                          original_files_csv,
                          str(tmp_path / "ok_modified"))

    assert not file_hash(original_summary_csv) == \
           file_hash(tmp_path / "ok_modified_summary.csv")

    # Add an illegal merge to MergeInto
    summary_df.loc[cant_merge_echotime_dwi_row, "MergeInto"] = summary_df.ParamGroup[
        complete_dwi_row]
    invalid_csv_file = csv_prefix + "_invalid_summary.csv"
    summary_df.to_csv(invalid_csv_file, index=False)

    with pytest.raises(Exception):
        bod.apply_csv_changes(invalid_csv_file,
                              str(tmp_path / "originals_files.csv"),
                              str(tmp_path / "ok_modified"))

    # Make sure MergeInto == 0 deletes the param group and all associations
    # summary_df = pd.read_csv(original_summary_csv)
    # summary_df.loc[fa_nan_dwi_row, "MergeInto"] = 0
    # delete_group = summary_df.loc[fa_nan_dwi_row, "KeyParamGroup"]

    # # files_df = pd.read_csv(original_files_csv)
    # # for row in files_df:
    # #     if files_df.iloc[row]['KeyParamGroup'] == delete_group:
    # #         filename = files_df.iloc[row]['FilePath']
    # #         file_to_rem = Path(filename)
    # #         file_to_rem.unlink()

    # delete_csv_file = csv_prefix + "_delete_summary.csv"
    # summary_df.to_csv(delete_csv_file, index=False)

    # bod.apply_csv_changes(delete_csv_file,
    #                       original_files_csv,
    #                       str(tmp_path / "ok_deleted"))

    # del_summary_csv = str(tmp_path / "ok_deleted")

    # original_summary_csv = csv_prefix + "_summary.csv"
    # original_files_csv = csv_prefix + "_files.csv"

    # assert delete_group not in tmp_path / "ok_deleted_summary.csv"

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

    # Suppose User tries to overwrite num with NaN (allowed)
    meta_NaN = deepcopy(meta1)
    meta_NaN["FlipAngle"] = np.nan
    valid_merge = merge_without_overwrite(meta_NaN, meta1)
    assert valid_merge

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
    complete_bod = CuBIDS(data_root / "complete")
    complete_misfit_fmaps = complete_bod._cache_fieldmaps()
    # There should be no unpaired fieldmaps
    assert len(complete_misfit_fmaps) == 0

    # Test that the correct key groups are found
    key_groups = complete_bod.get_key_groups()
    assert key_groups == COMPLETE_KEY_GROUPS

    # Test the incomplete
    ibod = CuBIDS(data_root / "inconsistent")
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
    complete_bod = CuBIDS(data_root / "complete")
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

    # check IntendedForXX and FieldmapKeyXX are boolean now
    bool_IF = False
    bool_FMAP = False
    for row in range(len(csummary_df)):
        if str(csummary_df.loc[row, "UsedAsFieldmap"]) == "True":
            bool_IF = True
        if str(csummary_df.loc[row, "HasFieldmap"]) == "True":
            bool_FMAP = True
    assert bool_IF == True
    assert bool_FMAP == True

    # Test the incomplete
    ibod = CuBIDS(data_root / "inconsistent")
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
    assert isummary_df.shape[0] == 12

    # check that summary csv param group nums are in the right order
    # and check that param groups are sorted by count vals
    for i, (index, row) in enumerate(isummary_df.iterrows()):
        if i == len(isummary_df) -1:
            break
        # if key groups in rows i and i+1 are the same
        if isummary_df.iloc[i]['KeyGroup'] == \
            isummary_df.iloc[i+1]['KeyGroup']:
            # param group i = param group i+1
            assert isummary_df.iloc[i]['ParamGroup'] == \
                isummary_df.iloc[i+1]['ParamGroup'] - 1
            # and count i < count i + 1
            assert isummary_df.iloc[i]['Counts'] >= \
                isummary_df.iloc[i+1]['Counts']

    # check that files csv param group nums are in the right order
    for i, (index, row) in enumerate(ifiles_df.iterrows()):
        if i == len(ifiles_df) -1:
            break
        # if key groups in rows i and i+1 are the same
        if ifiles_df.iloc[i]['KeyGroup'] == \
            ifiles_df.iloc[i+1]['KeyGroup']:
            # param group i = param group i+1
            assert ifiles_df.iloc[i]['ParamGroup'] <= \
                ifiles_df.iloc[i+1]['ParamGroup']


def test_apply_csv_changes(tmp_path):
    # set up like narrative of user using this
    # similar to test csv creation
    # open the csv, rename a key group
    # save csv
    # call change key groups
    # give csv with no changes (make sure it does nothing)
    # make sure files you wanted to rename exist in the bids dir

    data_root = get_data(tmp_path)
    bids_dir = str(data_root / "complete")
    for scan in Path(bids_dir).rglob('sub-*/*/*/*.nii.gz'):

        # add extension files
        _add_ext_files(str(scan))

    # path_to_img = str(data_root / "complete/sub-01/ses-phdiff/fmap/sub-01_ses-phdiff_acq-v4_magnitude1.nii.gz")
    # _add_ext_files(path_to_img)

    has_events = False
    has_physio = False

    # check if events and physio files
    if Path(data_root /
            "complete/sub-01/ses-phdiff/fmap/sub-01_ses-phdiff_acq-v4_events.tsv").exists():
        has_events = True
    if Path(data_root /
            "complete/sub-01/ses-phdiff/fmap/sub-01_ses-phdiff_acq-v4_physio.tsv.gz").exists():
        has_physio = True


    complete_cubids = CuBIDS(data_root / "complete", use_datalad=True)
    complete_cubids.datalad_save()

    complete_cubids.get_CSVs(str(tmp_path / "originals"))

    # give csv with no changes (make sure it does nothing)
    complete_cubids.apply_csv_changes(str(tmp_path / "originals_summary.csv"),
                                    str(tmp_path / "originals_files.csv"),
                                    str(tmp_path / "modified1"))

    og_path = tmp_path / "originals_summary.csv"
    with og_path.open("r") as f:
        og_content = "".join(f.readlines())

    mod1_path = tmp_path / "modified1_summary.csv"
    with mod1_path.open("r") as f:
        mod1_content = "".join(f.readlines())

    assert og_content == mod1_content

    # edit the csv, add a RenameKeyGroup

    # _edit_csv(str(tmp_path / "originals_summary.csv"))
    complete_cubids.apply_csv_changes(str(tmp_path / "originals_summary.csv"),
                                    str(tmp_path / "originals_files.csv"),
                                    str(tmp_path / "modified2"))

    # check files df to make sure extension files also got renmaed
    mod_files = tmp_path / "modified2_files.csv"
    # ensure fmap didn't get renamed
    # assert Path(data_root /
    #     "complete/sub-01/ses-phdiff/fmap/sub-01_ses-phdiff_acq-v5_magnitude1.json").exists() == False
    assert Path(data_root /
        "complete/sub-01/ses-phdiff/fmap/sub-01_ses-phdiff_acq-v4_magnitude1.json").exists() == True

    # check that old names are gone!
    # assert Path(data_root /
    #     "complete/sub-01/ses-phdiff/fmap/sub-01_ses-phdiff_acq-v5_physio.tsv.gz").exists() == True
    assert Path(data_root /
        "complete/sub-01/ses-phdiff/fmap/sub-01_ses-phdiff_acq-v4_physio.tsv.gz").exists() == True

    mod2_path = tmp_path / "modified2_summary.csv"
    with mod2_path.open("r") as f:
        mod2_content = "".join(f.readlines())

    assert og_content == mod2_content

    # check that MergeInto = 0 deletes scan and associations
    deleted_keyparam = _add_deletion(mod2_path)
    assert deleted_keyparam in mod2_content

    # check to delete keyparam  exist
    mod2_files = tmp_path / "modified2_files.csv"
    with mod2_files.open("r") as f:
        mod2_f_content = "".join(f.readlines())
    assert deleted_keyparam in mod2_f_content

    # check scans and associations to be deleted are currently in the bids dir
    mod2_summary_df = pd.read_csv(mod2_path)
    mod2_files_df = pd.read_csv(str(tmp_path / "modified2_files.csv"))
    deleted_f = []

    for row in range(len(mod2_files_df)):
        if mod2_files_df.loc[row, 'KeyParamGroup'] == deleted_keyparam:
            deleted_f.append(mod2_files_df.loc[row, 'FilePath'])

    for f in deleted_f:
        assert Path(f).exists() == True
        assert Path(f.replace('nii.gz', 'json')).exists() == True

    # apply deletion
    complete_cubids.apply_csv_changes(mod2_path,
                                    str(tmp_path / "modified2_files.csv"),
                                    str(tmp_path / "deleted"))

    # make sure deleted_keyparam gone from files_csv
    deleted = tmp_path / "deleted_summary.csv"
    with deleted.open("r") as f:
        deleted_content = "".join(f.readlines())
    assert deleted_keyparam not in deleted_content

    # make sure deleted_keyparam gone from summary csv
    deleted_files = tmp_path / "deleted_files.csv"
    with deleted_files.open("r") as f:
        deleted_f_content = "".join(f.readlines())
    assert deleted_keyparam not in deleted_f_content

    # make sure deleted files are gone
    for f in deleted_f:
        assert Path(f).exists() == False
        assert Path(f.replace('nii.gz', 'json')).exists() == False


def test_session_apply(tmp_path):
    # set up like narrative of user using this
    # similar to test csv creation
    # open the csv, rename a key group
    # save csv
    # call change key groups
    # give csv with no changes (make sure it does nothing)
    # make sure files you wanted to rename exist in the bids dir

    data_root = get_data(tmp_path)
    bids_dir = str(data_root / "inconsistent")

    ses_cubids = CuBIDS(data_root / "inconsistent", acq_group_level='session', use_datalad=True)

    ses_cubids.get_CSVs(str(tmp_path / "originals"))

    # give csv and make sure 'session' is in summary both pre and post apply
    ses_cubids.apply_csv_changes(str(tmp_path / "originals_summary.csv"),
                                    str(tmp_path / "originals_files.csv"),
                                    str(tmp_path / "modified1"))

    og_path = tmp_path / "originals_summary.csv"
    with og_path.open("r") as f:
        og_content = "".join(f.readlines())

    mod1_path = tmp_path / "modified1_summary.csv"
    with mod1_path.open("r") as f:
        mod1_content = "".join(f.readlines())

    assert 'session-' in og_content
    assert 'session-' in mod1_content



def _add_deletion(summary_csv):
    df = pd.read_csv(summary_csv)
    df.loc[3, 'MergeInto'] = 0
    df.to_csv(summary_csv, index=False)
    return df.loc[3, 'KeyParamGroup']


# def _edit_csv(summary_csv):
#     df = pd.read_csv(summary_csv)
#     df['RenameKeyGroup'] = df['RenameKeyGroup'].apply(str)
#     df['KeyGroup'] = df['KeyGroup'].apply(str)
#     for row in range(len(df)):
#         if df.loc[row, 'KeyGroup'] == \
#             "acquisition-v4_datatype-fmap_fmap-magnitude1_suffix-magnitude1":
#             df.at[row, 'RenameKeyGroup'] = \
#                 "acquisition-v5_datatype-fmap_fmap-magnitude1_suffix-magnitude1"
#     df.to_csv(summary_csv)

def _add_ext_files(img_path):
    # add and save extension files in
    dwi_exts = ['.bval', '.bvec']

    # everyone gets a physio file
    no_suffix = img_path.rpartition('_')[0]
    physio_file = no_suffix + '_physio' + '.tsv.gz'
    # save ext file in img_path's parent dir
    Path(physio_file).touch()

    if '/dwi/' in img_path:
        # add bval and bvec
        for ext in dwi_exts:
            dwi_ext_file = img_path.replace(".nii.gz", "").replace(".nii", "") + ext
            Path(dwi_ext_file).touch()
    if 'bold' in img_path:
        no_suffix = img_path.rpartition('_')[0]
        bold_ext_file = no_suffix + '_events' + '.tsv'
        Path(bold_ext_file).touch()


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
    bod = CuBIDS(data_root, use_datalad=False)

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

    # Test that an uninitialized CuBIDS raises exceptions
    uninit_cubids = CuBIDS(data_root / "complete", use_datalad=False)

    # Ensure an exception is raised if trying to use datalad without
    # initializing
    with pytest.raises(Exception):
        uninit_cubids.is_datalad_clean()

    # initialize the datalad repository and try again
    uninit_cubids.init_datalad()
    uninit_cubids.datalad_save('Test save')
    assert uninit_cubids.is_datalad_clean()

    # Now, the datalad repository is initialized and saved.
    # Make sure if we make a new CuBIDS object it recognizes that
    # the datalad status is OK
    complete_bod = CuBIDS(data_root / "complete", use_datalad=True)

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
    assert not uninit_cubids.is_datalad_clean()
    assert not complete_bod.is_datalad_clean()

    # Attempt to undo a change before checking in changes
    with pytest.raises(Exception):
        uninit_cubids.datalad_undo_last_commit()

    # Perform a save
    uninit_cubids.datalad_save(message="TEST SAVE!")
    assert uninit_cubids.is_datalad_clean()

    # Now undo the most recent save
    uninit_cubids.datalad_undo_last_commit()

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


    # change this assert
    # assert parsed.shape[1] < 1


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

    assert type(parsed) == pd.core.frame.DataFrame


def test_docker():
    """Verify that docker is installed and the user has permission to
    run docker images.
    Returns
    -------
    -1  Docker can't be found
     0  Docker found, but user can't connect to daemon
     1  Test run OK
     """
    try:

        return_status = 1
        ret = subprocess.run(['docker', 'version'], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    except OSError as e:
        from errno import ENOENT
        if e.errno == ENOENT:
            print("Cannot find Docker engine!")
            return_status = 0
        raise e
    if ret.stderr.startswith(b"Cannot connect to the Docker daemon."):
        print("Cannot connect to Docker daemon!")
        return_status = 0
    assert return_status


# def test_image(image='pennlinc/bond:latest'):
#     """Check whether image is present on local system"""
#     ret = subprocess.run(['docker', 'images', '-q', image],
#                          stdout=subprocess.PIPE)

#     return_status = ret.stdout.decode('UTF-8')
#     assert return_status
