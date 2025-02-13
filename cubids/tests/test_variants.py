import pytest
import pandas as pd
from cubids.utils import assign_variants


@pytest.fixture
def base_df():
    """Create a basic DataFrame for testing variant assignments.

    Returns
    -------
    pandas.DataFrame
        A DataFrame with basic structure needed for assign_variants testing
    """
    return pd.DataFrame({
        "ParamGroup": ["1", "2", "2"],
        "EntitySet": ["task-test", "task-test", "task-test"],
        "RenameEntitySet": ["", "", ""]
    })


def test_assign_variants_with_cluster_values(base_df):
    """Test that assign_variants includes cluster values in variant names."""
    # Add specific columns for this test
    base_df["EchoTime"] = ["0.03", "0.05", "0.07"]
    base_df["Cluster_EchoTime"] = ["1", "2", "3"]

    # Run assign_variants
    result = assign_variants(base_df, ["EchoTime"])

    # Check that variant names include cluster values
    assert "acquisition-VARIANTEchoTime2_" in result.loc[1, "RenameEntitySet"]
    assert "acquisition-VARIANTEchoTime3_" in result.loc[2, "RenameEntitySet"]


def test_assign_variants_mixed_parameters(base_df):
    """Test assign_variants with both clustered and non-clustered parameters."""
    # Add specific columns for this test
    base_df["EchoTime"] = ["0.03", "0.05", "0.07"]
    base_df["FlipAngle"] = ["90", "75", "60"]
    base_df["Cluster_EchoTime"] = ["1", "2", "3"]

    # Run assign_variants
    result = assign_variants(base_df, ["EchoTime", "FlipAngle"])

    # Check variant names include both cluster values and actual values
    assert "acquisition-VARIANTEchoTime2_FlipAngle75_task-test" in result.loc[1, "RenameEntitySet"]
    assert "acquisition-VARIANTEchoTime3_FlipAngle60_task-test" in result.loc[2, "RenameEntitySet"]


def test_assign_variants_special_parameters(base_df):
    """Test assign_variants handles special parameters correctly."""
    # Add specific columns for this test
    base_df["HasFieldmap"] = ["True", "False", "True"]
    base_df["UsedAsFieldmap"] = ["True", "False", "True"]

    # Run assign_variants
    result = assign_variants(base_df, ["HasFieldmap", "UsedAsFieldmap"])

    # Check special parameter handling
    assert "acquisition-VARIANTNoFmap_" in result.loc[1, "RenameEntitySet"]
    assert "acquisition-VARIANTIsUsed_" in result.loc[1, "RenameEntitySet"]