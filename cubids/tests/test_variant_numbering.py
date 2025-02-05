import pandas as pd
import numpy as np
import pytest
from cubids.cubids import CuBIDS
from cubids.utils import assign_variants

@pytest.fixture
def sample_summary_df():
    """Create a sample summary DataFrame with multiple variant groups."""
    return pd.DataFrame({
        "EntitySet": [
            "datatype-dwi_suffix-dwi",  # Dominant group
            "datatype-dwi_suffix-dwi",  # EchoTime variant 1
            "datatype-dwi_suffix-dwi",  # EchoTime variant 2
            "datatype-dwi_suffix-dwi",  # RepetitionTime variant
            "datatype-dwi_suffix-dwi",  # EchoTime + RepetitionTime variant
            "datatype-dwi_suffix-dwi",  # Other variant
        ],
        "ParamGroup": [1, 2, 3, 4, 5, 6],
        "EchoTime": ["0.05", "0.03", "0.07", "0.05", "0.03", "0.05"],
        "RepetitionTime": ["2.5", "2.5", "2.5", "3.0", "3.0", "2.5"],
        "FlipAngle": ["90", "90", "90", "90", "90", np.nan],
    })

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

def test_variant_numbering_fieldmap():
    """Test variant numbering with fieldmap-related variants."""
    df = pd.DataFrame({
        "EntitySet": ["datatype-dwi_suffix-dwi"] * 3,
        "ParamGroup": [1, 2, 3],
        "HasFieldmap": ["True", "False", "False"],
        "UsedAsFieldmap": ["False", "True", "False"],
    })

    result = assign_variants(df, ["HasFieldmap", "UsedAsFieldmap"])

    # Check fieldmap variant naming
    assert "VARIANTNoFmap1" in result.loc[1, "RenameEntitySet"]
    assert "VARIANTIsUsed1" in result.loc[1, "RenameEntitySet"]

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