"""Test cubids apply."""

import pandas as pd
import pytest
from niworkflows.utils.testing import generate_bids_skeleton

relpath_longitudinal_intendedfor = {
    '01': [
        {
            'session': '01',
            'anat': [{'suffix': 'T1w', 'metadata': {'EchoTime': 1}}],
            'fmap': [
                {
                    'dir': 'AP',
                    'suffix': 'epi',
                    'metadata': {
                        'IntendedFor': [
                            'ses-01/dwi/sub-01_ses-01_dir-AP_run-01_dwi.nii.gz'
                        ]
                    }
                },
                {
                    'dir': 'PA',
                    'suffix': 'epi',
                    'metadata': {
                        'IntendedFor': [
                            'ses-01/dwi/sub-01_ses-01_dir-AP_run-01_dwi.nii.gz'
                        ]
                    }
                },
            ],
            'dwi': [
                {
                    'dir': 'AP',
                    'run': '01',
                    'suffix': 'dwi',
                    'metadata': {
                        'RepetitionTime': 0.8,
                    },
                }
            ],
        },
    ],
}
bidsuri_longitudinal_intendedfor = {
    '01': [
        {
            'session': '01',
            'anat': [{'suffix': 'T1w', 'metadata': {'EchoTime': 1}}],
            'fmap': [
                {
                    'dir': 'AP',
                    'suffix': 'epi',
                    'metadata': {
                        'IntendedFor': [
                            'bids::sub-01/ses-01/dwi/sub-01_ses-01_dir-AP_run-01_dwi.nii.gz'
                        ]
                    }
                },
                {
                    'dir': 'PA',
                    'suffix': 'epi',
                    'metadata': {
                        'IntendedFor': [
                            'bids::sub-01/ses-01/dwi/sub-01_ses-01_dir-AP_run-01_dwi.nii.gz'
                        ]
                    }
                },
            ],
            'dwi': [
                {
                    'dir': 'AP',
                    'run': '01',
                    'suffix': 'dwi',
                    'metadata': {
                        'RepetitionTime': 0.8,
                    },
                }
            ],
        },
    ],
}
relpath_cs_intendedfor = {
    '01': [
        {
            'anat': [{'suffix': 'T1w', 'metadata': {'EchoTime': 1}}],
            'fmap': [
                {
                    'dir': 'AP',
                    'suffix': 'epi',
                    'metadata': {
                        'IntendedFor': [
                            'dwi/sub-01_dir-AP_run-01_dwi.nii.gz'
                        ]
                    }
                },
                {
                    'dir': 'PA',
                    'suffix': 'epi',
                    'metadata': {
                        'IntendedFor': [
                            'dwi/sub-01_dir-AP_run-01_dwi.nii.gz'
                        ]
                    }
                },
            ],
            'dwi': [
                {
                    'dir': 'AP',
                    'run': '01',
                    'suffix': 'dwi',
                    'metadata': {
                        'RepetitionTime': 0.8,
                    },
                }
            ],
        },
    ],
}
bidsuri_cs_intendedfor = {
    '01': [
        {
            'anat': [{'suffix': 'T1w', 'metadata': {'EchoTime': 1}}],
            'fmap': [
                {
                    'dir': 'AP',
                    'suffix': 'epi',
                    'metadata': {
                        'IntendedFor': [
                            'bids::sub-01/dwi/sub-01_dir-AP_run-01_dwi.nii.gz'
                        ]
                    }
                },
                {
                    'dir': 'PA',
                    'suffix': 'epi',
                    'metadata': {
                        'IntendedFor': [
                            'bids::sub-01/dwi/sub-01_dir-AP_run-01_dwi.nii.gz'
                        ]
                    }
                },
            ],
            'dwi': [
                {
                    'dir': 'AP',
                    'run': '01',
                    'suffix': 'dwi',
                    'metadata': {
                        'RepetitionTime': 0.8,
                    },
                }
            ],
        },
    ],
}

summary_data = {
    'RenameEntitySet': [
        None,
        "acquisition-VAR_datatype-dwi_direction-AP_run-01_suffix-dwi",
        None,
        None
    ],
    'KeyParamGroup': [
        "datatype-anat_suffix-T1w__1",
        "datatype-dwi_direction-AP_run-01_suffix-dwi__1",
        "datatype-fmap_direction-AP_fmap-epi_suffix-epi__1",
        "datatype-fmap_direction-PA_fmap-epi_suffix-epi__1"
    ],
    'HasFieldmap': [False, True, False, False],
    'UsedAsFieldmap': [False, False, True, True],
    'MergeInto': [None, None, None, None],
    'EntitySet': [
        "datatype-anat_suffix-T1w",
        "datatype-dwi_direction-AP_run-01_suffix-dwi",
        "datatype-fmap_direction-AP_fmap-epi_suffix-epi",
        "datatype-fmap_direction-PA_fmap-epi_suffix-epi"
    ],
    'ParamGroup': [1, 1, 1, 1]
}

files_data_longitudinal = {
    'ParamGroup': [1, 1, 1, 1],
    'EntitySet': [
        "datatype-anat_suffix-T1w",
        "datatype-dwi_direction-AP_run-01_suffix-dwi",
        "datatype-fmap_direction-AP_fmap-epi_suffix-epi",
        "datatype-fmap_direction-PA_fmap-epi_suffix-epi"
    ],
    'FilePath': [
        "/sub-01/ses-01/anat/sub-01_ses-01_T1w.nii.gz",
        "/sub-01/ses-01/dwi/sub-01_ses-01_dir-AP_run-01_dwi.nii.gz",
        "/sub-01/ses-01/fmap/sub-01_ses-01_dir-AP_epi.nii.gz",
        "/sub-01/ses-01/fmap/sub-01_ses-01_dir-PA_epi.nii.gz"
    ],
    'KeyParamGroup': [
        "datatype-anat_suffix-T1w__1",
        "datatype-dwi_direction-AP_run-01_suffix-dwi__1",
        "datatype-fmap_direction-AP_fmap-epi_suffix-epi__1",
        "datatype-fmap_direction-PA_fmap-epi_suffix-epi__1"
    ]
}

files_data_cs = {
    'ParamGroup': [1, 1, 1, 1],
    'EntitySet': [
        "datatype-anat_suffix-T1w",
        "datatype-dwi_direction-AP_run-01_suffix-dwi",
        "datatype-fmap_direction-AP_fmap-epi_suffix-epi",
        "datatype-fmap_direction-PA_fmap-epi_suffix-epi"
    ],
    'FilePath': [
        "/sub-01/anat/sub-01_T1w.nii.gz",
        "/sub-01/dwi/sub-01_dir-AP_run-01_dwi.nii.gz",
        "/sub-01/fmap/sub-01_dir-AP_epi.nii.gz",
        "/sub-01/fmap/sub-01_dir-PA_epi.nii.gz"
    ],
    'KeyParamGroup': [
        "datatype-anat_suffix-T1w__1",
        "datatype-dwi_direction-AP_run-01_suffix-dwi__1",
        "datatype-fmap_direction-AP_fmap-epi_suffix-epi__1",
        "datatype-fmap_direction-PA_fmap-epi_suffix-epi__1"
    ]
}

@pytest.mark.parametrize(
    ('name', 'skeleton', 'summary_data', 'files_data', 'expected'),
    [
        ('relpath_longitudinal', relpath_longitudinal_intendedfor, summary_data, files_data_longitudinal, 'ses-01/dwi/sub-01_ses-01_acq-VAR_dir-AP_run-001_dwi.nii.gz'),
        ('bidsuri_longitudinal', bidsuri_longitudinal_intendedfor, summary_data, files_data_longitudinal, 'bids::sub-01/ses-01/dwi/sub-01_ses-01_acq-VAR_dir-AP_run-001_dwi.nii.gz'),
        ('relpath_cs', relpath_cs_intendedfor, summary_data, files_data_cs, 'dwi/sub-01_acq-VAR_dir-AP_run-001_dwi.nii.gz'),
        ('bidsuri_cs', bidsuri_cs_intendedfor, summary_data, files_data_cs, 'bids::sub-01/dwi/sub-01_acq-VAR_dir-AP_run-001_dwi.nii.gz'),
    ],
)
def test_cubids_apply_intendedfor(tmpdir, name, skeleton, summary_data, files_data, expected):
    """Test cubids apply with different IntendedFor types."""
    import json

    from cubids.workflows import apply

    # Generate a BIDS dataset
    bids_dir = tmpdir / name
    generate_bids_skeleton(str(bids_dir), skeleton)

    # Create a summary tsv
    summary_tsv = tmpdir / 'summary.tsv'
    df = pd.DataFrame(summary_data)
    df.to_csv(summary_tsv, sep='\t', index=False)

    files_tsv = tmpdir / 'files.tsv'
    df = pd.DataFrame(files_data)
    df.to_csv(files_tsv, sep='\t', index=False)

    # Run cubids apply
    apply(
        bids_dir=str(bids_dir),
        use_datalad=False,
        acq_group_level='subject',
        config=None,
        edited_summary_tsv=summary_tsv,
        files_tsv=files_tsv,
        new_tsv_prefix=None,
        container=None,
    )
    if 'longitudinal' in name:
        fmap_json = bids_dir / 'sub-01/ses-01/fmap/sub-01_ses-01_dir-AP_epi.json'
    else:
        fmap_json = bids_dir / 'sub-01/fmap/sub-01_dir-AP_epi.json'

    with open(fmap_json) as f:
        metadata = json.load(f)

    # XXX: Should not have extra leading zero in run entity, but that's a known bug.
    assert metadata['IntendedFor'] == [expected]
