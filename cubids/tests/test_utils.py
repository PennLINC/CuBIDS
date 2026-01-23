"""Tests for the utils module."""

import pandas as pd

from cubids import utils
from cubids.constants import NON_KEY_ENTITIES
from cubids.cubids import CuBIDS
from cubids.tests.utils import compare_group_assignments


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
