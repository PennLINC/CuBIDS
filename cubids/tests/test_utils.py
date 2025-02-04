"""Tests for the utils module."""

import pandas as pd

from cubids.utils import cluster_single_parameters


def test_cluster_single_parameters():
    """Test the cluster_single_parameters function.

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
    param_group_df = pd.DataFrame(params)
    modality = "func"

    # Run the function
    out_df = cluster_single_parameters(
        param_group_df=param_group_df,
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
    out_df = cluster_single_parameters(
        param_group_df=param_group_df,
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


def compare_group_assignments(list1, list2):
    """Compare two lists for equality based on group assignments.

    This function checks if two lists can be considered equal based on their group assignments.
    The actual values in the lists do not matter, only the group assignments do. Each unique value
    in the first list is mapped to a unique value in the second list, and the function checks if
    this mapping is consistent throughout the lists.

    Parameters
    ----------
    list1 : list
        The first list to compare.
    list2 : list
        The second list to compare.

    Returns
    -------
    bool
        True if the lists are equal based on group assignments, False otherwise.

    Examples
    --------
    >>> list1 = [1, 2, 1, 3, 2]
    >>> list2 = ['a', 'b', 'a', 'c', 'b']
    >>> compare_group_assignments(list1, list2)
    True

    >>> list1 = [1, 2, 1, 3, 2]
    >>> list2 = ['b', 'd', 'b', 'q', 'd']
    >>> compare_group_assignments(list1, list2)
    True

    >>> list1 = [1, 2, 1, 3, 2]
    >>> list2 = ['a', 'b', 'a', 'c', 'd']
    >>> compare_group_assignments(list1, list2)
    False
    """
    if len(list1) != len(list2):
        return False

    mapping = {}
    for a, b in zip(list1, list2):
        if a in mapping:
            if mapping[a] != b:
                return False
        else:
            if b in mapping.values():
                return False
            mapping[a] = b

    return True
