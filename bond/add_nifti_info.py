'''Adds nifti voxel size/spacial matrix dimensions to sidecars.'''

import bids
from pathlib import Path
import json
import nibabel as nb
import numpy as np

# LOOP THROUGH DIRECTORY
# create bids layout object
# get all sidecars
# for each sidecar, add the important nift params

def img_to_json(img_path):
    return img_path.replace(".nii.gz", "").replace(".nii", "") + ".json"

def nifti_info_to_json(path):
    bids_dir = path
    layout = bids.BIDSLayout(bids_dir)

    # loop through all niftis in the bids dir
    for path in Path(bids_dir).rglob("sub-*/**/*.*"):
        if str(path).endswith(".nii") or str(path).endswith(".nii.gz"):
            img = nb.load(path)

            # get important info from niftis
            obliquity = np.any(nb.affines.obliquity(img.affine)
                                                > 1e-4)
            voxel_sizes = img.header.get_zooms()
            matrix_dims = img.shape

            # add nifti info to corresponding sidecars

            sidecar = img_to_json(str(path))

            if Path(sidecar).exists():

                with open(sidecar) as f:
                    data = json.load(f)

                data["VoxelSizeDim1"] = float(voxel_sizes[0])
                data["Dim1Size"] = matrix_dims[0]
                data["VoxelSizeDim2"] = float(voxel_sizes[1])
                data["Dim2Size"] = matrix_dims[1]
                data["VoxelSizeDim3"] = float(voxel_sizes[2])
                data["Dim3Size"] = matrix_dims[2]
                if img.ndim == 4:
                    data["NumVolumes"] = matrix_dims[3]

                with open(sidecar, 'w') as file:
                    json.dump(data, file, indent=4)




