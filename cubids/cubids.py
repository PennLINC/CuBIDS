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
from sklearn.cluster import AgglomerativeClustering
from tqdm import tqdm

from cubids.config import load_config, load_schema
from cubids.constants import ID_VARS, NON_KEY_ENTITIES
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
                sidecar = img_to_new_ext(str(path), ".json")
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
                        joined = "".join(orient) + "+"
                        data["ImageOrientation"] = joined

                    with open(sidecar, "w") as file:
                        json.dump(data, file, indent=4)

        if self.use_datalad:
            self.datalad_save(message="Added nifti info to sidecars")

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
            source_json = img_to_new_ext(img_full_path, ".json")
            for dest_nii in dest_files.FilePath:
                dest_json = img_to_new_ext(self.path + dest_nii, ".json")
                if Path(dest_json).exists() and Path(source_json).exists():
                    merge_commands.append(f"bids-sidecar-merge {source_json} {dest_json}")

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

                        new_entities = _entity_set_to_entities(new_key)

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
        new_path = build_path(
            filepath=filepath,
            out_entities=entities,
            out_dir=str(self.path),
            schema=self.schema,
            is_longitudinal=self.is_longitudinal,
        )

        exts = Path(filepath).suffixes
        old_ext = "".join(exts)

        suffix = entities["suffix"]

        sub = get_entity_value(filepath, "sub")
        if self.is_longitudinal:
            ses = get_entity_value(filepath, "ses")

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
                    new_ext_path = img_to_new_ext(new_path, "".join(Path(assoc_path).suffixes))
                    self.new_filenames.append(new_ext_path)

        # MAKE SURE THESE AREN'T COVERED BY get_associations!!!
        # Update DWI-specific files
        if "/dwi/" in filepath:
            # add the bval and bvec if there
            bval_old = img_to_new_ext(filepath, ".bval")
            bval_new = img_to_new_ext(new_path, ".bval")
            if Path(bval_old).exists() and bval_old not in self.old_filenames:
                self.old_filenames.append(bval_old)
                self.new_filenames.append(bval_new)

            bvec_old = img_to_new_ext(filepath, ".bvec")
            bvec_new = img_to_new_ext(new_path, ".bvec")
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

        # Update ASL-specific files
        if "/perf/" in filepath:
            old_context = filepath.replace(scan_end, "_aslcontext.tsv")
            if Path(old_context).exists():
                self.old_filenames.append(old_context)
                new_scan_end = "_" + suffix + old_ext
                new_context = new_path.replace(new_scan_end, "_aslcontext.tsv")
                self.new_filenames.append(new_context)

            old_m0scan = filepath.replace(scan_end, "_m0scan.nii.gz")
            if Path(old_m0scan).exists():
                self.old_filenames.append(old_m0scan)
                new_scan_end = "_" + suffix + old_ext
                new_m0scan = new_path.replace(new_scan_end, "_m0scan.nii.gz")
                self.new_filenames.append(new_m0scan)

            old_mjson = filepath.replace(scan_end, "_m0scan.json")
            if Path(old_mjson).exists():
                self.old_filenames.append(old_mjson)
                new_scan_end = "_" + suffix + old_ext
                new_mjson = new_path.replace(new_scan_end, "_m0scan.json")
                self.new_filenames.append(new_mjson)

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
            data = get_sidecar_metadata(filename_with_if)
            if data == "Erroneous sidecar":
                print("Error parsing sidecar: ", filename_with_if)
                continue

            if "IntendedFor" in data.keys():
                # Coerce IntendedFor to a list.
                data["IntendedFor"] = listify(data["IntendedFor"])
                for item in data["IntendedFor"]:
                    if item == _get_participant_relative_path(filepath):
                        # remove old filename
                        data["IntendedFor"].remove(item)
                        # add new filename
                        data["IntendedFor"].append(_get_participant_relative_path(new_path))

                    if item == _get_bidsuri(filepath, self.path):
                        # remove old filename
                        data["IntendedFor"].remove(item)
                        # add new filename
                        data["IntendedFor"].append(_get_bidsuri(new_path, self.path))

                # update the json with the new data dictionary
                _update_json(filename_with_if, data)

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
            from the cubids-group output)
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
            if_scans.append(_get_participant_relative_path(self.path + scan))

        for path in Path(self.path).rglob("sub-*/*/fmap/*.json"):
            # json_file = self.layout.get_file(str(path))
            # data = json_file.get_dict()
            data = get_sidecar_metadata(str(path))
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
                _update_json(str(path), data)

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
                    if Path(img_to_new_ext(str(path), ".bval")).exists():
                        to_remove.append(img_to_new_ext(str(path), ".bval"))
                    if Path(img_to_new_ext(str(path), ".bvec")).exists():
                        to_remove.append(img_to_new_ext(str(path), ".bvec"))

                if "/func/" in str(path):
                    # add tsvs
                    tsv = img_to_new_ext(str(path), ".tsv").replace("_bold", "_events")
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
            fmap_json = img_to_new_ext(fmap_file.path, ".json")
            metadata = get_sidecar_metadata(fmap_json)
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
        key_entities = _entity_set_to_entities(entity_set)
        key_entities["extension"] = ".nii[.gz]*"

        matching_files = self.layout.get(
            return_type="file", scope="self", regex_search=True, **key_entities
        )

        # ensure files who's entities contain key_entities but include other
        # entities do not also get added to matching_files
        to_include = []
        for filepath in matching_files:
            f_entity_set = _file_to_entity_set(filepath)

            if f_entity_set == entity_set:
                to_include.append(filepath)

        # get the modality associated with the entity set
        modalities = ["/dwi/", "/anat/", "/func/", "/perf/", "/fmap/"]
        modality = ""
        for mod in modalities:
            if mod in filepath:
                modality = mod.replace("/", "").replace("/", "")

        if modality == "":
            print("Unusual Modality Detected")
            modality = "other"

        ret = _get_param_groups(
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
        tuple of pandas.DataFrame
            A tuple containing two DataFrames:
            - big_df: DataFrame with labeled file parameters.
            - summary: DataFrame summarizing parameter groups with suggested renaming.
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

        big_df = _order_columns(pd.concat(labeled_files, ignore_index=True))

        # make Filepaths relative to bids dir
        for row in range(len(big_df)):
            long_name = big_df.loc[row, "FilePath"]
            big_df.loc[row, "FilePath"] = long_name.replace(self.path, "")

        summary = _order_columns(pd.concat(param_group_summaries, ignore_index=True))

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

        dom_dict = {}
        # loop through summary tsv and create dom_dict
        for row in range(len(summary)):
            # if 'NumVolumes' in summary.columns \
            #         and str(summary.loc[row, "NumVolumes"]) == 'nan':
            #     summary.at[row, "NumVolumes"] = 1.0

            # if dominant group identified
            if str(summary.loc[row, "ParamGroup"]) == "1":
                val = {}
                # grab col, all vals send to dict
                key = summary.loc[row, "EntitySet"]
                for col in rename_cols:
                    summary[col] = summary[col].apply(str)
                    val[col] = summary.loc[row, col]
                dom_dict[key] = val

        # now loop through again and ID variance
        for row in range(len(summary)):
            # check to see if renaming has already happened
            renamed = False
            entities = _entity_set_to_entities(summary.loc[row, "EntitySet"])
            if "VARIANT" in summary.loc[row, "EntitySet"]:
                renamed = True

            # if NumVolumes is nan, set to 1.0
            # if 'NumVolumes' in summary.columns \
            #         and str(summary.loc[row, "NumVolumes"]) == 'nan':
            #     summary.at[row, "NumVolumes"] = 1.0

            if summary.loc[row, "ParamGroup"] != 1 and not renamed:
                acq_str = "VARIANT"
                # now we know we have a deviant param group
                # check if TR is same as param group 1
                key = summary.loc[row, "EntitySet"]
                for col in rename_cols:
                    summary[col] = summary[col].apply(str)
                    if summary.loc[row, col] != dom_dict[key][col]:
                        if col == "HasFieldmap":
                            if dom_dict[key][col] == "True":
                                acq_str = acq_str + "NoFmap"
                            else:
                                acq_str = acq_str + "HasFmap"
                        elif col == "UsedAsFieldmap":
                            if dom_dict[key][col] == "True":
                                acq_str = acq_str + "Unused"
                            else:
                                acq_str = acq_str + "IsUsed"
                        else:
                            acq_str = acq_str + col

                if acq_str == "VARIANT":
                    acq_str = acq_str + "Other"

                if "acquisition" in entities.keys():
                    acq = f"acquisition-{entities['acquisition'] + acq_str}"

                    new_name = summary.loc[row, "EntitySet"].replace(
                        f"acquisition-{entities['acquisition']}",
                        acq,
                    )
                else:
                    acq = f"acquisition-{acq_str}"
                    new_name = acq + "_" + summary.loc[row, "EntitySet"]

                summary.at[row, "RenameEntitySet"] = new_name

            # convert all "nan" to empty str
            # so they don't show up in the summary tsv
            if summary.loc[row, "RenameEntitySet"] == "nan":
                summary.at[row, "RenameEntitySet"] = ""

            for col in rename_cols:
                if summary.loc[row, col] == "nan":
                    summary.at[row, col] = ""

        return (big_df, summary)

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
        with open(f"{path_prefix}_files.json", "w") as outfile:
            json.dump(files_dict, outfile, indent=4)

        with open(f"{path_prefix}_summary.json", "w") as outfile:
            json.dump(summary_dict, outfile, indent=4)

        big_df.to_csv(f"{path_prefix}_files.tsv", sep="\t", index=False)

        summary.to_csv(f"{path_prefix}_summary.tsv", sep="\t", index=False)

        # Calculate the acq groups
        group_by_acquisition_sets(f"{path_prefix}_files.tsv", path_prefix, self.acq_group_level)

        print(f"CuBIDS detected {len(summary)} Parameter Groups.")

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
                entity_sets.update((_file_to_entity_set(path),))

                # Fill the dictionary of entity set, list of filenames pairrs
                ret = _file_to_entity_set(path)

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
            bidsjson_file = img_to_new_ext(str(bidsfile), ".json")
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
                _update_json(json_file.path, sidecar)

    def get_all_metadata_fields(self):
        """Return all metadata fields in a BIDS directory.

        This method searches through all JSON files in the specified BIDS directory
        and collects all unique metadata fields present in those files. It skips
        files within any ".git" directory and handles empty files and JSON decoding
        errors gracefully.

        Returns
        -------
        list of str
            A sorted list of all unique metadata fields found in the BIDS directory.

        Raises
        ------
        UserWarning
            If there is an error decoding a JSON file or any unexpected error occurs
            while processing a file.
        """
        found_fields = set()
        for json_file in Path(self.path).rglob("*.json"):
            if ".git" not in str(json_file):
                # add this in case `print-metadata-fields` is run before validate
                try:
                    with open(json_file, "r", encoding="utf-8") as jsonr:
                        content = jsonr.read().strip()
                        if not content:
                            print(f"Empty file: {json_file}")
                            continue
                        metadata = json.loads(content)
                    found_fields.update(metadata.keys())
                except json.JSONDecodeError as e:
                    warnings.warn(f"Error decoding JSON in {json_file}: {e}")
                except Exception as e:
                    warnings.warn(f"Unexpected error with file {json_file}: {e}")

        return sorted(found_fields)

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


# XXX: Remove _validate_json?
def _validate_json():
    """Validate a JSON file's contents.

    This is currently not implemented, but would accept metadata as its param.
    """
    # TODO: implement this or delete ???
    return True


def _update_json(json_file, metadata):
    """Update a JSON file with the provided metadata.

    This function writes the given metadata to the specified JSON file if the
    JSON data is valid. If the JSON data is invalid, it prints an error message.

    Parameters
    ----------
    json_file : str
        The path to the JSON file to be updated.
    metadata : dict
        The metadata to be written to the JSON file.

    Returns
    -------
    None
    """
    if _validate_json():
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
    else:
        print("INVALID JSON DATA")


def _entity_set_to_entities(entity_set):
    """Split an entity_set name into a pybids dictionary of entities.

    Parameters
    ----------
    entity_set : str
        A string representing a set of entities, where each entity is
        separated by an underscore and each key-value pair is separated by a hyphen.

    Returns
    -------
    dict
        A dictionary where the keys are entity names and the values are entity values.

    Examples
    --------
    >>> _entity_set_to_entities("sub-01_ses-02_task-rest")
    {'sub': '01', 'ses': '02', 'task': 'rest'}
    """
    return dict([group.split("-") for group in entity_set.split("_")])


def _entities_to_entity_set(entities):
    """Convert a pybids entities dictionary into an entity set name.

    Parameters
    ----------
    entities : dict
        A dictionary containing pybids entities where keys are entity names
        and values are entity values.

    Returns
    -------
    str
        A string representing the entity set name, constructed by joining
        the sorted entity keys and their corresponding values, separated by hyphens.
    """
    group_keys = sorted(entities.keys() - NON_KEY_ENTITIES)
    return "_".join([f"{key}-{entities[key]}" for key in group_keys])


def _file_to_entity_set(filename):
    """Identify and return the entity set of a BIDS valid filename.

    Parameters
    ----------
    filename : str
        The filename to parse for BIDS entities.

    Returns
    -------
    set
        A set of entities extracted from the filename.
    """
    entities = parse_file_entities(str(filename))
    return _entities_to_entity_set(entities)


def _get_participant_relative_path(scan):
    """Build the relative-from-subject version of a Path to a file.

    Parameters
    ----------
    scan : str
        The full path to the scan file.

    Returns
    -------
    str
        The relative path from the subject directory.

    Raises
    ------
    ValueError
        If the subject directory cannot be found in the path.

    Examples
    --------
    >>> _get_participant_relative_path(
    ...    "/path/to/dset/sub-01/ses-01/func/sub-01_ses-01_bold.nii.gz",
    ... )
    'ses-01/func/sub-01_ses-01_bold.nii.gz'

    >>> _get_participant_relative_path(
    ...    "/path/to/dset/sub-01/func/sub-01_bold.nii.gz",
    ... )
    'func/sub-01_bold.nii.gz'

    >>> _get_participant_relative_path(
    ...    "/path/to/dset/ses-01/func/ses-01_bold.nii.gz",
    ... )
    Traceback (most recent call last):
    ValueError: Could not find subject in ...
    """
    parts = Path(scan).parts
    # Find the first part that starts with "sub-"
    for i, part in enumerate(parts):
        if part.startswith("sub-"):
            return "/".join(parts[i + 1 :])
    raise ValueError(f"Could not find subject in {scan}")


def _get_bidsuri(filename, dataset_root):
    """Convert a file path to a BIDS URI.

    Parameters
    ----------
    filename : str
        The full path to the file within the BIDS dataset.
    dataset_root : str
        The root directory of the BIDS dataset.

    Returns
    -------
    str
        The BIDS URI corresponding to the given file path.

    Raises
    ------
    ValueError
        If the filename is not within the dataset_root.

    Examples
    --------
    >>> _get_bidsuri("/path/to/bids/sub-01/ses-01/dataset_description.json", "/path/to/bids")
    'bids::sub-01/ses-01/dataset_description.json'
    """
    if dataset_root in filename:
        return filename.replace(dataset_root, "bids::").replace("bids::/", "bids::")
    raise ValueError(f"Only local datasets are supported: {filename}")


def _get_param_groups(
    files,
    fieldmap_lookup,
    entity_set_name,
    grouping_config,
    modality,
    keys_files,
):
    """Find a list of *parameter groups* from a list of files.

    For each file in `files`, find critical parameters for metadata. Then find
    unique sets of these critical parameters.

    Parameters
    ----------
    files : :obj:`list` of :obj:`str`
        List of file names
    fieldmap_lookup : :obj:`dict`
        mapping of filename strings relative to the bids root
        (e.g. "sub-X/ses-Y/func/sub-X_ses-Y_task-rest_bold.nii.gz")
    grouping_config : :obj:`dict`
        configuration for defining parameter groups

    Returns
    -------
    labeled_files : :obj:`pandas.DataFrame`
        A data frame with one row per file where the ParamGroup column
        indicates which group each scan is a part of.
    param_groups_with_counts : :obj:`pandas.DataFrame`
        A data frame with param group summaries.
    """
    if not files:
        print("WARNING: no files for", entity_set_name)
        return None, None

    # Split the config into separate parts
    imaging_params = grouping_config.get("sidecar_params", {})
    imaging_params = imaging_params[modality]

    relational_params = grouping_config.get("relational_params", {})

    derived_params = grouping_config.get("derived_params")
    derived_params = derived_params[modality]

    imaging_params.update(derived_params)

    dfs = []
    # path needs to be relative to the root with no leading prefix

    for path in files:
        # metadata = layout.get_metadata(path)
        metadata = get_sidecar_metadata(img_to_new_ext(path, ".json"))
        if metadata == "Erroneous sidecar":
            print("Error parsing sidecar: ", img_to_new_ext(path, ".json"))
        else:
            intentions = metadata.get("IntendedFor", [])
            slice_times = metadata.get("SliceTiming", [])

            wanted_keys = metadata.keys() & imaging_params
            example_data = {key: metadata[key] for key in wanted_keys}
            example_data["EntitySet"] = entity_set_name

            # Get the fieldmaps out and add their types
            if "FieldmapKey" in relational_params:
                fieldmap_types = sorted(
                    [_file_to_entity_set(fmap.path) for fmap in fieldmap_lookup[path]]
                )

                # check if config says columns or bool
                if relational_params["FieldmapKey"]["display_mode"] == "bool":
                    if len(fieldmap_types) > 0:
                        example_data["HasFieldmap"] = True
                    else:
                        example_data["HasFieldmap"] = False
                else:
                    for fmap_num, fmap_type in enumerate(fieldmap_types):
                        example_data[f"FieldmapKey{fmap_num:02d}"] = fmap_type

            # Add the number of slice times specified
            if "NSliceTimes" in derived_params:
                example_data["NSliceTimes"] = len(slice_times)

            example_data["FilePath"] = path

            # If it's a fieldmap, see what entity set it's intended to correct
            if "IntendedForKey" in relational_params:
                intended_entity_sets = sorted(
                    [_file_to_entity_set(intention) for intention in intentions]
                )

                # check if config says columns or bool
                if relational_params["IntendedForKey"]["display_mode"] == "bool":
                    if len(intended_entity_sets) > 0:
                        example_data["UsedAsFieldmap"] = True
                    else:
                        example_data["UsedAsFieldmap"] = False
                else:
                    for intention_num, intention_entity_set in enumerate(intended_entity_sets):
                        example_data[f"IntendedForKey{intention_num:02d}"] = intention_entity_set

            dfs.append(example_data)

    # Assign each file to a ParamGroup

    # round param groups based on precision
    df = round_params(pd.DataFrame(dfs), grouping_config, modality)

    # cluster param groups based on tolerance
    df = format_params(df, grouping_config, modality)
    # param_group_cols = list(set(df.columns.to_list()) - set(["FilePath"]))

    # get the subset of columns to drop duplicates by
    check_cols = []
    for col in list(df.columns):
        if f"Cluster_{col}" not in list(df.columns) and col != "FilePath":
            check_cols.append(col)

    # Find the unique ParamGroups and assign ID numbers in "ParamGroup"\
    try:
        deduped = df.drop("FilePath", axis=1)
    except Exception:
        return "erroneous sidecar found"

    deduped = deduped.drop_duplicates(subset=check_cols, ignore_index=True)
    deduped["ParamGroup"] = np.arange(deduped.shape[0]) + 1

    # add the modality as a column
    deduped["Modality"] = modality

    # add entity set count column (will delete later)
    deduped["EntitySetCount"] = len(keys_files[entity_set_name])

    # Add the ParamGroup to the whole list of files
    labeled_files = pd.merge(df, deduped, on=check_cols)

    value_counts = labeled_files.ParamGroup.value_counts()

    param_group_counts = pd.DataFrame(
        {"Counts": value_counts.to_numpy(), "ParamGroup": value_counts.index.to_numpy()}
    )

    param_groups_with_counts = pd.merge(deduped, param_group_counts, on=["ParamGroup"])

    # Sort by counts and relabel the param groups
    param_groups_with_counts.sort_values(by=["Counts"], inplace=True, ascending=False)
    param_groups_with_counts["ParamGroup"] = np.arange(param_groups_with_counts.shape[0]) + 1

    # Send the new, ordered param group ids to the files list
    ordered_labeled_files = pd.merge(
        df, param_groups_with_counts, on=check_cols, suffixes=("_x", "")
    )

    # sort ordered_labeled_files by param group
    ordered_labeled_files.sort_values(by=["Counts"], inplace=True, ascending=False)

    # now get rid of cluster cols from deduped and df
    for col in list(ordered_labeled_files.columns):
        if col.startswith("Cluster_"):
            ordered_labeled_files = ordered_labeled_files.drop(col, axis=1)
            param_groups_with_counts = param_groups_with_counts.drop(col, axis=1)
        if col.endswith("_x"):
            ordered_labeled_files = ordered_labeled_files.drop(col, axis=1)

    return ordered_labeled_files, param_groups_with_counts


def round_params(param_group_df, config, modality):
    """Round columns' values in a DataFrame according to requested precision.

    Parameters
    ----------
    param_group_df : pandas.DataFrame
        DataFrame containing the parameters to be rounded.
    config : dict
        Configuration dictionary containing rounding precision information.
    modality : str
        The modality key to access the relevant rounding precision settings in the config.

    Returns
    -------
    pandas.DataFrame
        DataFrame with the specified columns' values rounded to the requested precision.
    """
    to_format = config["sidecar_params"][modality]
    to_format.update(config["derived_params"][modality])

    for column_name, column_fmt in to_format.items():
        if column_name not in param_group_df:
            continue

        if "precision" in column_fmt:
            if isinstance(param_group_df[column_name], float):
                param_group_df[column_name] = param_group_df[column_name].round(
                    column_fmt["precision"]
                )

    return param_group_df


def get_sidecar_metadata(json_file):
    """Get all metadata values in a file's sidecar.

    Transform JSON dictionary to Python dictionary.

    Parameters
    ----------
    json_file : str
        Path to the JSON sidecar file.

    Returns
    -------
    dict or str
        Returns a dictionary containing the metadata if the file is successfully read,
        otherwise returns the string "Erroneous sidecar".

    Raises
    ------
    Exception
        If there is an error loading the JSON file.
    """
    try:
        with open(json_file) as json_file:
            data = json.load(json_file)
            return data
    except Exception:
        # print("Error loading sidecar: ", json_filename)
        return "Erroneous sidecar"


def format_params(param_group_df, config, modality):
    """Run AgglomerativeClustering on param groups and add columns to dataframe.

    Parameters
    ----------
    param_group_df : :obj:`pandas.DataFrame`
        A data frame with one row per file where the ParamGroup column
        indicates which group each scan is a part of.
    config : :obj:`dict`
        Configuration for defining parameter groups.
        This dictionary has two keys: ``'sidecar_params'`` and ``'derived_params'``.
    modality : :obj:`str`
        Modality of the scan.
        This is used to select the correct configuration from the config dict.

    Returns
    -------
    param_group_df : :obj:`pandas.DataFrame`
        An updated version of the input data frame,
        with a new column added for each element in the modality's
        ``'sidecar_params'`` and ``'derived_params'`` dictionaries.
        The new columns will have the name ``'Cluster_' + column_name``,
        and will contain the cluster labels for each parameter group.

    Notes
    -----
    ``'sidecar_params'`` is a dictionary of dictionaries, where keys are modalities.
    The modality-wise dictionary's keys are names of BIDS fields to directly include
    in the Parameter Groupings,
    and the values describe the parameters by which those BIDS' fields are compared.
    For example,
    {"RepetitionTime": {"tolerance": 0.000001, "precision": 6, "suggest_variant_rename": True}
    means that the RepetitionTime field should be compared across files and flagged as a
    variant if it differs from others by 0.000001 or more.

    ``'derived_params'`` is a dictionary of dictionaries, where keys are modalities.
    The modality-wise dictionary's keys are names of BIDS fields to derive from the
    NIfTI header and include in the Parameter Groupings.
    """
    to_format = config["sidecar_params"][modality]
    to_format.update(config["derived_params"][modality])

    for column_name, column_fmt in to_format.items():
        if column_name not in param_group_df:
            continue

        if "tolerance" in column_fmt and len(param_group_df) > 1:
            array = param_group_df[column_name].to_numpy().reshape(-1, 1)

            for i in range(len(array)):
                if np.isnan(array[i, 0]):
                    array[i, 0] = -999

            tolerance = to_format[column_name]["tolerance"]
            clustering = AgglomerativeClustering(
                n_clusters=None, distance_threshold=tolerance, linkage="complete"
            ).fit(array)

            for i in range(len(array)):
                if array[i, 0] == -999:
                    array[i, 0] = np.nan

            # now add clustering_labels as a column
            param_group_df[f"Cluster_{column_name}"] = clustering.labels_

    return param_group_df


def _order_columns(df):
    """Organize columns of the summary and files DataFrames.

    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame whose columns need to be organized.

    Returns
    -------
    pandas.DataFrame
        The DataFrame with columns organized such that 'EntitySet' and
        'ParamGroup' are the first two columns, 'FilePath' is the last
        column (if present), and the remaining columns are sorted
        alphabetically.

    Notes
    -----
    This is the only place where the constant ID_VARS is used,
    and the strings in that constant are hardcoded here,
    so we might not need that constant at all.
    """
    cols = set(df.columns.to_list())
    non_id_cols = cols - ID_VARS
    new_columns = ["EntitySet", "ParamGroup"] + sorted(non_id_cols)
    if "FilePath" in cols:
        new_columns.append("FilePath")

    df = df[new_columns]

    return df[new_columns]


def img_to_new_ext(img_path, new_ext):
    """Convert an image file path to a new extension.

    Parameters
    ----------
    img_path : str
        The file path of the image to be converted.
    new_ext : str
        The new extension to be applied to the image file path.

    Returns
    -------
    str
        The file path with the new extension applied.

    Examples
    --------
    >>> img_to_new_ext('/path/to/file_image.nii.gz', '.tsv')
    '/path/to/file_events.tsv'

    >>> img_to_new_ext('/path/to/file_image.nii.gz', '.tsv.gz')
    '/path/to/file_physio.tsv.gz'

    >>> img_to_new_ext('/path/to/file_image.nii.gz', '.json')
    '/path/to/file_image.json'

    Notes
    -----
    The hardcoded suffix associated with each extension may not be comprehensive.
    BIDS has been extended a lot in recent years.
    """
    # handle .tsv edge case
    if new_ext == ".tsv":
        # take out suffix
        return img_path.rpartition("_")[0] + "_events" + new_ext
    elif new_ext == ".tsv.gz":
        return img_path.rpartition("_")[0] + "_physio" + new_ext
    else:
        return img_path.replace(".nii.gz", "").replace(".nii", "") + new_ext


def get_entity_value(path, key):
    """Given a filepath and BIDS key name, return the value associated with the key.

    Parameters
    ----------
    path : str
        The file path to be parsed.
    key : str
        The BIDS key name to search for in the file path.

    Returns
    -------
    str or None
        The value associated with the BIDS key if found, otherwise None.

    Examples
    --------
    >>> get_entity_value('/path/to/sub-01/ses-01/func/sub-01_ses-02_task-rest_bold.nii.gz', 'sub')
    'sub-01'
    >>> get_entity_value('/path/to/sub-01/ses-02/func/sub-01_ses-02_task-rest_bold.nii.gz', 'ses')
    'ses-02'
    """
    parts = Path(path).parts
    for part in parts:
        if part.startswith(key + "-"):
            return part


def build_path(filepath, out_entities, out_dir, schema, is_longitudinal):
    """Build a new path for a file based on its BIDS entities.

    This function could ultimately be replaced with bids.BIDSLayout.build_path(),
    but that method doesn't use the schema.

    Parameters
    ----------
    filepath : str
        The original file path.
    out_entities : dict
        A dictionary of BIDS entities.
        This should include all of the entities in the filename *except* for subject and session.
    out_dir : str
        The output directory for the new file.
    schema : dict
        The BIDS schema. The elements that are used in this function include:

        -   schema["rules"]["entities"]: a list of valid BIDS entities,
            in the order they must appear in filenames.
        -   schema["objects"]["entities"]: a dictionary mapping entity names
            (e.g., acquisition) to their corresponding keys (e.g., acq).
        -   schema["objects"]["datatypes"]: a dictionary defining the valid datatypes.
            This function only uses the keys of this dictionary.
    is_longitudinal : bool
        If True, add "ses" to file path.

    Returns
    -------
    new_path : str
        The new file path.

    Examples
    --------
    >>> import json
    >>> import importlib
    >>> schema_file = Path(importlib.resources.files("cubids") / "data/schema.json")
    >>> with schema_file.open() as f:
    ...    schema = json.load(f)
    >>> build_path(
    ...    "/input/sub-01/ses-01/anat/sub-01_ses-01_T1w.nii.gz",
    ...    {"acquisition": "VAR", "suffix": "T2w"},
    ...    "/output",
    ...    schema,
    ...    True,
    ... )
    '/output/sub-01/ses-01/anat/sub-01_ses-01_acq-VAR_T2w.nii.gz'

    The function does not add an extra leading zero to the run entity when it's a string.

    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_bold.nii.gz",
    ...    {"task": "rest", "run": "2", "acquisition": "VAR", "suffix": "bold"},
    ...    "/output",
    ...    schema,
    ...    True,
    ... )
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-rest_acq-VAR_run-2_bold.nii.gz'

    The function adds an extra leading zero to the run entity when it's an integer
    and the original filename has a leading zero.

    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-00001_bold.nii.gz",
    ...    {"task": "rest", "run": 2, "acquisition": "VAR", "suffix": "bold"},
    ...    "/output",
    ...    schema,
    ...    True,
    ... )
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-rest_acq-VAR_run-00002_bold.nii.gz'

    The function does not add an extra leading zero to the run entity when it's an integer
    and the original filename doesn't have a leading zero.

    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-1_bold.nii.gz",
    ...    {"task": "rest", "run": 2, "acquisition": "VAR", "suffix": "bold"},
    ...    "/output",
    ...    schema,
    ...    True,
    ... )
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-rest_acq-VAR_run-2_bold.nii.gz'

    The function doesn't add an extra leading zero to the run entity when there isn't a zero.

    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-1_bold.nii.gz",
    ...    {"task": "rest", "run": "2", "acquisition": "VAR", "suffix": "bold"},
    ...    "/output",
    ...    schema,
    ...    True,
    ... )
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-rest_acq-VAR_run-2_bold.nii.gz'

    Entities in the original path, but not the entity dictionary, are not included,
    like run in this case.

    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_bold.nii.gz",
    ...    {"task": "rest", "acquisition": "VAR", "suffix": "bold"},
    ...    "/output",
    ...    schema,
    ...    True,
    ... )
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-rest_acq-VAR_bold.nii.gz'

    The "subject" and "session" entities are ignored.

    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_bold.nii.gz",
    ...    {"subject": "02", "task": "rest", "acquisition": "VAR", "suffix": "bold"},
    ...    "/output",
    ...    schema,
    ...    True,
    ... )
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-rest_acq-VAR_bold.nii.gz'

    But uncommon (but BIDS-valid) entities, like echo, will work.

    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_bold.nii.gz",
    ...    {"task": "rest", "acquisition": "VAR", "echo": 1, "suffix": "bold"},
    ...    "/output",
    ...    schema,
    ...    True,
    ... )
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-rest_acq-VAR_echo-1_bold.nii.gz'

    It can change the datatype, but will warn the user.

    >>> build_path(
    ...    "/input/sub-01/ses-01/anat/sub-01_ses-01_asl.nii.gz",
    ...    {"datatype": "perf", "acquisition": "VAR", "suffix": "asl"},
    ...    "/output",
    ...    schema,
    ...    True,
    ... )
    WARNING: DATATYPE CHANGE DETECTED
    '/output/sub-01/ses-01/perf/sub-01_ses-01_acq-VAR_asl.nii.gz'

    The datatype change is subject to false positives.

    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-meg_bold.nii.gz",
    ...    {"datatype": "func", "acquisition": "VAR", "task": "meg", "suffix": "bold"},
    ...    "/output",
    ...    schema,
    ...    True,
    ... )
    WARNING: DATATYPE CHANGE DETECTED
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-meg_acq-VAR_bold.nii.gz'

    It expects a longitudinal structure, so providing a cross-sectional filename won't work.
    XXX: This is a bug.

    It also works for cross-sectional filename.
    >>> build_path(
    ...    "/input/sub-01/func/sub-01_task-rest_run-01_bold.nii.gz",
    ...    {"task": "rest", "acquisition": "VAR", "suffix": "bold"},
    ...    "/output",
    ...    schema,
    ...    False,
    ... )
    '/output/sub-01/func/sub-01_task-rest_acq-VAR_bold.nii.gz'
    """
    exts = Path(filepath).suffixes
    old_ext = "".join(exts)

    suffix = out_entities["suffix"]

    valid_entities = schema["rules"]["entities"]
    entity_names_to_keys = entity_names_to_keys = {
        k: v["name"] for k, v in schema["objects"]["entities"].items()
    }
    valid_datatypes = list(schema["objects"]["datatypes"].keys())

    # Remove subject and session from the entities
    file_entities = {k: v for k, v in out_entities.items() if k not in ["subject", "session"]}
    # Limit file entities to valid entities from BIDS (sorted in right order)
    file_entities = {k: out_entities[k] for k in valid_entities if k in file_entities}
    # Replace entity names with keys (e.g., acquisition with acq)
    file_entities = {entity_names_to_keys[k]: v for k, v in file_entities.items()}

    sub = get_entity_value(filepath, "sub")
    if sub is None:
        raise ValueError(f"Could not extract subject from {filepath}")

    if is_longitudinal:
        ses = get_entity_value(filepath, "ses")
        if ses is None:
            raise ValueError(f"Could not extract session from {filepath}")

    # Add leading zeros to run entity if it's an integer.
    # If it's a string, respect the value provided.
    if "run" in file_entities.keys() and isinstance(file_entities["run"], int):
        # Infer the number of leading zeros needed from the original filename
        n_leading = 2  # default to 1 leading zero
        if "_run-" in filepath:
            run_str = filepath.split("_run-")[1].split("_")[0]
            n_leading = len(run_str)
        file_entities["run"] = str(file_entities["run"]).zfill(n_leading)

    filename = "_".join([f"{key}-{value}" for key, value in file_entities.items()])
    if len(filename) > 0:
        if is_longitudinal:
            filename = f"{sub}_{ses}_{filename}_{suffix}{old_ext}"
        elif not is_longitudinal:
            filename = f"{sub}_{filename}_{suffix}{old_ext}"
    else:
        raise ValueError(f"Could not construct new filename for {filepath}")

    # CHECK TO SEE IF DATATYPE CHANGED
    # datatype may be overridden/changed if the original file is located in the wrong folder.
    # XXX: This check for the datatype is fragile and should be improved.
    # For example, what if we have sub-01/func/sub-01_task-anatomy_bold.nii.gz?
    dtype_orig = ""
    for dtype in valid_datatypes:
        if dtype in filepath:
            dtype_orig = dtype

    dtype_new = out_entities.get("datatype", dtype_orig)
    if dtype_new != dtype_orig:
        print("WARNING: DATATYPE CHANGE DETECTED")

    # Construct the new filename
    if is_longitudinal:
        new_path = str(Path(out_dir) / sub / ses / dtype_new / filename)
    elif not is_longitudinal:
        new_path = str(Path(out_dir) / sub / dtype_new / filename)

    return new_path
