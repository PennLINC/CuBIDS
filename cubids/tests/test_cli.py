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
import pytest

from cubids.cli import _path_exists, _is_file, _get_parser, _main


def _test_path_exists():
    """Test whether a given path exists or not.

    This function tests the `_path_exists` function by providing a path that exists
    and a path that does not exist.
    It asserts that the function returns the expected path when the path exists,
    and raises an `argparse.ArgumentTypeError` when the path does not exist.
    """
    assert _path_exists("/path/to/existing/file", None) == "/path/to/existing/file"

    with pytest.raises(argparse.ArgumentTypeError):
        _path_exists("/path/to/nonexistent/file", None)


def _test_is_file():
    """Test whether a given path is a file or a directory.

    This function tests the `_is_file` function by providing a path that is a file
    and a path that is a directory.
    It asserts that the function returns the expected path when the path is a file,
    and raises an `argparse.ArgumentTypeError` when the path is a directory.
    """
    assert _is_file("/path/to/file.txt", None) == "/path/to/file.txt"

    with pytest.raises(argparse.ArgumentTypeError):
        _is_file("/path/to/directory", None)


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
