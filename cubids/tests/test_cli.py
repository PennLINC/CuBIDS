"""Unit tests for the command-line interface (CLI) of the CuBIDS package.

The tests cover the following:
- Path validation functions (_path_exists, _is_file)
- CLI commands (validate, purge, merge, etc.)

Each test case includes assertions to verify the expected behavior of the corresponding function.
"""

import argparse
from functools import partial
import json
import shutil

import pytest

from cubids.cli import _main, _path_exists, _is_file
from cubids.tests.utils import TEST_DATA, chdir


def test_path_exists(tmp_path):
    """Test whether a given path exists or not.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory path provided by pytest.

    Raises
    ------
    SystemExit
        If the path does not exist.
    """
    parser = argparse.ArgumentParser()

    # Test with an existing path
    existing_path = tmp_path / "existing_file.txt"
    existing_path.touch()  # Create the file
    result = _path_exists(str(existing_path), parser)
    assert result == existing_path.absolute()

    # Test with just filename
    with chdir(tmp_path):
        result = _path_exists("existing_file.txt", parser)
        assert result == existing_path.absolute()

    # Test with a non-existing path
    non_existing_path = tmp_path / "non_existing_file.txt"
    with pytest.raises(SystemExit):
        _path_exists(str(non_existing_path), parser)

    # Test within an argument parser
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    PathExists = partial(_path_exists, parser=parser)
    parser.add_argument(
        "existing_folder",
        type=PathExists,
        action="store",
    )

    # Test with an existing path within an argument parser
    parser.parse_args([str(existing_path)])

    # Test with just filename
    with chdir(tmp_path):
        parser.parse_args(["existing_file.txt"])

    # Test with a non-existing path within an argument parser
    with pytest.raises(SystemExit):
        parser.parse_args([str(non_existing_path)])


def test_is_file(tmp_path):
    """Test whether a given path is a file or not.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory path provided by pytest.

    Raises
    ------
    SystemExit
        If the path does not exist or is not a file.
    """
    parser = argparse.ArgumentParser()

    # Test with an existing path
    existing_path = tmp_path / "existing_file.txt"
    existing_path.touch()  # Create the file
    result = _is_file(str(existing_path), parser)
    assert result == existing_path.absolute()

    # Test with just filename
    with chdir(tmp_path):
        result = _is_file("existing_file.txt", parser)
        assert result == existing_path.absolute()

    # Test with a non-existing path
    non_existing_path = tmp_path / "non_existing_file.txt"
    with pytest.raises(SystemExit):
        _is_file(str(non_existing_path), parser)

    # Test within an argument parser
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    IsFile = partial(_is_file, parser=parser)
    parser.add_argument(
        "existing_file",
        type=IsFile,
        action="store",
    )

    # Test with an existing path within an argument parser
    parser.parse_args([str(existing_path)])

    # Test with just filename
    with chdir(tmp_path):
        parser.parse_args(["existing_file.txt"])

    # Test with a non-existing path within an argument parser
    with pytest.raises(SystemExit):
        parser.parse_args([str(non_existing_path)])


def test_main_version(capsys):
    """Test the --version flag."""
    with pytest.raises(SystemExit) as excinfo:
        _main(["--version"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "cubids" in captured.out


def test_main_help(capsys):
    """Test the --help flag."""
    with pytest.raises(SystemExit) as excinfo:
        _main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "CuBIDS commands" in captured.out


def test_validate_command(tmp_path):
    """Test the validate command."""
    # Create mock BIDS dataset
    bids_dir = tmp_path / "bids_dataset"
    bids_dir.mkdir()
    (bids_dir / "dataset_description.json").touch()

    # Create output prefix
    output_prefix = tmp_path / "validation_output"

    # Test validation
    with pytest.raises(SystemExit) as excinfo:
        _main(["validate", str(bids_dir), str(output_prefix)])
    assert excinfo.value.code == 0

    # Check that output files were created
    assert (output_prefix.parent / f"{output_prefix.name}_validation.txt").exists()


def test_validate_command_invalid_dir(tmp_path):
    """Test the validate command with an invalid directory."""
    invalid_dir = tmp_path / "nonexistent"
    with pytest.raises(SystemExit) as excinfo:
        _main(["validate", str(invalid_dir)])
    assert excinfo.value.code != 0


def test_purge_command(tmp_path):
    """Test the purge command."""
    # Create mock BIDS dataset with .cubids directory
    bids_dir = tmp_path / "bids_dataset"
    bids_dir.mkdir()
    cubids_dir = bids_dir / ".cubids"
    cubids_dir.mkdir()
    (cubids_dir / "validation_data.json").touch()

    # Test purge
    with pytest.raises(SystemExit) as excinfo:
        _main(["purge", str(bids_dir), str(bids_dir / "scans.txt")])
    assert excinfo.value.code == 0
    assert not cubids_dir.exists()


def test_group_command(tmp_path):
    """Test the group command."""
    # Create mock BIDS dataset
    bids_dir = tmp_path / "bids_dataset"
    bids_dir.mkdir()
    (bids_dir / "dataset_description.json").touch()

    # Test grouping
    output_prefix = tmp_path / "group_output"
    with pytest.raises(SystemExit) as excinfo:
        _main(["group", str(bids_dir), str(output_prefix)])
    assert excinfo.value.code == 0


def test_add_nifti_info_command(tmp_path):
    """Test the add-nifti-info command."""
    # Create mock BIDS dataset
    bids_dir = tmp_path / "bids_dataset"
    bids_dir.mkdir()
    (bids_dir / "dataset_description.json").touch()

    # Test add-nifti-info
    with pytest.raises(SystemExit) as excinfo:
        _main(["add-nifti-info", str(bids_dir)])
    assert excinfo.value.code == 0


def test_print_metadata_fields_command(tmp_path):
    """Test the print-metadata-fields command."""
    # Create mock BIDS dataset
    bids_dir = tmp_path / "bids_dataset"
    bids_dir.mkdir()
    (bids_dir / "dataset_description.json").touch()

    # Test print-metadata-fields
    with pytest.raises(SystemExit) as excinfo:
        _main(["print-metadata-fields", str(bids_dir)])
    assert excinfo.value.code == 0


def test_remove_metadata_fields_command(tmp_path):
    """Test the remove-metadata-fields command."""
    # Create mock BIDS dataset
    bids_dir = tmp_path / "bids_dataset"
    bids_dir.mkdir()
    (bids_dir / "dataset_description.json").touch()

    # Test remove-metadata-fields
    with pytest.raises(SystemExit) as excinfo:
        _main(["remove-metadata-fields", str(bids_dir), "--fields", "field1", "field2"])
    assert excinfo.value.code == 0


def test_validate_command_with_test_dataset(tmp_path):
    """Test the validate command with the test BIDS dataset."""
    # Copy test dataset to temporary directory
    test_data = TEST_DATA / "BIDS_Dataset"
    bids_dir = tmp_path / "BIDS_Dataset"
    shutil.copytree(test_data, bids_dir)

    # Run validation
    output_prefix = tmp_path / "validation_output"
    with pytest.raises(SystemExit) as excinfo:
        _main(["validate", str(bids_dir), str(output_prefix)])
    assert excinfo.value.code == 0

    # Check that output files were created
    assert (output_prefix.parent / f"{output_prefix.name}_summary.tsv").exists()
    assert (output_prefix.parent / f"{output_prefix.name}_files.tsv").exists()


def test_group_command_with_test_dataset(tmp_path):
    """Test the group command with the test BIDS dataset."""
    # Copy test dataset to temporary directory
    test_data = TEST_DATA / "BIDS_Dataset"
    bids_dir = tmp_path / "BIDS_Dataset"
    shutil.copytree(test_data, bids_dir)

    # Run grouping
    output_prefix = tmp_path / "group_output"
    with pytest.raises(SystemExit) as excinfo:
        _main(["group", str(bids_dir), str(output_prefix)])
    assert excinfo.value.code == 0

    # Check that output files were created
    assert (output_prefix.parent / f"{output_prefix.name}_summary.tsv").exists()
    assert (output_prefix.parent / f"{output_prefix.name}_files.tsv").exists()
    assert (output_prefix.parent / f"{output_prefix.name}_AcqGrouping.tsv").exists()


def test_add_nifti_info_command_with_test_dataset(tmp_path):
    """Test the add-nifti-info command with the test BIDS dataset."""
    # Copy test dataset to temporary directory
    test_data = TEST_DATA / "BIDS_Dataset"
    bids_dir = tmp_path / "BIDS_Dataset"
    shutil.copytree(test_data, bids_dir)

    # Get a sample NIfTI file and its JSON sidecar
    nifti_file = next(bids_dir.rglob("*.nii.gz"))
    json_file = nifti_file.with_suffix("").with_suffix(".json")

    # Store original JSON content
    with open(json_file) as f:
        original_json = json.load(f)

    # Run add-nifti-info
    with pytest.raises(SystemExit) as excinfo:
        _main(["add-nifti-info", str(bids_dir)])
    assert excinfo.value.code == 0

    # Check that JSON was modified
    with open(json_file) as f:
        modified_json = json.load(f)

    # Verify NIfTI info was added
    assert len(modified_json) > len(original_json)
    assert any(key.startswith("Nifti") for key in modified_json)


def test_print_metadata_fields_command_with_test_dataset(tmp_path, capsys):
    """Test the print-metadata-fields command with the test BIDS dataset."""
    # Copy test dataset to temporary directory
    test_data = TEST_DATA / "BIDS_Dataset"
    bids_dir = tmp_path / "BIDS_Dataset"
    shutil.copytree(test_data, bids_dir)

    # Run print-metadata-fields
    with pytest.raises(SystemExit) as excinfo:
        _main(["print-metadata-fields", str(bids_dir)])
    assert excinfo.value.code == 0

    # Check output
    captured = capsys.readouterr()
    assert captured.out  # Verify there is output
    assert "Manufacturer" in captured.out  # Common BIDS metadata field


def test_remove_metadata_fields_command_with_test_dataset(tmp_path):
    """Test the remove-metadata-fields command with the test BIDS dataset."""
    # Copy test dataset to temporary directory
    test_data = TEST_DATA / "BIDS_Dataset"
    bids_dir = tmp_path / "BIDS_Dataset"
    shutil.copytree(test_data, bids_dir)

    # Get a sample JSON sidecar
    json_file = next(bids_dir.rglob("*.json"))

    # Store original JSON content
    with open(json_file) as f:
        original_json = json.load(f)

    # Choose a field that exists in the JSON
    field_to_remove = next(iter(original_json.keys()))

    # Run remove-metadata-fields
    with pytest.raises(SystemExit) as excinfo:
        _main(["remove-metadata-fields", str(bids_dir), "--fields", field_to_remove])
    assert excinfo.value.code == 0

    # Check that field was removed
    with open(json_file) as f:
        modified_json = json.load(f)
    assert field_to_remove not in modified_json


def test_purge_command_with_test_dataset(tmp_path):
    """Test the purge command with the test BIDS dataset."""
    # Copy test dataset to temporary directory
    test_data = TEST_DATA / "BIDS_Dataset"
    bids_dir = tmp_path / "BIDS_Dataset"
    shutil.copytree(test_data, bids_dir)

    # Create .cubids directory and add some files
    cubids_dir = bids_dir / ".cubids"
    cubids_dir.mkdir()
    (cubids_dir / "validation_data.json").touch()

    # Create scans.txt with a list of files to purge
    scans_file = tmp_path / "scans.txt"
    with open(scans_file, "w") as f:
        f.write(str(next(bids_dir.rglob("*.nii.gz")).relative_to(bids_dir)))

    # Run purge
    with pytest.raises(SystemExit) as excinfo:
        _main(["purge", str(bids_dir), str(scans_file)])
    assert excinfo.value.code == 0

    # Verify .cubids directory was removed
    assert not cubids_dir.exists()
