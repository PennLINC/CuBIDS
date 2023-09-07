"""Utility functions for CuBIDS' tests."""
import hashlib
import json
import os
import shutil
from pathlib import Path

import nibabel as nb
import numpy as np
import pandas as pd
from pkg_resources import resource_filename as pkgrf

TEST_DATA = pkgrf("cubids", "tests/data")


def get_data(tmp_path):
    """Copy testing data to a local directory."""
    data_root = tmp_path / "testdata"
    shutil.copytree(TEST_DATA, str(data_root))
    return data_root


def _remove_a_json(json_file):
    os.remove(json_file)


def _edit_a_nifti(nifti_file):
    img = nb.load(nifti_file)
    new_img = nb.Nifti1Image(np.random.rand(*img.shape), affine=img.affine, header=img.header)
    new_img.to_filename(nifti_file)


def file_hash(file_name):
    """Create a hash from a file."""
    with open(str(file_name), "rb") as fcheck:
        data = fcheck.read()
    return hashlib.md5(data).hexdigest()


def _get_json_string(json_path):
    with json_path.open("r") as f:
        content = "".join(f.readlines())
    return content


def _add_deletion(summary_tsv):
    df = pd.read_table(summary_tsv)
    df.loc[3, "MergeInto"] = 0
    df.to_csv(summary_tsv, sep="\t", index=False)
    return df.loc[3, "KeyParamGroup"]


# def _edit_tsv(summary_tsv):
#     df = pd.read_table(summary_tsv)
#     df['RenameKeyGroup'] = df['RenameKeyGroup'].apply(str)
#     df['KeyGroup'] = df['KeyGroup'].apply(str)
#     for row in range(len(df)):
#         if df.loc[row, 'KeyGroup'] == \
#             "acquisition-v4_datatype-fmap_fmap-magnitude1_suffix-magnitude1":
#             df.at[row, 'RenameKeyGroup'] = \
#                 "acquisition-v5_datatype-fmap_fmap-magnitude1_suffix-magnitude1"
#     df.to_csv(summary_tsv)


def _add_ext_files(img_path):
    # add and save extension files in
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
    """Open a json file, write something to it and save it to the same name."""
    with open(json_file, "r") as metadatar:
        metadata = json.load(metadatar)

    metadata["THIS_IS_A_TEST"] = True
    with open(json_file, "w") as metadataw:
        json.dump(metadata, metadataw)
