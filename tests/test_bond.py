#!/usr/bin/env python

"""Tests for `bond` package."""
import sys
sys.path.append("..")
import os
import pytest
from pkg_resources import resource_filename as pkgrf
import shutil
import bond
import tempfile
from pathlib import Path
import os.path as op
from copy import deepcopy
import base64
from glob import glob

TEST_DATA = pkgrf("bond", "testdata")


def test_data(tmp_path):
    data_root = Path(tmp_path) / "testdata"
    shutil.copytree(TEST_DATA, str(data_root))
    assert len(list(data_root.rglob("*"))) > 5


"""
def test_fill_metadata(tmp_path):
    data_root = tmp_path / "testdata"
    shutil.copytree(TEST_DATA, str(data_root))
    data_root = op.join(bids_data + "/incomplete/fill-metadata")
    my_bond = bond.BOnD(data_root)
    # fill_metadata should add metadata elements to the json sidecar
    my_bond.fill_metadata(pattern="*acq-multiband_bold.nii.gz",
                          metadata={"EchoTime": 0.005})
    # get_metadata shold return a list of dictionaries that contain metadata for
    # scans matching `pattern`
    for metadata in my_bond.get_metadata(pattern="*acq-multiband_bold"):
        assert metadata['EchoTime'] == 0.005

    # fill_metadata should add metadata elements to the json sidecar
    my_bond.fill_metadata(pattern="*acq-multiband_bold.nii.gz",
                          metadata={"EchoTime": 0.009})
    # get_metadata shold return a list of dictionaries that contain metadata for
    # scans matching `pattern`
    for metadata in my_bond.get_metadata(pattern="*acq-multiband_bold"):
        assert metadata['EchoTime'] == 0.009


def test_detect_unique_parameter_sets(bids_data):
    data_root = op.join(bids_data + "/incomplete/multi_param_sets")
    my_bond = bond.BOnD(data_root)

    # Ground truth groups
    true_combinations = [
        {"EchoTime": 0.005, "PhaseEncodingDirection": "j"},
        {"EchoTime": 0.005, "PhaseEncodingDirection": "j-"}
    ]

    # Find param sets from the data on
    combinations = my_bond.find_param_sets(pattern="*_bold")

    assert len(true_combinations) == len(combinations)

"""


def test_rename_files(tmp_path):
    data_root = tmp_path / "testdata"
    shutil.copytree(TEST_DATA, str(data_root))
    data_root = str(data_root / "complete")
    my_bond = bond.BOnD(data_root)

    original_suffix = "_run-01_bold"
    renamed_suffix = "_acq-multiband_run-01_bold"

    # Show that there are none of these files already there
    assert not glob("*" + renamed_suffix + "*")

    # Actually do the renaming
    my_bond.rename_files(original_suffix, renamed_suffix)

    # Show that these files are now there
    assert not glob("*" + renamed_suffix + "*")


"""
def test_fieldmap_exists(bids_data):
    ok_data_root = op.join(bids_data + "/complete/fieldmaps")
    not_ok_data_root = op.join(bids_data + "/incomplete/fieldmaps")

    ok_bond = bond.BOnD(ok_data_root)
    assert ok_bond.fieldmaps_ok()

    not_ok_bond = bond.BOnD(not_ok_data_root)
    assert not not_ok_bond.fieldmaps_ok()
"""
