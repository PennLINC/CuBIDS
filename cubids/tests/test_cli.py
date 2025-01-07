"""
This file contains unit tests for the command-line interface (CLI) of the CuBIDS package.

The tests cover the following functions:
- _path_exists: Tests whether a given path exists or not.
- _is_file: Tests whether a given path is a file or a directory.
- _get_parser: Tests the creation and configuration of the argument parser.
- _main: Tests the main function of the CLI.

Each test case includes assertions to verify the expected behavior of the corresponding function.

Author: [Your Name]
Date: [Current Date]
"""

import argparse
from functools import partial

import pytest

from cubids.cli import _get_parser, _is_file, _main, _path_exists
from cubids.tests.utils import chdir


def test_path_exists(tmp_path):
    """Test whether a given path exists or not."""
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
    """Test whether a given path exists or not."""
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


def _test_get_parser():
    """Test the creation and configuration of the argument parser.

    This function tests the `_get_parser` function by asserting that the returned object is an
    instance of `argparse.ArgumentParser`, and that it has the expected `prog` and `description`
    attributes.
    Additional assertions can be added to test the configuration of the parser.
    """
    parser = _get_parser()
    assert isinstance(parser, argparse.ArgumentParser)
    assert parser.prog == "cubids"
    assert parser.description == "Console script for cubids"
    # Add more assertions for the parser configuration


def _test_main():
    """Test the main function of the CLI.

    This function tests the `_main` function by providing different sets of arguments.
    It asserts that the function returns the expected exit code (0 or 1) based on the provided
    arguments.
    """
    # Test the main function with valid arguments
    argv = ["validate", "/path/to/dataset"]
    assert _main(argv) == 0

    # Test the main function with invalid arguments
    argv = ["invalid-command", "/path/to/dataset"]
    assert _main(argv) == 1

    # Test the main function with missing arguments
    argv = []
    assert _main(argv) == 1
