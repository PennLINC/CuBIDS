"""Main module."""
from collections import defaultdict
import subprocess
import bids
import json
from pathlib import Path
from bids.layout import parse_file_entities
from bids.utils import listify
import numpy as np
import pandas as pd
import datalad.api as dlapi
# import ipdb
from tqdm import tqdm
from .constants import ID_VARS, NON_KEY_ENTITIES, IMAGING_PARAMS
from .metadata_merge import (
    check_merging_operations, group_by_acquisition_sets)
bids.config.set_option('extension_initial_dot', True)


class BOnD(object):

    def __init__(self, data_root, use_datalad=False):

        self.path = data_root
        self._layout = None
        self.keys_files = {}
        self.fieldmaps_cached = False
        self.datalad_ready = False
        self.datalad_handle = None
        self.old_filenames = []  # files whose key groups changed
        self.new_filenames = []  # new filenames for files to change

        # Initialize datalad if
        if use_datalad:
            self.init_datalad()

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
        statuses = self.datalad_handle.save(message=message or "BOnD Save")
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
        print("Performing %d merges" % len(merge_commands))

        # Get the delete commands
        delete_commands = []
        for rm_id in deletions:
            files_to_rm = files_df.loc[
                (files_df[["ParamGroup", "KeyGroup"]] == rm_id).all(1)]
            for rm_me in files_to_rm.FilePath:
                if Path(rm_me).exists():
                    delete_commands.append("rm " + rm_me)
        print("Deleting %d files" % len(delete_commands))

        # Now do the file renaming
        change_keys_df = summary_df[summary_df.RenameKeyGroup.notnull()]
        move_ops = []
        # return if nothing to change
        if len(change_keys_df) > 0:

            # dictionary
            # KEYS = (orig key group, param num)
            # VALUES = new key group
            key_groups = {}

            for i in range(len(change_keys_df)):
                new_key = change_keys_df.iloc[i]['RenameKeyGroup']
                old_key = change_keys_df.iloc[i]['KeyGroup']
                param_group = change_keys_df.iloc[i]['ParamGroup']

                # add to dictionary
                key_groups[(old_key, param_group)] = new_key

            # orig key/param tuples that will have new key group
            pairs_to_change = list(key_groups.keys())

            for row in range(len(files_df)):
                file_path = files_df.iloc[row]['FilePath']
                if Path(file_path).exists():

                    key_group = files_df.iloc[row]['KeyGroup']
                    param_group = files_df.iloc[row]['ParamGroup']

                    if (key_group, param_group) in pairs_to_change:

                        orig_key = files_df.iloc[row]['KeyGroup']
                        param_num = files_df.iloc[row]['ParamGroup']

                        new_key = key_groups[(orig_key, param_num)]

                        new_entities = _key_group_to_entities(new_key)

                        # change each filename according to new key group
                        self.change_filename(file_path, new_entities)

            # create string of mv command ; mv command for dlapi.run
            for from_file, to_file in zip(self.old_filenames,
                                          self.new_filenames):
                if Path(from_file).exists():
                    move_ops.append('mv %s %s' % (from_file, to_file))
        print("Performing %d renamings" % len(move_ops))

        full_cmd = "; ".join(merge_commands + delete_commands + move_ops)
        if full_cmd:
            print("RUNNING:\n\n", full_cmd)
            self.datalad_handle.run(full_cmd)
            self.reset_bids_layout()
        else:
            print("Not running any commands")

        # NOW rename all references to renamed files in IntendedFors
        self.rename_IntendedFor()

        self.get_CSVs(new_prefix)

    def rename_IntendedFor(self):
        return

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
        path = Path(filepath)
        exts = path.suffixes
        old_ext = ""
        for ext in exts:
            old_ext += ext

        # check if need to change the modality (one directory level up)
        l_keys = list(entities.keys())

        if "datatype" in l_keys:
            # create path string a and add new modality
            modality = entities['datatype']
            l_keys.remove('datatype')
        else:
            large = str(path.parent)
            small = str(path.parents[1]) + '/'
            modality = large.replace(small, '')

        # detect the subject/session string and keep it together
        # front_stem is the string of subject/session pairs
        # these two entities don't change with the key group
        front_stem = ""
        cntr = 0
        for char in path.stem:
            if char == "_" and cntr == 1:
                cntr = 2
                break
            if char == "_" and cntr == 0:
                cntr += 1
            if cntr != 2:
                front_stem = front_stem + char

        parent = str(path.parents[1])
        new_path_front = parent + '/' + modality + '/' + front_stem

        # remove fmap (not part of filename string)
        if "fmap" in l_keys:
            l_keys.remove("fmap")

        # now need to create the key/value string from the keys!
        new_filename = "_".join(["{}-{}".format(key, entities[key])
                                for key in l_keys])

        # shorten "acquisition" in the filename
        new_filename = new_filename.replace("acquisition", "acq")

        # shorten "reconstruction" in the filename
        new_filename = new_filename.replace("reconstruction", "rec")

        # REMOVE "suffix-"
        new_filename = new_filename.replace("suffix-", "")

        new_path = new_path_front + "_" + new_filename + old_ext

        self.old_filenames.append(str(path))
        self.new_filenames.append(new_path)

        # now also rename files with same stem diff extension
        extensions = ['.json', '.bval', '.bvec', '.tsv', '.tsv.gz']
        for ext in extensions:
            ext_file = img_to_new_ext(filepath, ext)

            # check if ext_file exists in the bids dir
            if Path(ext_file).exists():
                # need to remove suffix for .tsv and .tsv.gz files
                if ext == '.tsv':
                    new_filename = new_filename.rpartition('_')[0] + '_events'
                if ext == '.tsv.gz':
                    new_filename = new_filename.rpartition('_')[0] + '_physio'
                new_ext_path = new_path_front + "_" + new_filename + ext
                self.old_filenames.append(ext_file)
                self.new_filenames.append(new_ext_path)

    def _cache_fieldmaps(self):
        """Searches all fieldmaps and creates a lookup for each file.

        Returns:
        -----------
            misfits : list
                A list of fmap filenames for whom BOnD has not detected
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
        ret = _get_param_groups(
            matching_files, self.layout, self.fieldmap_lookup, key_group)

        return ret

    def get_param_groups_dataframes(self):
        '''Creates DataFrames of files x param groups and a summary'''

        key_groups = self.get_key_groups()
        labeled_files = []
        param_group_summaries = []
        for key_group in key_groups:
            labeled_file_params, param_summary = \
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

        return (big_df, summary)

    def get_CSVs(self, path_prefix, split_by_session=True):
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

        big_df.to_csv(path_prefix + "_files.csv", index=False)
        summary.to_csv(path_prefix + "_summary.csv", index=False)

        # Calculate the acq groups
        group_by_acquisition_sets(path_prefix + "_files.csv", path_prefix,
                                  split_session=split_by_session)

    def get_key_groups(self):
        '''Identifies the key groups for the bids dataset'''

        key_groups = set()

        for path in Path(self.path).rglob("sub-*/**/*.*"):

            if str(path).endswith(".nii") or str(path).endswith(".nii.gz"):
                key_groups.update((_file_to_key_group(path),))

                # Fill the dictionary of key group, list of filenames pairrs
                ret = _file_to_key_group(path)

                if ret not in self.keys_files.keys():

                    self.keys_files[ret] = []

                self.keys_files[ret].append(path)

        return sorted(key_groups)

    def change_metadata(self, filters, pattern, metadata):

        # TODO: clean prints and add warnings

        files_to_change = self.layout.get(return_type='object', **filters)
        if not files_to_change:
            print('NO FILES FOUND')
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


def _get_param_groups(files, layout, fieldmap_lookup, key_group_name):
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

    dfs = []
    # path needs to be relative to the root with no leading prefix
    for path in files:
        metadata = layout.get_metadata(path)
        intentions = metadata.get("IntendedFor", [])
        slice_times = metadata.get("SliceTiming", [])
        wanted_keys = metadata.keys() & IMAGING_PARAMS
        example_data = {key: metadata[key] for key in wanted_keys}
        example_data["KeyGroup"] = key_group_name

        # Get the fieldmaps out and add their types
        fieldmap_types = sorted([_file_to_key_group(fmap.path) for
                                 fmap in fieldmap_lookup[path]])
        for fmap_num, fmap_type in enumerate(fieldmap_types):
            example_data['FieldmapKey%02d' % fmap_num] = fmap_type

        # Add the number of slice times specified
        example_data["NSliceTimes"] = len(slice_times)
        example_data["FilePath"] = path

        # If it's a fieldmap, see what key group it's intended to correct
        intended_key_groups = sorted([_file_to_key_group(intention) for
                                      intention in intentions])
        for intention_num, intention_key_group in \
                enumerate(intended_key_groups):
            example_data[
                "IntendedForKey%02d" % intention_num] = intention_key_group

        dfs.append(example_data)

    # Assign each file to a ParamGroup
    df = pd.DataFrame(dfs)
    param_group_cols = list(set(df.columns.to_list()) - set(["FilePath"]))

    # Find the unique ParamGroups and assign ID numbers in "ParamGroup"
    deduped = df.drop('FilePath', axis=1).drop_duplicates(ignore_index=True)
    deduped["ParamGroup"] = np.arange(deduped.shape[0]) + 1

    # Add the ParamGroup to the whole list of files
    labeled_files = pd.merge(df, deduped, on=param_group_cols)
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
                                     on=param_group_cols)

    # sort ordered_labeled_files by param group
    ordered_labeled_files.sort_values(by=['Counts'], inplace=True,
                                      ascending=False)

    return ordered_labeled_files, param_groups_with_counts


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
