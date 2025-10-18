"""Main module for CuBIDS.

This module provides the core functionalities of the CuBIDS package, including
operations for handling BIDS datasets, clustering, and metadata merging.
"""

import csv
import json
import os
import re
import subprocess
import warnings
from collections import defaultdict
from pathlib import Path
from shutil import copyfile, copytree

import bids
import bids.layout
import datalad.api as dlapi
import nibabel as nb
import numpy as np
import pandas as pd
from bids.layout import parse_file_entities
from bids.utils import listify
from tqdm import tqdm

from cubids import utils
from cubids.config import load_config, load_schema
from cubids.constants import NON_KEY_ENTITIES
from cubids.metadata_merge import check_merging_operations, group_by_acquisition_sets

warnings.simplefilter(action="ignore", category=FutureWarning)
bids.config.set_option("extension_initial_dot", True)


class CuBIDS(object):
    """The main CuBIDS class.

    Parameters
    ----------
    data_root : :obj:`str`
        Path to the root of the BIDS dataset.
    use_datalad : :obj:`bool`, optional
        If True, use datalad to track changes to the BIDS dataset.
        Default is False.
    acq_group_level : :obj:`str`, optional
        The level at which to group scans. Default is "subject".
    grouping_config : :obj:`str`, optional
        Path to the grouping config file.
        Default is None, in which case the default config in CuBIDS is used.
    force_unlock : :obj:`bool`, optional
        If True, force unlock all files in the BIDS dataset.
        Default is False.
    schema_json : :obj:`str`, optional
        Path to a BIDS schema JSON file.
        Default is None, in which case the default schema in CuBIDS is used.

    Attributes
    ----------
    path : :obj:`str`
        Path to the root of the BIDS dataset.
    _layout : :obj:`bids.layout.BIDSLayout`
        The BIDSLayout object.
    keys_files : :obj:`dict`
        A dictionary of entity sets and the files that belong to them.
    fieldmaps_cached : :obj:`bool`
        If True, the fieldmaps have been cached.
    datalad_ready : :obj:`bool`
        If True, the datalad dataset has been initialized.
    datalad_handle : :obj:`datalad.api.Dataset`
        The datalad dataset handle.
    old_filenames : :obj:`list`
        A list of old filenames.
    new_filenames : :obj:`list`
        A list of new filenames.
    IF_rename_paths : :obj:`list`
        A list of IntendedFor paths that have been renamed.
    grouping_config : :obj:`dict`
        The grouping config dictionary.
    acq_group_level : :obj:`str`
        The level at which to group scans.
    scans_txt : :obj:`str`
        Path to the .txt file that lists the scans
        you want to be deleted from the dataset, along
        with their associations.
    force_unlock : :obj:`bool`
        If True, force unlock all files in the BIDS dataset.
    cubids_code_dir : :obj:`bool`
        If True, the CuBIDS code directory exists.
    data_dict : :obj:`dict`
        A data dictionary for TSV outputs.
    use_datalad : :obj:`bool`
        If True, use datalad to track changes to the BIDS dataset.
    schema : :obj:`dict`
        The BIDS schema dictionary.
    is_longitudinal : :obj:`bool`
        If True, adds "ses" in filepath.
    """

    def __init__(
        self,
        data_root,
        use_datalad=False,
        acq_group_level="subject",
        grouping_config=None,
        force_unlock=False,
        schema_json=None,
    ):
        self.path = os.path.abspath(data_root)
        self._layout = None
        self.keys_files = {}
        self.fieldmaps_cached = False
        self.datalad_ready = False
        self.datalad_handle = None
        self.old_filenames = []  # files whose entity sets changed
        self.new_filenames = []  # new filenames for files to change
        self.IF_rename_paths = []  # fmap jsons with rename intended fors
        self.grouping_config = load_config(grouping_config)
        self.acq_group_level = acq_group_level
        self.scans_txt = None  # txt file of scans to purge (for purge only)
        self.force_unlock = force_unlock  # force unlock for add-nifti-info
        self.cubids_code_dir = Path(self.path + "/code/CuBIDS").is_dir()
        self.data_dict = {}  # data dictionary for TSV outputs
        self.use_datalad = use_datalad  # True if flag set, False if flag unset
        self.schema = load_schema(schema_json)
        self.is_longitudinal = self._infer_longitudinal()  # inferred from dataset structure

        if self.use_datalad:
            self.init_datalad()

        if self.is_longitudinal and self.acq_group_level == "session":
            NON_KEY_ENTITIES.remove("session")
        elif not self.is_longitudinal and self.acq_group_level == "session":
            raise ValueError(
                'Data is not longitudinal, so "session" is not a valid grouping level.'
            )

    @property
    def layout(self):
        """Return the BIDSLayout object.

        Returns
        -------
        BIDSLayout
            The BIDSLayout object associated with the current instance.
        """
        if self._layout is None:
            # print("SETTING LAYOUT OBJECT")
            self.reset_bids_layout()
            # print("LAYOUT OBJECT SET")
        return self._layout

    def _infer_longitudinal(self):
        """Infer if the dataset is longitudinal based on its structure.

        This method checks if any file or directory within the dataset path
        contains the substring "ses-" in its name, which is a common convention
        used to denote session identifiers in longitudinal datasets.

        Returns
        -------
        bool
            True if the dataset is longitudinal (i.e., contains session identifiers),
            False otherwise.
        """
        return any("ses-" in str(f) for f in Path(self.path).rglob("*"))

    def reset_bids_layout(self, validate=False):
        """Reset the BIDS layout.

        This sets the ``_layout`` attribute to a new :obj:`bids.layout.BIDSLayout` object.

        Parameters
        ----------
        validate : :obj:`bool`, optional
            If True, validate the BIDS dataset. Default is False.
        """
        # create BIDS Layout Indexer class

        ignores = [
            "code",
            "stimuli",
            "sourcedata",
            "models",
            re.compile(r"^\."),
            re.compile(r"/\."),
        ]

        indexer = bids.BIDSLayoutIndexer(validate=validate, ignore=ignores, index_metadata=False)

        self._layout = bids.BIDSLayout(self.path, validate=validate, indexer=indexer)

    def create_cubids_code_dir(self):
        """Create CuBIDS code directory.

        This creates the CuBIDS code directory at self.path/code/CuBIDS.

        Returns
        -------
        :obj:`str`
            Path to the CuBIDS code directory.

        Notes
        -----
        Why not use ``os.makedirs``?
        """
        # check if BIDS_ROOT/code/CuBIDS exists
        if not self.cubids_code_dir:
            subprocess.run(["mkdir", self.path + "/code"])
            subprocess.run(["mkdir", self.path + "/code/CuBIDS/"])
            self.cubids_code_dir = True
        return self.cubids_code_dir

    def init_datalad(self):
        """Initialize a datalad Dataset at the specified path.

        This method creates a datalad dataset at the path specified by `self.path`.
        It sets the `datalad_ready` attribute to True and assigns the datalad.Dataset
        object to the `datalad_handle` attribute.

        Attributes
        ----------
        datalad_ready : bool
            Indicates whether the datalad dataset has been successfully initialized.
        datalad_handle : datalad.api.Dataset
            The datalad dataset object associated with the specified path.

        Notes
        -----
        If the dataset is not already installed at the specified path, this method
        will create a new dataset with the configuration process "text2git" and
        enable the annex feature.
        """
        self.datalad_ready = True

        self.datalad_handle = dlapi.Dataset(self.path)
        if not self.datalad_handle.is_installed():
            self.datalad_handle = dlapi.create(
                self.path, cfg_proc="text2git", force=True, annex=True
            )

    def datalad_save(self, message=None):
        """Perform a DataLad Save operation on the BIDS tree.

        This method checks for an active DataLad handle and ensures that the
        status of all objects after the save operation is "ok".

        Parameters
        ----------
        message : str or None, optional
            Commit message to use with DataLad save. If None, a default message
            "CuBIDS Save" will be used.

        Raises
        ------
        Exception
            If DataLad has not been initialized or if the save operation fails.
        """
        if not self.datalad_ready:
            raise Exception("DataLad has not been initialized. use datalad_init()")

        statuses = self.datalad_handle.save(message=message or "CuBIDS Save")
        saved_status = set([status["status"] for status in statuses])
        if not saved_status == set(["ok"]):
            raise Exception("Failed to save in DataLad")

    def is_datalad_clean(self):
        """If True, no changes are detected in the datalad dataset.

        Returns
        -------
        :obj:`bool`
            True if the datalad dataset is clean, False otherwise.

        Raises
        ------
        Exception
            If datalad has not been initialized.
        """
        if not self.datalad_ready:
            raise Exception("Datalad not initialized, can't determine status")
        statuses = set([status["state"] for status in self.datalad_handle.status()])
        return statuses == set(["clean"])

    def datalad_undo_last_commit(self):
        """Revert the most recent commit, remove it from history.

        Uses git reset --hard to revert to the previous commit.

        Raises
        ------
        Exception
            If there are untracked changes in the datalad dataset.
        """
        if not self.is_datalad_clean():
            raise Exception("Untracked changes present. Run clear_untracked_changes first")
        reset_proc = subprocess.run(["git", "reset", "--hard", "HEAD~1"], cwd=self.path)
        reset_proc.check_returncode()

    def add_nifti_info(self):
        """
        Add information from NIfTI files to their corresponding JSON sidecars.

        This method processes all NIfTI files in the BIDS directory specified by `self.path`.
        It extracts relevant metadata from each NIfTI file and updates the corresponding JSON
        sidecar files with this information. If `self.force_unlock` is set, it will unlock
        the dataset using `datalad` before processing the files.

        Metadata added to the JSON sidecars includes:
        - Obliquity
        - Voxel sizes (dimensions 1, 2, and 3)
        - Matrix dimensions (sizes of dimensions 1, 2, and 3)
        - Number of volumes (for 4D images)
        - Image orientation

        If `self.use_datalad` is set, the changes will be saved using `datalad`.

        Raises
        ------
        Exception
            If there is an error loading a NIfTI file or parsing a JSON sidecar file.

        Notes
        -----
        - This method assumes that the NIfTI files are organized in a BIDS-compliant
            directory structure.
        - The method will skip any files in hidden directories (directories starting with a dot).
        - If a JSON sidecar file does not exist for a NIfTI file, it will be skipped.
        """
        # check if force_unlock is set
        if self.force_unlock:
            # CHANGE TO SUBPROCESS.CALL IF NOT BLOCKING
            subprocess.run(["datalad", "unlock"], cwd=self.path)

        # loop through all niftis in the bids dir
        for path in Path(self.path).rglob("sub-*/**/*.*"):
            # ignore all dot directories
            if "/." in str(path):
                continue

            if str(path).endswith(".nii") or str(path).endswith(".nii.gz"):
                try:
                    img = nb.load(str(path))
                except Exception:
                    print("Empty Nifti File: ", str(path))
                    continue

                # get important info from niftis
                obliquity = np.any(nb.affines.obliquity(img.affine) > 1e-4)
                voxel_sizes = img.header.get_zooms()
                matrix_dims = img.shape
                # add nifti info to corresponding sidecars​
                sidecar = utils.img_to_new_ext(str(path), ".json")
                if Path(sidecar).exists():
                    try:
                        with open(sidecar) as f:
                            data = json.load(f)
                    except Exception:
                        print("Error parsing this sidecar: ", sidecar)

                    if "Obliquity" not in data.keys():
                        data["Obliquity"] = str(obliquity)
                    if "VoxelSizeDim1" not in data.keys():
                        data["VoxelSizeDim1"] = float(voxel_sizes[0])
                    if "VoxelSizeDim2" not in data.keys():
                        data["VoxelSizeDim2"] = float(voxel_sizes[1])
                    if "VoxelSizeDim3" not in data.keys():
                        data["VoxelSizeDim3"] = float(voxel_sizes[2])
                    if "Dim1Size" not in data.keys():
                        data["Dim1Size"] = matrix_dims[0]
                    if "Dim2Size" not in data.keys():
                        data["Dim2Size"] = matrix_dims[1]
                    if "Dim3Size" not in data.keys():
                        data["Dim3Size"] = matrix_dims[2]
                    if "NumVolumes" not in data.keys():
                        if img.ndim == 4:
                            data["NumVolumes"] = matrix_dims[3]
                        elif img.ndim == 3:
                            data["NumVolumes"] = 1
                    if "ImageOrientation" not in data.keys():
                        orient = nb.orientations.aff2axcodes(img.affine)
                        orient = [str(orientation) for orientation in orient]
                        joined = "".join(orient) + "+"
                        data["ImageOrientation"] = joined

                    with open(sidecar, "w") as file:
                        json.dump(data, file, indent=4)

        if self.use_datalad:
            self.datalad_save(message="Added nifti info to sidecars")

        self.reset_bids_layout()

    def add_file_collections(self):
        """Add file collections to the dataset.

        This method processes all files in the BIDS directory specified by `self.path`.
        It identifies file collections based on the presence of specific entities in the filenames.

        Notes
        -----
        This method uses metadata from direct sidecar JSON files,
        so it will not work with inherited metadata.
        """
        # check if force_unlock is set
        if self.force_unlock:
            # CHANGE TO SUBPROCESS.CALL IF NOT BLOCKING
            subprocess.run(["datalad", "unlock"], cwd=self.path)

        checked_files = []

        # loop through all niftis in the bids dir
        for bids_file in self.layout.get(extension=[".nii", ".nii.gz"]):
            path = bids_file.path

            if path in checked_files:
                continue

            # Add file collection metadata to the sidecar
            files, collection_metadata = utils.collect_file_collections(self.layout, path)
            filepaths = [f.path for f in files]
            checked_files.extend(filepaths)

            for collection_path in filepaths:
                # Add metadata to the sidecar
                sidecar = utils.img_to_new_ext(str(collection_path), ".json")
                if Path(sidecar).exists():
                    with open(sidecar, "r") as f:
                        data = json.load(f)
                else:
                    data = {}

                data.update(collection_metadata)
                with open(sidecar, "w") as f:
                    json.dump(data, f, sort_keys=True, indent=4)

        if self.use_datalad:
            self.datalad_save(message="Added file collection metadata to sidecars")

        self.reset_bids_layout()

    def apply_tsv_changes(self, summary_tsv, files_tsv, new_prefix, raise_on_error=True):
        """Apply changes documented in the edited summary tsv and generate the new tsv files.

        This function looks at the RenameEntitySet and MergeInto
        columns and modifies the bids dataset according to the
        specified changs.

        Parameters
        ----------
        summary_tsv : :obj:`str`
            Path to the edited summary tsv file.
        files_tsv : :obj:`str`
            Path to the edited files tsv file.
        new_prefix : :obj:`str`
            Path prefix to the new tsv files.
        raise_on_error : :obj:`bool`
            If True, raise an error if the MergeInto column contains invalid merges.
        """
        # reset lists of old and new filenames
        self.old_filenames = []
        self.new_filenames = []

        if "/" not in str(summary_tsv):
            if not self.cubids_code_dir:
                self.create_cubids_code_dir()
            summary_tsv = self.path + "/code/CuBIDS/" + summary_tsv

        if "/" not in str(files_tsv):
            if not self.cubids_code_dir:
                self.create_cubids_code_dir()
            files_tsv = self.path + "/code/CuBIDS/" + files_tsv

        summary_df = pd.read_table(summary_tsv)
        files_df = pd.read_table(files_tsv)

        # Check that the MergeInto column only contains valid merges
        ok_merges, deletions = check_merging_operations(summary_tsv, raise_on_error=raise_on_error)

        merge_commands = []
        for source_id, dest_id in ok_merges:
            dest_files = files_df.loc[(files_df[["ParamGroup", "EntitySet"]] == dest_id).all(1)]
            source_files = files_df.loc[
                (files_df[["ParamGroup", "EntitySet"]] == source_id).all(1)
            ]

            # Get a source json file
            img_full_path = self.path + source_files.iloc[0].FilePath
            source_json = utils.img_to_new_ext(img_full_path, ".json")
            for dest_nii in dest_files.FilePath:
                dest_json = utils.img_to_new_ext(self.path + dest_nii, ".json")
                if Path(dest_json).exists() and Path(source_json).exists():
                    merge_commands.append(f"cubids bids-sidecar-merge {source_json} {dest_json}")

        # Get the delete commands
        to_remove = []
        for rm_id in deletions:
            files_to_rm = files_df.loc[(files_df[["ParamGroup", "EntitySet"]] == rm_id).all(1)]

            for rm_me in files_to_rm.FilePath:
                if Path(self.path + rm_me).exists():
                    to_remove.append(self.path + rm_me)

        # call purge associations on list of files to remove
        self._purge_associations(to_remove)

        # Now do the file renaming
        change_keys_df = summary_df[summary_df.RenameEntitySet.notnull()]
        move_ops = []
        # return if nothing to change
        if len(change_keys_df) > 0:
            entity_sets = {}

            for i in range(len(change_keys_df)):
                new_key = change_keys_df.iloc[i]["RenameEntitySet"]
                old_key_param = change_keys_df.iloc[i]["KeyParamGroup"]

                # add to dictionary
                entity_sets[old_key_param] = new_key

            # orig key/param tuples that will have new entity set
            to_change = list(entity_sets.keys())

            for row in range(len(files_df)):
                file_path = self.path + files_df.loc[row, "FilePath"]
                if Path(file_path).exists() and "/fmap/" not in file_path:
                    key_param_group = files_df.loc[row, "KeyParamGroup"]

                    if key_param_group in to_change:
                        orig_key_param = files_df.loc[row, "KeyParamGroup"]

                        new_key = entity_sets[orig_key_param]

                        new_entities = utils._entity_set_to_entities(new_key)

                        # generate new filenames according to new entity set
                        self.change_filename(file_path, new_entities)

            # create string of mv command ; mv command for dlapi.run
            for from_file, to_file in zip(self.old_filenames, self.new_filenames):
                if Path(from_file).exists():
                    # if using datalad, we want to git mv instead of mv
                    if self.use_datalad:
                        move_ops.append(f"git mv {from_file} {to_file}")
                    else:
                        move_ops.append(f"mv {from_file} {to_file}")

        full_cmd = "\n".join(merge_commands + move_ops)
        if full_cmd:
            renames = str(Path(self.path) / (new_prefix + "_full_cmd.sh"))

            # write full_cmd to a .sh file
            with open(renames, "w") as fo:
                fo.write("#!/bin/bash\n")
                fo.write(full_cmd)

            if self.use_datalad:
                # first check if IntendedFor renames need to be saved
                if not self.is_datalad_clean():
                    s1 = "Renamed IntendedFor references to "
                    s2 = "Variant Group scans"
                    IF_rename_msg = s1 + s2
                    self.datalad_handle.save(message=IF_rename_msg)

                s1 = "Renamed Variant Group scans according to their variant "
                s2 = "parameters"

                rename_commit = s1 + s2

                self.datalad_handle.run(cmd=["bash", renames], message=rename_commit)
            else:
                subprocess.run(
                    ["bash", renames],
                    stdout=subprocess.PIPE,
                    cwd=str(Path(new_prefix).parent),
                )
        else:
            print("Not running any commands")

        self.reset_bids_layout()
        self.get_tsvs(new_prefix)

        # remove renames file that gets created under the hood
        subprocess.run(["rm", "-rf", "renames"])

    def change_filename(self, filepath, entities):
        """Apply changes to a filename based on the renamed entity sets.

        This function takes into account the new entity set names
        and renames all files whose entity set names changed.

        Parameters
        ----------
        filepath : :obj:`str`
            Path prefix to a file in the affected entity set change.
        entities : :obj:`dict`
            A pybids dictionary of entities parsed from the new entity set name.

        Notes
        -----
        This is the function I need to spend the most time on, since it has entities hardcoded.
        """
        new_path = utils.build_path(
            filepath=filepath,
            out_entities=entities,
            out_dir=str(self.path),
            schema=self.schema,
            is_longitudinal=self.is_longitudinal,
        )

        exts = Path(filepath).suffixes
        old_ext = "".join(exts)

        suffix = entities["suffix"]

        sub = utils.get_entity_value(filepath, "sub")
        if self.is_longitudinal:
            ses = utils.get_entity_value(filepath, "ses")

        # Add the scan path + new path to the lists of old, new filenames
        self.old_filenames.append(filepath)
        self.new_filenames.append(new_path)

        # NOW NEED TO RENAME ASSOCIATED FILES
        # bids_file = self.layout.get_file(filepath)
        bids_file = filepath
        # associations = bids_file.get_associations()
        associations = self.get_nifti_associations(str(bids_file))
        for assoc_path in associations:
            # assoc_path = assoc.path
            if Path(assoc_path).exists():
                # print("FILE: ", filepath)
                # print("ASSOC: ", assoc.path)
                # ensure assoc not an IntendedFor reference
                if ".nii" not in str(assoc_path):
                    self.old_filenames.append(assoc_path)
                    new_ext_path = utils.img_to_new_ext(
                        new_path,
                        "".join(Path(assoc_path).suffixes),
                    )
                    self.new_filenames.append(new_ext_path)

        # MAKE SURE THESE AREN'T COVERED BY get_associations!!!
        # Update DWI-specific files
        if "/dwi/" in filepath:
            # add the bval and bvec if there
            bval_old = utils.img_to_new_ext(filepath, ".bval")
            bval_new = utils.img_to_new_ext(new_path, ".bval")
            if Path(bval_old).exists() and bval_old not in self.old_filenames:
                self.old_filenames.append(bval_old)
                self.new_filenames.append(bval_new)

            bvec_old = utils.img_to_new_ext(filepath, ".bvec")
            bvec_new = utils.img_to_new_ext(new_path, ".bvec")
            if Path(bvec_old).exists() and bvec_old not in self.old_filenames:
                self.old_filenames.append(bvec_old)
                self.new_filenames.append(bvec_new)

        # Update func-specific files
        # now rename _events and _physio files!
        old_suffix = parse_file_entities(filepath)["suffix"]
        scan_end = "_" + old_suffix + old_ext

        if "_task-" in filepath:
            old_events = filepath.replace(scan_end, "_events.tsv")
            if Path(old_events).exists():
                self.old_filenames.append(old_events)
                new_scan_end = "_" + suffix + old_ext
                new_events = new_path.replace(new_scan_end, "_events.tsv")
                self.new_filenames.append(new_events)

            old_ejson = filepath.replace(scan_end, "_events.json")
            if Path(old_ejson).exists():
                self.old_filenames.append(old_ejson)
                new_scan_end = "_" + suffix + old_ext
                new_ejson = new_path.replace(new_scan_end, "_events.json")
                self.new_filenames.append(new_ejson)

        old_physio = filepath.replace(scan_end, "_physio.tsv.gz")
        if Path(old_physio).exists():
            self.old_filenames.append(old_physio)
            new_scan_end = "_" + suffix + old_ext
            new_physio = new_path.replace(new_scan_end, "_physio.tsv.gz")
            self.new_filenames.append(new_physio)

        # Update ASL-specific files only when ASL timeseries is being renamed
        if "/perf/" in filepath and old_suffix == "asl":
            old_context = filepath.replace(scan_end, "_aslcontext.tsv")
            if Path(old_context).exists():
                self.old_filenames.append(old_context)
                new_scan_end = "_" + suffix + old_ext
                new_context = new_path.replace(new_scan_end, "_aslcontext.tsv")
                self.new_filenames.append(new_context)

            # Do NOT rename M0 scans or their JSON sidecars. M0 files should
            # retain their original filenames to preserve independent variability.
            # The IntendedFor field in M0 JSONs will be updated below to point
            # to the newly renamed ASL files.

            old_labeling = filepath.replace(scan_end, "_asllabeling.jpg")
            if Path(old_labeling).exists():
                self.old_filenames.append(old_labeling)
                new_scan_end = "_" + suffix + old_ext
                new_labeling = new_path.replace(new_scan_end, "_asllabeling.jpg")
                self.new_filenames.append(new_labeling)

        # RENAME INTENDED FORS!
        if self.is_longitudinal:
            ses_path = self.path + "/" + sub + "/" + ses
        elif not self.is_longitudinal:
            ses_path = self.path + "/" + sub
        files_with_if = []
        files_with_if += Path(ses_path).rglob("fmap/*.json")
        files_with_if += Path(ses_path).rglob("perf/*_m0scan.json")
        for path_with_if in files_with_if:
            filename_with_if = str(path_with_if)
            self.IF_rename_paths.append(filename_with_if)
            # json_file = self.layout.get_file(filename_with_if)
            # data = json_file.get_dict()
            data = utils.get_sidecar_metadata(filename_with_if)
            if data == "Erroneous sidecar":
                print("Error parsing sidecar: ", filename_with_if)
                continue

            if "IntendedFor" in data.keys():
                # Coerce IntendedFor to a list.
                data["IntendedFor"] = listify(data["IntendedFor"])
                for item in data["IntendedFor"]:
                    if item == utils._get_participant_relative_path(filepath):
                        # remove old filename
                        data["IntendedFor"].remove(item)
                        # add new filename
                        data["IntendedFor"].append(utils._get_participant_relative_path(new_path))

                    if item == utils._get_bidsuri(filepath, self.path):
                        # remove old filename
                        data["IntendedFor"].remove(item)
                        # add new filename
                        data["IntendedFor"].append(utils._get_bidsuri(new_path, self.path))

                # update the json with the new data dictionary
                utils._update_json(filename_with_if, data)

        # save IntendedFor purges so that you can datalad run the
        # remove association file commands on a clean dataset
        # if self.use_datalad:
        #     if not self.is_datalad_clean():
        #         self.datalad_save(message="Renamed IntendedFors")
        #         self.reset_bids_layout()
        # else:
        #     print("No IntendedFor References to Rename")

    def copy_exemplars(self, exemplars_dir, exemplars_tsv, min_group_size):
        """Copy one subject from each Acquisition Group into a new directory for testing preps.

        Raises an error if the subjects are not unlocked,
        unlocks each subject before copying if --force_unlock is set.

        Parameters
        ----------
        exemplars_dir : :obj:`str`
            path to the directory that will contain one subject
            from each Acqusition Group (*_AcqGrouping.tsv)
            example path: /Users/Covitz/tsvs/CCNP_Acq_Groups/
        exemplars_tsv : :obj:`str`
            path to the .tsv file that lists one subject
            from each Acqusition Group (*_AcqGrouping.tsv
            from the `cubids group` output)
            example path: /Users/Covitz/tsvs/CCNP_Acq_Grouping.tsv
        min_group_size : :obj:`int`
            Minimum number of subjects in an acq group for it to be included
            in the exemplar dataset.
        """
        # create the exemplar ds
        if self.use_datalad:
            subprocess.run(
                [
                    "datalad",
                    "--log-level",
                    "error",
                    "create",
                    "-c",
                    "text2git",
                    exemplars_dir,
                ]
            )
        if os.sep not in str(exemplars_tsv):
            if not self.cubids_code_dir:
                self.create_cubids_code_dir()
            exemplars_tsv = self.path + "/code/CuBIDS/" + exemplars_tsv

        # load the exemplars tsv
        subs = pd.read_table(exemplars_tsv)

        # if min group size flag set, drop acq groups with less than min
        if min_group_size > 1:
            for row in range(len(subs)):
                acq_group = subs.loc[row, "AcqGroup"]
                size = int(subs["AcqGroup"].value_counts()[acq_group])
                if size < min_group_size:
                    subs = subs.drop([row])

        # get one sub from each acq group
        unique = subs.drop_duplicates(subset=["AcqGroup"])

        # cast list to a set to drop duplicates, then convert back to list
        unique_subs = list(set(unique["subject"].tolist()))
        for subid in unique_subs:
            source = str(self.path) + "/" + subid
            dest = exemplars_dir + "/" + subid
            # Copy the content of source to destination
            copytree(source, dest)

        # Copy the dataset_description.json
        copyfile(
            str(self.path) + "/" + "dataset_description.json",
            exemplars_dir + "/" + "dataset_description.json",
        )

        s1 = "Copied one subject from each Acquisition Group "
        s2 = "into the Exemplar Dataset"
        msg = s1 + s2
        if self.use_datalad:
            subprocess.run(["datalad", "save", "-d", exemplars_dir, "-m", msg])

    def purge(self, scans_txt):
        """Purge all associations of desired scans from a bids dataset.

        Parameters
        ----------
        scans_txt : str
            path to the .txt file that lists the scans
            you want to be deleted from the dataset, along
            with their associations.
            example path: /Users/Covitz/CCNP/scans_to_delete.txt
        """
        self.scans_txt = scans_txt

        scans = []
        with open(scans_txt, "r") as fd:
            reader = csv.reader(fd)
            for row in reader:
                scans.append(self.path + "/" + str(row[0]))

        # check to ensure scans are all real files in the ds!

        self._purge_associations(scans)

    def _purge_associations(self, scans):
        """Purge field map JSONs' IntendedFor references.

        Parameters
        ----------
        scans : :obj:`list` of :obj:`str`
            List of file paths to remove from field map JSONs.
        """
        # truncate all paths to intendedfor reference format
        # sub, ses, modality only (no self.path)
        if_scans = []
        for scan in scans:
            if_scans.append(utils._get_participant_relative_path(self.path + scan))

        for path in Path(self.path).rglob("sub-*/*/fmap/*.json"):
            # json_file = self.layout.get_file(str(path))
            # data = json_file.get_dict()
            data = utils.get_sidecar_metadata(str(path))
            if data == "Erroneous sidecar":
                print("Error parsing sidecar: ", str(path))
                continue

            # remove scan references in the IntendedFor
            if "IntendedFor" in data.keys():
                data["IntendedFor"] = listify(data["IntendedFor"])

                for item in data["IntendedFor"]:
                    if item in if_scans:
                        data["IntendedFor"].remove(item)

                # update the json with the new data dictionary
                utils._update_json(str(path), data)

        # save IntendedFor purges so that you can datalad run the
        # remove association file commands on a clean dataset
        if self.use_datalad:
            if not self.is_datalad_clean():
                s1 = "Purged IntendedFor references to files "
                s2 = "requested for removal"
                message = s1 + s2
                self.datalad_save(message=message)
                self.reset_bids_layout()

        # NOW WE WANT TO PURGE ALL ASSOCIATIONS

        to_remove = []

        for path in Path(self.path).rglob("sub-*/**/*.nii.gz"):
            if str(path) in scans:
                # bids_file = self.layout.get_file(str(path))
                # associations = bids_file.get_associations()
                associations = self.get_nifti_associations(str(path))
                for assoc in associations:
                    to_remove.append(assoc)
                    # filepath = assoc.path

            # ensure association is not an IntendedFor reference!
            if ".nii" not in str(path):
                if "/dwi/" in str(path):
                    # add the bval and bvec if there
                    if Path(utils.img_to_new_ext(str(path), ".bval")).exists():
                        to_remove.append(utils.img_to_new_ext(str(path), ".bval"))
                    if Path(utils.img_to_new_ext(str(path), ".bvec")).exists():
                        to_remove.append(utils.img_to_new_ext(str(path), ".bvec"))

                if "/func/" in str(path):
                    # add tsvs
                    tsv = utils.img_to_new_ext(str(path), ".tsv").replace("_bold", "_events")
                    if Path(tsv).exists():
                        to_remove.append(tsv)
                    # add tsv json (if exists)
                    if Path(tsv.replace(".tsv", ".json")).exists():
                        to_remove.append(tsv.replace(".tsv", ".json"))

        to_remove += scans

        # create rm commands for all files that need to be purged
        purge_commands = []
        for rm_me in to_remove:
            if Path(rm_me).exists():
                purge_commands.append("rm " + rm_me)

        # datalad run the file deletions (purges)
        full_cmd = "\n".join(purge_commands)
        if full_cmd:
            # write full_cmd to a .sh file
            # Open file for writing

            path_prefix = str(Path(self.path).parent)

            with open(path_prefix + "/" + "_full_cmd.sh", "w") as fo:
                fo.write("#!/bin/bash\n")
                fo.write(full_cmd)

            if self.scans_txt:
                cmt = f"Purged scans listed in {self.scans_txt} from dataset"
            else:
                cmt = "Purged Parameter Groups marked for removal"

            purge_file = path_prefix + "/" + "_full_cmd.sh"
            if self.use_datalad:
                self.datalad_handle.run(cmd=["bash", purge_file], message=cmt)
            else:
                subprocess.run(
                    ["bash", path_prefix + "/" + "_full_cmd.sh"],
                    stdout=subprocess.PIPE,
                    cwd=path_prefix,
                )

            self.reset_bids_layout()

        else:
            print("Not running any association removals")

    def get_nifti_associations(self, nifti):
        """Get nifti associations.

        Parameters
        ----------
        nifti : str or Path
            The path to the NIfTI file for which to find associated files.

        Returns
        -------
        associations : list of str
            A list of paths to files associated with the given NIfTI file, excluding
            the NIfTI file itself.
        """
        # get all assocation files of a nifti image
        no_ext_file = str(nifti).split("/")[-1].split(".")[0]
        associations = []
        for path in Path(self.path).rglob(f"sub-*/**/{no_ext_file}.*"):
            if ".nii.gz" not in str(path):
                associations.append(str(path))

        return associations

    def _cache_fieldmaps(self):
        """Search all fieldmaps and create a lookup for each file.

        This method scans for fieldmap files with specific suffixes and extensions,
        retrieves their metadata, and creates a lookup dictionary that maps each
        file to its corresponding fieldmap(s). If a fieldmap file does not have an
        "IntendedFor" field in its metadata, it is added to a list of misfits.

        Returns
        -------
        misfits : list
            A list of fieldmap files that do not have an "IntendedFor" field in their metadata.
        """
        suffix = "(phase1|phasediff|epi|fieldmap)"
        fmap_files = self.layout.get(
            suffix=suffix, regex_search=True, extension=[".nii.gz", ".nii"]
        )

        misfits = []
        files_to_fmaps = defaultdict(list)
        for fmap_file in tqdm(fmap_files):
            # intentions = listify(fmap_file.get_metadata().get("IntendedFor"))
            fmap_json = utils.img_to_new_ext(fmap_file.path, ".json")
            metadata = utils.get_sidecar_metadata(fmap_json)
            if metadata == "Erroneous sidecar":
                print("Error parsing sidecar: ", str(fmap_json))
                continue
            if_list = metadata.get("IntendedFor")
            intentions = listify(if_list)
            subject_prefix = f"sub-{fmap_file.entities['subject']}"

            if intentions is not None:
                for intended_for in intentions:
                    full_path = Path(self.path) / subject_prefix / intended_for
                    files_to_fmaps[str(full_path)].append(fmap_file)

            # fmap file detected, no intended for found
            else:
                misfits.append(fmap_file)

        self.fieldmap_lookup = files_to_fmaps
        self.fieldmaps_cached = True

        # return a list of all filenames where fmap file detected,
        # no intended for found
        return misfits

    def get_param_groups_from_entity_set(self, entity_set):
        """Split entity sets into param groups based on json metadata.

        Parameters
        ----------
        entity_set : str
            Entity set name.

        Returns
        -------
        ret : tuple of two DataFrames
            1. A data frame with one row per file where the ParamGroup
            column indicates the group to which each scan belongs.
            2. A data frame with param group summaries
        """
        if not self.fieldmaps_cached:
            raise Exception("Fieldmaps must be cached to find parameter groups.")
        key_entities = utils._entity_set_to_entities(entity_set)
        key_entities["extension"] = ".nii[.gz]*"

        matching_files = self.layout.get(
            return_type="file", scope="self", regex_search=True, **key_entities
        )

        # ensure files who's entities contain key_entities but include other
        # entities do not also get added to matching_files
        to_include = []
        for filepath in matching_files:
            f_entity_set = utils._file_to_entity_set(filepath)

            if f_entity_set == entity_set:
                to_include.append(filepath)

        # get the modality associated with the entity set
        modalities = ["/dwi/", "/anat/", "/func/", "/perf/", "/fmap/"]
        modality = ""
        for mod in modalities:
            if mod in filepath:
                modality = mod.replace("/", "").replace("/", "")

        if modality == "":
            print(f"Unusual Modality Detected: {filepath}")
            modality = "other"

        ret = utils._get_param_groups(
            to_include,
            self.fieldmap_lookup,
            entity_set,
            self.grouping_config,
            modality,
            self.keys_files,
        )

        if ret == "erroneous sidecar found":
            return "erroneous sidecar found"

        # add modality to the return tuple
        l_ret = list(ret)
        l_ret.append(modality)
        tup_ret = tuple(l_ret)
        return tup_ret

    def create_data_dictionary(self):
        """Create a data dictionary for scanning parameters and other metadata.

        This method populates the `data_dict` attribute with descriptions for various
        scanning parameters, relational parameters, and derived parameters based on
        the `grouping_config` attribute. Additionally, it manually adds descriptions
        for non-sidecar columns.

        Attributes
        ----------
        grouping_config : dict
            Configuration dictionary containing `sidecar_params`, `relational_params`,
            and `derived_params` which are used to populate the `data_dict`.

        data_dict : dict
            Dictionary to be populated with parameter descriptions.

        Sidecar Parameters
        ------------------
        - Scanning Parameter: Parameters extracted from sidecar files.
        - NIfTI Header Parameter: Parameters derived from NIfTI headers.

        Manually Added Columns
        ----------------------
        - ManualCheck: Column where users mark groups to manually check.
        - Notes: Column to mark notes about the parameter group.
        - RenameEntitySet: Auto-generated suggested rename of Non-Dominant Groups
            based on variant scanning parameters.
        - Counts: Number of files in the parameter group.
        - Modality: MRI image type.
        - MergeInto: Column to mark groups to remove with a '0'.
        - FilePath: Location of file.
        - EntitySetCount: Number of participants in an Entity Set.
        - EntitySet: A set of scans whose filenames share all BIDS filename key-value
            pairs, excluding subject and session.
        - ParamGroup: The set of scans with identical metadata parameters in their
            sidecars (defined within an Entity Set and denoted numerically).
        - KeyParamGroup: Entity Set name and Param Group number separated by a double
            underscore.
        """
        sidecar_params = self.grouping_config.get("sidecar_params")
        for mod in sidecar_params.keys():
            mod_dict = sidecar_params[mod]
            for s_param in mod_dict.keys():
                if s_param not in self.data_dict.keys():
                    self.data_dict[s_param] = {"Description": "Scanning Parameter"}

        relational_params = self.grouping_config.get("relational_params")
        for r_param in relational_params.keys():
            if r_param not in self.data_dict.keys():
                self.data_dict[r_param] = {"Description": "Scanning Parameter"}

        derived_params = self.grouping_config.get("derived_params")
        for mod in derived_params.keys():
            mod_dict = derived_params[mod]
            for d_param in mod_dict.keys():
                if d_param not in self.data_dict.keys():
                    self.data_dict[d_param] = {"Description": "NIfTI Header Parameter"}

        # Manually add non-sidecar columns/descriptions to data_dict
        desc1 = "Column where users mark groups to manually check"
        self.data_dict["ManualCheck"] = {}
        self.data_dict["ManualCheck"]["Description"] = desc1
        desc2 = "Column to mark notes about the param group"
        self.data_dict["Notes"] = {}
        self.data_dict["Notes"]["Description"] = desc2
        desc31 = "Auto-generated suggested rename of Non-Domiannt Groups"
        desc32 = " based on variant scanning parameters"
        self.data_dict["RenameEntitySet"] = {}
        self.data_dict["RenameEntitySet"]["Description"] = desc31 + desc32
        desc4 = "Number of Files in the Parameter Group"
        self.data_dict["Counts"] = {}
        self.data_dict["Counts"]["Description"] = desc4
        self.data_dict["Modality"] = {}
        self.data_dict["Modality"]["Description"] = "MRI image type"
        desc5 = "Column to mark groups to remove with a '0'"
        self.data_dict["MergeInto"] = {}
        self.data_dict["MergeInto"]["Description"] = desc5
        self.data_dict["FilePath"] = {}
        self.data_dict["FilePath"]["Description"] = "Location of file"
        desc6 = "Number of participants in a Entity Set"
        self.data_dict["EntitySetCount"] = {}
        self.data_dict["EntitySetCount"]["Description"] = desc6
        desc71 = "A set of scans whose filenames share all BIDS filename"
        desc72 = " key-value pairs, excluding subject and session"
        self.data_dict["EntitySet"] = {}
        self.data_dict["EntitySet"]["Description"] = desc71 + desc72
        desc81 = "The set of scans with identical metadata parameters in their"
        desc82 = " sidecars (defined within a Entity Set and denoted"
        desc83 = " numerically)"
        self.data_dict["ParamGroup"] = {}
        self.data_dict["ParamGroup"]["Description"] = desc81 + desc82 + desc83
        desc91 = "Entity Set name and Param Group number separated by a double"
        desc92 = " underscore"
        self.data_dict["KeyParamGroup"] = {}
        self.data_dict["KeyParamGroup"]["Description"] = desc91 + desc92

    def get_data_dictionary(self, df):
        """Create a BIDS data dictionary from dataframe columns.

        Parameters
        ----------
        df : Pandas DataFrame
            Pre export TSV that will be converted to a json dictionary

        Returns
        -------
        data_dict : dictionary
            Python dictionary in BIDS data dictionary format
        """
        json_dict = {}

        # Build column dictionary
        col_list = df.columns.values.tolist()

        data_dict_keys = self.data_dict.keys()

        for col in data_dict_keys:
            if col in col_list:
                json_dict[col] = self.data_dict[col]

        # for col in range(len(col_list)):
        #     col_dict[col + 1] = col_list[col]

        # header_dict = {}
        # # build header dictionary
        # header_dict['Long Description'] = name
        # description = 'https://cubids.readthedocs.io/en/latest/usage.html'
        # header_dict['Description'] = description
        # header_dict['Version'] = 'CuBIDS v1.0.5'
        # header_dict['Levels'] = col_dict

        # # Build top level dictionary
        # data_dict = {}
        # data_dict[name] = header_dict

        return json_dict

    def get_param_groups_dataframes(self):
        """Create DataFrames of files x param groups and a summary.

        This method processes entity sets to generate two DataFrames:
        one containing labeled file parameters and another summarizing
        parameter groups. It also suggests renaming based on variant parameters.

        Returns
        -------
        big_df : pandas.DataFrame
            DataFrame with labeled file parameters.
        summary : pandas.DataFrame
            DataFrame summarizing parameter groups with suggested renaming.
        """
        entity_sets = self.get_entity_sets()
        labeled_files = []
        param_group_summaries = []
        for entity_set in entity_sets:
            try:
                (
                    labeled_file_params,
                    param_summary,
                    modality,
                ) = self.get_param_groups_from_entity_set(entity_set)
            except Exception:
                continue
            if labeled_file_params is None:
                continue
            param_group_summaries.append(param_summary)
            labeled_files.append(labeled_file_params)

        big_df = utils._order_columns(pd.concat(labeled_files, ignore_index=True))

        # make Filepaths relative to bids dir
        for row in range(len(big_df)):
            long_name = big_df.loc[row, "FilePath"]
            big_df.loc[row, "FilePath"] = long_name.replace(self.path, "")

        summary = utils._order_columns(pd.concat(param_group_summaries, ignore_index=True))

        # create new col that strings key and param group together
        summary["KeyParamGroup"] = summary["EntitySet"] + "__" + summary["ParamGroup"].map(str)

        # move this column to the front of the dataframe
        key_param_col = summary.pop("KeyParamGroup")
        summary.insert(0, "KeyParamGroup", key_param_col)

        # do the same for the files df
        big_df["KeyParamGroup"] = big_df["EntitySet"] + "__" + big_df["ParamGroup"].map(str)

        # move this column to the front of the dataframe
        key_param_col = big_df.pop("KeyParamGroup")
        big_df.insert(0, "KeyParamGroup", key_param_col)

        summary.insert(0, "RenameEntitySet", np.nan)
        summary.insert(0, "MergeInto", np.nan)
        summary.insert(0, "ManualCheck", np.nan)
        summary.insert(0, "Notes", np.nan)

        # Now automate suggested rename based on variant params
        # loop though imaging and derived param keys

        sidecar = self.grouping_config.get("sidecar_params")
        sidecar = sidecar[modality]

        relational = self.grouping_config.get("relational_params")

        # list of columns names that we account for in suggested renaming
        summary["RenameEntitySet"] = summary["RenameEntitySet"].apply(str)

        rename_cols = []
        tolerance_cols = []
        for col in sidecar.keys():
            if "suggest_variant_rename" in sidecar[col].keys():
                if sidecar[col]["suggest_variant_rename"] and col in summary.columns:
                    rename_cols.append(col)
                    if "tolerance" in sidecar[col].keys():
                        tolerance_cols.append(col)

        # deal with Fmap!
        if "FieldmapKey" in relational:
            if "suggest_variant_rename" in relational["FieldmapKey"].keys():
                if relational["FieldmapKey"]["suggest_variant_rename"]:
                    # check if 'bool' or 'columns'
                    if relational["FieldmapKey"]["display_mode"] == "bool":
                        rename_cols.append("HasFieldmap")

        # deal with IntendedFor Key!
        if "IntendedForKey" in relational:
            if "suggest_variant_rename" in relational["IntendedForKey"].keys():
                if relational["FieldmapKey"]["suggest_variant_rename"]:
                    # check if 'bool' or 'columns'
                    if relational["IntendedForKey"]["display_mode"] == "bool":
                        rename_cols.append("UsedAsFieldmap")

        summary = utils.assign_variants(summary, rename_cols)

        return big_df, summary

    def get_tsvs(self, path_prefix):
        """Create the _summary and _files tsvs for the bids dataset.

        Parameters
        ----------
        path_prefix : str
            prefix of the path to the directory where you want
            to save your tsvs
            example path: /Users/Covitz/PennLINC/RBC/CCNP/
        """
        self._cache_fieldmaps()

        # check if path_prefix is absolute or relative
        # if relative, put output in BIDS_ROOT/code/CuBIDS/ dir
        if "/" not in path_prefix:
            # path is relative
            # first check if code/CuBIDS dir exits
            # if not, create it
            self.create_cubids_code_dir()
            # send outputs to code/CuBIDS in BIDS tree
            path_prefix = self.path + "/code/CuBIDS/" + path_prefix

        big_df, summary = self.get_param_groups_dataframes()

        summary = summary.sort_values(by=["Modality", "EntitySetCount"], ascending=[True, False])
        big_df = big_df.sort_values(by=["Modality", "EntitySetCount"], ascending=[True, False])

        # Create json dictionaries for summary and files tsvs
        self.create_data_dictionary()
        files_dict = self.get_data_dictionary(big_df)
        summary_dict = self.get_data_dictionary(summary)

        # Save data dictionaires as JSONs
        files_tsv = f"{path_prefix}_files.tsv"
        files_json = f"{path_prefix}_files.json"
        summary_tsv = f"{path_prefix}_summary.tsv"
        summary_json = f"{path_prefix}_summary.json"

        with open(files_json, "w") as outfile:
            json.dump(files_dict, outfile, indent=4)

        with open(summary_json, "w") as outfile:
            json.dump(summary_dict, outfile, indent=4)

        big_df.to_csv(files_tsv, sep="\t", index=False)

        summary.to_csv(summary_tsv, sep="\t", index=False)

        # Calculate the acq groups
        group_by_acquisition_sets(files_tsv, path_prefix, self.acq_group_level)

        print(f"CuBIDS detected {len(summary)} Parameter Groups.")
        print(
            f"""Groupings info is available in

  * {files_tsv}
  * {files_json}
  * {summary_tsv}
  * {summary_json}

"""
        )

    def get_entity_sets(self):
        """Identify the entity sets for the BIDS dataset.

        This method scans the dataset directory for files matching the BIDS
        specification and identifies unique entity sets based on the filenames.
        It also populates a dictionary mapping each entity set to a list of
        corresponding file paths.

        Returns
        -------
        list of str
            A sorted list of unique entity sets found in the dataset.
        """
        # reset self.keys_files
        self.keys_files = {}

        entity_sets = set()

        for path in Path(self.path).rglob("sub-*/**/*.*"):
            # ignore all dot directories
            if "/." in str(path):
                continue

            if str(path).endswith(".nii") or str(path).endswith(".nii.gz"):
                entity_sets.update((utils._file_to_entity_set(path),))

                # Fill the dictionary of entity set, list of filenames pairrs
                ret = utils._file_to_entity_set(path)

                if ret not in self.keys_files.keys():
                    self.keys_files[ret] = []

                self.keys_files[ret].append(path)

        return sorted(entity_sets)

    def change_metadata(self, filters, metadata):
        """Change metadata of BIDS files based on provided filters.

        This method updates the metadata of BIDS files that match the given filters.
        It retrieves the associated JSON sidecar files, updates them with the provided
        metadata, and writes the changes back to the JSON files.

        Parameters
        ----------
        filters : dict
            A dictionary of filters to apply when searching for BIDS files.
            The keys should correspond to BIDS entity names (e.g., 'subject', 'session').
        metadata : dict
            A dictionary containing the metadata to update in the JSON sidecar files.
            The keys should correspond to the metadata fields to be updated.

        Raises
        ------
        FileNotFoundError
            If no JSON sidecar files are found for the BIDS files.
        ValueError
            If irregular associations are found (i.e., more than one JSON file is
            associated with a BIDS file).

        Notes
        -----
        This method appears to be unused in the current codebase.
        """
        files_to_change = self.layout.get(return_type="object", **filters)

        for bidsfile in files_to_change:
            # get the sidecar file
            # bidsjson_file = bidsfile.get_associations()
            bidsjson_file = utils.img_to_new_ext(str(bidsfile), ".json")
            if not bidsjson_file:
                print("NO JSON FILES FOUND IN ASSOCIATIONS")
                continue

            json_file = [x for x in bidsjson_file if "json" in x.filename]
            if not len(json_file) == 1:
                print("FOUND IRREGULAR ASSOCIATIONS")

            else:
                # get the data from it
                json_file = json_file[0]

                sidecar = json_file.get_dict()
                sidecar.update(metadata)

                # write out
                utils._update_json(json_file.path, sidecar)

    def get_all_metadata_fields(self):
        """Return unique metadata fields grouped by root JSON files and modalities.

        This method collects metadata fields from root JSON files and groups nested
        JSON files by modality (func, anat, dwi, fmap, etc.). For root JSON files like
        dataset_description.json and participants.json, all fields are listed. For
        modalities, all unique fields across all subjects/sessions are listed (avoiding
        duplication within each modality). It skips files within any ".git" directory 
        and handles empty files and JSON decoding errors gracefully.

        Returns
        -------
        dict
            A dictionary where keys are root JSON filenames or modality names (str) and
            values are sorted lists of metadata fields (list of str) for that category.

        Raises
        ------
        UserWarning
            If there is an error decoding a JSON file or any unexpected error occurs
            while processing a file.
        """
        import re
        from collections import defaultdict
        bids_path = Path(self.path)
        
        # Collect root JSON files
        root_fields = {}
        for json_file in bids_path.glob("*.json"):
            if ".git" not in str(json_file) and not json_file.name.startswith('.'):
                try:
                    with open(json_file, "r", encoding="utf-8") as jsonr:
                        content = jsonr.read().strip()
                        if not content:
                            continue
                        metadata = json.loads(content)
                    root_fields[json_file.name] = set(metadata.keys())
                except json.JSONDecodeError as e:
                    warnings.warn(f"Error decoding JSON in {json_file}: {e}")
                except Exception as e:
                    warnings.warn(f"Unexpected error with file {json_file}: {e}")
        
        # Collect fields by modality
        modalities = defaultdict(set)
        for sub_dir in bids_path.glob("sub-*/"):
            ses_dirs = list(sub_dir.glob("ses-*/"))
            if ses_dirs:
                # Longitudinal dataset: modalities under ses-*/
                for ses_dir in ses_dirs:
                    for mod_dir in ses_dir.glob("*/"):
                        mod = mod_dir.name
                        for json_file in mod_dir.glob("*.json"):
                            if ".git" not in str(json_file):
                                try:
                                    with open(json_file, "r", encoding="utf-8") as jsonr:
                                        content = jsonr.read().strip()
                                        if not content:
                                            continue
                                        metadata = json.loads(content)
                                    modalities[mod].update(metadata.keys())
                                except json.JSONDecodeError as e:
                                    warnings.warn(f"Error decoding JSON in {json_file}: {e}")
                                except Exception as e:
                                    warnings.warn(f"Unexpected error with file {json_file}: {e}")
            else:
                # Cross-sectional dataset: modalities directly under sub-*/
                for mod_dir in sub_dir.glob("*/"):
                    mod = mod_dir.name
                    for json_file in mod_dir.glob("*.json"):
                        if ".git" not in str(json_file):
                            try:
                                with open(json_file, "r", encoding="utf-8") as jsonr:
                                    content = jsonr.read().strip()
                                    if not content:
                                        continue
                                    metadata = json.loads(content)
                                modalities[mod].update(metadata.keys())
                            except json.JSONDecodeError as e:
                                warnings.warn(f"Error decoding JSON in {json_file}: {e}")
                            except Exception as e:
                                warnings.warn(f"Unexpected error with file {json_file}: {e}")
        
        # Group task events into 'events' modality
        events_fields = set()
        root_to_remove = []
        for cat in root_fields:
            if '_events.json' in cat:
                events_fields.update(root_fields[cat])
                root_to_remove.append(cat)
        for cat in root_to_remove:
            del root_fields[cat]
        if events_fields:
            modalities['events'] = events_fields
        
        # Prepare output dictionary with all fields
        result = {}
        
        # For root files, list all fields
        for cat, fields in root_fields.items():
            result[cat] = sorted(fields)
        
        # For modalities, list all fields (already unique within each modality)
        for mod, fields in modalities.items():
            result[mod] = sorted(fields)
        
        return result

    def remove_metadata_fields(self, fields_to_remove):
        """Remove specific fields from all metadata files in the directory.

        This method iterates through all JSON files in the specified directory
        and removes the specified fields from each file's metadata.

        Parameters
        ----------
        fields_to_remove : list of str
            A list of field names to be removed from the metadata files.

        Returns
        -------
        None
        """
        remove_fields = set(fields_to_remove)
        if not remove_fields:
            return

        for json_file in tqdm(Path(self.path).rglob("*.json")):
            # Check for offending keys in the json file
            if ".git" not in str(json_file):
                with open(json_file, "r") as jsonr:
                    metadata = json.load(jsonr)

                offending_keys = remove_fields.intersection(metadata.keys())
                # Quit if there are none in there
                if not offending_keys:
                    continue

                # Remove the offending keys
                for key in offending_keys:
                    del metadata[key]
                # Write the cleaned output
                with open(json_file, "w") as jsonr:
                    json.dump(metadata, jsonr, indent=4)

    # # # # FOR TESTING # # # #
    def get_filenames(self):
        """Get filenames."""
        return self.keys_files

    def get_fieldmap_lookup(self):
        """Get fieldmap lookup."""
        return self.fieldmap_lookup

    def get_layout(self):
        """Get layout."""
        return self.layout
