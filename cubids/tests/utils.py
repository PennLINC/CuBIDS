"""Utility functions for CuBIDS' tests."""

import hashlib
import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path

import nibabel as nb
import numpy as np
import pandas as pd
import importlib.resources

TEST_DATA = importlib.resources.files("cubids") / "tests/data"


def get_data(tmp_path):
    """Copy testing data to a local directory.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary path where the test data will be copied.

    Returns
    -------
    pathlib.Path
        The path to the copied test data.
    """
    data_root = tmp_path / "testdata"
    shutil.copytree(TEST_DATA, str(data_root))
    return data_root


def _remove_a_json(json_file):
    """Remove a JSON file.

    Parameters
    ----------
    json_file : str or pathlib.Path
        The path to the JSON file to be removed.
    """
    os.remove(json_file)


def _edit_a_nifti(nifti_file):
    """Edit a NIfTI file by replacing its data with random values.

    Parameters
    ----------
    nifti_file : str or pathlib.Path
        The path to the NIfTI file to be edited.
    """
    img = nb.load(nifti_file)
    new_img = nb.Nifti1Image(np.random.rand(*img.shape), affine=img.affine, header=img.header)
    new_img.to_filename(nifti_file)


def file_hash(file_name):
    """Create a hash from a file.

    Parameters
    ----------
    file_name : str or pathlib.Path
        The path to the file to be hashed.

    Returns
    -------
    str
        The MD5 hash of the file.
    """
    with open(str(file_name), "rb") as fcheck:
        data = fcheck.read()
    return hashlib.md5(data).hexdigest()


def _get_json_string(json_path):
    """Get the content of a JSON file as a string.

    Parameters
    ----------
    json_path : pathlib.Path
        The path to the JSON file.

    Returns
    -------
    str
        The content of the JSON file as a string.
    """
    with json_path.open("r") as f:
        content = "".join(f.readlines())
    return content


def _add_deletion(summary_tsv):
    """Add a deletion entry to a summary TSV file.

    Parameters
    ----------
    summary_tsv : str or pathlib.Path
        The path to the summary TSV file.

    Returns
    -------
    object
        The value of the 'KeyParamGroup' column for the modified row.
    """
    df = pd.read_table(summary_tsv)
    df.loc[3, "MergeInto"] = 0
    df.to_csv(summary_tsv, sep="\t", index=False)
    return df.loc[3, "KeyParamGroup"]


def _add_ext_files(img_path):
    """Add and save extension files in the same directory as the image file.

    Parameters
    ----------
    img_path : str or pathlib.Path
        The path to the image file.
    """
    dwi_exts = [".bval", ".bvec"]

    # everyone gets a physio file
    no_suffix = img_path.rpartition("_")[0]
    physio_file = no_suffix + "_physio" + ".tsv.gz"
    # save ext file in img_path's parent dir
    Path(physio_file).touch()

    if "/dwi/" in img_path:
        # add bval and bvec
        for ext in dwi_exts:
            dwi_ext_file = img_path.replace(".nii.gz", "").replace(".nii", "") + ext
            Path(dwi_ext_file).touch()
    if "bold" in img_path:
        no_suffix = img_path.rpartition("_")[0]
        bold_ext_file = no_suffix + "_events" + ".tsv"
        Path(bold_ext_file).touch()


def _edit_a_json(json_file):
    """Open a JSON file, write a test entry to it, and save it to the same name.

    Parameters
    ----------
    json_file : str or pathlib.Path
        The path to the JSON file to be edited.
    """
    with open(json_file, "r") as metadatar:
        metadata = json.load(metadatar)

    metadata["THIS_IS_A_TEST"] = True
    with open(json_file, "w") as metadataw:
        json.dump(metadata, metadataw)


@contextmanager
def chdir(path):
    """Temporarily change directories.

    Taken from https://stackoverflow.com/a/37996581/2589328.
    """
    oldpwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(oldpwd)
