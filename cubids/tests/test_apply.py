"""Test cubids apply."""

import pandas as pd
import pytest


@pytest.fixture(scope="module")
def files_data():
    """A dictionary describing a CuBIDS files tsv file for testing.

    Returns
    -------
    dict
        A dictionary containing file data for longitudinal and cross-sectional datasets.
    """
    dict_ = {
        "longitudinal": {
            "ParamGroup": [1, 1, 1, 1],
            "EntitySet": [
                "datatype-anat_suffix-T1w",
                "datatype-dwi_direction-AP_run-01_suffix-dwi",
                "datatype-fmap_direction-AP_fmap-epi_suffix-epi",
                "datatype-fmap_direction-PA_fmap-epi_suffix-epi",
            ],
            "FilePath": [
                "/sub-01/ses-01/anat/sub-01_ses-01_T1w.nii.gz",
                "/sub-01/ses-01/dwi/sub-01_ses-01_dir-AP_run-01_dwi.nii.gz",
                "/sub-01/ses-01/fmap/sub-01_ses-01_dir-AP_epi.nii.gz",
                "/sub-01/ses-01/fmap/sub-01_ses-01_dir-PA_epi.nii.gz",
            ],
            "KeyParamGroup": [
                "datatype-anat_suffix-T1w__1",
                "datatype-dwi_direction-AP_run-01_suffix-dwi__1",
                "datatype-fmap_direction-AP_fmap-epi_suffix-epi__1",
                "datatype-fmap_direction-PA_fmap-epi_suffix-epi__1",
            ],
        },
        "cross-sectional": {
            "ParamGroup": [1, 1, 1, 1],
            "EntitySet": [
                "datatype-anat_suffix-T1w",
                "datatype-dwi_direction-AP_run-01_suffix-dwi",
                "datatype-fmap_direction-AP_fmap-epi_suffix-epi",
                "datatype-fmap_direction-PA_fmap-epi_suffix-epi",
            ],
            "FilePath": [
                "/sub-01/anat/sub-01_T1w.nii.gz",
                "/sub-01/dwi/sub-01_dir-AP_run-01_dwi.nii.gz",
                "/sub-01/fmap/sub-01_dir-AP_epi.nii.gz",
                "/sub-01/fmap/sub-01_dir-PA_epi.nii.gz",
            ],
            "KeyParamGroup": [
                "datatype-anat_suffix-T1w__1",
                "datatype-dwi_direction-AP_run-01_suffix-dwi__1",
                "datatype-fmap_direction-AP_fmap-epi_suffix-epi__1",
                "datatype-fmap_direction-PA_fmap-epi_suffix-epi__1",
            ],
        },
    }
    return dict_


@pytest.fixture(scope="module")
def summary_data():
    """A dictionary describing a CuBIDS summary tsv file for testing.

    Returns
    -------
    dict
        A dictionary containing summary data for CuBIDS.
    """
    dict_ = {
        "RenameEntitySet": [
            None,
            "datatype-dwi_direction-AP_run-01_suffix-dwi_acquisition-VAR",
            None,
            None,
        ],
        "KeyParamGroup": [
            "datatype-anat_suffix-T1w__1",
            "datatype-dwi_direction-AP_run-01_suffix-dwi__1",
            "datatype-fmap_direction-AP_fmap-epi_suffix-epi__1",
            "datatype-fmap_direction-PA_fmap-epi_suffix-epi__1",
        ],
        "HasFieldmap": [False, True, False, False],
        "UsedAsFieldmap": [False, False, True, True],
        "MergeInto": [None, None, None, None],
        "EntitySet": [
            "datatype-anat_suffix-T1w",
            "datatype-dwi_direction-AP_run-01_suffix-dwi",
            "datatype-fmap_direction-AP_fmap-epi_suffix-epi",
            "datatype-fmap_direction-PA_fmap-epi_suffix-epi",
        ],
        "ParamGroup": [1, 1, 1, 1],
    }
    return dict_


@pytest.mark.parametrize(
    ("name", "skeleton_name", "intended_for_mode", "intended_for", "is_longitudinal"),
    [
        (
            "relpath_long",
            "skeleton_apply_longitudinal_realistic.yml",
            "relative_path",
            "ses-01/dwi/sub-01_ses-01_acq-VAR_dir-AP_run-01_dwi.nii.gz",
            True,
        ),
        (
            "bidsuri_long",
            "skeleton_apply_longitudinal_realistic.yml",
            "bids_uri",
            "bids::sub-01/ses-01/dwi/sub-01_ses-01_acq-VAR_dir-AP_run-01_dwi.nii.gz",
            True,
        ),
        (
            "relpath_cs",
            "skeleton_apply_cross_sectional_realistic.yml",
            "relative_path",
            "dwi/sub-01_acq-VAR_dir-AP_run-01_dwi.nii.gz",
            False,
        ),
        (
            "bidsuri_cs",
            "skeleton_apply_cross_sectional_realistic.yml",
            "bids_uri",
            "bids::sub-01/dwi/sub-01_acq-VAR_dir-AP_run-01_dwi.nii.gz",
            False,
        ),
    ],
)
def test_cubids_apply_intendedfor(
    tmp_path,
    build_bids_dataset,
    summary_data,
    files_data,
    name,
    skeleton_name,
    intended_for_mode,
    intended_for,
    is_longitudinal,
):
    """Test cubids apply with different IntendedFor types.

    Parameters
    ----------
    tmpdir : LocalPath
        Temporary directory for the test.
    summary_data : dict
        Summary data fixture.
    files_data : dict
        Files data fixture.
    name : str
        Name of the test case.
    skeleton_name : str
        Name of the BIDS skeleton YAML file.
    intended_for_mode : {"relative_path", "bids_uri"}
        IntendedFor value format.
    intended_for : str
        IntendedFor field value.
    is_longitudinal : bool
        Indicate whether the data structure is longitudinal or cross-sectional.
    """
    import json

    from cubids.workflows import apply

    # Generate a BIDS dataset
    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name=name,
        skeleton_name=skeleton_name,
        intended_for_mode=intended_for_mode,
    )

    if is_longitudinal:
        fdata = files_data["longitudinal"]
        fmap_json = bids_dir / "sub-01/ses-01/fmap/sub-01_ses-01_dir-AP_epi.json"
    else:
        fdata = files_data["cross-sectional"]
        fmap_json = bids_dir / "sub-01/fmap/sub-01_dir-AP_epi.json"

    # Create a CuBIDS summary tsv
    summary_tsv = tmp_path / "summary.tsv"
    df = pd.DataFrame(summary_data)
    df.to_csv(summary_tsv, sep="\t", index=False)

    # Create a CuBIDS files tsv
    files_tsv = tmp_path / "files.tsv"
    df = pd.DataFrame(fdata)
    df.to_csv(files_tsv, sep="\t", index=False)

    # Run cubids apply
    apply(
        bids_dir=str(bids_dir),
        use_datalad=False,
        acq_group_level="subject",
        config=None,
        schema=None,
        edited_summary_tsv=summary_tsv,
        files_tsv=files_tsv,
        new_tsv_prefix=None,
    )

    with open(fmap_json) as f:
        metadata = json.load(f)

    assert metadata["IntendedFor"] == [intended_for]


def test_cubids_apply_intendedfor_large_dataset(tmp_path, build_bids_dataset, summary_data):
    """Ensure IntendedFor rewriting still works in a larger realistic dataset."""
    import json

    from cubids.workflows import apply

    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="large_realistic",
        skeleton_name="skeleton_apply_longitudinal_realistic.yml",
        intended_for_mode="relative_path",
    )

    # Only one subset is renamed; additional dataset content is retained.
    files_data = {
        "ParamGroup": [1],
        "EntitySet": ["datatype-dwi_direction-AP_run-01_suffix-dwi"],
        "FilePath": ["/sub-ABC/ses-01/dwi/sub-ABC_ses-01_dir-AP_run-01_dwi.nii.gz"],
        "KeyParamGroup": ["datatype-dwi_direction-AP_run-01_suffix-dwi__1"],
    }
    summary_data_large = pd.DataFrame(summary_data).copy()
    summary_data_large = summary_data_large[
        summary_data_large["EntitySet"] == "datatype-dwi_direction-AP_run-01_suffix-dwi"
    ]

    summary_data_large.loc[:, "RenameEntitySet"] = (
        "datatype-dwi_direction-AP_run-01_suffix-dwi_acquisition-VAR"
    )

    summary_tsv = tmp_path / "summary.tsv"
    summary_data_large.to_csv(summary_tsv, sep="\t", index=False)

    files_tsv = tmp_path / "files.tsv"
    pd.DataFrame(files_data).to_csv(files_tsv, sep="\t", index=False)

    apply(
        bids_dir=str(bids_dir),
        use_datalad=False,
        acq_group_level="subject",
        config=None,
        schema=None,
        edited_summary_tsv=summary_tsv,
        files_tsv=files_tsv,
        new_tsv_prefix=None,
    )

    fmap_json = bids_dir / "sub-ABC/ses-01/fmap/sub-ABC_ses-01_dir-AP_epi.json"
    with open(fmap_json) as f:
        metadata = json.load(f)

    assert metadata["IntendedFor"] == ["ses-01/dwi/sub-ABC_ses-01_acq-VAR_dir-AP_run-01_dwi.nii.gz"]
