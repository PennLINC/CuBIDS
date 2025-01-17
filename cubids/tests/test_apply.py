"""Test cubids apply."""

import pandas as pd
import pytest
from niworkflows.utils.testing import generate_bids_skeleton

relpath_intendedfor_long = {
    "01": [
        {
            "session": "01",
            "anat": [{"suffix": "T1w", "metadata": {"EchoTime": 1}}],
            "fmap": [
                {
                    "dir": "AP",
                    "suffix": "epi",
                    "metadata": {
                        "IntendedFor": ["ses-01/dwi/sub-01_ses-01_dir-AP_run-01_dwi.nii.gz"],
                    },
                },
                {
                    "dir": "PA",
                    "suffix": "epi",
                    "metadata": {
                        "IntendedFor": ["ses-01/dwi/sub-01_ses-01_dir-AP_run-01_dwi.nii.gz"],
                    },
                },
            ],
            "dwi": [
                {
                    "dir": "AP",
                    "run": "01",
                    "suffix": "dwi",
                    "metadata": {
                        "RepetitionTime": 0.8,
                    },
                }
            ],
        },
    ],
}
bidsuri_intendedfor_long = {
    "01": [
        {
            "session": "01",
            "anat": [{"suffix": "T1w", "metadata": {"EchoTime": 1}}],
            "fmap": [
                {
                    "dir": "AP",
                    "suffix": "epi",
                    "metadata": {
                        "IntendedFor": [
                            "bids::sub-01/ses-01/dwi/sub-01_ses-01_dir-AP_run-01_dwi.nii.gz"
                        ],
                    },
                },
                {
                    "dir": "PA",
                    "suffix": "epi",
                    "metadata": {
                        "IntendedFor": [
                            "bids::sub-01/ses-01/dwi/sub-01_ses-01_dir-AP_run-01_dwi.nii.gz"
                        ],
                    },
                },
            ],
            "dwi": [
                {
                    "dir": "AP",
                    "run": "01",
                    "suffix": "dwi",
                    "metadata": {
                        "RepetitionTime": 0.8,
                    },
                }
            ],
        },
    ],
}
relpath_intendedfor_cs = {
    "01": [
        {
            "anat": [{"suffix": "T1w", "metadata": {"EchoTime": 1}}],
            "fmap": [
                {
                    "dir": "AP",
                    "suffix": "epi",
                    "metadata": {
                        "IntendedFor": ["dwi/sub-01_dir-AP_run-01_dwi.nii.gz"],
                    },
                },
                {
                    "dir": "PA",
                    "suffix": "epi",
                    "metadata": {
                        "IntendedFor": ["dwi/sub-01_dir-AP_run-01_dwi.nii.gz"],
                    },
                },
            ],
            "dwi": [
                {
                    "dir": "AP",
                    "run": "01",
                    "suffix": "dwi",
                    "metadata": {
                        "RepetitionTime": 0.8,
                    },
                }
            ],
        },
    ],
}
bidsuri_intendedfor_cs = {
    "01": [
        {
            "anat": [{"suffix": "T1w", "metadata": {"EchoTime": 1}}],
            "fmap": [
                {
                    "dir": "AP",
                    "suffix": "epi",
                    "metadata": {
                        "IntendedFor": ["bids::sub-01/dwi/sub-01_dir-AP_run-01_dwi.nii.gz"],
                    },
                },
                {
                    "dir": "PA",
                    "suffix": "epi",
                    "metadata": {
                        "IntendedFor": ["bids::sub-01/dwi/sub-01_dir-AP_run-01_dwi.nii.gz"],
                    },
                },
            ],
            "dwi": [
                {
                    "dir": "AP",
                    "run": "01",
                    "suffix": "dwi",
                    "metadata": {
                        "RepetitionTime": 0.8,
                    },
                }
            ],
        },
    ],
}


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
            "acquisition-VAR_datatype-dwi_direction-AP_run-01_suffix-dwi",
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
    ("name", "skeleton", "intended_for", "is_longitudinal", "expected"),
    [
        (  # doesn't have acq-VAR
            "relpath_long",
            relpath_intendedfor_long,
            "ses-01/dwi/sub-01_ses-01_acq-VAR_dir-AP_run-01_dwi.nii.gz",
            True,
            "pass",
        ),
        (  # doesn't have ses-01
            "bidsuri_long",
            bidsuri_intendedfor_long,
            "bids::sub-01/ses-01/dwi/sub-01_ses-01_acq-VAR_dir-AP_run-01_dwi.nii.gz",
            True,
            "pass",
        ),
        (  # doesn't have acq-VAR
            "relpath_cs",
            relpath_intendedfor_cs,
            "dwi/sub-01_acq-VAR_dir-AP_run-01_dwi.nii.gz",
            False,
            "pass",
        ),
        (  # pass
            "bidsuri_cs",
            bidsuri_intendedfor_cs,
            "bids::sub-01/dwi/sub-01_acq-VAR_dir-AP_run-01_dwi.nii.gz",
            False,
            "pass",
        ),
    ],
)
def test_cubids_apply_intendedfor(
    tmpdir,
    summary_data,
    files_data,
    name,
    skeleton,
    intended_for,
    is_longitudinal,
    expected,
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
    skeleton : dict
        BIDS skeleton structure.
    intended_for : str
        IntendedFor field value.
    expected : str or Exception
        Expected result or exception.

    Raises
    ------
    ValueError
        If the test case is expected to raise an error.
    """
    import json

    from cubids.workflows import apply

    # Generate a BIDS dataset
    bids_dir = tmpdir / name
    generate_bids_skeleton(str(bids_dir), skeleton)

    if is_longitudinal:
        fdata = files_data["longitudinal"]
        fmap_json = bids_dir / "sub-01/ses-01/fmap/sub-01_ses-01_dir-AP_epi.json"
    else:
        fdata = files_data["cross-sectional"]
        fmap_json = bids_dir / "sub-01/fmap/sub-01_dir-AP_epi.json"

    # Create a CuBIDS summary tsv
    summary_tsv = tmpdir / "summary.tsv"
    df = pd.DataFrame(summary_data)
    df.to_csv(summary_tsv, sep="\t", index=False)

    # Create a CuBIDS files tsv
    files_tsv = tmpdir / "files.tsv"
    df = pd.DataFrame(fdata)
    df.to_csv(files_tsv, sep="\t", index=False)

    # Run cubids apply
    if isinstance(expected, str):
        apply(
            bids_dir=str(bids_dir),
            use_datalad=False,
            acq_group_level="subject",
            config=None,
            edited_summary_tsv=summary_tsv,
            files_tsv=files_tsv,
            new_tsv_prefix=None,
            container=None,
            is_longitudinal=is_longitudinal,
        )

        with open(fmap_json) as f:
            metadata = json.load(f)

        assert metadata["IntendedFor"] == [intended_for]
    else:
        with pytest.raises(expected):
            apply(
                bids_dir=str(bids_dir),
                use_datalad=False,
                acq_group_level="subject",
                config=None,
                edited_summary_tsv=summary_tsv,
                files_tsv=files_tsv,
                new_tsv_prefix=None,
                container=None,
                is_longitudinal=is_longitudinal,
            )
