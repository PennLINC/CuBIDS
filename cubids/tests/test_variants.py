"""Tests for variant name generation in CuBIDS.

This module tests the assign_variants function which is responsible for generating
variant names when files differ from the dominant group. The tests cover:

1. Basic variant name generation
2. Handling of cluster values (e.g., from parameter clustering)
3. Special parameter handling (HasFieldmap, UsedAsFieldmap)
4. Mixed parameter cases (both clustered and non-clustered parameters)

The variant naming follows the format:
    acquisition-VARIANT{parameter}{value}_
where:
- VARIANT indicates a deviation from the dominant group
- {parameter} is the name of the differing parameter
- {value} is either the cluster number or actual value
"""

import pandas as pd
import pytest

from cubids.utils import assign_variants


@pytest.fixture
def base_df():
    """Create a basic DataFrame for testing variant assignments.

    Returns
    -------
    pandas.DataFrame
        A DataFrame with basic structure needed for assign_variants testing
    """
    return pd.DataFrame(
        {
            "ParamGroup": ["1", "2", "2"],
            "EntitySet": ["task-test", "task-test", "task-test"],
            "RenameEntitySet": ["", "", ""],
        }
    )


def test_assign_variants_with_cluster_values(base_df):
    """Test that assign_variants includes cluster values in variant names."""
    # Add specific columns for this test
    base_df["EchoTime"] = ["0.03", "0.05", "0.07"]
    base_df["Cluster_EchoTime"] = ["1", "2", "3"]

    # Run assign_variants
    result = assign_variants(base_df, ["EchoTime"])

    # Check that variant names include cluster values
    assert result.loc[1, "RenameEntitySet"].endswith("acquisition-VARIANTEchoTimeC2")
    assert result.loc[2, "RenameEntitySet"].endswith("acquisition-VARIANTEchoTimeC3")


def test_assign_variants_mixed_parameters(base_df):
    """Test assign_variants with both clustered and non-clustered parameters."""
    # Add specific columns for this test
    base_df["EchoTime"] = ["0.03", "0.05", "0.07"]
    base_df["FlipAngle"] = ["90", "75", "60"]
    base_df["Cluster_EchoTime"] = ["1", "2", "3"]

    # Run assign_variants
    result = assign_variants(base_df, ["EchoTime", "FlipAngle"])

    # Check variant names include both cluster values and actual values
    assert result.loc[1, "RenameEntitySet"].endswith("acquisition-VARIANTEchoTimeC2FlipAngle75")
    assert result.loc[2, "RenameEntitySet"].endswith("acquisition-VARIANTEchoTimeC3FlipAngle60")


def test_assign_variants_special_parameters(base_df):
    """Test assign_variants handles special parameters correctly."""
    # Add specific columns for this test
    base_df["HasFieldmap"] = ["True", "False", "False"]
    base_df["UsedAsFieldmap"] = ["False", "True", "False"]

    # Run assign_variants
    result = assign_variants(base_df, ["HasFieldmap", "UsedAsFieldmap"])

    # Check special parameter handling
    assert result.loc[0, "RenameEntitySet"].endswith("acquisition-VARIANTOther")
    assert result.loc[1, "RenameEntitySet"].endswith("acquisition-VARIANTNoFmapIsUsed")
    assert result.loc[2, "RenameEntitySet"].endswith("acquisition-VARIANTNoFmap")


def test_assign_variants_ignores_matching_missing_values():
    """Test that missing values shared with the dominant group are not variants."""
    summary = pd.DataFrame(
        {
            "ParamGroup": [1, 2],
            "Counts": [2, 1],
            "EntitySet": [
                "datatype-anat_reconstruction-RMS_suffix-T1w_acquisition-MEMPRAGE",
                "datatype-anat_reconstruction-RMS_suffix-T1w_acquisition-MEMPRAGE",
            ],
            "RenameEntitySet": ["", ""],
            "PhaseEncodingDirection": [float("nan"), float("nan")],
            "Dim1Size": [160, 155],
        }
    )

    result = assign_variants(summary, ["PhaseEncodingDirection", "Dim1Size"])

    assert result.loc[1, "RenameEntitySet"].endswith("acquisition-MEMPRAGEVARIANTDim1Size155")
    assert "PhaseEncodingDirection" not in result.loc[1, "RenameEntitySet"]


def test_assign_variants_labels_missing_value_that_differs_from_dominant():
    """Test that a missing variant value is named when the dominant value is set."""
    summary = pd.DataFrame(
        {
            "ParamGroup": [1, 2],
            "Counts": [2, 1],
            "EntitySet": ["datatype-anat_suffix-T1w", "datatype-anat_suffix-T1w"],
            "RenameEntitySet": ["", ""],
            "PhaseEncodingDirection": ["j", float("nan")],
        }
    )

    result = assign_variants(summary, ["PhaseEncodingDirection"])

    assert result.loc[1, "RenameEntitySet"].endswith(
        "acquisition-VARIANTPhaseEncodingDirectionnan"
    )
