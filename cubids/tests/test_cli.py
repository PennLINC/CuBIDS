"""Unit tests for the command-line interface (CLI) of the CuBIDS package.

The tests cover the following:
- Path validation functions (_path_exists, _is_file)
- CLI commands (validate, purge, merge, etc.)

Each test case includes assertions to verify the expected behavior of the corresponding function.
"""

import argparse
import json
import shutil
import stat
from functools import partial

import pandas as pd
import pytest

from cubids.cli import _is_file, _main, _path_exists
from cubids.tests.utils import TEST_DATA, chdir


def _build_cli_dataset(tmp_path, build_bids_dataset, dataset_name="bids_dataset"):
    """Build a skeleton-backed CLI test dataset."""
    return build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name=dataset_name,
        skeleton_name="skeleton_cli_commands.yml",
    )


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


def _create_date_time_shift_dataset(tmp_path):
    """Create a small dataset containing all date/time metadata handled by the command."""
    bids_dir = tmp_path / "date_time_shift_dataset"
    scans_dir = bids_dir / "sub-01" / "ses-01"
    later_scans_dir = bids_dir / "sub-01" / "ses-02"
    sidecar_dir = scans_dir / "func"
    scans_dir.mkdir(parents=True)
    later_scans_dir.mkdir(parents=True)
    sidecar_dir.mkdir()
    (bids_dir / "dataset_description.json").write_text('{"Name": "test"}\n')
    git_dir = bids_dir / ".git"
    git_dir.mkdir()
    (git_dir / "ignored.json").write_text("not BIDS metadata")

    (scans_dir / "sub-01_ses-01_scans.tsv").write_text(
        "filename\tacq_time\tnote\n"
        "func/sub-01_task-rest_bold.nii.gz\t2024-01-10T13:43:04\tkeep\n"
        "func/sub-01_task-other_bold.nii.gz\t2024-01-10T23:45:00\tkeep\n"
        "func/sub-01_task-na_bold.nii.gz\tn/a\tkeep\n"
        "func/sub-01_task-invalid_bold.nii.gz\tnot-a-date\tkeep\n"
    )
    (later_scans_dir / "sub-01_ses-02_scans.tsv").write_text(
        "filename\tacq_time\tnote\n"
        'func/sub-01_task-rest_bold.nii.gz\t2024-01-24T09:12:20\tsay "hi"\n'
    )

    acquisition_json = sidecar_dir / "sub-01_task-rest_bold.json"
    acquisition_json.write_text(
        json.dumps(
            {
                "AcquisitionTime": "23:30:00.123",
                "AcquisitionDateTime": "2024-01-10T23:30:00",
                "RepetitionTime": 2.0,
                "Nested": {"Unchanged": True},
                "global": {
                    "const": {
                        "PerformedProcedureStepStartTime": "151258.640000",
                        "SeriesTime": "154553.343000",
                        "StudyTime": 91258.562,
                    }
                },
                "time": {
                    "samples": {
                        "AcquisitionTime": ["154550.195000", "152958.000000"],
                        "ContentTime": ["154553.359000", "152958.000000"],
                    }
                },
            }
        )
    )
    untouched_json = sidecar_dir / "sub-01_task-other_bold.json"
    untouched_json.write_text('{"RepetitionTime": 3.0}\n')
    return bids_dir, acquisition_json, untouched_json


def test_date_time_shift_command(tmp_path, caplog):
    """Shift scans dates, round acquisition times, and retain unrelated metadata."""
    bids_dir, acquisition_json, untouched_json = _create_date_time_shift_dataset(tmp_path)
    untouched_contents = untouched_json.read_text()

    assert _main(["date-time-shift", str(bids_dir), "--n-cpus", "2"]) == 0

    first_table = pd.read_csv(
        bids_dir / "sub-01" / "ses-01" / "sub-01_ses-01_scans.tsv",
        sep="\t",
        keep_default_na=False,
    )
    later_table = pd.read_csv(
        bids_dir / "sub-01" / "ses-02" / "sub-01_ses-02_scans.tsv",
        sep="\t",
        keep_default_na=False,
    )
    assert first_table["acq_time"].tolist() == [
        "1800-01-01T14:00:00",
        "1800-01-02T00:00:00",
        "n/a",
        "not-a-date",
    ]
    assert later_table["acq_time"].tolist() == ["1800-01-15T09:00:00"]
    # Quote characters in untouched columns survive the rewrite verbatim.
    later_scans_file = bids_dir / "sub-01" / "ses-02" / "sub-01_ses-02_scans.tsv"
    assert 'say "hi"' in later_scans_file.read_text()

    metadata = json.loads(acquisition_json.read_text())
    assert metadata == {
        "AcquisitionTime": "00:00:00",
        "AcquisitionDateTime": "2024-01-10T23:30:00",
        "RepetitionTime": 2.0,
        "Nested": {"Unchanged": True},
        "global": {
            "const": {
                "PerformedProcedureStepStartTime": "15:00:00",
                "SeriesTime": "16:00:00",
                "StudyTime": "09:00:00",
            }
        },
        "time": {
            "samples": {
                "AcquisitionTime": ["16:00:00", "15:00:00"],
                "ContentTime": ["16:00:00", "15:00:00"],
            }
        },
    }
    assert untouched_json.read_text() == untouched_contents
    assert "Processed 2 scans.tsv files and 3 JSON files" in caplog.text
    assert "Unparseable acq_time" in caplog.text
    assert "Date field AcquisitionDateTime is not de-identified" in caplog.text


def test_date_time_shift_includes_subject_level_scans_tables(tmp_path):
    """Shift subject-level scans tables independently when no sessions exist."""
    bids_dir = tmp_path / "cross_sectional_dataset"
    (bids_dir / "dataset_description.json").parent.mkdir()
    (bids_dir / "dataset_description.json").write_text('{"Name": "test"}\n')
    scans_files = []
    for subject, acquisition_time in (
        ("sub-01", "2024-01-10T13:43:04"),
        ("sub-02", "2024-02-10T13:43:04"),
    ):
        scans_file = bids_dir / subject / f"{subject}_scans.tsv"
        scans_file.parent.mkdir()
        scans_file.write_text(
            f"filename\tacq_time\nfunc/{subject}_task-rest_bold.nii.gz\t{acquisition_time}\n"
        )
        scans_files.append(scans_file)

    assert _main(["date-time-shift", str(bids_dir)]) == 0

    for scans_file in scans_files:
        scans_table = pd.read_csv(scans_file, sep="\t", keep_default_na=False)
        assert scans_table["acq_time"].tolist() == ["1800-01-01T14:00:00"]


def test_date_time_shift_warns_for_subject_without_parseable_dates(tmp_path, caplog):
    """Warn about unparseable acq_time values even when a subject has no valid dates."""
    bids_dir = tmp_path / "unparseable_dataset"
    scans_file = bids_dir / "sub-01" / "sub-01_scans.tsv"
    scans_file.parent.mkdir(parents=True)
    scans_file.write_text("filename\tacq_time\nfunc/sub-01_task-rest_bold.nii.gz\tJan 10 2024\n")
    original_scans = scans_file.read_text()

    assert _main(["date-time-shift", str(bids_dir)]) == 0

    assert "Unparseable acq_time" in caplog.text
    assert scans_file.read_text() == original_scans


def test_date_time_shift_makes_updated_files_writable(tmp_path, caplog):
    """Add owner-write permission before updating a read-only metadata file."""
    bids_dir, acquisition_json, _ = _create_date_time_shift_dataset(tmp_path)
    acquisition_json.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    assert _main(["date-time-shift", str(bids_dir)]) == 0

    assert acquisition_json.stat().st_mode & stat.S_IWUSR
    assert json.loads(acquisition_json.read_text())["AcquisitionTime"] == "00:00:00"
    assert f"Made file writable: {acquisition_json}" in caplog.text


def test_date_time_shift_dry_run_does_not_modify_files(tmp_path, caplog):
    """Report planned date/time anonymization without writing to the dataset."""
    bids_dir, acquisition_json, _ = _create_date_time_shift_dataset(tmp_path)
    scans_file = bids_dir / "sub-01" / "ses-01" / "sub-01_ses-01_scans.tsv"
    original_scans = scans_file.read_text()
    original_json = acquisition_json.read_text()

    assert _main(["date-time-shift", str(bids_dir), "--dry-run"]) == 0

    assert scans_file.read_text() == original_scans
    assert acquisition_json.read_text() == original_json
    assert "WOULD CHANGE" in caplog.text
    assert "Checked 2 scans.tsv files and 3 JSON files" in caplog.text


def test_date_time_shift_validates_all_metadata_before_writing(tmp_path, caplog):
    """Do not change valid metadata when another JSON file cannot be read."""
    bids_dir, acquisition_json, _ = _create_date_time_shift_dataset(tmp_path)
    scans_file = bids_dir / "sub-01" / "ses-01" / "sub-01_ses-01_scans.tsv"
    original_scans = scans_file.read_text()
    original_json = acquisition_json.read_text()
    (bids_dir / "invalid.json").write_text("not valid JSON")

    assert _main(["date-time-shift", str(bids_dir)]) == 1

    assert scans_file.read_text() == original_scans
    assert acquisition_json.read_text() == original_json
    assert "validation failed; no files were modified" in caplog.text


def test_date_time_shift_help_and_input_validation(tmp_path, capsys):
    """Expose command help and reject a file path in place of a BIDS directory."""
    with pytest.raises(SystemExit) as excinfo:
        _main(["date-time-shift", "--help"])
    assert excinfo.value.code == 0
    help_output = capsys.readouterr().out
    assert "before" in help_output
    assert "DataLad" in help_output
    assert "--n-cpus" in help_output

    path_file = tmp_path / "not_a_directory"
    path_file.touch()
    with pytest.raises(SystemExit) as excinfo:
        _main(["date-time-shift", str(path_file)])
    assert excinfo.value.code == 2

    assert _main(["date-time-shift", str(tmp_path), "--n-cpus", "0"]) == 2


def test_validate_command(tmp_path):
    """Test the validate command."""
    # Create mock BIDS dataset
    bids_dir = tmp_path / "bids_dataset"
    bids_dir.mkdir()
    (bids_dir / "dataset_description.json").touch()

    # Create output prefix
    output_prefix = tmp_path / "validation_output"

    # Test validation
    _main(["validate", str(bids_dir), str(output_prefix)])

    # Check that output files were created
    assert (output_prefix.parent / f"{output_prefix.name}_validation.tsv").exists()


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
    assert excinfo.value.code == 2


def test_group_command(tmp_path):
    """Test the group command."""
    # Create mock BIDS dataset
    bids_dir = tmp_path / "bids_dataset"
    bids_dir.mkdir()
    (bids_dir / "dataset_description.json").touch()

    # Test grouping
    output_prefix = tmp_path / "group_output"
    with pytest.raises(ValueError, match="No objects to concatenate"):
        _main(["group", str(bids_dir), str(output_prefix)])


def test_add_nifti_info_command(tmp_path):
    """Test the add-nifti-info command."""
    # Create mock BIDS dataset
    bids_dir = tmp_path / "bids_dataset"
    bids_dir.mkdir()
    (bids_dir / "dataset_description.json").touch()

    # Test add-nifti-info
    _main(["add-nifti-info", str(bids_dir)])


def test_print_metadata_fields_command(tmp_path):
    """Test the print-metadata-fields command."""
    # Create mock BIDS dataset
    bids_dir = tmp_path / "bids_dataset"
    bids_dir.mkdir()
    (bids_dir / "dataset_description.json").touch()

    # Test print-metadata-fields
    _main(["print-metadata-fields", str(bids_dir)])


def test_remove_metadata_fields_command(tmp_path):
    """Test the remove-metadata-fields command."""
    from json.decoder import JSONDecodeError

    # Create mock BIDS dataset
    bids_dir = tmp_path / "bids_dataset"
    bids_dir.mkdir()
    (bids_dir / "dataset_description.json").touch()

    # Test remove-metadata-fields
    with pytest.raises(JSONDecodeError):
        _main(["remove-metadata-fields", str(bids_dir), "--fields", "field1", "field2"])


def test_validate_command_with_test_dataset(tmp_path, build_bids_dataset):
    """Test the validate command with the test BIDS dataset."""
    bids_dir = _build_cli_dataset(tmp_path, build_bids_dataset, dataset_name="validate_dataset")

    # Run validation
    output_prefix = tmp_path / "validation_output"
    _main(["validate", str(bids_dir), str(output_prefix)])

    # Check that output files were created
    assert (output_prefix.parent / f"{output_prefix.name}_validation.tsv").exists()
    assert (output_prefix.parent / f"{output_prefix.name}_validation.json").exists()


def test_validate_subject_scope_with_n_cpus(tmp_path, build_bids_dataset):
    """Test the validate command with validation-scope subject and n_cpus parallelization."""
    bids_dir = _build_cli_dataset(tmp_path, build_bids_dataset, dataset_name="validate_parallel")

    # Run subject-level validation with 2 CPUs (parallel processing)
    output_prefix = tmp_path / "validation_parallel"

    # This should complete without error
    _main(
        [
            "validate",
            str(bids_dir),
            str(output_prefix),
            "--validation-scope",
            "subject",
            "--n-cpus",
            "1",
        ]
    )

    # Verify the command completed successfully by checking if the output files exist
    assert (output_prefix.parent / f"{output_prefix.name}_validation.tsv").exists()
    assert (output_prefix.parent / f"{output_prefix.name}_validation.json").exists()


def test_group_command_with_test_dataset(tmp_path, build_bids_dataset):
    """Test the group command with the test BIDS dataset."""
    bids_dir = _build_cli_dataset(tmp_path, build_bids_dataset, dataset_name="group_dataset")

    # Run grouping
    output_prefix = tmp_path / "group_output"
    _main(["group", str(bids_dir), str(output_prefix)])

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
    _main(["add-nifti-info", str(bids_dir)])

    # Check that JSON was modified
    with open(json_file) as f:
        modified_json = json.load(f)

    # Verify NIfTI info was added
    assert len(modified_json) > len(original_json)
    assert not any(key.startswith("VoxelSize") for key in original_json)
    assert any(key.startswith("VoxelSize") for key in modified_json)


def test_print_metadata_fields_command_with_test_dataset(tmp_path, capsys, build_bids_dataset):
    """Test the print-metadata-fields command with the test BIDS dataset."""
    bids_dir = _build_cli_dataset(
        tmp_path, build_bids_dataset, dataset_name="metadata_fields_dataset"
    )

    # Run print-metadata-fields
    _main(["print-metadata-fields", str(bids_dir)])

    # Check output
    captured = capsys.readouterr()
    assert captured.out  # Verify there is output
    assert "Manufacturer" in captured.out  # Common BIDS metadata field


def test_remove_metadata_fields_command_with_test_dataset(tmp_path, build_bids_dataset):
    """Test the remove-metadata-fields command with the test BIDS dataset."""
    bids_dir = _build_cli_dataset(
        tmp_path, build_bids_dataset, dataset_name="remove_metadata_dataset"
    )

    # Get a sample JSON sidecar
    json_file = next(bids_dir.rglob("*.json"))

    # Store original JSON content
    with open(json_file) as f:
        original_json = json.load(f)

    # Choose a field that exists in the JSON
    field_to_remove = next(iter(original_json.keys()))
    assert field_to_remove in original_json

    # Run remove-metadata-fields
    _main(["remove-metadata-fields", str(bids_dir), "--fields", field_to_remove])

    # Check that field was removed
    with open(json_file) as f:
        modified_json = json.load(f)
    assert field_to_remove not in modified_json


def test_purge_command_with_test_dataset(tmp_path, build_bids_dataset):
    """Test the purge command with the test BIDS dataset."""
    bids_dir = _build_cli_dataset(tmp_path, build_bids_dataset, dataset_name="purge_dataset")

    # Create .cubids directory and add some files
    cubids_dir = bids_dir / ".cubids"
    cubids_dir.mkdir()
    (cubids_dir / "validation_data.json").touch()

    # Create scans.txt with a list of files to purge
    scans_file = tmp_path / "scans.txt"
    dwi_niis = list(bids_dir.rglob("*_dwi.nii.gz"))
    for dwi_nii in dwi_niis:
        assert dwi_nii.exists()

    with open(scans_file, "w") as f:
        f.write("\n".join([str(dwi_nii.relative_to(bids_dir)) for dwi_nii in dwi_niis]))

    # Run purge
    _main(["purge", str(bids_dir), str(scans_file)])

    # Verify .cubids directory was removed
    for dwi_nii in dwi_niis:
        assert not dwi_nii.exists()
