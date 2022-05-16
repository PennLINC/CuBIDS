"""Main module."""
import warnings
from collections import defaultdict
import subprocess
import bids
import bids.layout
import json
import csv
import os
from pathlib import Path
from bids.layout import parse_file_entities
from bids.utils import listify
import numpy as np
import pandas as pd
import nibabel as nb
import datalad.api as dlapi
from shutil import copytree, copyfile
from sklearn.cluster import AgglomerativeClustering
from tqdm import tqdm
from .constants import ID_VARS, NON_KEY_ENTITIES
from .config import load_config
from .metadata_merge import (
    check_merging_operations, group_by_acquisition_sets)
warnings.simplefilter(action='ignore', category=FutureWarning)
bids.config.set_option('extension_initial_dot', True)


class CuBIDS(object):

    def __init__(self, data_root, use_datalad=False, acq_group_level='subject',
                 grouping_config=None, force_unlock=False):

        self.path = os.path.abspath(data_root)
        self._layout = None
        self.keys_files = {}
        self.fieldmaps_cached = False
        self.datalad_ready = False
        self.datalad_handle = None
        self.old_filenames = []  # files whose key groups changed
        self.new_filenames = []  # new filenames for files to change
        self.IF_rename_paths = []  # fmap jsons with rename intended fors
        self.grouping_config = load_config(grouping_config)
        self.acq_group_level = acq_group_level
        self.scans_txt = None  # txt file of scans to purge (for purge only)
        self.force_unlock = force_unlock  # force unlock for add-nifti-info

        self.use_datalad = use_datalad  # True if flag set, False if flag unset
        if self.use_datalad:
            self.init_datalad()

        if self.acq_group_level == 'session':
            NON_KEY_ENTITIES.remove("session")

    @property
    def layout(self):
        if self._layout is None:
            self.reset_bids_layout()
        return self._layout

    def reset_bids_layout(self, validate=False):
        self._layout = bids.BIDSLayout(self.path, validate=validate)

    def init_datalad(self):
        """Initializes a datalad Dataset at self.path.

        Parameters:
        -----------

            save: bool
                Run datalad save to add any untracked files
            message: str or None
                Message to add to
        """
        self.datalad_ready = True

        self.datalad_handle = dlapi.Dataset(self.path)
        if not self.datalad_handle.is_installed():
            self.datalad_handle = dlapi.create(self.path,
                                               cfg_proc='text2git',
                                               force=True,
                                               annex=True)

    def datalad_save(self, message=None):
        """Performs a DataLad Save operation on the BIDS tree.

        Additionally a check for an active datalad handle and that the
        status of all objects after the save is "ok".

        Parameters:
        -----------
            message : str or None
                Commit message to use with datalad save
        """

        if not self.datalad_ready:
            raise Exception(
                "DataLad has not been initialized. use datalad_init()")
        statuses = self.datalad_handle.save(message=message or "CuBIDS Save")
        saved_status = set([status['status'] for status in statuses])
        if not saved_status == set(["ok"]):
            raise Exception("Failed to save in DataLad")

    def is_datalad_clean(self):
        """If True, no changes are detected in the datalad dataset."""
        if not self.datalad_ready:
            raise Exception(
                "Datalad not initialized, can't determine status")
        statuses = set([status['state'] for status in
                        self.datalad_handle.status()])
        return statuses == set(["clean"])

    def datalad_undo_last_commit(self):
        """Revert the most recent commit, remove it from history.

        Uses git reset --hard to revert to the previous commit.
        """
        if not self.is_datalad_clean():
            raise Exception("Untracked changes present. "
                            "Run clear_untracked_changes first")
        reset_proc = subprocess.run(
            ["git", "reset", "--hard", "HEAD~1"], cwd=self.path)
        reset_proc.check_returncode()

    def add_nifti_info(self, raise_on_error=True):
        """Adds info from nifti files to json sidecars."""
        # check if force_unlock is set
        if self.force_unlock:
            # CHANGE TO SUBPROCESS.CALL IF NOT BLOCKING
            subprocess.run(["datalad", "unlock"], cwd=self.path)

        # loop through all niftis in the bids dir
        for path in Path(self.path).rglob("sub-*/**/*.*"):
            # ignore all dot directories
            if '/.' in str(path):
                continue
            if str(path).endswith(".nii") or str(path).endswith(".nii.gz"):
                try:
                    img = nb.load(str(path))
                except Exception:
                    print("Empty Nifti File: ", str(path))
                    continue
                # get important info from niftis
                obliquity = np.any(nb.affines.obliquity(img.affine)
                                   > 1e-4)
                voxel_sizes = img.header.get_zooms()
                matrix_dims = img.shape
                # add nifti info to corresponding sidecars​
                sidecar = img_to_new_ext(str(path), '.json')
                if Path(sidecar).exists():

                    with open(sidecar) as f:
                        data = json.load(f)

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
                            data["NumVolumes"] = 1.0
                    if "ImageOrientation" not in data.keys():
                        orient = nb.orientations.aff2axcodes(img.affine)
                        joined = ''.join(orient) + '+'
                        data["ImageOrientation"] = joined
                    with open(sidecar, 'w') as file:
                        json.dump(data, file, indent=4)

        if self.use_datalad:
            self.datalad_save(message="Added nifti info to sidecars")
            self.reset_bids_layout()

    def apply_csv_changes(self, summary_csv, files_csv, new_prefix,
                          raise_on_error=True):
        """Applies changes documented in the edited _summary csv
        and generates the new csv files.

        This function looks at the RenameKeyGroup and MergeInto
        columns and modifies the bids datset according to the
        specified changs.

        Parameters:
        -----------
            orig_prefix : str
                Path prefix and file stem for the original
                _summary and _files csvs.
                For example, if orig_prefix is
                '/cbica/projects/HBN/old_CSVs' then the paths to
                the summary and files csvs will be
                '/cbica/projects/HBN/old_CSVs_summary.csv' and
                '/cbica/projects/HBN/old_CSVs_files.csv' respectively.
            new_prefix : str
                Path prefix and file stem for the new summary and
                files csvs.
        """
        # reset lists of old and new filenames
        self.old_filenames = []
        self.new_filenames = []

        files_df = pd.read_csv(files_csv)
        summary_df = pd.read_csv(summary_csv)

        # Check that the MergeInto column only contains valid merges
        ok_merges, deletions = check_merging_operations(
            summary_csv, raise_on_error=raise_on_error)

        merge_commands = []
        for source_id, dest_id in ok_merges:
            dest_files = files_df.loc[
                (files_df[["ParamGroup", "KeyGroup"]] == dest_id).all(1)]
            source_files = files_df.loc[
                (files_df[["ParamGroup", "KeyGroup"]] == source_id).all(1)]

            # Get a source json file
            source_json = img_to_new_ext(source_files.iloc[0].FilePath,
                                         '.json')
            for dest_nii in dest_files.FilePath:
                dest_json = img_to_new_ext(dest_nii, '.json')
                if Path(dest_json).exists() and Path(source_json).exists():
                    merge_commands.append(
                        'bids-sidecar-merge %s %s'
                        % (source_json, dest_json))

        # Get the delete commands
        # delete_commands = []
        to_remove = []
        for rm_id in deletions:
            files_to_rm = files_df.loc[
                (files_df[["ParamGroup", "KeyGroup"]] == rm_id).all(1)]
            for rm_me in files_to_rm.FilePath:
                if Path(rm_me).exists():
                    to_remove.append(rm_me)
                    # delete_commands.append("rm " + rm_me)

        # call purge associations on list of files to remove
        self._purge_associations(to_remove)

        # Now do the file renaming
        change_keys_df = summary_df[summary_df.RenameKeyGroup.notnull()]
        move_ops = []
        # return if nothing to change
        if len(change_keys_df) > 0:

            key_groups = {}

            for i in range(len(change_keys_df)):
                new_key = change_keys_df.iloc[i]['RenameKeyGroup']
                old_key_param = change_keys_df.iloc[i]['KeyParamGroup']

                # add to dictionary
                key_groups[old_key_param] = new_key

            # orig key/param tuples that will have new key group
            to_change = list(key_groups.keys())

            for row in range(len(files_df)):
                file_path = files_df.loc[row, 'FilePath']
                if Path(file_path).exists() and '/fmap/' not in file_path:

                    key_param_group = files_df.loc[row, 'KeyParamGroup']

                    if key_param_group in to_change:

                        orig_key_param = files_df.loc[row, 'KeyParamGroup']

                        new_key = key_groups[orig_key_param]

                        new_entities = _key_group_to_entities(new_key)

                        # generate new filenames according to new key group
                        self.change_filename(file_path, new_entities)

            # create string of mv command ; mv command for dlapi.run
            for from_file, to_file in zip(self.old_filenames,
                                          self.new_filenames):

                if Path(from_file).exists():
                    # if using datalad, we want to git mv instead of mv
                    if self.use_datalad:
                        move_ops.append('git mv %s %s' % (from_file, to_file))
                    else:
                        move_ops.append('mv %s %s' % (from_file, to_file))
        full_cmd = "\n".join(merge_commands + move_ops)
        if full_cmd:
            # write full_cmd to a .sh file
            # Open file for writing
            fileObject = open(new_prefix + "_full_cmd.sh", "w")
            fileObject.write("#!/bin/bash\n")
            fileObject.write(full_cmd)
            # Close the file
            fileObject.close()

            renames = new_prefix + '_full_cmd.sh'

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

                self.datalad_handle.run(cmd=["bash", renames],
                                        message=rename_commit)
            else:
                subprocess.run(["bash", renames],
                               stdout=subprocess.PIPE,
                               cwd=str(Path(new_prefix).parent))
        else:
            print("Not running any commands")

        self.reset_bids_layout()
        self.get_CSVs(new_prefix)

    def change_filename(self, filepath, entities):
        """Applies changes to a filename based on the renamed
        key groups.
        This function takes into account the new key group names
        and renames all files whose key group names changed.
        Parameters:
        -----------
            filepath : str
                Path prefix to a file in the affected key group change
            entities : dictionary
                A pybids dictionary of entities parsed from the new key
                group name.
        """
        exts = Path(filepath).suffixes
        old_ext = ""
        for ext in exts:
            old_ext += ext

        suffix = entities['suffix']
        entity_file_keys = []
        file_keys = ['task', 'acquisition', 'direction',
                     'reconstruction', 'run']

        for key in file_keys:
            if key in list(entities.keys()):
                entity_file_keys.append(key)

        sub = get_key_name(filepath, 'sub')
        ses = get_key_name(filepath, 'ses')
        sub_ses = sub + '_' + ses

        if 'run' in list(entities.keys()) and 'run-0' in filepath:
            entities['run'] = '0' + str(entities['run'])

        filename = "_".join(["{}-{}".format(key, entities[key])
                             for key in entity_file_keys])
        filename = filename.replace('acquisition', 'acq') \
            .replace('direction', 'dir') \
            .replace('reconstruction', 'rec')
        if len(filename) > 0:
            filename = sub_ses + '_' + filename + '_' + suffix + old_ext
        else:
            filename = sub_ses + filename + '_' + suffix + old_ext

        # CHECK TO SEE IF DATATYPE CHANGED
        dtypes = ['anat', 'func', 'perf', 'fmap', 'dwi']
        old = ''
        for dtype in dtypes:
            if dtype in filepath:
                old = dtype

        if 'datatype' in entities.keys():
            dtype = entities['datatype']
            if entities['datatype'] != old:
                print("WARNING: DATATYPE CHANGE DETECETD")
        else:
            dtype = old
        new_path = str(self.path) + '/' + sub + '/' + ses \
            + '/' + dtype + '/' + filename

        # add the scan path + new path to the lists of old, new filenames
        self.old_filenames.append(filepath)
        self.new_filenames.append(new_path)

        # NOW NEED TO RENAME ASSOCIATIONS
        bids_file = self.layout.get_file(filepath)
        associations = bids_file.get_associations()
        for assoc in associations:
            assoc_path = assoc.path
            if Path(assoc_path).exists():
                # print("FILE: ", filepath)
                # print("ASSOC: ", assoc.path)
                # ensure assoc not an IntendedFor reference
                if '.nii' not in str(assoc_path):
                    self.old_filenames.append(assoc_path)
                    new_ext_path = img_to_new_ext(new_path,
                                                  ''.join(Path(assoc.path)
                                                          .suffixes))
                    self.new_filenames.append(new_ext_path)

        # MAKE SURE THESE AREN'T COVERED BY get_associations!!!
        if '/dwi/' in filepath:
            # add the bval and bvec if there
            if Path(img_to_new_ext(filepath, '.bval')).exists() \
                    and img_to_new_ext(filepath, '.bval') \
                    not in self.old_filenames:
                self.old_filenames.append(img_to_new_ext(filepath,
                                                         '.bval'))
                self.new_filenames.append(img_to_new_ext(new_path,
                                                         '.bval'))

            if Path(img_to_new_ext(filepath, '.bvec')).exists() \
                    and img_to_new_ext(filepath, '.bvec') \
                    not in self.old_filenames:
                self.old_filenames.append(img_to_new_ext(filepath,
                                                         '.bvec'))
                self.new_filenames.append(img_to_new_ext(new_path,
                                                         '.bvec'))

        # now rename _events and _physio files!
        old_suffix = parse_file_entities(filepath)['suffix']
        scan_end = '_' + old_suffix + old_ext

        if '_task-' in filepath:
            old_events = filepath.replace(scan_end, '_events.tsv')
            old_ejson = filepath.replace(scan_end, '_events.json')
            if Path(old_events).exists():
                self.old_filenames.append(old_events)
                new_scan_end = '_' + suffix + old_ext
                new_events = new_path.replace(new_scan_end, '_events.tsv')
                self.new_filenames.append(new_events)
            if Path(old_ejson).exists():
                self.old_filenames.append(old_ejson)
                new_scan_end = '_' + suffix + old_ext
                new_ejson = new_path.replace(new_scan_end, '_events.json')
                self.new_filenames.append(new_ejson)

        old_physio = filepath.replace(scan_end, '_physio.tsv.gz')
        if Path(old_physio).exists():
            self.old_filenames.append(old_physio)
            new_scan_end = '_' + suffix + old_ext
            new_physio = new_path.replace(new_scan_end, '_physio.tsv.gz')
            self.new_filenames.append(new_physio)

        # RENAME INTENDED FORS!
        ses_path = self.path + '/' + sub + '/' + ses
        for path in Path(ses_path).rglob("fmap/*.json"):
            self.IF_rename_paths.append(str(path))
            json_file = self.layout.get_file(str(path))
            data = json_file.get_dict()

            if 'IntendedFor' in data.keys():
                # check if IntendedFor field is a str or list
                if isinstance(data['IntendedFor'], str):
                    if data['IntendedFor'] == \
                            _get_intended_for_reference(filepath):
                        # replace old filename with new one (overwrite string)
                        data['IntendedFor'] = \
                                _get_intended_for_reference(new_path)

                        # update the json with the new data dictionary
                        _update_json(json_file.path, data)

                if isinstance(data['IntendedFor'], list):
                    for item in data['IntendedFor']:
                        if item in _get_intended_for_reference(filepath):

                            # remove old filename
                            data['IntendedFor'].remove(item)
                            # add new filename
                            data['IntendedFor'].append(
                                    _get_intended_for_reference(new_path))

                        # update the json with the new data dictionary
                        _update_json(json_file.path, data)

        # save IntendedFor purges so that you can datalad run the
        # remove association file commands on a clean dataset
        # if self.use_datalad:
        #     if not self.is_datalad_clean():
        #         self.datalad_save(message="Renamed IntendedFors")
        #         self.reset_bids_layout()
            # else:
            #     print("No IntendedFor References to Rename")

    def copy_exemplars(self, exemplars_dir, exemplars_csv, min_group_size,
                       raise_on_error=True):
        """Copies one subject from each Acquisition Group into a new directory
        for testing *preps, raises an error if the subjects are not unlocked,
        unlocks each subject before copying if --force_unlock is set.

        Parameters:
        -----------
            exemplars_dir: str
                path to the directory that will contain one subject
                from each Acqusition Gorup (*_AcqGrouping.csv)
                example path: /Users/Covitz/CSVs/CCNP_Acq_Groups/

            exemplars_csv: str
                path to the .csv file that lists one subject
                from each Acqusition Group (*_AcqGrouping.csv
                from the cubids-group output)
                example path: /Users/Covitz/CSVs/CCNP_Acq_Grouping.csv
        """
        # create the exemplar ds
        if self.use_datalad:
            subprocess.run(['datalad', '--log-level', 'error', 'create', '-c',
                            'text2git', exemplars_dir])

        # load the exemplars csv
        subs = pd.read_csv(exemplars_csv)

        # if min group size flag set, drop acq groups with less than min
        if int(min_group_size) > 1:
            for row in range(len(subs)):
                acq_group = subs.loc[row, 'AcqGroup']
                size = int(subs['AcqGroup'].value_counts()[acq_group])
                if size < int(min_group_size):
                    subs = subs.drop([row])

        # get one sub from each acq group
        unique = subs.drop_duplicates(subset=["AcqGroup"])

        # cast list to a set to drop duplicates, then convert back to list
        unique_subs = list(set(unique['subject'].tolist()))
        for subid in unique_subs:
            source = str(self.path) + '/' + subid
            dest = exemplars_dir + '/' + subid
            # Copy the content of source to destination
            copytree(source, dest)

        # Copy the dataset_description.json
        copyfile(str(self.path) + '/' + 'dataset_description.json',
                 exemplars_dir + '/' + 'dataset_description.json')

        s1 = "Copied one subject from each Acquisition Group "
        s2 = "into the Exemplar Dataset"
        msg = s1 + s2
        if self.use_datalad:
            subprocess.run(['datalad', 'save', '-d', exemplars_dir,
                            '-m', msg])

    def purge(self, scans_txt, raise_on_error=True):
        """Purges all associations of desired scans from a bids dataset.

        Parameters:
        -----------
            scans_txt: str
                path to the .txt file that lists the scans
                you want to be deleted from the dataset, along
                with thier associations.
                example path: /Users/Covitz/CCNP/scans_to_delete.txt
        """

        self.scans_txt = scans_txt

        scans = []
        with open(scans_txt, 'r') as fd:
            reader = csv.reader(fd)
            for row in reader:
                scans.append(str(row[0]))

        # check to ensure scans are all real files in the ds!

        self._purge_associations(scans)

    def _purge_associations(self, scans):

        # PURGE FMAP JSONS' INTENDED FOR REFERENCES

        # truncate all paths to intendedfor reference format
        # sub, ses, modality only (no self.path)
        if_scans = []
        for scan in scans:
            if_scans.append(_get_intended_for_reference(scan))

        for path in Path(self.path).rglob("sub-*/*/fmap/*.json"):

            json_file = self.layout.get_file(str(path))

            data = json_file.get_dict()

            # remove scan references in the IntendedFor

            if 'IntendedFor' in data.keys():
                # check if IntendedFor field value is a list or a string
                if isinstance(data['IntendedFor'], str):
                    if data['IntendedFor'] in if_scans:
                        data['IntendedFor'] = []
                        # update the json with the new data dictionary
                        _update_json(json_file.path, data)

                if isinstance(data['IntendedFor'], list):
                    for item in data['IntendedFor']:
                        if item in if_scans:
                            data['IntendedFor'].remove(item)

                            # update the json with the new data dictionary
                            _update_json(json_file.path, data)

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
                bids_file = self.layout.get_file(str(path))
                associations = bids_file.get_associations()

                for assoc in associations:
                    filepath = assoc.path

                    # ensure association is not an IntendedFor reference!
                    if '.nii' not in str(filepath):
                        to_remove.append(filepath)
                if '/dwi/' in str(path):
                    # add the bval and bvec if there
                    if Path(img_to_new_ext(str(path), '.bval')).exists():
                        to_remove.append(img_to_new_ext(str(path), '.bval'))
                    if Path(img_to_new_ext(str(path), '.bvec')).exists():
                        to_remove.append(img_to_new_ext(str(path), '.bvec'))
                if '/func/' in str(path):
                    # add tsvs
                    tsv = img_to_new_ext(str(path), '.tsv').replace(
                            '_bold', '_events')
                    if Path(tsv).exists():
                        to_remove.append(tsv)
                    # add tsv json (if exists)
                    if Path(tsv.replace('.tsv', '.json')).exists():
                        to_remove.append(tsv.replace('.tsv', '.json'))
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

            fileObject = open(path_prefix + "/" + "_full_cmd.sh", "w")
            fileObject.write("#!/bin/bash\n")
            fileObject.write(full_cmd)
            # Close the file
            fileObject.close()
            if self.scans_txt:
                cmt = "Purged scans listed in %s from dataset" % self.scans_txt
            else:
                cmt = "Purged Parameter Groups marked for removal"
            purge_file = path_prefix + "/" + '_full_cmd.sh'
            if self.use_datalad:
                self.datalad_handle.run(cmd=["bash", purge_file],
                                        message=cmt)
            else:
                subprocess.run(["bash", path_prefix + "/" + "_full_cmd.sh"],
                               stdout=subprocess.PIPE,
                               cwd=path_prefix)
            self.reset_bids_layout()
        else:
            print("Not running any association removals")

    def _cache_fieldmaps(self):
        """Searches all fieldmaps and creates a lookup for each file.

        Returns:
        -----------
            misfits : list
                A list of fmap filenames for whom CuBIDS has not detected
                an IntnededFor.
        """

        suffix = '(phase1|phasediff|epi|fieldmap)'
        fmap_files = self.layout.get(suffix=suffix, regex_search=True,
                                     extension=['.nii.gz', '.nii'])
        misfits = []
        files_to_fmaps = defaultdict(list)
        for fmap_file in tqdm(fmap_files):
            intentions = listify(fmap_file.get_metadata().get("IntendedFor"))
            subject_prefix = "sub-%s" % fmap_file.entities['subject']

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

    def get_param_groups_from_key_group(self, key_group):
        """Splits key groups into param groups based on json metadata.

        Parameters:
        -----------
            key_group : str
                Key group name.

        Returns:
        -----------
            ret : tuple of two DataFrames
                1. A data frame with one row per file where the ParamGroup
                column indicates the group to which each scan belongs.
                2. A data frame with param group summaries
        """
        if not self.fieldmaps_cached:
            raise Exception(
                "Fieldmaps must be cached to find parameter groups.")
        key_entities = _key_group_to_entities(key_group)
        key_entities["extension"] = ".nii[.gz]*"

        matching_files = self.layout.get(return_type="file", scope="self",
                                         regex_search=True, **key_entities)

        # ensure files who's entities contain key_entities but include other
        # entities do not also get added to matching_files
        to_include = []
        for filepath in matching_files:
            f_key_group = _file_to_key_group(filepath)

            if f_key_group == key_group:
                to_include.append(filepath)

        # get the modality associated with the key group
        modalities = ['/dwi/', '/anat/', '/func/', '/perf/', '/fmap/']
        modality = ''
        for mod in modalities:
            if mod in filepath:
                modality = mod.replace('/', '').replace('/', '')
        if modality == '':
            print("Unusual Modality Detected")
            modality = 'other'

        ret = _get_param_groups(
            to_include, self.layout, self.fieldmap_lookup, key_group,
            self.grouping_config, modality, self.keys_files)

        # add modality to the retun tuple
        l_ret = list(ret)
        l_ret.append(modality)
        tup_ret = tuple(l_ret)
        return tup_ret

    def get_param_groups_dataframes(self):
        '''Creates DataFrames of files x param groups and a summary'''

        key_groups = self.get_key_groups()
        labeled_files = []
        param_group_summaries = []
        for key_group in key_groups:
            labeled_file_params, param_summary, modality = \
                self.get_param_groups_from_key_group(key_group)
            if labeled_file_params is None:
                continue
            param_group_summaries.append(param_summary)
            labeled_files.append(labeled_file_params)

        big_df = _order_columns(pd.concat(labeled_files, ignore_index=True))
        summary = _order_columns(pd.concat(param_group_summaries,
                                 ignore_index=True))

        # create new col that strings key and param group together
        summary["KeyParamGroup"] = summary["KeyGroup"] \
            + '__' + summary["ParamGroup"].map(str)

        # move this column to the front of the dataframe
        key_param_col = summary.pop("KeyParamGroup")
        summary.insert(0, "KeyParamGroup", key_param_col)

        # do the same for the files df
        big_df["KeyParamGroup"] = big_df["KeyGroup"] \
            + '__' + big_df["ParamGroup"].map(str)

        # move this column to the front of the dataframe
        key_param_col = big_df.pop("KeyParamGroup")
        big_df.insert(0, "KeyParamGroup", key_param_col)

        summary.insert(0, "RenameKeyGroup", np.nan)
        summary.insert(0, "MergeInto", np.nan)
        summary.insert(0, "ManualCheck", np.nan)
        summary.insert(0, "Notes", np.nan)

        # NOW WANT TO AUTOMATE RENAME!
        # loop though imaging and derrived param keys

        sidecar = self.grouping_config.get('sidecar_params')
        sidecar = sidecar[modality]

        relational = self.grouping_config.get('relational_params')

        # list of columns names that we account for in suggested renaming
        summary['RenameKeyGroup'] = summary['RenameKeyGroup'].apply(str)

        rename_cols = []
        tolerance_cols = []
        for col in sidecar.keys():
            if 'suggest_variant_rename' in sidecar[col].keys():
                if sidecar[col]['suggest_variant_rename'] \
                        and col in summary.columns:
                    rename_cols.append(col)
                    if 'tolerance' in sidecar[col].keys():
                        tolerance_cols.append(col)

        # deal with Fmap!
        if 'FieldmapKey' in relational:
            if 'suggest_variant_rename' in relational['FieldmapKey'].keys():
                if relational['FieldmapKey']['suggest_variant_rename']:
                    # check if 'bool' or 'columns'
                    if relational['FieldmapKey']['display_mode'] == 'bool':
                        rename_cols.append("HasFieldmap")

        # deal with IntendedFor Key!
        if 'IntendedForKey' in relational:
            if 'suggest_variant_rename' in relational['IntendedForKey'].keys():
                if relational['FieldmapKey']['suggest_variant_rename']:
                    # check if 'bool' or 'columns'
                    if relational['IntendedForKey']['display_mode'] == 'bool':
                        rename_cols.append("UsedAsFieldmap")

        dom_dict = {}
        # loop through summary csv and create dom_dict
        for row in range(len(summary)):
            # if 'NumVolumes' in summary.columns \
            #         and str(summary.loc[row, "NumVolumes"]) == 'nan':
            #     summary.at[row, "NumVolumes"] = 1.0

            # if dominant group identified
            if str(summary.loc[row, 'ParamGroup']) == '1':
                val = {}
                # grab col, all vals send to dict
                key = summary.loc[row, "KeyGroup"]
                for col in rename_cols:
                    summary[col] = summary[col].apply(str)
                    val[col] = summary.loc[row, col]
                dom_dict[key] = val

        # now loop through again and ID variance
        for row in range(len(summary)):
            # check to see if renaming has already happened
            renamed = False
            entities = _key_group_to_entities(summary.loc[row, "KeyGroup"])
            if 'VARIANT' in summary.loc[row, 'KeyGroup']:
                renamed = True

            # if NumVolumes is nan, set to 1.0
            # if 'NumVolumes' in summary.columns \
            #         and str(summary.loc[row, "NumVolumes"]) == 'nan':
            #     summary.at[row, "NumVolumes"] = 1.0

            if summary.loc[row, "ParamGroup"] != 1 and not renamed:
                acq_str = 'VARIANT'
                # now we know we have a deviant param group
                # check if TR is same as param group 1
                key = summary.loc[row, "KeyGroup"]
                for col in rename_cols:
                    summary[col] = summary[col].apply(str)
                    if summary.loc[row, col] != dom_dict[key][col]:

                        if col == 'HasFieldmap':
                            if dom_dict[key][col] == 'True':
                                acq_str = acq_str + 'NoFmap'
                            else:
                                acq_str = acq_str + 'HasFmap'
                        elif col == 'UsedAsFieldmap':
                            if dom_dict[key][col] == 'True':
                                acq_str = acq_str + 'Unused'
                            else:
                                acq_str = acq_str + 'IsUsed'
                        else:
                            acq_str = acq_str + col

                if acq_str == 'VARIANT':
                    acq_str = acq_str + 'Other'

                if 'acquisition' in entities.keys():
                    acq = 'acquisition-%s' % entities['acquisition'] + acq_str

                    new_name = summary.loc[row, "KeyGroup"].replace(
                            'acquisition-%s' % entities['acquisition'], acq)
                else:
                    acq = 'acquisition-%s' % acq_str
                    new_name = acq + '_' + summary.loc[row, "KeyGroup"]

                summary.at[row, 'RenameKeyGroup'] = new_name

            # convert all "nan" to empty str
            # so they don't show up in the summary csv
            if summary.loc[row, "RenameKeyGroup"] == 'nan':
                summary.at[row, "RenameKeyGroup"] = ''

            for col in rename_cols:
                if summary.loc[row, col] == 'nan':
                    summary.at[row, col] = ''

        return (big_df, summary)

    def get_CSVs(self, path_prefix):
        """Creates the _summary and _files CSVs for the bids dataset.

        Parameters:
        -----------
            prefix_path: str
                prefix of the path to the directory where you want
                to save your CSVs
                example path: /Users/Covitz/PennLINC/RBC/CCNP/
        """

        self._cache_fieldmaps()

        big_df, summary = self.get_param_groups_dataframes()

        summary = summary.sort_values(by=['Modality', 'KeyGroupCount'],
                                      ascending=[True, False])
        big_df = big_df.sort_values(by=['Modality', 'KeyGroupCount'],
                                    ascending=[True, False])

        big_df.to_csv(path_prefix + "_files.csv", index=False)
        summary.to_csv(path_prefix + "_summary.csv", index=False)

        # Calculate the acq groups
        group_by_acquisition_sets(path_prefix + "_files.csv", path_prefix,
                                  self.acq_group_level)

        print("Detected " + str(len(summary)) + " Parameter Groups.")

    def get_key_groups(self):
        '''Identifies the key groups for the bids dataset'''

        # reset self.keys_files
        self.keys_files = {}

        key_groups = set()

        for path in Path(self.path).rglob("sub-*/**/*.*"):
            # ignore all dot directories
            if '/.' in str(path):
                continue

            if str(path).endswith(".nii") or str(path).endswith(".nii.gz"):
                key_groups.update((_file_to_key_group(path),))

                # Fill the dictionary of key group, list of filenames pairrs
                ret = _file_to_key_group(path)

                if ret not in self.keys_files.keys():

                    self.keys_files[ret] = []

                self.keys_files[ret].append(path)

        return sorted(key_groups)

    def change_metadata(self, filters, pattern, metadata):

        files_to_change = self.layout.get(return_type='object', **filters)

        for bidsfile in files_to_change:
            # get the sidecar file
            bidsjson_file = bidsfile.get_associations()

            if not bidsjson_file:
                print("NO JSON FILES FOUND IN ASSOCIATIONS")
                continue

            json_file = [x for x in bidsjson_file if 'json' in x.filename]
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
        ''' Returns all metadata fields in a bids directory'''

        found_fields = set()
        for json_file in Path(self.path).rglob("*.json"):
            if '.git' not in str(json_file):
                with open(json_file, "r") as jsonr:
                    metadata = json.load(jsonr)
                found_fields.update(metadata.keys())
        return sorted(found_fields)

    def remove_metadata_fields(self, fields_to_remove):
        '''Removes specific fields from all metadata files.'''

        remove_fields = set(fields_to_remove)
        if not remove_fields:
            return
        for json_file in tqdm(Path(self.path).rglob("*.json")):
            # Check for offending keys in the json file
            if '.git' not in str(json_file):
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
        return self.keys_files

    def get_fieldmap_lookup(self):
        return self.fieldmap_lookup

    def get_layout(self):
        return self.layout


def _validateJSON(json_file):
    # TODO: implement this or delete ???
    return True


def _update_json(json_file, metadata):

    if _validateJSON(metadata):
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
    else:
        print("INVALID JSON DATA")


def _key_group_to_entities(key_group):
    '''Splits a key_group name into a pybids dictionary of entities.'''

    return dict([group.split("-") for group in key_group.split("_")])


def _entities_to_key_group(entities):
    '''Converts a pybids entities dictionary into a key group name.'''

    group_keys = sorted(entities.keys() - NON_KEY_ENTITIES)
    return "_".join(
        ["{}-{}".format(key, entities[key]) for key in group_keys])


def _file_to_key_group(filename):
    '''Identifies and returns the key group of a bids valid filename.'''

    entities = parse_file_entities(str(filename))
    return _entities_to_key_group(entities)


def _get_intended_for_reference(scan):
    return '/'.join(Path(scan).parts[-3:])


def _get_param_groups(files, layout, fieldmap_lookup, key_group_name,
                      grouping_config, modality, keys_files):

    """Finds a list of *parameter groups* from a list of files.

    For each file in `files`, find critical parameters for metadata. Then find
    unique sets of these critical parameters.

    Parameters:
    -----------
    files : list
        List of file names

    layout : bids.BIDSLayout
        PyBIDS BIDSLayout object where `files` come from

    fieldmap_lookup : defaultdict
        mapping of filename strings relative to the bids root
        (e.g. "sub-X/ses-Y/func/sub-X_ses-Y_task-rest_bold.nii.gz")

    grouping_config : dict
        configuration for defining parameter groups

    Returns:
    --------
    labeled_files : pd.DataFrame
        A data frame with one row per file where the ParamGroup column
        indicates which group each scan is a part of.

    param_groups_with_counts : pd.DataFrame
        A data frame with param group summaries

    """

    if not files:
        print("WARNING: no files for", key_group_name)
        return None, None

    # Split the config into separate parts
    imaging_params = grouping_config.get('sidecar_params', {})
    imaging_params = imaging_params[modality]

    relational_params = grouping_config.get('relational_params', {})

    derived_params = grouping_config.get('derived_params')
    derived_params = derived_params[modality]

    imaging_params.update(derived_params)

    dfs = []
    # path needs to be relative to the root with no leading prefix
    for path in files:
        metadata = layout.get_metadata(path)
        intentions = metadata.get("IntendedFor", [])
        slice_times = metadata.get("SliceTiming", [])

        wanted_keys = metadata.keys() & imaging_params
        example_data = {key: metadata[key] for key in wanted_keys}
        example_data["KeyGroup"] = key_group_name

        # Get the fieldmaps out and add their types
        if 'FieldmapKey' in relational_params:
            fieldmap_types = sorted([_file_to_key_group(fmap.path) for
                                    fmap in fieldmap_lookup[path]])

            # check if config says columns or bool
            if relational_params['FieldmapKey']['display_mode'] == \
                    'bool':
                if len(fieldmap_types) > 0:
                    example_data['HasFieldmap'] = True
                else:
                    example_data['HasFieldmap'] = False
            else:
                for fmap_num, fmap_type in enumerate(fieldmap_types):
                    example_data['FieldmapKey%02d' % fmap_num] = fmap_type

        # Add the number of slice times specified
        if "NSliceTimes" in derived_params:
            example_data["NSliceTimes"] = len(slice_times)

        example_data["FilePath"] = path

        # If it's a fieldmap, see what key group it's intended to correct
        if "IntendedForKey" in relational_params:
            intended_key_groups = sorted([_file_to_key_group(intention) for
                                          intention in intentions])

            # check if config says columns or bool
            if relational_params['IntendedForKey']['display_mode'] == \
                    'bool':
                if len(intended_key_groups) > 0:
                    example_data["UsedAsFieldmap"] = True
                else:
                    example_data["UsedAsFieldmap"] = False
            else:
                for intention_num, intention_key_group in \
                        enumerate(intended_key_groups):
                    example_data[
                        "IntendedForKey%02d" % intention_num] = \
                                intention_key_group

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
        if "Cluster_" + col not in list(df.columns) and col != 'FilePath':
            check_cols.append(col)

    # Find the unique ParamGroups and assign ID numbers in "ParamGroup"
    deduped = df.drop('FilePath', axis=1).drop_duplicates(subset=check_cols,
                                                          ignore_index=True)

    deduped["ParamGroup"] = np.arange(deduped.shape[0]) + 1

    # add the modality as a column
    deduped["Modality"] = modality

    # add key group count column (will delete later)
    deduped["KeyGroupCount"] = len(keys_files[key_group_name])

    # Add the ParamGroup to the whole list of files
    labeled_files = pd.merge(df, deduped, on=check_cols)

    value_counts = labeled_files.ParamGroup.value_counts()

    param_group_counts = pd.DataFrame(
        {"Counts": value_counts.to_numpy(),
         "ParamGroup": value_counts.index.to_numpy()})

    param_groups_with_counts = pd.merge(
        deduped, param_group_counts, on=["ParamGroup"])

    # Sort by counts and relabel the param groups
    param_groups_with_counts.sort_values(by=['Counts'], inplace=True,
                                         ascending=False)
    param_groups_with_counts["ParamGroup"] = np.arange(
        param_groups_with_counts.shape[0]) + 1

    # Send the new, ordered param group ids to the files list
    ordered_labeled_files = pd.merge(df, param_groups_with_counts,
                                     on=check_cols, suffixes=('_x', ''))

    # sort ordered_labeled_files by param group
    ordered_labeled_files.sort_values(by=['Counts'], inplace=True,
                                      ascending=False)

    # now get rid of cluster cols from deduped and df
    for col in list(ordered_labeled_files.columns):
        if col.startswith('Cluster_'):
            ordered_labeled_files = ordered_labeled_files.drop(col, axis=1)
            param_groups_with_counts = param_groups_with_counts.drop(col,
                                                                     axis=1)
        if col.endswith('_x'):
            ordered_labeled_files = ordered_labeled_files.drop(col, axis=1)

    return ordered_labeled_files, param_groups_with_counts


def round_params(param_group_df, config, modality):
    to_format = config['sidecar_params'][modality]
    to_format.update(config['derived_params'][modality])

    for column_name, column_fmt in to_format.items():
        if column_name not in param_group_df:
            continue
        if 'precision' in column_fmt:
            param_group_df[column_name] = \
                param_group_df[column_name].round(column_fmt['precision'])

    return param_group_df


def format_params(param_group_df, config, modality):
    '''Run AgglomerativeClustering on param groups, add columns to dataframe'''

    to_format = config['sidecar_params'][modality]
    to_format.update(config['derived_params'][modality])

    for column_name, column_fmt in to_format.items():
        if column_name not in param_group_df:
            continue
        if 'tolerance' in column_fmt and len(param_group_df) > 1:
            array = param_group_df[column_name].to_numpy().reshape(-1, 1)

            for i in range(len(array)):
                if np.isnan(array[i, 0]):
                    array[i, 0] = -999

            tolerance = to_format[column_name]['tolerance']
            clustering = AgglomerativeClustering(n_clusters=None,
                                                 distance_threshold=tolerance,
                                                 linkage='complete').fit(array)
            for i in range(len(array)):
                if array[i, 0] == -999:
                    array[i, 0] = np.nan

            # now add clustering_labels as a column
            param_group_df['Cluster_' + column_name] = clustering.labels_

    return param_group_df


def _order_columns(df):
    '''Organizes columns of the summary and files DataFrames so that
    KeyGroup and ParamGroup are the first two columns, FilePath is
    the last, and the others are sorted alphabetically.'''

    cols = set(df.columns.to_list())
    non_id_cols = cols - ID_VARS
    new_columns = ["KeyGroup", "ParamGroup"] + sorted(non_id_cols)
    if "FilePath" in cols:
        new_columns.append("FilePath")

    df = df[new_columns]

    return df[new_columns]


def img_to_new_ext(img_path, new_ext):
    # handle .tsv edge case
    if new_ext == '.tsv':
        # take out suffix
        return img_path.rpartition('_')[0] + '_events' + new_ext
    if new_ext == '.tsv.gz':
        return img_path.rpartition('_')[0] + '_physio' + new_ext
    else:
        return img_path.replace(".nii.gz", "").replace(".nii", "") + new_ext


def get_key_name(path, key):
    # given a filepath and BIDS key name, return value
    parts = Path(path).parts
    for part in parts:
        if part.startswith(key + '-'):
            return part
