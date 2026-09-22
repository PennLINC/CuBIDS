"""Tests for the utils module."""

from copy import deepcopy

import pandas as pd
import pytest

from cubids import file_collections, utils
from cubids.constants import NON_KEY_ENTITIES
from cubids.cubids import CuBIDS
from cubids.tests.utils import compare_group_assignments
from cubids.workflows import find_dataset_file


def test_find_json_files_excludes_git_metadata(tmp_path):
    """Find JSON files in a dataset without traversing hidden paths like Git metadata."""
    dataset_json = tmp_path / "sub-01" / "metadata.json"
    dataset_json.parent.mkdir()
    dataset_json.write_text("{}")
    (tmp_path / "dataset_description.json").write_text("{}")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored.json").write_text("{}")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "config.json").write_text("{}")
    (tmp_path / ".datalad").mkdir()
    (tmp_path / ".datalad" / "config.json").write_text("{}")
    (tmp_path / ".hidden.json").write_text("{}")
    (tmp_path / "directory.json").mkdir()

    assert utils.find_json_files(tmp_path) == [
        tmp_path / "dataset_description.json",
        dataset_json,
    ]


def test_find_dataset_file_prefers_subject_file_list_then_dataset_root(tmp_path):
    """Validation's common lookup handles listed, root-level, and absent files."""
    listed_file = tmp_path / "listed" / "participants.tsv"
    listed_file.parent.mkdir()
    listed_file.write_text("participant_id\nsub-01\n")
    root_file = tmp_path / "dataset_description.json"
    root_file.write_text("{}\n")

    assert find_dataset_file("participants.tsv", [listed_file], tmp_path) == str(listed_file)
    assert find_dataset_file("dataset_description.json", [], tmp_path) == str(root_file)
    assert find_dataset_file("missing.json", [], tmp_path) is None


def test_collection_rules_come_from_the_bids_schema(bare_cubids):
    """Which files make up a collection is read off the schema, not hardcoded."""
    rules = file_collections.get_collection_rules(bare_cubids.schema)
    fmap_rules = bare_cubids.schema["rules"]["files"]["raw"]["fmap"]

    # Every suffix the spec lists for a multi-file fieldmap type has a rule.
    for group in (
        "fieldmaps",
        "pepolar",
        "pepolar_m0scan",
        "RFFieldMaps",
        "TB1DAM",
        "TB1EPI",
        "TB1SRGE",
    ):
        for suffix in fmap_rules[group]["suffixes"]:
            assert ("fmap", suffix) in rules

    # A required entity spans a collection only when it can distinguish members,
    # so the task of a func image does not make separate acquisitions into one.
    assert ("func", "bold") not in rules
    assert file_collections.get_collection_rule(
        rules, {"datatype": "func", "suffix": "bold"}
    ).is_generic

    # Parametric maps are the fieldmap suffixes that stand on their own.
    for suffix in fmap_rules["parametric"]["suffixes"]:
        assert ("fmap", suffix) not in rules

    # Members of one collection agree on everything outside its axes.
    pepolar = file_collections.get_collection_rule(rules, {"datatype": "fmap", "suffix": "epi"})
    ap_entities = {"subject": "01", "direction": "AP", "suffix": "epi", "acquisition": "x"}
    pa_entities = {**ap_entities, "direction": "PA"}
    assert file_collections.collection_context(
        ap_entities, pepolar
    ) == file_collections.collection_context(pa_entities, pepolar)
    assert file_collections.collection_context(
        {**pa_entities, "acquisition": "y"}, pepolar
    ) != file_collections.collection_context(ap_entities, pepolar)

    # The role prefix links acquisition-based RF field maps, while trailing text
    # keeps separate use cases from being merged into one collection.
    rf = file_collections.get_collection_rule(rules, {"datatype": "fmap", "suffix": "TB1TFL"})
    anat_test = {
        "subject": "01",
        "suffix": "TB1TFL",
        "acquisition": "anatTest",
    }
    famp_test = {**anat_test, "acquisition": "fampTest"}
    famp_retest = {**anat_test, "acquisition": "fampRetest"}
    assert file_collections.collection_context(
        anat_test, rf
    ) == file_collections.collection_context(famp_test, rf)
    assert file_collections.collection_context(
        anat_test, rf
    ) != file_collections.collection_context(famp_retest, rf)


def test_bids_tsv_helpers_preserve_empty_cells_and_literal_quotes(tmp_path):
    """Shared BIDS-TSV I/O preserves the settings needed by both callers."""
    source = tmp_path / "source.tsv"
    destination = tmp_path / "destination.tsv"
    source.write_text('filename\tnote\nfunc/example.nii.gz\tsay "hi"\nfunc/empty.nii.gz\t\n')

    table = utils.read_bids_tsv(source)
    utils.write_bids_tsv(table, destination)

    assert table["note"].tolist() == ['say "hi"', ""]
    assert destination.read_text() == source.read_text()


@pytest.mark.parametrize("param_groups", [[1, 2], [1.0, 2.0], ["1", "2"]])
def test_get_variant_components_share_dominant_group_comparison(param_groups):
    """Clustered and plain fields report only differences from ParamGroup 1.

    ParamGroup is compared numerically, so a summary that read it back as float or
    string still finds its dominant group.
    """
    summary = pd.DataFrame(
        {
            "EntitySet": ["datatype-fmap_suffix-epi", "datatype-fmap_suffix-epi"],
            "ParamGroup": param_groups,
            "EchoTime": [0.05, 0.048],
            "Cluster_EchoTime": [0, 1],
            "TaskName": ["rest", "rest"],
        }
    )

    assert utils.get_variant_components(summary, summary.iloc[1], ["EchoTime", "TaskName"]) == [
        ("EchoTime", 1, 0, True)
    ]
    assert utils.get_variant_components(summary, summary.iloc[0], ["EchoTime"]) == []


def test_get_variant_rename_columns_pool_every_modality_in_the_summary():
    """Variant labels are built from the same columns whatever order modalities came in."""
    cubids = CuBIDS.__new__(CuBIDS)
    cubids.grouping_config = {
        "sidecar_params": {
            "func": {"EchoTime": {"suggest_variant_rename": True}},
            "perf": {
                "EchoTime": {"suggest_variant_rename": True},
                "LabelingDistance": {"suggest_variant_rename": True},
                "M0Type": {"suggest_variant_rename": False},
            },
        },
        "derived_params": {
            "fmap": {
                "Dim3Size": {"suggest_variant_rename": True},
                "NumVolumes": {"suggest_variant_rename": False},
            }
        },
        "relational_params": {"FieldmapKey": {"suggest_variant_rename": True, "display_mode": ""}},
    }
    summary = pd.DataFrame(
        columns=[
            "EchoTime",
            "LabelingDistance",
            "M0Type",
            "Dim3Size",
            "NumVolumes",
            "HasFieldmap",
        ]
    )

    assert cubids.get_variant_rename_columns(summary) == [
        "EchoTime",
        "LabelingDistance",
        "Dim3Size",
    ]
    assert cubids.get_variant_rename_columns(summary[["EchoTime"]]) == ["EchoTime"]


def test_fmap_variant_name_includes_derived_difference():
    """A derived NIfTI difference must not fall back to VARIANTOther."""
    cubids = CuBIDS.__new__(CuBIDS)
    cubids.grouping_config = {
        "sidecar_params": {"fmap": {"EchoTime": {"suggest_variant_rename": True}}},
        "derived_params": {"fmap": {"Dim3Size": {"suggest_variant_rename": True}}},
        "relational_params": {},
    }
    summary = pd.DataFrame(
        {
            "EntitySet": [
                "datatype-fmap_fmap-magnitude1_suffix-magnitude1",
                "datatype-fmap_fmap-magnitude1_suffix-magnitude1",
            ],
            "ParamGroup": [1, 2],
            "RenameEntitySet": ["", ""],
            "EchoTime": [0.004, 0.004],
            "Dim3Size": [64, 65],
        }
    )

    rename_cols = cubids.get_variant_rename_columns(summary)
    result = utils.assign_variants(summary, rename_cols)

    assert result.loc[1, "RenameEntitySet"].endswith("acquisition-VARIANTDim3Size65")


def test_round_params():
    """Test the cubids.utils.round_params function."""
    # Example DataFrame
    df = pd.DataFrame(
        {
            "A": [1.12345, 2.23456, 3.34567],
            "B": [[1.12345, 2.23456], [3.34567, 4.45678], [5.56789, 6.67890]],
            "C": ["text", "more text", "even more text"],
            "D": [1.12345, 2.23456, 3.34567],
        }
    )

    # Example config
    config = {
        "sidecar_params": {
            "func": {
                "A": {"precision": 2},
                "B": {"precision": 2},
            },
        },
        "derived_params": {
            "func": {},
        },
    }

    # Expected DataFrame after rounding
    expected_df = pd.DataFrame(
        {
            "A": [1.12, 2.23, 3.35],
            "B": [[1.12, 2.23], [3.35, 4.46], [5.57, 6.68]],
            "C": ["text", "more text", "even more text"],
            "D": [1.12345, 2.23456, 3.34567],
        }
    )

    # Round columns
    rounded_df = utils.round_params(df, config, "func")

    # Assert that the rounded DataFrame matches the expected DataFrame
    pd.testing.assert_frame_equal(rounded_df, expected_df)


def test_get_modality_params_combines_settings_without_mutating_config():
    """Sidecar and derived settings are combined without changing the config."""
    config = {
        "sidecar_params": {"func": {"EchoTime": {"precision": 3}}},
        "derived_params": {"func": {"NumVolumes": {"precision": 0}}},
    }
    original_config = deepcopy(config)

    assert utils.get_modality_params(config, "func") == {
        "EchoTime": {"precision": 3},
        "NumVolumes": {"precision": 0},
    }
    assert config == original_config


def test_cluster_single_parameters():
    """Test the cubids.utils.cluster_single_parameters function.

    We want to test that the function correctly clusters parameters based on the
    configuration dictionary.
    """
    config = {
        "sidecar_params": {
            "func": {
                "RepetitionTime": {"tolerance": 0.01, "suggest_variant_rename": True},
                "TaskName": {"suggest_variant_rename": True},
                "SliceTiming": {"tolerance": 0.01, "suggest_variant_rename": True},
                "ImageType": {"suggest_variant_rename": True},
            },
        },
        "derived_params": {
            "func": {},
        },
    }

    # Mock up the input. The variants are explicitly prepared.
    params = [
        {
            "RepetitionTime": 2.0,
            "TaskName": "rest eyes closed",
            "SliceTiming": [0.0, 1.0, 2.0],
            "ImageType": ["ORIGINAL", "NONE", "M"],
        },
        {
            "RepetitionTime": 2.0,
            "TaskName": "rest eyes closed",
            "SliceTiming": [0.0, 1.0, 2.0],
            "ImageType": ["ORIGINAL", "NONE", "M"],
        },
        {
            "RepetitionTime": 2.0,
            # TaskName variant
            "TaskName": "rest eyes open",
            "SliceTiming": [0.0, 1.0, 2.0],
            "ImageType": ["ORIGINAL", "NONE", "M"],
        },
        {
            # RepetitionTime variant
            "RepetitionTime": 1.9,
            "TaskName": "rest eyes closed",
            "SliceTiming": [0.0, 1.0, 2.0],
            "ImageType": ["ORIGINAL", "NONE", "M"],
        },
        {
            "RepetitionTime": 2.0,
            "TaskName": "rest eyes closed",
            # SliceTiming variant (length)
            "SliceTiming": [0.0, 0.5, 1.0, 1.5, 2.0],
            "ImageType": ["ORIGINAL", "NONE", "M"],
        },
        {
            "RepetitionTime": 2.0,
            "TaskName": "rest eyes closed",
            # SliceTiming variant (values)
            "SliceTiming": [0.0, 1.0, 1.9],
            "ImageType": ["ORIGINAL", "NONE", "M"],
        },
        {
            "RepetitionTime": 2.0,
            "TaskName": "rest eyes closed",
            "SliceTiming": [0.0, 1.0, 2.0],
            # ImageType variant (length)
            "ImageType": ["ORIGINAL", "NONE", "M", "NORM"],
        },
        {
            "RepetitionTime": 2.0,
            "TaskName": "rest eyes closed",
            "SliceTiming": [0.0, 1.0, 2.0],
            # ImageType variant (values)
            "ImageType": ["ORIGINAL", "NONE", "P"],
        },
    ]
    files_df = pd.DataFrame(params)
    modality = "func"

    # Run the function
    out_df = utils.cluster_single_parameters(
        df=files_df,
        config=config,
        modality=modality,
    )
    assert isinstance(out_df, pd.DataFrame)
    assert "Cluster_RepetitionTime" in out_df.columns
    assert "Cluster_SliceTiming" in out_df.columns
    assert "Cluster_ImageType" in out_df.columns
    # Non-list columns without tolerance don't get clustered
    assert "Cluster_TaskName" not in out_df.columns

    assert compare_group_assignments(
        out_df["Cluster_RepetitionTime"].values.astype(int),
        [0, 0, 0, 1, 0, 0, 0, 0],
    )
    assert compare_group_assignments(
        out_df["Cluster_SliceTiming"].values.astype(int),
        [0, 0, 0, 0, 2, 1, 0, 0],
    )
    assert compare_group_assignments(
        out_df["Cluster_ImageType"].values.astype(int),
        [0, 0, 0, 0, 0, 0, 1, 2],
    )

    # Change the tolerance for SliceTiming
    config["sidecar_params"]["func"]["SliceTiming"]["tolerance"] = 0.5
    out_df = utils.cluster_single_parameters(
        df=files_df,
        config=config,
        modality=modality,
    )
    assert isinstance(out_df, pd.DataFrame)
    assert "Cluster_RepetitionTime" in out_df.columns
    assert "Cluster_SliceTiming" in out_df.columns
    assert "Cluster_ImageType" in out_df.columns
    # Non-list columns without tolerance don't get clustered
    assert "Cluster_TaskName" not in out_df.columns

    assert compare_group_assignments(
        out_df["Cluster_RepetitionTime"].values.astype(int),
        [0, 0, 0, 1, 0, 0, 0, 0],
    )
    # Different lengths still produce different clusters,
    # but the value-based variants are now the same
    assert compare_group_assignments(
        out_df["Cluster_SliceTiming"].values.astype(int),
        [0, 0, 0, 0, 1, 0, 0, 0],
    )
    assert compare_group_assignments(
        out_df["Cluster_ImageType"].values.astype(int),
        [0, 0, 0, 0, 0, 0, 1, 2],
    )


def test_ignore_entities_in_entity_set(tmp_path):
    """Test that ignore_entities updates NON_KEY_ENTITIES."""
    original_non_key = NON_KEY_ENTITIES.copy()
    try:
        CuBIDS(tmp_path, ignore_entities=["task", "run"])
        entity_set = utils._entities_to_entity_set(
            {"subject": "01", "task": "rest", "run": "01", "acquisition": "x"}
        )
        assert "task-" not in entity_set
        assert "run-" not in entity_set
        assert "acquisition-x" in entity_set
    finally:
        NON_KEY_ENTITIES.clear()
        NON_KEY_ENTITIES.update(original_non_key)
