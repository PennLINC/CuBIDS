"""Tests for fieldmap-collection variant checks and acquisition substitutions."""

import pandas as pd
import pytest

from cubids import file_collections, utils


def _fmap_entity_set(suffix, **entities):
    """Return the entity set of one fieldmap, as pybids would parse its name."""
    entities = {"datatype": "fmap", "suffix": suffix, **entities}
    if suffix in {"epi", "phasediff", "phase1", "phase2", "fieldmap"}:
        # pybids parses an extra fmap entity from the suffix of some fieldmaps.
        entities["fmap"] = suffix

    return utils._entities_to_entity_set(entities)


def _pepolar_frames(ap_rename, pa_rename, suffix="epi"):
    """Create one PEPOLAR collection whose AP and PA files are variants."""
    base_acq = "Acquisition"
    ap_entity = _fmap_entity_set(suffix, direction="AP", acquisition=base_acq)
    pa_entity = _fmap_entity_set(suffix, direction="PA", acquisition=base_acq)
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
                f"/sub-01/ses-01/fmap/sub-01_ses-01_dir-AP_{suffix}.nii.gz",
                f"/sub-01/ses-01/fmap/sub-01_ses-01_dir-PA_{suffix}.nii.gz",
            ],
            "KeyParamGroup": [f"{ap_entity}__2", f"{pa_entity}__2"],
            "PhaseEncodingDirection": ["j", "j-"],
        }
    )
    return files, summary


def _pepolar_entity_set(direction, acquisition="VARIANTVar1"):
    """Return the planned entity set for one member of the PEPOLAR pair."""
    return _fmap_entity_set("epi", direction=direction, acquisition=acquisition)


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

    report, proposals = file_collections.analyze_collection_variant_consistency(
        bare_cubids.collection_rules, files, summary, ["EchoTime"]
    )

    assert report.loc[0, "Status"] == "PROPOSED"
    assert report.loc[0, "ProposedAcquisition"] == "TestPEPOLARVARIANTEchoTime"
    assert proposals[f"{original_ap}__2"] == {expected_ap}
    assert proposals[f"{original_pa}__2"] == {expected_pa}

    updated = file_collections.apply_collection_variant_proposals(summary, proposals)
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

    report, proposals = file_collections.analyze_collection_variant_consistency(
        bare_cubids.collection_rules, files, summary, ["EchoTime"]
    )

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

    report, proposals = file_collections.analyze_collection_variant_consistency(
        bare_cubids.collection_rules, files, summary
    )

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

    report, proposals = file_collections.analyze_collection_variant_consistency(
        bare_cubids.collection_rules, files, summary, ["EchoTime"]
    )

    assert report.loc[0, "Case"] == expected_case
    assert report.loc[0, "Status"] == "PASS"
    assert not proposals


def test_fmap_variant_analysis_pairs_pepolar_m0scans(bare_cubids):
    """M0 scans under fmap/ are the PEPOLAR fieldmap of perfusion data."""
    files, summary = _pepolar_frames(
        _fmap_entity_set("m0scan", direction="AP", acquisition="AcquisitionVARIANTEchoTimeA"),
        _fmap_entity_set("m0scan", direction="PA", acquisition="AcquisitionVARIANTEchoTimeB"),
        suffix="m0scan",
    )

    report, proposals = file_collections.analyze_collection_variant_consistency(
        bare_cubids.collection_rules, files, summary, ["EchoTime"]
    )

    assert report.loc[0, "Case"] == "pepolar"
    assert report.loc[0, "Status"] == "PROPOSED"
    assert report.loc[0, "ProposedAcquisition"] == "AcquisitionVARIANTEchoTime"
    assert set(proposals) == set(files["KeyParamGroup"])


def test_fmap_variant_analysis_pairs_pepolar_across_parts(bare_cubids):
    """The parts of a complex-valued PEPOLAR pair are checked as one collection."""
    entity_sets = [
        _fmap_entity_set("epi", direction=direction, part=part, acquisition="VARIANTVar1")
        for direction in ("AP", "PA")
        for part in ("mag", "phase")
    ]
    summary = pd.DataFrame(
        {
            "KeyParamGroup": [f"{entity_set}__1" for entity_set in entity_sets],
            "EntitySet": entity_sets,
            "ParamGroup": [1] * len(entity_sets),
            "RenameEntitySet": entity_sets,
            "EchoTime": [0.05] * len(entity_sets),
            "ManualCheck": [""] * len(entity_sets),
            "Notes": [""] * len(entity_sets),
        }
    )
    files = pd.DataFrame(
        {
            "FilePath": [
                f"/sub-01/fmap/sub-01_dir-{direction}_part-{part}_epi.nii.gz"
                for direction in ("AP", "PA")
                for part in ("mag", "phase")
            ],
            "KeyParamGroup": [f"{entity_set}__1" for entity_set in entity_sets],
            "PhaseEncodingDirection": ["j", "j", "j-", "j-"],
        }
    )

    report, proposals = file_collections.analyze_collection_variant_consistency(
        bare_cubids.collection_rules, files, summary, ["EchoTime"]
    )

    assert len(report) == 1
    assert report.loc[0, "Case"] == "pepolar"
    assert report.loc[0, "Status"] == "PASS"
    assert report.loc[0, "FilePaths"].count("|") == 3
    assert not proposals


def test_fmap_variant_analysis_keeps_rf_field_map_acquisition_labels(bare_cubids):
    """Members that acquisition labels tell apart keep those labels when renamed."""
    entity_sets = [
        _fmap_entity_set("TB1TFL", acquisition=acquisition) for acquisition in ("anat", "famp")
    ]
    summary = pd.DataFrame(
        {
            "KeyParamGroup": [
                f"{entity_set}__{group}" for entity_set in entity_sets for group in (1, 2)
            ],
            "EntitySet": [entity_set for entity_set in entity_sets for _ in (1, 2)],
            "ParamGroup": [1, 2, 1, 2],
            "RenameEntitySet": [
                "",
                _fmap_entity_set("TB1TFL", acquisition="anatVARIANTEchoTimeA"),
                "",
                _fmap_entity_set("TB1TFL", acquisition="fampVARIANTEchoTimeB"),
            ],
            "EchoTime": [0.05, 0.048, 0.05, 0.049],
            "ManualCheck": [""] * 4,
            "Notes": [""] * 4,
        }
    )
    files = pd.DataFrame(
        {
            "FilePath": [
                "/sub-01/fmap/sub-01_acq-anat_TB1TFL.nii.gz",
                "/sub-01/fmap/sub-01_acq-famp_TB1TFL.nii.gz",
            ],
            "KeyParamGroup": [f"{entity_sets[0]}__2", f"{entity_sets[1]}__2"],
        }
    )

    report, proposals = file_collections.analyze_collection_variant_consistency(
        bare_cubids.collection_rules, files, summary, ["EchoTime"]
    )

    assert report.loc[0, "Case"] == "rf-field-map"
    assert report.loc[0, "Status"] == "PROPOSED"
    assert report.loc[0, "ProposedAcquisition"] == "anatVARIANTEchoTime|fampVARIANTEchoTime"
    assert proposals[f"{entity_sets[0]}__2"] == {
        _fmap_entity_set("TB1TFL", acquisition="anatVARIANTEchoTime")
    }
    assert proposals[f"{entity_sets[1]}__2"] == {
        _fmap_entity_set("TB1TFL", acquisition="fampVARIANTEchoTime")
    }


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
        # A fieldmap acquired in one phase-encoding direction is valid BIDS.
        ("epi", "sub-01_dir-PA_epi.nii.gz", "j-", "single-direction epi"),
        # An M0 scan under fmap/ is the PEPOLAR fieldmap of perfusion data.
        ("m0scan", "sub-01_dir-PA_m0scan.nii.gz", "j-", "single-direction m0scan"),
        # An RF field map whose acq-famp partner is missing has nothing to match yet.
        ("TB1TFL", "sub-01_acq-anat_TB1TFL.nii.gz", None, "rf-field-map"),
        # A parametric map belongs to no collection, so it is left out of the report.
        ("TB1map", "sub-01_TB1map.nii.gz", None, None),
    ],
)
def test_fmap_renames_allow_fieldmaps_with_no_collection_partner(
    bare_cubids, suffix, filename, phase_encoding_direction, expected_case
):
    """A fieldmap with nothing to stay consistent with is renamed like any other image."""
    bare_cubids.path = ""
    files, summary, planned = _standalone_fmap_frames(suffix, filename, phase_encoding_direction)

    report, proposals = file_collections.analyze_collection_variant_consistency(
        bare_cubids.collection_rules, files, summary, ["EchoTime"]
    )

    assert report["Case"].tolist() == ([expected_case] if expected_case else [])
    assert (report["Status"] == "PASS").all()
    assert not proposals
    file_collections.validate_collection_renames(
        bare_cubids.collection_rules,
        bare_cubids.path,
        files,
        summary,
        planned,
        allow_fmap_renames=True,
    )


def test_fmap_renames_reject_a_magnitude_image_left_without_its_collection(bare_cubids):
    """An orphan magnitude image is reported rather than silently left unclassified."""
    bare_cubids.path = ""
    files, summary, planned = _standalone_fmap_frames("magnitude1", "sub-01_magnitude1.nii.gz")

    report, _ = file_collections.analyze_collection_variant_consistency(
        bare_cubids.collection_rules, files, summary, ["EchoTime"]
    )

    assert report.loc[0, "Case"] == "orphan-magnitude"
    assert report.loc[0, "Status"] == "MANUAL_REVIEW"
    with pytest.raises(ValueError, match="matching, complete file collections"):
        file_collections.validate_collection_renames(
            bare_cubids.collection_rules,
            bare_cubids.path,
            files,
            summary,
            planned,
            allow_fmap_renames=True,
        )


def test_validate_collection_renames_ignores_groups_that_are_only_being_deleted(bare_cubids):
    """A mismatched pair that apply deletes does not have to pass the rename check."""
    bare_cubids.path = "/bids"
    files, summary = _pepolar_frames(
        _pepolar_entity_set("AP", "VARIANTVar1"), _pepolar_entity_set("PA", "VARIANTVar2")
    )
    planned = dict(zip(files["KeyParamGroup"], summary.loc[[1, 3], "RenameEntitySet"]))
    deletions = ["/bids" + path for path in files["FilePath"]]

    with pytest.raises(ValueError, match="matching, complete file collections"):
        file_collections.validate_collection_renames(
            bare_cubids.collection_rules,
            bare_cubids.path,
            files,
            summary,
            planned,
            allow_fmap_renames=True,
        )

    file_collections.validate_collection_renames(
        bare_cubids.collection_rules,
        bare_cubids.path,
        files,
        summary,
        planned,
        pending_deletions=deletions,
        allow_fmap_renames=True,
    )


def test_validate_collection_deletions_rejects_a_partial_collection_deletion(bare_cubids):
    """Deleting one PEPOLAR member names the entity set that would be left behind."""
    pa_entity_set = _pepolar_entity_set("PA")
    files, summary = _pepolar_frames(_pepolar_entity_set("AP"), pa_entity_set)
    ap_key, _ = files["KeyParamGroup"].tolist()

    with pytest.raises(ValueError, match="Deleting part of a file collection") as excinfo:
        file_collections.validate_collection_deletions(
            bare_cubids.collection_rules, files, summary, {ap_key}
        )

    assert pa_entity_set in str(excinfo.value)


def test_validate_collection_deletions_accepts_a_whole_collection_deletion(bare_cubids):
    """Deleting every member of a collection is allowed."""
    files, summary = _pepolar_frames(_pepolar_entity_set("AP"), _pepolar_entity_set("PA"))

    file_collections.validate_collection_deletions(
        bare_cubids.collection_rules, files, summary, set(files["KeyParamGroup"])
    )


def test_validate_collection_deletions_accepts_deleting_an_unpaired_fieldmap(bare_cubids):
    """An fmap with no surviving collection members can be deleted on its own."""
    files, summary = _pepolar_frames(_pepolar_entity_set("AP"), _pepolar_entity_set("PA"))
    files = files.iloc[[0]]

    file_collections.validate_collection_deletions(
        bare_cubids.collection_rules, files, summary, set(files["KeyParamGroup"])
    )
