import pandas as pd
from cubids.utils import assign_variants

def test_assign_variants_with_cluster_values(tmp_path):
    """Test that assign_variants includes cluster values in variant names."""
    # Create test DataFrame
    data = {
        "ParamGroup": ["1", "2", "2"],
        "EntitySet": ["task-test", "task-test", "task-test"],
        "EchoTime": ["0.03", "0.05", "0.07"],
        "Cluster_EchoTime": ["1", "2", "3"],
        "RenameEntitySet": ["", "", ""],
    }
    df = pd.DataFrame(data)

    # Run assign_variants
    result = assign_variants(df, ["EchoTime"])

    # Check that variant names include cluster values
    assert "VARIANTEchoTime2" in result.loc[1, "RenameEntitySet"]
    assert "VARIANTEchoTime3" in result.loc[2, "RenameEntitySet"]

def test_assign_variants_mixed_parameters(tmp_path):
    """Test assign_variants with both clustered and non-clustered parameters."""
    data = {
        "ParamGroup": ["1", "2", "2"],
        "EntitySet": ["task-test", "task-test", "task-test"],
        "EchoTime": ["0.03", "0.05", "0.07"],
        "FlipAngle": ["90", "75", "60"],
        "Cluster_EchoTime": ["1", "2", "3"],
        "RenameEntitySet": ["", "", ""],
    }
    df = pd.DataFrame(data)

    # Run assign_variants
    result = assign_variants(df, ["EchoTime", "FlipAngle"])

    # Check variant names include both cluster values and actual values
    assert "VARIANTEchoTime2FlipAngle75" in result.loc[1, "RenameEntitySet"]
    assert "VARIANTEchoTime3FlipAngle60" in result.loc[2, "RenameEntitySet"]

def test_assign_variants_special_parameters(tmp_path):
    """Test assign_variants handles special parameters correctly."""
    data = {
        "ParamGroup": ["1", "2", "2"],
        "EntitySet": ["task-test", "task-test", "task-test"],
        "HasFieldmap": ["True", "False", "True"],
        "UsedAsFieldmap": ["True", "False", "True"],
        "RenameEntitySet": ["", "", ""],
    }
    df = pd.DataFrame(data)

    # Run assign_variants
    result = assign_variants(df, ["HasFieldmap", "UsedAsFieldmap"])

    # Check special parameter handling
    assert "VARIANTNoFmap" in result.loc[1, "RenameEntitySet"]
    assert "Unused" in result.loc[1, "RenameEntitySet"]