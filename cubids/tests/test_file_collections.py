"""Test file collection management in CuBIDS."""

import json

import pandas as pd
import pytest

from cubids import file_collections, utils
from cubids.workflows import add_file_collections


def _multi_echo_frames(first_acquisition, second_acquisition):
    """Create grouping tables for one two-echo BOLD collection."""
    entity_sets = [
        utils._entities_to_entity_set(
            {
                "datatype": "func",
                "task": "rest",
                "echo": str(echo),
                "suffix": "bold",
            }
        )
        for echo in (1, 2)
    ]
    planned = [
        utils._entities_to_entity_set(
            {
                "datatype": "func",
                "task": "rest",
                "echo": str(echo),
                "suffix": "bold",
                "acquisition": acquisition,
            }
        )
        for echo, acquisition in zip((1, 2), (first_acquisition, second_acquisition))
    ]
    summary = pd.DataFrame(
        {
            "KeyParamGroup": [
                f"{entity_set}__{group}" for entity_set in entity_sets for group in (1, 2)
            ],
            "EntitySet": [entity_set for entity_set in entity_sets for _ in (1, 2)],
            "ParamGroup": [1, 2, 1, 2],
            "RenameEntitySet": ["", planned[0], "", planned[1]],
            "EchoTime": [0.01, 0.011, 0.02, 0.021],
            "ManualCheck": [""] * 4,
            "Notes": [""] * 4,
        }
    )
    files = pd.DataFrame(
        {
            "FilePath": [
                f"/sub-01/func/sub-01_task-rest_echo-{echo}_bold.nii.gz" for echo in (1, 2)
            ],
            "KeyParamGroup": [f"{entity_set}__2" for entity_set in entity_sets],
        }
    )
    return files, summary, planned


def test_collection_variant_analysis_covers_non_fieldmap_collections(bare_cubids):
    """Multi-echo BOLD members receive one shared variant proposal."""
    files, summary, _ = _multi_echo_frames("RestVARIANTEchoTimeA", "RestVARIANTEchoTimeB")

    report, proposals = file_collections.analyze_collection_variant_consistency(
        bare_cubids.collection_rules, files, summary, ["EchoTime"]
    )

    assert report.loc[0, "Case"] == "entity-linked"
    assert report.loc[0, "Status"] == "PROPOSED"
    assert report.loc[0, "ProposedAcquisition"] == "RestVARIANTEchoTime"
    assert set(proposals) == set(files["KeyParamGroup"])
    assert all(
        next(iter(entity_sets)).endswith("acquisition-RestVARIANTEchoTime")
        for entity_sets in proposals.values()
    )


def test_collection_guards_cover_non_fieldmap_collections(bare_cubids):
    """Rename and deletion safeguards apply to ordinary file collections too."""
    bare_cubids.path = "/bids"
    files, summary, planned = _multi_echo_frames("VARIANTOne", "VARIANTTwo")
    rename_plan = dict(zip(files["KeyParamGroup"], planned))

    with pytest.raises(ValueError, match="matching, complete file collections"):
        file_collections.validate_collection_renames(
            bare_cubids.collection_rules, bare_cubids.path, files, summary, rename_plan
        )

    with pytest.raises(ValueError, match="Deleting part of a file collection"):
        file_collections.validate_collection_deletions(
            bare_cubids.collection_rules, files, summary, {files.loc[0, "KeyParamGroup"]}
        )


@pytest.mark.parametrize(
    "skeleton_name",
    ["skeleton_file_collection_01.yml", "skeleton_file_collection_02.yml"],
)
def test_add_file_collections(tmp_path, build_bids_dataset, skeleton_name):
    """Test adding file collections to a BIDS dataset."""
    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name=f"add_file_collections_{skeleton_name.replace('.yml', '')}",
        skeleton_name=skeleton_name,
    )
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


def test_add_file_collections_covers_fieldmaps(tmp_path, build_bids_dataset):
    """Fieldmap collections are collected like any other, whatever spans them."""
    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="add_file_collections_fmap",
        skeleton_name="skeleton_file_collection_fmap.yml",
    )
    add_file_collections(str(bids_dir), use_datalad=False, force_unlock=True)

    fmap_dir = bids_dir / "sub-01" / "fmap"

    def file_collection(name):
        return json.loads((fmap_dir / name).read_text()).get("FileCollection")

    # A gradient-echo B0 fieldmap collection is spanned by its suffixes.
    gradient_echo = [
        "bids::sub-01/fmap/sub-01_magnitude1.nii.gz",
        "bids::sub-01/fmap/sub-01_magnitude2.nii.gz",
        "bids::sub-01/fmap/sub-01_phasediff.nii.gz",
    ]
    assert file_collection("sub-01_phasediff.json") == gradient_echo
    assert file_collection("sub-01_magnitude1.json") == gradient_echo

    # A PEPOLAR collection is spanned by its phase-encoding direction, for EPI
    # images and for the M0 scans that arterial spin labeling data use instead.
    assert file_collection("sub-01_dir-AP_epi.json") == [
        "bids::sub-01/fmap/sub-01_dir-AP_epi.nii.gz",
        "bids::sub-01/fmap/sub-01_dir-PA_epi.nii.gz",
    ]
    assert file_collection("sub-01_dir-PA_m0scan.json") == [
        "bids::sub-01/fmap/sub-01_dir-AP_m0scan.nii.gz",
        "bids::sub-01/fmap/sub-01_dir-PA_m0scan.nii.gz",
    ]

    # Acquisition-linked RF field maps use the role prefixes defined by BIDS.
    assert file_collection("sub-01_acq-anat_TB1TFL.json") == [
        "bids::sub-01/fmap/sub-01_acq-anat_TB1TFL.nii.gz",
        "bids::sub-01/fmap/sub-01_acq-famp_TB1TFL.nii.gz",
    ]
    assert file_collection("sub-01_acq-anat_TB1RFM.json") == [
        "bids::sub-01/fmap/sub-01_acq-anat_TB1RFM.nii.gz",
        "bids::sub-01/fmap/sub-01_acq-famp_TB1RFM.nii.gz",
    ]
    assert file_collection("sub-01_acq-body_RB1COR.json") == [
        "bids::sub-01/fmap/sub-01_acq-body_RB1COR.nii.gz",
        "bids::sub-01/fmap/sub-01_acq-head_RB1COR.nii.gz",
    ]

    # The free-form text after the AFI role keeps Test and Retest separate.
    assert file_collection("sub-01_acq-tr1Test_TB1AFI.json") == [
        "bids::sub-01/fmap/sub-01_acq-tr1Test_TB1AFI.nii.gz",
        "bids::sub-01/fmap/sub-01_acq-tr2Test_TB1AFI.nii.gz",
    ]
    assert file_collection("sub-01_acq-tr1Retest_TB1AFI.json") == [
        "bids::sub-01/fmap/sub-01_acq-tr1Retest_TB1AFI.nii.gz",
        "bids::sub-01/fmap/sub-01_acq-tr2Retest_TB1AFI.nii.gz",
    ]

    # Other RF field maps are linked by their required flip, echo, and inversion
    # entities, as specified for each acquisition method.
    assert file_collection("sub-01_flip-1_TB1DAM.json") == [
        "bids::sub-01/fmap/sub-01_flip-1_TB1DAM.nii.gz",
        "bids::sub-01/fmap/sub-01_flip-2_TB1DAM.nii.gz",
    ]
    assert file_collection("sub-01_echo-1_flip-1_TB1EPI.json") == [
        "bids::sub-01/fmap/sub-01_echo-1_flip-1_TB1EPI.nii.gz",
        "bids::sub-01/fmap/sub-01_echo-1_flip-2_TB1EPI.nii.gz",
        "bids::sub-01/fmap/sub-01_echo-2_flip-1_TB1EPI.nii.gz",
        "bids::sub-01/fmap/sub-01_echo-2_flip-2_TB1EPI.nii.gz",
    ]
    assert file_collection("sub-01_flip-1_inv-1_TB1SRGE.json") == [
        "bids::sub-01/fmap/sub-01_flip-1_inv-1_TB1SRGE.nii.gz",
        "bids::sub-01/fmap/sub-01_flip-2_inv-2_TB1SRGE.nii.gz",
    ]

    # A parametric map is a standalone image, so it belongs to no collection.
    assert json.loads((fmap_dir / "sub-01_TB1map.json").read_text()) == {"Units": "arbitrary"}
