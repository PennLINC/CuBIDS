"""Tests for fieldmap-collection variant checks and acquisition substitutions."""

import pandas as pd
import pytest

from cubids import utils


def _pepolar_frames(ap_rename, pa_rename):
    """Create one PEPOLAR collection whose AP and PA files are variants."""
    base_acq = "Acquisition"
    base_entities = {
        "datatype": "fmap",
        "fmap": "epi",
        "suffix": "epi",
        "acquisition": base_acq,
    }
    ap_entity = utils._entities_to_entity_set({**base_entities, "direction": "AP"})
    pa_entity = utils._entities_to_entity_set({**base_entities, "direction": "PA"})
    summary = pd.DataFrame(
        {
            "KeyParamGroup": [
                f"{ap_entity}__1",
                f"{ap_entity}__2",
                f"{pa_entity}__1",
                f"{pa_entity}__2",
            ],
            "EntitySet": [ap_entity, ap_entity, pa_entity, pa_entity],
            "ParamGroup": [1, 2, 1, 2],
            "RenameEntitySet": ["", ap_rename, "", pa_rename],
            "EchoTime": [0.05, 0.048, 0.05, 0.049],
            "ManualCheck": ["", "", "", ""],
            "Notes": ["", "", "", ""],
        }
    )
    files = pd.DataFrame(
        {
            "FilePath": [
                "/sub-01/ses-01/fmap/sub-01_ses-01_dir-AP_epi.nii.gz",
                "/sub-01/ses-01/fmap/sub-01_ses-01_dir-PA_epi.nii.gz",
            ],
            "KeyParamGroup": [f"{ap_entity}__2", f"{pa_entity}__2"],
            "PhaseEncodingDirection": ["j", "j-"],
        }
    )
    return files, summary


def _pepolar_entity_set(direction, acquisition="VARIANTVar1"):
    """Return the planned entity set for one member of the PEPOLAR pair."""
    return utils._entities_to_entity_set(
        {
            "datatype": "fmap",
            "direction": direction,
            "fmap": "epi",
            "suffix": "epi",
            "acquisition": acquisition,
        }
    )


def test_fmap_variant_analysis_proposes_one_shared_pepolar_variant(bare_cubids):
    """Different PEPOLAR variant values yield one structured shared proposal."""
    ap_rename = utils._entities_to_entity_set(
        {
            "datatype": "fmap",
            "direction": "AP",
            "fmap": "epi",
            "suffix": "epi",
            "acquisition": "TestPEPOLARVARIANTEchoTimeA",
        }
    )
    pa_rename = utils._entities_to_entity_set(
        {
            "datatype": "fmap",
            "direction": "PA",
            "fmap": "epi",
            "suffix": "epi",
            "acquisition": "TestPEPOLARVARIANTEchoTimeB",
        }
    )
    expected_ap = utils._entities_to_entity_set(
        {
            "datatype": "fmap",
            "direction": "AP",
            "fmap": "epi",
            "suffix": "epi",
            "acquisition": "TestPEPOLARVARIANTEchoTime",
        }
    )
    expected_pa = utils._entities_to_entity_set(
        {
            "datatype": "fmap",
            "direction": "PA",
            "fmap": "epi",
            "suffix": "epi",
            "acquisition": "TestPEPOLARVARIANTEchoTime",
        }
    )
    files, summary = _pepolar_frames(ap_rename, pa_rename)
    original_ap = utils._entities_to_entity_set(
        {
            "datatype": "fmap",
            "direction": "AP",
            "fmap": "epi",
            "suffix": "epi",
            "acquisition": "Acquisition",
        }
    )
    original_pa = utils._entities_to_entity_set(
        {
            "datatype": "fmap",
            "direction": "PA",
            "fmap": "epi",
            "suffix": "epi",
            "acquisition": "Acquisition",
        }
    )

    report, proposals = bare_cubids.analyze_fmap_variant_consistency(files, summary, ["EchoTime"])

    assert report.loc[0, "Status"] == "PROPOSED"
    assert report.loc[0, "ProposedAcquisition"] == "TestPEPOLARVARIANTEchoTime"
    assert proposals[f"{original_ap}__2"] == {expected_ap}
    assert proposals[f"{original_pa}__2"] == {expected_pa}

    updated = bare_cubids.apply_fmap_variant_proposals(summary, proposals)
    assert updated.loc[1, "RenameEntitySet"] == expected_ap
    assert updated.loc[3, "RenameEntitySet"] == expected_pa


def test_fmap_variant_analysis_accepts_matching_pepolar_variants(bare_cubids):
    """A collection whose planned acquisition labels match passes validation."""
    ap_rename = utils._entities_to_entity_set(
        {
            "datatype": "fmap",
            "direction": "AP",
            "fmap": "epi",
            "suffix": "epi",
            "acquisition": "VARIANTVar1",
        }
    )
    pa_rename = utils._entities_to_entity_set(
        {
            "datatype": "fmap",
            "direction": "PA",
            "fmap": "epi",
            "suffix": "epi",
            "acquisition": "VARIANTVar1",
        }
    )
    files, summary = _pepolar_frames(ap_rename, pa_rename)

    report, proposals = bare_cubids.analyze_fmap_variant_consistency(files, summary, ["EchoTime"])

    assert report.loc[0, "Status"] == "PASS"
    assert not proposals


def test_fmap_variant_analysis_without_rename_cols_defers_to_manual_review(bare_cubids):
    """The apply-time validation path cannot propose, so mismatches must not PASS."""
    ap_rename = utils._entities_to_entity_set(
        {
            "datatype": "fmap",
            "direction": "AP",
            "fmap": "epi",
            "suffix": "epi",
            "acquisition": "VARIANTEchoTimeA",
        }
    )
    pa_rename = utils._entities_to_entity_set(
        {
            "datatype": "fmap",
            "direction": "PA",
            "fmap": "epi",
            "suffix": "epi",
            "acquisition": "VARIANTEchoTimeB",
        }
    )
    files, summary = _pepolar_frames(ap_rename, pa_rename)

    report, proposals = bare_cubids.analyze_fmap_variant_consistency(files, summary)

    assert report.loc[0, "Status"] == "MANUAL_REVIEW"
    assert not proposals


@pytest.mark.parametrize(
    ("expected_case", "suffixes"),
    [
        ("phase-difference", ["phasediff", "magnitude1"]),
        ("two-phase", ["phase1", "phase2", "magnitude1", "magnitude2"]),
        ("direct-fieldmap", ["fieldmap", "magnitude"]),
    ],
)
def test_fmap_variant_analysis_covers_non_pepolar_b0_cases(bare_cubids, expected_case, suffixes):
    """Phase-difference, two-phase, and direct fieldmaps are checked as collections."""
    acquisition = "VARIANTVar1"
    entity_sets = [
        utils._entities_to_entity_set(
            {
                "datatype": "fmap",
                "fmap": suffix,
                "suffix": suffix,
                "acquisition": acquisition,
            }
        )
        for suffix in suffixes
    ]
    summary = pd.DataFrame(
        {
            "KeyParamGroup": [f"{entity_set}__1" for entity_set in entity_sets],
            "EntitySet": entity_sets,
            "ParamGroup": [1] * len(entity_sets),
            "RenameEntitySet": entity_sets,
            "EchoTime": [0.048] * len(entity_sets),
            "ManualCheck": [""] * len(entity_sets),
            "Notes": [""] * len(entity_sets),
        }
    )
    files = pd.DataFrame(
        {
            "FilePath": [
                f"/sub-01/ses-01/fmap/sub-01_ses-01_{suffix}.nii.gz" for suffix in suffixes
            ],
            "KeyParamGroup": [f"{entity_set}__1" for entity_set in entity_sets],
        }
    )

    report, proposals = bare_cubids.analyze_fmap_variant_consistency(files, summary, ["EchoTime"])

    assert report.loc[0, "Case"] == expected_case
    assert report.loc[0, "Status"] == "PASS"
    assert not proposals


def _standalone_fmap_frames(suffix, filename, phase_encoding_direction=None):
    """Create tables holding one fieldmap file that has no collection partner."""
    entity_set = utils._entities_to_entity_set(
        {"datatype": "fmap", "fmap": suffix, "suffix": suffix}
    )
    key_param_group = f"{entity_set}__1"
    summary = pd.DataFrame(
        {
            "KeyParamGroup": [key_param_group],
            "EntitySet": [entity_set],
            "ParamGroup": [1],
            "RenameEntitySet": [""],
            "ManualCheck": [""],
            "Notes": [""],
        }
    )
    files = pd.DataFrame(
        {
            "FilePath": [f"/sub-01/fmap/{filename}"],
            "KeyParamGroup": [key_param_group],
            "PhaseEncodingDirection": [phase_encoding_direction],
        }
    )
    planned = {key_param_group: f"{entity_set}_acquisition-VARIANTVar1"}
    return files, summary, planned


@pytest.mark.parametrize(
    ("suffix", "filename", "phase_encoding_direction", "expected_case"),
    [
        # A single EPI is valid BIDS, and a non-B0 fieldmap is not a collection at all.
        ("epi", "sub-01_dir-PA_epi.nii.gz", "j-", "single-direction epi"),
        ("TB1TFL", "sub-01_TB1TFL.nii.gz", None, None),
    ],
)
def test_fmap_renames_allow_fieldmaps_with_no_collection_partner(
    bare_cubids, suffix, filename, phase_encoding_direction, expected_case
):
    """A fieldmap with nothing to stay consistent with is renamed like any other image."""
    bare_cubids.path = ""
    files, summary, planned = _standalone_fmap_frames(suffix, filename, phase_encoding_direction)

    report, proposals = bare_cubids.analyze_fmap_variant_consistency(files, summary, ["EchoTime"])

    assert report["Case"].tolist() == ([expected_case] if expected_case else [])
    assert (report["Status"] == "PASS").all()
    assert not proposals
    bare_cubids.validate_fmap_renames(files, summary, planned)


def test_fmap_renames_reject_a_magnitude_image_left_without_its_collection(bare_cubids):
    """An orphan magnitude image is reported rather than silently left unclassified."""
    bare_cubids.path = ""
    files, summary, planned = _standalone_fmap_frames("magnitude1", "sub-01_magnitude1.nii.gz")

    report, _ = bare_cubids.analyze_fmap_variant_consistency(files, summary, ["EchoTime"])

    assert report.loc[0, "Case"] == "orphan-magnitude"
    assert report.loc[0, "Status"] == "MANUAL_REVIEW"
    with pytest.raises(ValueError, match="matching, complete fieldmap collections"):
        bare_cubids.validate_fmap_renames(files, summary, planned)


def test_validate_fmap_renames_ignores_groups_that_are_only_being_deleted(bare_cubids):
    """A mismatched pair that apply deletes does not have to pass the rename check."""
    bare_cubids.path = "/bids"
    files, summary = _pepolar_frames(
        _pepolar_entity_set("AP", "VARIANTVar1"), _pepolar_entity_set("PA", "VARIANTVar2")
    )
    planned = dict(zip(files["KeyParamGroup"], summary.loc[[1, 3], "RenameEntitySet"]))
    deletions = ["/bids" + path for path in files["FilePath"]]

    with pytest.raises(ValueError, match="matching, complete fieldmap collections"):
        bare_cubids.validate_fmap_renames(files, summary, planned)

    bare_cubids.validate_fmap_renames(files, summary, planned, pending_deletions=deletions)


def test_validate_fmap_deletions_rejects_a_partial_collection_deletion(bare_cubids):
    """Deleting one PEPOLAR member names the entity set that would be left behind."""
    pa_entity_set = _pepolar_entity_set("PA")
    files, summary = _pepolar_frames(_pepolar_entity_set("AP"), pa_entity_set)
    ap_key, _ = files["KeyParamGroup"].tolist()

    with pytest.raises(ValueError, match="Deleting part of a fieldmap collection") as excinfo:
        bare_cubids.validate_fmap_deletions(files, summary, {ap_key})

    assert pa_entity_set in str(excinfo.value)


def test_validate_fmap_deletions_accepts_a_whole_collection_deletion(bare_cubids):
    """Deleting every member of a collection is allowed."""
    files, summary = _pepolar_frames(_pepolar_entity_set("AP"), _pepolar_entity_set("PA"))

    bare_cubids.validate_fmap_deletions(files, summary, set(files["KeyParamGroup"]))


def test_validate_fmap_deletions_accepts_deleting_an_unpaired_fieldmap(bare_cubids):
    """An fmap with no surviving collection members can be deleted on its own."""
    files, summary = _pepolar_frames(_pepolar_entity_set("AP"), _pepolar_entity_set("PA"))
    files = files.iloc[[0]]

    bare_cubids.validate_fmap_deletions(files, summary, set(files["KeyParamGroup"]))
