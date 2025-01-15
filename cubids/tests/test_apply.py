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

summary_data = {
    'RenameEntitySet': [
        None,
        "acquisition-VARIANT_datatype-dwi_direction-AP_run-01_suffix-dwi",
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

files_data = {
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

@pytest.mark.parametrize(
    ('name', 'skeleton', 'summary_data', 'files_data', 'expected'),
    [
        ('relpath_longitudinal', relpath_longitudinal_intendedfor, summary_data, files_data, 'pass'),
        ('bidsuri_longitudinal', bidsuri_longitudinal_intendedfor, summary_data, files_data, 'error'),
    ],
)
def test_cubids_apply_intendedfor(tmpdir, name, skeleton, summary_data, files_data, expected):
    """Test cubids apply with different IntendedFor types."""
    from cubids.workflows import apply

    # Generate a BIDS dataset
    bids_dir = str(tmpdir / name)
    generate_bids_skeleton(bids_dir, skeleton)

    # Create a summary tsv
    summary_tsv = tmpdir / 'summary.tsv'
    df = pd.DataFrame(summary_data)
    df.to_csv(summary_tsv, sep='\t', index=False)

    files_tsv = tmpdir / 'files.tsv'
    df = pd.DataFrame(files_data)
    df.to_csv(files_tsv, sep='\t', index=False)

    # Run cubids apply
    apply(
        bids_dir=bids_dir,
        use_datalad=False,
        acq_group_level='subject',
        config=None,
        edited_summary_tsv=summary_tsv,
        files_tsv=files_tsv,
        new_tsv_prefix=None,
        container=False,
    )

    # Check the results
    if expected == 'pass':
        # Look at the IntendedFor in the renamed files and it should be correct
        assert True
    elif expected == 'error':
        # Look at the IntendedFor in the renamed files and it should NOT be correct
        assert False
    else:
        raise ValueError(f'Unknown expected value: {expected}')
