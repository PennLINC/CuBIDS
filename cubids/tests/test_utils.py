"""Tests for the utils module."""

import numpy as np
import pandas as pd

from cubids.cubids import format_params


def test_format_params():
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

    # Mock up the input
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
            "TaskName": "rest eyes open",
            "SliceTiming": [0.0, 1.0, 2.0],
            "ImageType": ["ORIGINAL", "NONE", "M"],
        },
        {
            "RepetitionTime": 1.9,
            "TaskName": "rest eyes closed",
            "SliceTiming": [0.0, 1.0, 2.0],
            "ImageType": ["ORIGINAL", "NONE", "M"],
        },
        {
            "RepetitionTime": 2.0,
            "TaskName": "rest eyes closed",
            "SliceTiming": [0.0, 0.5, 1.0, 1.5, 2.0],
            "ImageType": ["ORIGINAL", "NONE", "M"],
        },
        {
            "RepetitionTime": 2.0,
            "TaskName": "rest eyes closed",
            "SliceTiming": [0.0, 1.0, 1.9],
            "ImageType": ["ORIGINAL", "NONE", "M"],
        },
        {
            "RepetitionTime": 2.0,
            "TaskName": "rest eyes closed",
            "SliceTiming": [0.0, 1.0, 2.0],
            "ImageType": ["ORIGINAL", "NONE", "M", "NORM"],
        },
    ]
    param_group_df = pd.DataFrame(params)
    modality = "func"

    # Run the function
    formatted_params = format_params(
        param_group_df=param_group_df,
        config=config,
        modality=modality,
    )
    assert isinstance(formatted_params, pd.DataFrame)
    assert "Cluster_RepetitionTime" in formatted_params.columns
    assert "Cluster_TaskName" not in formatted_params.columns
    assert "Cluster_SliceTiming" in formatted_params.columns
    assert "Cluster_ImageType" in formatted_params.columns
    assert np.array_equal(
        formatted_params["Cluster_RepetitionTime"].values,
        [0, 0, 0, 1, 0, 0, 0],
    )
    assert np.array_equal(
        formatted_params["Cluster_SliceTiming"].values,
        [0, 0, 0, 0, 2, 1, 0],
    )
    assert np.array_equal(
        formatted_params["Cluster_ImageType"].values,
        [0, 0, 0, 0, 0, 0, 1],
    )
