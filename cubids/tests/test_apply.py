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


@pytest.mark.parametrize(
    ('name', 'skeleton', 'expected'),
    [
        ('relpath_longitudinal', relpath_longitudinal_intendedfor, 'pass'),
        ('bidsuri_longitudinal', bidsuri_longitudinal_intendedfor, 'error'),
    ],
)
def test_cubids_apply_intendedfor(tmpdir, name, skeleton, expected):
    """Test cubids apply with different IntendedFor types."""
    from cubids.workflows import apply

    # Generate a BIDS dataset
    bids_dir = str(tmpdir / name)
    generate_bids_skeleton(bids_dir, skeleton)

    # Create a summary tsv
    summary_tsv = tmpdir / 'summary.tsv'
    df = pd.DataFrame()
    df.to_csv(summary_tsv, sep='\t', index=False)

    # Run cubids apply
    apply(bids_dir, summary_tsv)

    # Check the results
    if expected == 'pass':
        # Look at the IntendedFor in the renamed files and it should be correct
        assert True
    elif expected == 'error':
        # Look at the IntendedFor in the renamed files and it should NOT be correct
        assert False
    else:
        raise ValueError(f'Unknown expected value: {expected}')
