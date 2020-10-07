#!/usr/bin/env python

"""Tests for `bond` package."""
import sys
sys.path.append("..")
import os
import argparse
import pytest
import tempfile
import os.path as op
from copy import deepcopy
import base64
import shutil
from glob import glob

# Can't use pytest's temp_dir because input directories have to be mocked
WORKING_DIR = tempfile.mkdtemp()
BIDS_DATA_ZIP_URL = "https://github.com/PennLINC/bids-examples/" \
                    "archive/master.tar.gz"


@pytest.fixture(scope="session")
def bids_data(work_dir=WORKING_DIR):
    """Download example bids data."""
    status = os.system('curl -sSL {} | tar xfz - -C {}'.format(
        BIDS_DATA_ZIP_URL, work_dir))
    assert status == 0
    assert 'bids-examples-master' in os.listdir(work_dir)
    return work_dir


def test_synthetic(bids_data):
    assert 1 == 1
    assert True
    assert op.exists(op.join(bids_data, "bids-examples-master/synthetic/"))


def test_fill_metadata(bids_data):
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


def test_rename_files(bids_data):
    data_root = op.join(bids_data + "/incomplete/to-rename")
    my_bond = bond.BOnD(data_root)

    original_suffix = "_run-01_bold"
    renamed_suffix = "_acq-multiband_run-01_bold"

    # Show that there are none of these files already there
    assert not glob("*" + renamed_suffix + "*")

    # Actually do the renaming
    my_bond.rename_files(original_suffix, renamed_suffix)

    # Show that these files are now there
    assert not glob("*" + renamed_suffix + "*")


def test_fieldmap_exists(bids_data):
    ok_data_root = op.join(bids_data + "/complete/fieldmaps")
    not_ok_data_root = op.join(bids_data + "/incomplete/fieldmaps")

    ok_bond = bond.BOnD(ok_data_root)
    assert ok_bond.fieldmaps_ok()

    not_ok_bond = bond.BOnD(not_ok_data_root)
    assert not not_ok_bond.fieldmaps_ok()
