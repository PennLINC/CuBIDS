"""Test cubids apply."""

import pytest
from niworkflows.utils.testing import generate_bids_skeleton

relpath_intendedfor = {
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

bidsuri_intendedfor = {
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
