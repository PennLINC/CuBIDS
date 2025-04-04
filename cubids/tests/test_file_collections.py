"""Test file collection management in CuBIDS."""

import json

from niworkflows.utils.testing import generate_bids_skeleton

from cubids.tests.utils import TEST_DATA
from cubids.workflows import add_file_collections


def test_add_file_collections(tmp_path):
    """Test adding file collections to a BIDS dataset."""
    bids_dir = tmp_path / "add_file_collections"
    dset_yaml = str(TEST_DATA / "skeletons" / "skeleton_file_collection_01.yml")
    generate_bids_skeleton(str(bids_dir), dset_yaml)
    add_file_collections(str(bids_dir), use_datalad=False, force_unlock=True)

    # A JSON sidecar that's part of a file collection should be modified.
    f1 = bids_dir / "sub-01" / "func" / "sub-01_task-rest_acq-meepi_echo-3_part-phase_bold.json"
    assert f1.exists()
    expected = {
        "EchoTime": 0.45,
        "EchoTimes": [0.15, 0.15, 0.3, 0.3, 0.45, 0.45],
        "Parts": ["mag", "phase", "mag", "phase", "mag", "phase"],
        "FileCollection": [
            "bids::sub-01/func/sub-01_task-rest_acq-meepi_echo-1_part-mag_bold.nii.gz",
            "bids::sub-01/func/sub-01_task-rest_acq-meepi_echo-1_part-phase_bold.nii.gz",
            "bids::sub-01/func/sub-01_task-rest_acq-meepi_echo-2_part-mag_bold.nii.gz",
            "bids::sub-01/func/sub-01_task-rest_acq-meepi_echo-2_part-phase_bold.nii.gz",
            "bids::sub-01/func/sub-01_task-rest_acq-meepi_echo-3_part-mag_bold.nii.gz",
            "bids::sub-01/func/sub-01_task-rest_acq-meepi_echo-3_part-phase_bold.nii.gz",
        ],
        "Units": "arbitrary",
    }
    assert json.loads(f1.read_text()) == expected

    # A JSON sidecar that's part of a file collection should be modified.
    # Same as above, but with a different file collection (4-echo).
    f2 = bids_dir / "sub-02" / "func" / "sub-02_task-rest_acq-meepi_echo-3_part-mag_bold.json"
    assert f2.exists()
    expected = {
        "EchoTime": 0.45,
        "EchoTimes": [0.15, 0.15, 0.3, 0.3, 0.45, 0.45, 0.6, 0.6],
        "Parts": ["mag", "phase", "mag", "phase", "mag", "phase", "mag", "phase"],
        "FileCollection": [
            "bids::sub-02/func/sub-02_task-rest_acq-meepi_echo-1_part-mag_bold.nii.gz",
            "bids::sub-02/func/sub-02_task-rest_acq-meepi_echo-1_part-phase_bold.nii.gz",
            "bids::sub-02/func/sub-02_task-rest_acq-meepi_echo-2_part-mag_bold.nii.gz",
            "bids::sub-02/func/sub-02_task-rest_acq-meepi_echo-2_part-phase_bold.nii.gz",
            "bids::sub-02/func/sub-02_task-rest_acq-meepi_echo-3_part-mag_bold.nii.gz",
            "bids::sub-02/func/sub-02_task-rest_acq-meepi_echo-3_part-phase_bold.nii.gz",
            "bids::sub-02/func/sub-02_task-rest_acq-meepi_echo-4_part-mag_bold.nii.gz",
            "bids::sub-02/func/sub-02_task-rest_acq-meepi_echo-4_part-phase_bold.nii.gz",
        ],
    }
    assert json.loads(f2.read_text()) == expected

    # A NIfTI that's not part of a file collection shouldn't be modified.
    f3 = bids_dir / "sub-01" / "func" / "sub-01_task-rest_acq-seepi_bold.json"
    assert f3.exists()
    expected = {
        "EchoTime": 0.35,
    }
    assert json.loads(f3.read_text()) == expected
