"""Tests for general-purpose RenameEntitySet substitutions."""

import pandas as pd
import pytest

from cubids import utils
from cubids.metadata_merge import check_merging_operations

DWI_ENTITIES = {"datatype": "dwi", "direction": "AP", "run": "01", "suffix": "dwi"}


def _summary(entity_sets):
    """Build a minimal summary with one row per entity set."""
    return pd.DataFrame(
        {
            "KeyParamGroup": [f"{entity_set}__1" for entity_set in entity_sets],
            "EntitySet": list(entity_sets),
            "ParamGroup": [1] * len(entity_sets),
            "RenameEntitySet": [""] * len(entity_sets),
            "MergeInto": [pd.NA] * len(entity_sets),
        }
    )


def test_change_rename_entity_set_rewrites_only_the_matching_entity_set(bare_cubids):
    """Entity set substitutions are exact and create a RenameEntitySet instruction."""
    old = utils._entities_to_entity_set(
        {**DWI_ENTITIES, "acquisition": "VARIANTEchoTimeC1TotalReadoutTimeC1"}
    )
    new = utils._entities_to_entity_set({**DWI_ENTITIES, "acquisition": "VARIANTVar1"})
    unchanged = utils._entities_to_entity_set({**DWI_ENTITIES, "acquisition": "VARIANTVar2"})
    summary = _summary([old, unchanged])

    result = bare_cubids.apply_entity_set_changes(summary, {old: new})

    assert result.loc[0, "RenameEntitySet"] == new
    assert result.loc[1, "RenameEntitySet"] == ""


def test_change_rename_entity_set_matches_an_already_planned_entity_set(bare_cubids):
    """A value copied from RenameEntitySet matches the planned, not the original, entity set."""
    original = utils._entities_to_entity_set(DWI_ENTITIES)
    planned = utils._entities_to_entity_set({**DWI_ENTITIES, "acquisition": "VARIANTEchoTime2"})
    new = utils._entities_to_entity_set({**DWI_ENTITIES, "acquisition": "VARIANTVar1"})
    summary = _summary([original])
    summary.loc[0, "RenameEntitySet"] = planned

    result = bare_cubids.apply_entity_set_changes(summary, {planned: new})

    assert result.loc[0, "RenameEntitySet"] == new


def test_change_rename_entity_set_rejects_unmatched_entity_sets(bare_cubids):
    """A typo raises instead of silently applying nothing."""
    summary = _summary([utils._entities_to_entity_set(DWI_ENTITIES)])
    missing = utils._entities_to_entity_set({**DWI_ENTITIES, "acquisition": "VARIANTTypo"})

    with pytest.raises(ValueError, match="No summary rows matched"):
        bare_cubids.apply_entity_set_changes(summary, {missing: missing})


def test_remove_rename_entity_set_marks_only_the_matching_group_for_deletion(bare_cubids):
    """Removal writes MergeInto=0 only for an exact planned entity set."""
    remove = utils._entities_to_entity_set({**DWI_ENTITIES, "acquisition": "VARIANTVar1"})
    keep = utils._entities_to_entity_set({**DWI_ENTITIES, "acquisition": "VARIANTVar2"})
    summary = _summary([remove, keep])

    result = bare_cubids.apply_entity_set_removals(summary, {remove})

    assert result.loc[0, "MergeInto"] == 0
    assert pd.isna(result.loc[1, "MergeInto"])


@pytest.mark.parametrize(("suffix", "separator"), [(".tsv", "\t"), (".csv", ",")])
def test_change_rename_entity_set_accepts_csv_and_tsv_mapping_files(
    bare_cubids, tmp_path, suffix, separator
):
    """A --change-RenameEntitySet value may be a CSV or TSV mapping-table path."""
    old = utils._entities_to_entity_set({**DWI_ENTITIES, "acquisition": "VARIANTEchoTimeC1"})
    new = utils._entities_to_entity_set({**DWI_ENTITIES, "acquisition": "VARIANTVar1"})
    mapping_file = tmp_path / f"entity_set_changes{suffix}"
    pd.DataFrame({"old_entity_set": [old], "new_entity_set": [new]}).to_csv(
        mapping_file, sep=separator, index=False
    )

    changes = bare_cubids.load_entity_set_changes([mapping_file])

    assert changes == {old: new}


def test_load_entity_set_changes_rejects_partial_entities(bare_cubids):
    """Bare labels are rejected, so a partial value cannot match by accident."""
    with pytest.raises(ValueError, match="underscore-separated entity-label pairs"):
        bare_cubids.load_entity_set_changes(["VARIANTVar1=VARIANTVar2"])


@pytest.mark.parametrize(("suffix", "separator"), [(".tsv", "\t"), (".csv", ",")])
def test_load_entity_set_removals_mixes_values_and_table_files(
    bare_cubids, tmp_path, suffix, separator
):
    """Removals may be given directly, in a CSV or TSV table, or both at once."""
    tabled = utils._entities_to_entity_set({**DWI_ENTITIES, "acquisition": "VARIANTVar1"})
    supplied = utils._entities_to_entity_set({**DWI_ENTITIES, "acquisition": "VARIANTVar2"})
    removals_file = tmp_path / f"removals{suffix}"
    pd.DataFrame({"entity_set": [tabled]}).to_csv(removals_file, sep=separator, index=False)

    removals = bare_cubids.load_entity_set_removals([removals_file, supplied])

    assert removals == {tabled, supplied}


def test_removals_are_readable_as_merge_instructions_without_a_round_trip(bare_cubids):
    """Apply checks the merges it derived in memory, so nothing is written before validation."""
    remove = utils._entities_to_entity_set({**DWI_ENTITIES, "acquisition": "VARIANTVar1"})
    keep = utils._entities_to_entity_set({**DWI_ENTITIES, "acquisition": "VARIANTVar2"})
    summary = _summary([remove, keep])
    summary["ParamGroup"] = [2, 1]

    edited = bare_cubids.apply_entity_set_removals(summary, {remove})
    ok_merges, deletions = check_merging_operations(edited)

    assert not ok_merges
    assert deletions == [(2, remove)]


def test_load_entity_set_removals_requires_an_entity_set_column(bare_cubids, tmp_path):
    """A table without the expected column names the column it needs."""
    removals_file = tmp_path / "removals.tsv"
    pd.DataFrame({"KeyParamGroup": ["datatype-dwi_suffix-dwi__1"]}).to_csv(
        removals_file, sep="\t", index=False
    )

    with pytest.raises(ValueError, match="entity_set"):
        bare_cubids.load_entity_set_removals([removals_file])
