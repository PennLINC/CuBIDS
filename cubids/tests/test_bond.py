"""Tests for `cubids` package."""

import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from packaging.version import Version

from cubids.cubids import CuBIDS
from cubids.metadata_merge import merge_json_into_json, merge_without_overwrite
from cubids.tests.utils import (
    _add_deletion,
    _add_ext_files,
    _edit_a_json,
    _edit_a_nifti,
    _get_json_string,
    _remove_a_json,
    file_hash,
    get_data,
)
from cubids.validator import (
    build_validator_call,
    extract_summary_info,
    get_bids_validator_version,
    parse_validator_output,
    run_validator,
)

COMPLETE_KEY_GROUPS = [
    "datatype-anat_suffix-T1w",
    "datatype-dwi_suffix-dwi_acquisition-HASC55AP",
    "datatype-fmap_direction-PA_fmap-epi_suffix-epi",
    "datatype-fmap_fmap-magnitude1_suffix-magnitude1_acquisition-v4",
    "datatype-fmap_fmap-magnitude2_suffix-magnitude2_acquisition-v4",
    "datatype-fmap_fmap-phasediff_suffix-phasediff_acquisition-v4",
    "datatype-func_suffix-bold_task-rest",
]


def test_ok_json_merge(tmp_path):
    """Test that a successful merge can happen.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)

    # Test that a successful merge can happen
    dest_json = (
        data_root
        / "inconsistent"
        / "sub-02"
        / "ses-phdiff"
        / "dwi"
        / "sub-02_ses-phdiff_acq-HASC55AP_dwi.json"
    )
    orig_dest_json_content = _get_json_string(dest_json)
    source_json = (
        data_root
        / "inconsistent"
        / "sub-03"
        / "ses-phdiff"
        / "dwi"
        / "sub-03_ses-phdiff_acq-HASC55AP_dwi.json"
    )

    merge_return = merge_json_into_json(source_json, dest_json)
    assert merge_return == 0
    assert not _get_json_string(dest_json) == orig_dest_json_content


def test_ok_json_merge_cli(tmp_path):
    """Test that a successful merge can happen using the CLI.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)

    # Test that a successful merge can happen
    dest_json = (
        data_root
        / "inconsistent"
        / "sub-02"
        / "ses-phdiff"
        / "dwi"
        / "sub-02_ses-phdiff_acq-HASC55AP_dwi.json"
    )
    orig_dest_json_content = _get_json_string(dest_json)
    source_json = (
        data_root
        / "inconsistent"
        / "sub-03"
        / "ses-phdiff"
        / "dwi"
        / "sub-03_ses-phdiff_acq-HASC55AP_dwi.json"
    )

    assert os.path.isfile(source_json)
    assert os.path.isfile(dest_json)
    merge_proc = subprocess.run(["cubids", "bids-sidecar-merge", str(source_json), str(dest_json)])
    assert merge_proc.returncode == 0
    assert not _get_json_string(dest_json) == orig_dest_json_content


def test_get_param_groups(tmp_path):
    """Test the retrieval of parameter groups.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)
    bod = CuBIDS(data_root / "inconsistent", use_datalad=True)
    entity_sets = bod.get_entity_sets()
    bod._cache_fieldmaps()

    for entity_set in entity_sets:
        ret = bod.get_param_groups_from_entity_set(entity_set)
        assert sum(ret[1].Counts) == ret[1].loc[0, "EntitySetCount"]


def test_copy_exemplars(tmp_path):
    """Test the copying of exemplars.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)
    bod = CuBIDS(data_root / "complete", use_datalad=True)
    tsv_prefix = str(tmp_path / "tsvs")
    bod.get_tsvs(tsv_prefix)
    acq_group_tsv = tsv_prefix + "_AcqGrouping.tsv"
    print("ACQ GROUP PATH: ", acq_group_tsv)
    exemplars_dir = str(tmp_path / "exemplars")
    print("EXEMPLARS DIR: ", exemplars_dir)
    df = pd.read_table(acq_group_tsv)

    bod.copy_exemplars(exemplars_dir, acq_group_tsv, min_group_size=1)

    # check exemplar dir got created and has the correct number of subs
    cntr = 0
    for path in Path(exemplars_dir).glob("sub-*"):
        cntr += 1
    assert cntr == len(df.drop_duplicates(subset=["AcqGroup"]))

    # check that dataset_description.json got added
    assert Path(exemplars_dir + "/dataset_description.json").exists()


def test_purge_no_datalad(tmp_path):
    """Test the purge operation without using DataLad.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)
    scans = []
    scan_name = "sub-03/ses-phdiff/func/sub-03_ses-phdiff_task-rest_bold.nii.gz"
    json_name = (
        data_root
        / "complete"
        / "sub-03"
        / "ses-phdiff"
        / "func"
        / "sub-03_ses-phdiff_task-rest_bold.json"
    )
    scans.append(scan_name)
    scans.append("sub-01/ses-phdiff/dwi/sub-01_ses-phdiff_acq-HASC55AP_dwi.nii.gz")

    # create and save .txt with list of scans
    purge_path = str(tmp_path / "purge_scans.txt")
    with open(purge_path, "w") as filehandle:
        for listitem in scans:
            filehandle.write(f"{listitem}\n")

    bod = CuBIDS(data_root / "complete", use_datalad=False)

    assert Path(data_root / "complete" / scan_name).exists()
    assert Path(json_name).exists()

    # Check that IntendedFor purge worked
    with open(
        str(
            data_root
            / "complete"
            / "sub-01"
            / "ses-phdiff"
            / "fmap"
            / "sub-01_ses-phdiff_acq-v4_phasediff.json"
        )
    ) as f:
        j_dict = json.load(f)

    assert "ses-phdiff/dwi/sub-01_ses-phdiff_acq-HASC55AP_dwi.nii.gz" in j_dict.values()
    assert isinstance(j_dict["IntendedFor"], str)
    # PURGE
    bod.purge(purge_path)

    with open(
        str(
            data_root
            / "complete"
            / "sub-01"
            / "ses-phdiff"
            / "fmap"
            / "sub-01_ses-phdiff_acq-v4_phasediff.json"
        )
    ) as f:
        purged_dict = json.load(f)

    assert not Path(data_root / "complete" / scan_name).exists()
    assert not Path(json_name).exists()
    assert "ses-phdiff/dwi/sub-01_ses-phdiff_acq-HASC55AP_dwi.nii.gz" not in purged_dict.values()
    assert isinstance(purged_dict["IntendedFor"], list)
    assert purged_dict["IntendedFor"] == []


def test_purge(tmp_path):
    """Test the purge operation using DataLad.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)
    scans = []
    scan_name = "sub-03/ses-phdiff/func/sub-03_ses-phdiff_task-rest_bold.nii.gz"
    json_name = (
        data_root
        / "complete"
        / "sub-03"
        / "ses-phdiff"
        / "func"
        / "sub-03_ses-phdiff_task-rest_bold.json"
    )
    scans.append(scan_name)
    purge_path = str(tmp_path / "purge_scans.txt")

    with open(purge_path, "w") as filehandle:
        for listitem in scans:
            filehandle.write(f"{listitem}\n")
    bod = CuBIDS(data_root / "complete", use_datalad=True)
    bod.datalad_save()

    assert bod.is_datalad_clean()
    assert Path(data_root / "complete" / scan_name).exists()
    assert Path(json_name).exists()

    # create and save .txt with list of scans
    bod.purge(purge_path)

    assert not Path(scan_name).exists()
    assert not Path(json_name).exists()


def test_bad_json_merge(tmp_path):
    """Test that an unsuccessful merge returns an error.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)

    # Test that a successful merge can happen
    dest_json = (
        data_root
        / "inconsistent"
        / "sub-02"
        / "ses-phdiff"
        / "dwi"
        / "sub-02_ses-phdiff_acq-HASC55AP_dwi.json"
    )
    orig_dest_json_content = _get_json_string(dest_json)
    invalid_source_json = (
        data_root
        / "inconsistent"
        / "sub-01"
        / "ses-phdiff"
        / "dwi"
        / "sub-01_ses-phdiff_acq-HASC55AP_dwi.json"
    )

    assert merge_json_into_json(invalid_source_json, dest_json) > 0
    assert _get_json_string(dest_json) == orig_dest_json_content


def test_bad_json_merge_cli(tmp_path):
    """Test that an unsuccessful merge returns an error using the CLI.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)

    # Test that a successful merge can happen
    dest_json = (
        data_root
        / "inconsistent"
        / "sub-02"
        / "ses-phdiff"
        / "dwi"
        / "sub-02_ses-phdiff_acq-HASC55AP_dwi.json"
    )
    orig_dest_json_content = _get_json_string(dest_json)
    invalid_source_json = (
        data_root
        / "inconsistent"
        / "sub-01"
        / "ses-phdiff"
        / "dwi"
        / "sub-01_ses-phdiff_acq-HASC55AP_dwi.json"
    )

    merge_proc = subprocess.run(
        ["cubids", "bids-sidecar-merge", str(invalid_source_json), str(dest_json)]
    )
    assert merge_proc.returncode > 0
    assert _get_json_string(dest_json) == orig_dest_json_content


def test_add_nifti_info_datalad(tmp_path):
    """Test adding NIfTI info to sidecars using DataLad.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)
    bod = CuBIDS(data_root / "complete", use_datalad=True, force_unlock=True)
    tsv_prefix = str(tmp_path / "tsvs")
    bod.get_tsvs(tsv_prefix)
    summary_tsv = tsv_prefix + "_summary.tsv"
    summary_df = pd.read_table(summary_tsv)
    l_cols = summary_df.columns.tolist()
    assert "NumVolumes" not in l_cols
    assert "Obliquity" not in l_cols

    # now add nifti info
    bod.add_nifti_info()

    found_fields = set()
    for json_file in Path(bod.path).rglob("*.json"):
        if ".git" not in str(json_file):
            with open(json_file, "r") as jsonr:
                metadata = json.load(jsonr)
            found_fields.update(metadata.keys())
    assert "NumVolumes" in found_fields
    assert "Obliquity" in found_fields
    assert "ImageOrientation" in found_fields

    # nifti_tsv_prefix = str(tmp_path / "nifti_tsvs")
    # bod.get_tsvs(nifti_tsv_prefix)
    # nifti_summary_tsv = nifti_tsv_prefix + "_summary.tsv"
    # nifti_summary_df = pd.read_table(nifti_summary_tsv)
    # nifti_l_cols = nifti_summary_df.columns.tolist()
    # assert 'NumVolumes' in nifti_l_cols
    # assert 'Obliquity' in nifti_l_cols
    # assert 'ImageOrientation' in nifti_l_cols


def test_add_nifti_info_no_datalad(tmp_path):
    """Test adding NIfTI info to sidecars without using DataLad.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)
    bod = CuBIDS(data_root / "complete", use_datalad=False, force_unlock=False)
    bod.add_nifti_info()

    found_fields = set()
    for json_file in Path(bod.path).rglob("*.json"):
        if ".git" not in str(json_file):
            with open(json_file, "r") as jsonr:
                metadata = json.load(jsonr)
            found_fields.update(metadata.keys())
    assert "NumVolumes" in found_fields
    assert "Obliquity" in found_fields
    assert "ImageOrientation" in found_fields

    # tsv_prefix = str(tmp_path / "tsvs")
    # bod.get_tsvs(tsv_prefix)
    # summary_tsv = tsv_prefix + "_summary.tsv"
    # summary_df = pd.read_table(summary_tsv)
    # l_cols = summary_df.columns.tolist()
    # assert 'NumVolumes' in l_cols
    # assert 'Obliquity' in l_cols


# TODO: add tests that return an error for invalid merge


def test_tsv_merge_no_datalad(tmp_path):
    """Test merging TSV files without using DataLad.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)
    bod = CuBIDS(data_root / "inconsistent", use_datalad=False)

    # Get an initial grouping summary and files list
    tsv_prefix = str(tmp_path / "originals")
    bod.get_tsvs(tsv_prefix)
    original_summary_tsv = tsv_prefix + "_summary.tsv"
    original_files_tsv = tsv_prefix + "_files.tsv"

    # give tsv with no changes (make sure it does nothing)
    bod.apply_tsv_changes(original_summary_tsv, original_files_tsv, str(tmp_path / "unmodified"))

    # these will not actually be equivalent because of the auto renames
    assert file_hash(original_summary_tsv) != file_hash(tmp_path / "unmodified_summary.tsv")

    # Find the dwi with no FlipAngle
    summary_df = pd.read_table(original_summary_tsv)
    (fa_nan_dwi_row,) = np.flatnonzero(
        np.isnan(summary_df.FlipAngle)
        & summary_df.EntitySet.str.fullmatch("datatype-dwi_suffix-dwi_acquisition-HASC55AP")
    )
    # Find the dwi with and EchoTime ==
    (complete_dwi_row,) = np.flatnonzero(
        summary_df.EntitySet.str.fullmatch("datatype-dwi_suffix-dwi_acquisition-HASC55AP")
        & (summary_df.FlipAngle == 90.0)
        & (summary_df.EchoTime > 0.05)
    )
    (cant_merge_echotime_dwi_row,) = np.flatnonzero(
        summary_df.EntitySet.str.fullmatch("datatype-dwi_suffix-dwi_acquisition-HASC55AP")
        & (summary_df.FlipAngle == 90.0)
        & (summary_df.EchoTime < 0.05)
    )

    # Set a legal MergeInto value. This effectively fills in data
    # where there was previously as missing FlipAngle
    summary_df.loc[fa_nan_dwi_row, "MergeInto"] = summary_df.ParamGroup[complete_dwi_row]

    valid_tsv_file = tsv_prefix + "_valid_summary.tsv"
    summary_df.to_csv(valid_tsv_file, sep="\t", index=False)

    # about to apply merges!

    bod.apply_tsv_changes(valid_tsv_file, original_files_tsv, str(tmp_path / "ok_modified"))

    assert not file_hash(original_summary_tsv) == file_hash(tmp_path / "ok_modified_summary.tsv")

    # Add an illegal merge to MergeInto
    summary_df.loc[cant_merge_echotime_dwi_row, "MergeInto"] = summary_df.ParamGroup[
        complete_dwi_row
    ]
    invalid_tsv_file = tsv_prefix + "_invalid_summary.tsv"
    summary_df.to_csv(invalid_tsv_file, sep="\t", index=False)

    with pytest.raises(Exception):
        bod.apply_tsv_changes(
            invalid_tsv_file, str(tmp_path / "originals_files.tsv"), str(tmp_path / "ok_modified")
        )


def test_tsv_merge_changes(tmp_path):
    """Test merging TSV files with changes.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)
    bod = CuBIDS(data_root / "inconsistent", use_datalad=True)
    bod.datalad_save()
    assert bod.is_datalad_clean()

    # Get an initial grouping summary and files list
    tsv_prefix = str(tmp_path / "originals")
    bod.get_tsvs(tsv_prefix)
    original_summary_tsv = tsv_prefix + "_summary.tsv"
    original_files_tsv = tsv_prefix + "_files.tsv"

    # give tsv with no changes (make sure it does nothing except rename)
    bod.apply_tsv_changes(original_summary_tsv, original_files_tsv, str(tmp_path / "unmodified"))
    orig = pd.read_table(original_summary_tsv)
    # TEST RenameEntitySet column got populated CORRECTLY
    for row in range(len(orig)):
        if orig.loc[row, "ParamGroup"] != 1:
            assert str(orig.loc[row, "RenameEntitySet"]) != "nan"

    # TESTING RENAMES GOT APPLIED
    applied_summary_df = pd.read_table(str(tmp_path / "unmodified_summary.tsv"))
    applied_files_df = pd.read_table(str(tmp_path / "unmodified_files.tsv"))

    # Check for inconsistencies between FilePath and KeyParamGroup
    odd = []
    for _, row in applied_files_df.iterrows():
        if "VARIANT" in row["FilePath"] and "VARIANT" not in row["KeyParamGroup"]:
            odd.append(row["FilePath"])

    # Track KeyParamGroups for files with inconsistencies
    occurrences = {}
    for _, row in applied_files_df.iterrows():
        fp = row["FilePath"]
        if fp in odd:
            if fp in occurrences.keys():
                occurrences[fp].append(row["KeyParamGroup"])
            else:
                occurrences[fp] = [row["KeyParamGroup"]]

    # Ensure no rows were lost
    assert len(orig) == len(applied_summary_df)

    # Check that all the RenameEntitySet values are in the renamed entity sets
    renamed = True
    new_keys = applied_summary_df["EntitySet"].tolist()
    for _, row in orig.iterrows():
        if row["Modality"] == "fmap":
            # Ignore field map renaming
            continue

        res = row["RenameEntitySet"]
        if isinstance(res, str) and (res != "nan") and (res not in new_keys):
            renamed = False

    assert renamed, orig["RenameEntitySet"].tolist()

    # will no longer be equal because of auto rename!
    assert file_hash(original_summary_tsv) != file_hash(tmp_path / "unmodified_summary.tsv")

    # Find the dwi with no FlipAngle
    summary_df = pd.read_table(original_summary_tsv)
    (fa_nan_dwi_row,) = np.flatnonzero(
        np.isnan(summary_df.FlipAngle)
        & summary_df.EntitySet.str.fullmatch("datatype-dwi_suffix-dwi_acquisition-HASC55AP")
    )
    # Find the dwi with and EchoTime ==
    (complete_dwi_row,) = np.flatnonzero(
        summary_df.EntitySet.str.fullmatch("datatype-dwi_suffix-dwi_acquisition-HASC55AP")
        & (summary_df.FlipAngle == 90.0)
        & (summary_df.EchoTime > 0.05)
    )
    (cant_merge_echotime_dwi_row,) = np.flatnonzero(
        summary_df.EntitySet.str.fullmatch("datatype-dwi_suffix-dwi_acquisition-HASC55AP")
        & (summary_df.FlipAngle == 90.0)
        & (summary_df.EchoTime < 0.05)
    )

    # Set a legal MergeInto value. This effectively fills in data
    # where there was previously as missing FlipAngle
    summary_df.loc[fa_nan_dwi_row, "MergeInto"] = summary_df.ParamGroup[complete_dwi_row]

    valid_tsv_file = tsv_prefix + "_valid_summary.tsv"
    summary_df.to_csv(valid_tsv_file, sep="\t", index=False)

    # about to merge
    bod.apply_tsv_changes(valid_tsv_file, original_files_tsv, str(tmp_path / "ok_modified"))

    assert not file_hash(original_summary_tsv) == file_hash(tmp_path / "ok_modified_summary.tsv")

    # Add an illegal merge to MergeInto
    summary_df.loc[cant_merge_echotime_dwi_row, "MergeInto"] = summary_df.ParamGroup[
        complete_dwi_row
    ]
    invalid_tsv_file = tsv_prefix + "_invalid_summary.tsv"
    summary_df.to_csv(invalid_tsv_file, sep="\t", index=False)

    with pytest.raises(Exception):
        bod.apply_tsv_changes(
            invalid_tsv_file, str(tmp_path / "originals_files.tsv"), str(tmp_path / "ok_modified")
        )

    # Make sure MergeInto == 0 deletes the param group and all associations
    # summary_df = pd.read_table(original_summary_tsv)
    # summary_df.loc[fa_nan_dwi_row, "MergeInto"] = 0
    # delete_group = summary_df.loc[fa_nan_dwi_row, "KeyParamGroup"]

    # # files_df = pd.read_table(original_files_tsv)
    # # for row in files_df:
    # #     if files_df.iloc[row]['KeyParamGroup'] == delete_group:
    # #         filename = files_df.iloc[row]['FilePath']
    # #         file_to_rem = Path(filename)
    # #         file_to_rem.unlink()

    # delete_tsv_file = tsv_prefix + "_delete_summary.tsv"
    # summary_df.to_csv(delete_tsv_file, index=False)

    # bod.apply_tsv_changes(delete_tsv_file,
    #                       original_files_tsv,
    #                       str(tmp_path / "ok_deleted"))

    # del_summary_tsv = str(tmp_path / "ok_deleted")

    # original_summary_tsv = tsv_prefix + "_summary.tsv"
    # original_files_tsv = tsv_prefix + "_files.tsv"

    # assert delete_group not in tmp_path / "ok_deleted_summary.tsv"


def test_merge_without_overwrite():
    """Test merge_without_overwrite.

    Test that metadata fields are merged without overwriting existing values.
    """
    meta1 = {
        "ManualCheck": 1.0,
        "RenameEntitySet": np.nan,
        "MergeInto": 2.0,
        "EntitySet": "datatype-func_suffix-bold_task-rest",
        "ParamGroup": 12,
        "Counts": 2,
        "DwellTime": 2.6e-06,
        "EchoTime": 0.03,
        "EffectiveEchoSpacing": 0.000580013,
        "FieldmapKey00": "datatype-fmap_direction-AP_fmap-epi_suffix-epi_acquisition-fMRI",
        "FieldmapKey01": "datatype-fmap_direction-PA_fmap-epi_run-1_suffix-epi_acquisition-fMRI",
        "FieldmapKey02": "datatype-fmap_direction-PA_fmap-epi_run-2_suffix-epi_acquisition-fMRI",
        "FieldmapKey03": np.nan,
        "FieldmapKey04": np.nan,
        "FieldmapKey05": np.nan,
        "FieldmapKey06": np.nan,
        "FieldmapKey07": np.nan,
        "FlipAngle": 31.0,
        "IntendedForKey00": np.nan,
        "IntendedForKey01": np.nan,
        "IntendedForKey02": np.nan,
        "IntendedForKey03": np.nan,
        "IntendedForKey04": np.nan,
        "IntendedForKey05": np.nan,
        "IntendedForKey06": np.nan,
        "IntendedForKey07": np.nan,
        "IntendedForKey08": np.nan,
        "IntendedForKey09": np.nan,
        "MultibandAccelerationFactor": 6.0,
        "NSliceTimes": 60,
        "ParallelReductionFactorInPlane": np.nan,
        "PartialFourier": 1.0,
        "PhaseEncodingDirection": "j-",
        "RepetitionTime": 0.8,
        "TotalReadoutTime": 0.0481411,
    }

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


def test_entitysets(tmp_path):
    """Test entitysets.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)

    # Test the complete data
    complete_bod = CuBIDS(data_root / "complete")
    complete_misfit_fmaps = complete_bod._cache_fieldmaps()
    # There should be no unpaired fieldmaps
    assert len(complete_misfit_fmaps) == 0

    # Test that the correct entity sets are found
    entity_sets = complete_bod.get_entity_sets()
    assert entity_sets == COMPLETE_KEY_GROUPS

    # Test the incomplete
    ibod = CuBIDS(data_root / "inconsistent")
    inc_misfit_fmaps = ibod._cache_fieldmaps()
    assert len(inc_misfit_fmaps) == 1

    # There will still be the same number of entity sets
    ientity_sets = ibod.get_entity_sets()
    assert ientity_sets == COMPLETE_KEY_GROUPS


def test_tsv_creation(tmp_path):
    """Test the Entity Set and Parameter Group creation on sample data.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)

    # Test the complete data
    complete_bod = CuBIDS(data_root / "complete")
    complete_misfit_fmaps = complete_bod._cache_fieldmaps()
    # There should be no unpaired fieldmaps
    assert len(complete_misfit_fmaps) == 0

    # Test that the correct entity sets are found
    entity_sets = complete_bod.get_entity_sets()
    assert entity_sets == COMPLETE_KEY_GROUPS

    # Get the tsvs from the complete data
    cfiles_df, csummary_df = complete_bod.get_param_groups_dataframes()

    # Make sure we got all 21 of the files
    assert cfiles_df.shape[0] == 21

    # This data should have the same number of param
    # groups as entity sets
    assert csummary_df.shape[0] == len(COMPLETE_KEY_GROUPS)

    # check IntendedForXX and FieldmapKeyXX are boolean now
    bool_IF = False
    bool_FMAP = False
    for row in range(len(csummary_df)):
        if str(csummary_df.loc[row, "UsedAsFieldmap"]) == "True":
            bool_IF = True

        if str(csummary_df.loc[row, "HasFieldmap"]) == "True":
            bool_FMAP = True

    assert bool_IF
    assert bool_FMAP

    # Test the incomplete
    ibod = CuBIDS(data_root / "inconsistent")
    inc_misfit_fmaps = ibod._cache_fieldmaps()
    assert len(inc_misfit_fmaps) == 1

    # There will still be the same number of entity sets
    ientity_sets = ibod.get_entity_sets()
    assert ientity_sets == COMPLETE_KEY_GROUPS

    # Get the tsvs from the inconsistent data
    ifiles_df, isummary_df = ibod.get_param_groups_dataframes()

    # There are still 21 files
    assert ifiles_df.shape[0] == 21

    # But now there are more parameter groups
    assert isummary_df.shape[0] == 12

    # check that summary tsv param group nums are in the right order
    # and check that param groups are sorted by count vals
    for i, (_, row) in enumerate(isummary_df.iterrows()):
        if i == len(isummary_df) - 1:
            break
        # if entity sets in rows i and i+1 are the same
        if isummary_df.iloc[i]["EntitySet"] == isummary_df.iloc[i + 1]["EntitySet"]:
            # param group i = param group i+1
            assert isummary_df.iloc[i]["ParamGroup"] == isummary_df.iloc[i + 1]["ParamGroup"] - 1
            # and count i < count i + 1
            assert isummary_df.iloc[i]["Counts"] >= isummary_df.iloc[i + 1]["Counts"]

    # check that files tsv param group nums are in the right order
    for i, (_, row) in enumerate(ifiles_df.iterrows()):
        if i == len(ifiles_df) - 1:
            break
        # if entity sets in rows i and i+1 are the same
        if ifiles_df.iloc[i]["EntitySet"] == ifiles_df.iloc[i + 1]["EntitySet"]:
            # param group i = param group i+1
            assert ifiles_df.iloc[i]["ParamGroup"] <= ifiles_df.iloc[i + 1]["ParamGroup"]


def test_apply_tsv_changes(tmp_path):
    """Test apply_tsv_changes.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    # set up like narrative of user using this
    # similar to test tsv creation
    # open the tsv, rename a entity set
    # save tsv
    # call change entity sets
    # give tsv with no changes (make sure it does nothing)
    # make sure files you wanted to rename exist in the bids dir

    data_root = get_data(tmp_path)
    bids_dir = str(data_root / "complete")
    for scan in Path(bids_dir).rglob("sub-*/*/*/*.nii.gz"):
        # add extension files
        _add_ext_files(str(scan))

    # path_to_img = str(
    #    data_root / "complete/sub-01/ses-phdiff/fmap/sub-01_ses-phdiff_acq-v4_magnitude1.nii.gz"
    # )
    # _add_ext_files(path_to_img)

    complete_cubids = CuBIDS(data_root / "complete", use_datalad=True)
    complete_cubids.datalad_save()

    complete_cubids.get_tsvs(str(tmp_path / "originals"))

    # give tsv with no changes (make sure it does nothing)
    complete_cubids.apply_tsv_changes(
        str(tmp_path / "originals_summary.tsv"),
        str(tmp_path / "originals_files.tsv"),
        str(tmp_path / "modified1"),
    )

    og_path = tmp_path / "originals_summary.tsv"
    with og_path.open("r") as f:
        og_content = "".join(f.readlines())

    mod1_path = tmp_path / "modified1_summary.tsv"
    with mod1_path.open("r") as f:
        mod1_content = "".join(f.readlines())

    assert og_content == mod1_content

    # edit the tsv, add a RenameEntitySet

    # _edit_tsv(str(tmp_path / "originals_summary.tsv"))
    complete_cubids.apply_tsv_changes(
        str(tmp_path / "originals_summary.tsv"),
        str(tmp_path / "originals_files.tsv"),
        str(tmp_path / "modified2"),
    )

    # check files df to make sure extension files also got renmaed
    # mod_files = tmp_path / "modified2_files.tsv"
    # ensure fmap didn't get renamed
    # assert not Path(
    #    data_root /
    #    "complete/sub-01/ses-phdiff/fmap/sub-01_ses-phdiff_acq-v5_magnitude1.json"
    # ).exists()
    assert Path(
        data_root / "complete/sub-01/ses-phdiff/fmap/sub-01_ses-phdiff_acq-v4_magnitude1.json"
    ).exists()

    # check that old names are gone!
    # assert Path(
    #    data_root / "complete/sub-01/ses-phdiff/fmap/sub-01_ses-phdiff_acq-v5_physio.tsv.gz"
    # ).exists()
    assert Path(
        data_root / "complete/sub-01/ses-phdiff/fmap/sub-01_ses-phdiff_acq-v4_physio.tsv.gz"
    ).exists()

    mod2_path = tmp_path / "modified2_summary.tsv"
    with mod2_path.open("r") as f:
        mod2_content = "".join(f.readlines())

    assert og_content == mod2_content

    # check that MergeInto = 0 deletes scan and associations
    deleted_keyparam = _add_deletion(mod2_path)
    assert deleted_keyparam in mod2_content

    # check to delete keyparam  exist
    mod2_files = tmp_path / "modified2_files.tsv"
    with mod2_files.open("r") as f:
        mod2_f_content = "".join(f.readlines())
    assert deleted_keyparam in mod2_f_content

    # check scans and associations to be deleted are currently in the bids dir
    # mod2_summary_df = pd.read_table(mod2_path)
    mod2_files_df = pd.read_table(str(tmp_path / "modified2_files.tsv"))
    deleted_f = []

    for row in range(len(mod2_files_df)):
        if mod2_files_df.loc[row, "KeyParamGroup"] == deleted_keyparam:
            deleted_f.append(mod2_files_df.loc[row, "FilePath"])

    for f in deleted_f:
        assert Path(str(data_root / "complete") + f).exists()
        assert Path(str(data_root / "complete") + f.replace("nii.gz", "json")).exists()

    # apply deletion
    complete_cubids.apply_tsv_changes(
        mod2_path, str(tmp_path / "modified2_files.tsv"), str(tmp_path / "deleted")
    )

    # make sure deleted_keyparam gone from files_tsv
    deleted = tmp_path / "deleted_summary.tsv"
    with deleted.open("r") as f:
        deleted_content = "".join(f.readlines())
    assert deleted_keyparam not in deleted_content

    # make sure deleted_keyparam gone from summary tsv
    deleted_files = tmp_path / "deleted_files.tsv"
    with deleted_files.open("r") as f:
        deleted_f_content = "".join(f.readlines())
    assert deleted_keyparam not in deleted_f_content

    # make sure deleted files are gone
    for f in deleted_f:
        assert not Path(f).exists()
        assert not Path(f.replace("nii.gz", "json")).exists()


def test_session_apply(tmp_path):
    """Test session_apply.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    # set up like narrative of user using this
    # similar to test tsv creation
    # open the tsv, rename a entity set
    # save tsv
    # call change entity sets
    # give tsv with no changes (make sure it does nothing)
    # make sure files you wanted to rename exist in the bids dir

    data_root = get_data(tmp_path)

    ses_cubids = CuBIDS(
        data_root / "inconsistent",
        acq_group_level="session",
        use_datalad=True,
    )

    ses_cubids.get_tsvs(str(tmp_path / "originals"))

    # give tsv and make sure 'session' is in summary both pre and post apply
    ses_cubids.apply_tsv_changes(
        str(tmp_path / "originals_summary.tsv"),
        str(tmp_path / "originals_files.tsv"),
        str(tmp_path / "modified1"),
    )

    og_path = tmp_path / "originals_summary.tsv"
    with og_path.open("r") as f:
        og_content = "".join(f.readlines())

    mod1_path = tmp_path / "modified1_summary.tsv"
    with mod1_path.open("r") as f:
        mod1_content = "".join(f.readlines())

    assert "session-" in og_content
    assert "session-" in mod1_content


def test_remove_fields(tmp_path):
    """Test that we metadata fields are detected and removed.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)
    bod = CuBIDS(data_root, use_datalad=False)

    # Get the metadata fields
    metadata_fields = bod.get_all_metadata_fields()
    assert metadata_fields

    # Simulate some fields we might want to remove
    fields_to_remove = [
        "DeviceSerialNumber",
        "AcquisitionTime",
        "InstitutionAddress",
        "InstitutionName",
        "StationName",
        "NotARealField",
    ]

    bod.remove_metadata_fields(fields_to_remove)
    new_fields = bod.get_all_metadata_fields()
    assert not set(new_fields).intersection(fields_to_remove)


def test_datalad_integration(tmp_path):
    """Test that datalad works for basic file modification operations.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
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
    uninit_cubids.datalad_save("Test save")
    assert uninit_cubids.is_datalad_clean()

    # Now, the datalad repository is initialized and saved.
    # Make sure if we make a new CuBIDS object it recognizes that
    # the datalad status is OK
    complete_bod = CuBIDS(data_root / "complete", use_datalad=True)

    assert complete_bod.datalad_ready
    assert complete_bod.is_datalad_clean()

    # Test clean and revert functionality
    test_file = (
        data_root
        / "complete"
        / "sub-03"
        / "ses-phdiff"
        / "func"
        / "sub-03_ses-phdiff_task-rest_bold.json"
    )
    test_binary = (
        data_root
        / "complete"
        / "sub-03"
        / "ses-phdiff"
        / "func"
        / "sub-03_ses-phdiff_task-rest_bold.nii.gz"
    )

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


def test_validator(tmp_path):
    """Test validator.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)

    # test the validator in valid dataset
    call = build_validator_call(str(data_root) + "/complete")
    ret = run_validator(call)

    assert ret.returncode == 0
    parsed = parse_validator_output(ret.stdout.decode("UTF-8"))

    # change this assert
    # assert parsed.shape[1] < 1

    # bungle some data and test

    # get data
    test_file = (
        data_root
        / "complete"
        / "sub-03"
        / "ses-phdiff"
        / "func"
        / "sub-03_ses-phdiff_task-rest_bold.json"
    )
    test_binary = (
        data_root
        / "complete"
        / "sub-03"
        / "ses-phdiff"
        / "func"
        / "sub-03_ses-phdiff_task-rest_bold.nii.gz"
    )

    # Edit the files
    _edit_a_nifti(test_binary)
    _remove_a_json(test_file)

    call = build_validator_call(str(data_root) + "/complete")
    ret = run_validator(call)

    assert ret.returncode == 1

    parsed = parse_validator_output(ret.stdout.decode("UTF-8"))

    assert isinstance(parsed, pd.DataFrame)


def test_bids_version(tmp_path):
    """Test workflows.bids_version.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.
    """
    data_root = get_data(tmp_path)
    bids_dir = Path(data_root) / "complete"

    # Ensure the test directory exists
    assert bids_dir.exists()

    # test the validator in valid dataset
    call = build_validator_call(bids_dir)
    ret = run_validator(call)

    assert ret.returncode == 0

    decoded = ret.stdout.decode("UTF-8")

    # Get the BIDS validator version
    validator_version = Version(get_bids_validator_version()["ValidatorVersion"])
    # Extract schemaVersion
    schema_version = Version(extract_summary_info(decoded)["SchemaVersion"])

    # Set baseline versions to compare against
    min_validator_version = Version("2.0.0")
    min_schema_version = Version("0.11.3")

    assert (
        validator_version >= min_validator_version
    ), f"Validator version {validator_version} is less than minimum {min_validator_version}"
    assert (
        schema_version >= min_schema_version
    ), f"Schema version {schema_version} is less than minimum {min_schema_version}"


# def test_image(image='pennlinc/bond:latest'):
#     """Check whether image is present on local system."""
#     ret = subprocess.run(['docker', 'images', '-q', image],
#                          stdout=subprocess.PIPE)

#     return_status = ret.stdout.decode('UTF-8')
#     assert return_status
