import pandas as pd
import numpy as np
import pytest
from cubids.cubids import CuBIDS
from cubids.utils import assign_variants


@pytest.fixture
def sample_summary_df():
    """Create a sample summary DataFrame with multiple variant groups."""
    df = pd.DataFrame({
        "EntitySet": [
            "datatype-dwi_suffix-dwi",  # Dominant group
            "datatype-dwi_suffix-dwi",  # EchoTime variant cluster 1
            "datatype-dwi_suffix-dwi",  # EchoTime variant cluster 2
            "datatype-dwi_suffix-dwi",  # RepetitionTime variant cluster 1
            "datatype-dwi_suffix-dwi",  # Combined variant
        ],
        "ParamGroup": [1, 2, 3, 4, 5],
        "EchoTime": ["0.05", "0.03", "0.07", "0.05", "0.03"],
        "RepetitionTime": ["2.5", "2.5", "2.5", "3.0", "3.0"],
    })
    # Add cluster columns
    df["Cluster_EchoTime"] = [1, 2, 3, 1, 2]
    df["Cluster_RepetitionTime"] = [1, 1, 1, 2, 2]
    # Initialize RenameEntitySet column
    df["RenameEntitySet"] = np.nan
    return df

def test_variant_numbering_with_clusters(sample_summary_df):
    """Test variant numbering using cluster values."""
    rename_cols = ["EchoTime", "RepetitionTime"]
    result = assign_variants(sample_summary_df, rename_cols)

    # Check that dominant group has no rename
    assert pd.isna(result.loc[0, "RenameEntitySet"])

    # Check EchoTime variants use cluster numbers
    assert "VARIANTEchoTime2" in result.loc[1, "RenameEntitySet"]
    assert "VARIANTEchoTime3" in result.loc[2, "RenameEntitySet"]

    # Check RepetitionTime variant uses cluster number
    assert "VARIANTRepetitionTime2" in result.loc[3, "RenameEntitySet"]

    # Check combined variant uses both cluster numbers
    assert "VARIANTEchoTime2RepetitionTime2" in result.loc[4, "RenameEntitySet"]

def test_variant_numbering_mixed_clustering():
    """Test variant numbering with mix of clustered and non-clustered parameters."""
    df = pd.DataFrame({
        "EntitySet": ["datatype-dwi_suffix-dwi"] * 3,
        "ParamGroup": [1, 2, 3],
        "EchoTime": ["0.05", "0.03", "0.07"],
        "FlipAngle": ["90", "45", "90"],
        "Cluster_EchoTime": [1, 2, 3],
        "RenameEntitySet": [np.nan] * 3  # Initialize RenameEntitySet column
    })

    result = assign_variants(df, ["EchoTime", "FlipAngle"])

    # Check that clustered parameter uses cluster number
    assert "VARIANTEchoTime2" in result.loc[1, "RenameEntitySet"]
    # Check that non-clustered parameter appears without number
    assert "FlipAngle" in result.loc[1, "RenameEntitySet"]

def test_variant_numbering_fieldmap():
    """Test variant numbering with fieldmap-related variants."""
    df = pd.DataFrame({
        "EntitySet": ["datatype-dwi_suffix-dwi"] * 3,
        "ParamGroup": [1, 2, 3],
        "HasFieldmap": ["True", "False", "False"],
        "UsedAsFieldmap": ["False", "True", "False"],
        "RenameEntitySet": [np.nan] * 3  # Initialize RenameEntitySet column
    })

    result = assign_variants(df, ["HasFieldmap", "UsedAsFieldmap"])

    # Check fieldmap variant naming (these don't use clusters)
    assert "VARIANTNoFmap" in result.loc[1, "RenameEntitySet"]
    assert "VARIANTIsUsed" in result.loc[1, "RenameEntitySet"]

def test_variant_numbering_basic(sample_summary_df):
    """Test basic variant numbering functionality."""
    rename_cols = ["EchoTime", "RepetitionTime", "FlipAngle"]
    result = assign_variants(sample_summary_df, rename_cols)

    # Check that dominant group (ParamGroup 1) has no rename
    assert pd.isna(result.loc[0, "RenameEntitySet"])

    # Check EchoTime variants are numbered
    assert "VARIANTEchoTime1" in result.loc[1, "RenameEntitySet"]
    assert "VARIANTEchoTime2" in result.loc[2, "RenameEntitySet"]

    # Check RepetitionTime variant
    assert "VARIANTRepetitionTime1" in result.loc[3, "RenameEntitySet"]

    # Check combined variant
    assert "VARIANTEchoTimeRepetitionTime1" in result.loc[4, "RenameEntitySet"]

    # Check Other variant
    assert "VARIANTOther1" in result.loc[5, "RenameEntitySet"]

def test_variant_numbering_multiple_groups():
    """Test variant numbering with multiple entity sets."""
    df = pd.DataFrame({
        "EntitySet": [
            # First entity set
            "datatype-dwi_direction-AP_suffix-dwi",
            "datatype-dwi_direction-AP_suffix-dwi",
            # Second entity set
            "datatype-dwi_direction-PA_suffix-dwi",
            "datatype-dwi_direction-PA_suffix-dwi",
        ],
        "ParamGroup": [1, 2, 1, 2],
        "EchoTime": ["0.05", "0.03", "0.05", "0.03"],
        "RepetitionTime": ["2.5", "2.5", "2.5", "2.5"],
    })

    result = assign_variants(df, ["EchoTime", "RepetitionTime"])

    # Check that each entity set has its own variant numbering
    variant_counts = result["RenameEntitySet"].str.count("VARIANTEchoTime1").fillna(0)
    assert variant_counts.sum() == 2  # Should have two "VARIANTEchoTime1" instances

def test_variant_numbering_acquisition_handling():
    """Test variant numbering with existing acquisition entities."""
    df = pd.DataFrame({
        "EntitySet": [
            "acquisition-base_datatype-dwi_suffix-dwi",
            "acquisition-base_datatype-dwi_suffix-dwi",
        ],
        "ParamGroup": [1, 2],
        "EchoTime": ["0.05", "0.03"],
    })

    result = assign_variants(df, ["EchoTime"])

    # Check that acquisition entity is properly handled
    assert "acquisition-baseVARIANTEchoTime1" in result.loc[1, "RenameEntitySet"]

def test_variant_numbering_consistency():
    """Test that variant numbering is consistent across multiple runs."""
    df = pd.DataFrame({
        "EntitySet": ["datatype-dwi_suffix-dwi"] * 4,
        "ParamGroup": [1, 2, 3, 4],
        "EchoTime": ["0.05", "0.03", "0.03", "0.07"],
    })

    # Run variant assignment twice
    result1 = assign_variants(df, ["EchoTime"])
    result2 = assign_variants(df, ["EchoTime"])

    # Check results are identical
    pd.testing.assert_frame_equal(result1, result2)