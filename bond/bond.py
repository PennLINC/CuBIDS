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
from tqdm import tqdm

bids.config.set_option('extension_initial_dot', True)

ID_VARS = set(["KeyGroup", "ParamGroup", "FilePath"])
NON_KEY_ENTITIES = set(["subject", "session", "extension"])
# Multi-dimensional keys SliceTiming
IMAGING_PARAMS = set([
    "ParallelReductionFactorInPlane", "ParallelAcquisitionTechnique",
    "ParallelAcquisitionTechnique", "PartialFourier", "PhaseEncodingDirection",
    "EffectiveEchoSpacing", "TotalReadoutTime", "EchoTime",
    "SliceEncodingDirection", "DwellTime", "FlipAngle",
    "MultibandAccelerationFactor", "RepetitionTime",
    "VolumeTiming", "NumberOfVolumesDiscardedByScanner",
    "NumberOfVolumesDiscardedByUser"])


class BOnD(object):

    def __init__(self, data_root, use_datalad=False):

        self.path = data_root
        self.layout = bids.BIDSLayout(self.path, validate=False)
        # dictionary of KEY: keys group, VALUE: list of files
        self.keys_files = {}
        self.fieldmaps_cached = False
        self.datalad_ready = False
        self.datalad_handle = None
        self.old_filenames = []  # files whose key groups changed
        self.new_filenames = []  # new filenames for files to change

        # Initialize datalad if
        if use_datalad:
            self.init_datalad()

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

        uses git reset --hard
        """
        if not self.is_datalad_clean():
            raise Exception("Untracked changes present. "
                            "Run clear_untracked_changes first")
        reset_proc = subprocess.run(
            ["git", "reset", "--hard", "HEAD~1"], cwd=self.path)
        reset_proc.check_returncode()

    def merge_params(self, merge_df, files_df):
        key_param_merge = {}
        for i in range(len(merge_df)):
            key_group = merge_df.iloc[i]['KeyGroup']
            param_group = merge_df.iloc[i]['ParamGroup']
            merge_into = merge_df.iloc[i]['MergeInto']
            key_param_merge[(key_group, param_group)] = merge_into
        pairs_to_change = list(key_param_merge.keys())

        # locate files that need to change param groups/be deleted
        for row in range(len(files_df)):

            key = files_df.iloc[row]['KeyGroup']
            param = files_df.iloc[row]['ParamGroup']

            if (key, param) in pairs_to_change:
                if key_param_merge[(key, param)] == 0:
                    file_path = files_df.iloc[row]['FilePath']
                    file_to_rem = Path(file_path)
                    file_to_rem.unlink()
                # else:
                    # need to merge the param groups
                    # NEED TO COPY THE METADATA FROM
                    # "MergeInto" --> "ParamGroup"
                    # self.change_metadata

    def change_key_groups(self, og_prefix, new_prefix):
        # reset lists of old and new filenames
        self.old_filenames = []
        self.new_filenames = []

        files_df = pd.read_csv(og_prefix + '_files.csv')
        summary_df = pd.read_csv(og_prefix + '_summary.csv')

        # TODO: IMPLEMENT merge_params (above)
        # merge_df = summary_df[summary_df.MergeInto.notnull()]
        # self.merge_params(merge_df, files_df)

        change_keys_df = summary_df[summary_df.RenameKeyGroup.notnull()]

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

                key_group = files_df.iloc[row]['KeyGroup']
                param_group = files_df.iloc[row]['ParamGroup']

                if (key_group, param_group) in pairs_to_change:

                    file_path = files_df.iloc[row]['FilePath']
                    orig_key = files_df.iloc[row]['KeyGroup']
                    param_num = files_df.iloc[row]['ParamGroup']

                    new_key = key_groups[(orig_key, param_num)]

                    new_entities = _key_group_to_entities(new_key)

                    # change each filename according to new key group
                    self.change_filename(file_path, new_entities)

        with open(new_prefix + '_change_files.sh', 'w') \
                as exe_script:
            for old, new in zip(self.old_filenames, self.new_filenames):
                exe_script.write("git mv %s %s\n" % (old, new))

        my_proc = subprocess.run(
            ['bash', new_prefix + '_change_files.sh'])

        # with open(new_prefix + '_undo_files.sh', 'w') \
        #         as exe_script:
        #     for new, old in zip(self.new_filenames, self.old_filenames):
        #         exe_script.write("mv %s %s\n" % (new, old))

        dlapi.save()
        dlapi.run(cmd=new_prefix + '_change_files.sh',
                                message='change filenames',
                                inputs=self.old_filenames,
                                outputs=self.new_filenames)


        self.layout = bids.BIDSLayout(self.path, validate=False)
        self.get_CSVs(new_prefix)

        return my_proc

    def change_filename(self, filepath, entities):

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
        # front_stem is the string of subject/session paris
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

        # now also rename json file
        bidsfile = self.layout.get_file(filepath, scope='all')

        bidsjson_file = bidsfile.get_associations()
        if bidsjson_file:
            json_file = [x for x in bidsjson_file if 'json' in x.filename]
        else:
            print("NO JSON FILES FOUND IN ASSOCIATIONS")
        if len(json_file) == 1:
            json_file = json_file[0]
            new_json_path = new_path_front + "_" + new_filename + ".json"
            self.old_filenames.append(json_file.path)
            self.new_filenames.append(new_json_path)
        else:
            print("FOUND IRREGULAR NUMBER OF JSONS")

    def fieldmaps_ok(self):
        pass

    def _cache_fieldmaps(self):
        """Searches all fieldmaps and creates a lookup for each file.
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
        if not self.fieldmaps_cached:
            raise Exception(
                "Fieldmaps must be cached to find parameter groups.")
        key_entities = _key_group_to_entities(key_group)
        key_entities["extension"] = ".nii[.gz]*"
        matching_files = self.layout.get(return_type="file", scope="self",
                                         regex_search=True, **key_entities)
        return _get_param_groups(
            matching_files, self.layout, self.fieldmap_lookup, key_group)

    def get_param_groups_dataframes(self):
        """Creates DataFrames of files x param groups and a summary
        """
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

    def get_CSVs(self, path_prefix):
        """
        Parameters:
        -----------
            prefix_path: str
                prefix of the path to the directory where you want
                to save your CSVs
                example path: /Users/Covitz/PennLINC/RBC/CCNP/
        Returns
        -----------
            - None
        """

        self._cache_fieldmaps()

        big_df, summary = self.get_param_groups_dataframes()

        big_df.to_csv(path_prefix + "_files.csv", index=False)
        summary.to_csv(path_prefix + "_summary.csv", index=False)

    def get_file_params(self, key_group):
        key_entities = _key_group_to_entities(key_group)
        key_entities["extension"] = ".nii[.gz]*"
        matching_files = self.layout.get(return_type="file", scope="self",
                                         regex_search=True, **key_entities)
        return _get_file_params(matching_files, self.layout)

    def get_key_groups(self):

        key_groups = set()

        for path in Path(self.path).rglob("*.*"):

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

    def apply_csv_changes(self, previous_output_prefix, new_output_prefix):
        pass

    def get_all_metadata_fields(self):
        found_fields = set()
        for json_file in Path(self.path).rglob("*.json"):
            with open(json_file, "r") as jsonr:
                metadata = json.load(jsonr)
            found_fields.update(metadata.keys())
        return sorted(found_fields)

    def remove_metadata_fields(self, fields_to_remove):
        """Removes specific fields from all metadata files."""
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


def _update_json(json_file, metadata):

    if _validateJSON(metadata):
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
    else:
        print("INVALID JSON DATA")


def _validateJSON(json_data):

    # TODO
    return True


def _key_group_to_entities(key_group):
    return dict([group.split("-") for group in key_group.split("_")])


def _entities_to_key_group(entities):
    group_keys = sorted(entities.keys() - NON_KEY_ENTITIES)
    return "_".join(
        ["{}-{}".format(key, entities[key]) for key in group_keys])


def _file_to_key_group(filename):
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

    return labeled_files, param_groups_with_counts


def _order_columns(df):
    cols = set(df.columns.to_list())
    non_id_cols = cols - ID_VARS
    new_columns = ["KeyGroup", "ParamGroup"] + sorted(non_id_cols)
    if "FilePath" in cols:
        new_columns.append("FilePath")
    return df[new_columns]


def _get_file_params(files, layout):
    """Finds a list of *parameter groups* from a list of files.
    Parameters:
    -----------
    files : list
        List of file names
    Returns:
    --------
    dict_files_params : dictionary
        A dictionary of KEYS: filenames, VALUES: their param dictionaries
    For each file in `files`, find critical parameters for metadata. Then find
    unique sets of these critical parameters.
    """
    dict_files_params = {}

    for path in files:
        metadata = layout.get_metadata(path)
        wanted_keys = metadata.keys() & IMAGING_PARAMS
        example_data = {key: metadata[key] for key in wanted_keys}
        # Expand slice timing to multiple columns
        SliceTime = example_data.get('SliceTiming')
        if SliceTime:
            # round each slice time to one place after the decimal
            for i in range(len(SliceTime)):
                SliceTime[i] = round(SliceTime[i], 1)
            example_data.update(
                {"SliceTime%03d" % SliceNum: time for
                 SliceNum, time in enumerate(SliceTime)})
            del example_data['SliceTiming']

        dict_files_params[path] = example_data

    return dict_files_params
