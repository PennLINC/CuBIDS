"""Main module."""
from collections import defaultdict
import bids
import json
from pathlib import Path
from bids.layout import parse_file_entities
from bids.utils import listify
import pandas as pd
import pdb
from tqdm import tqdm

bids.config.set_option('extension_initial_dot', True)

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

    def __init__(self, data_root):

        self.path = data_root
        self.layout = bids.BIDSLayout(self.path, validate = False)
        self.keys_files = {} # dictionary of KEYS: keys groups, VALUES: list of files
        self.fieldmaps_cached = False

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

        # return a list of all filenames where fmap file detected, no intended for found
        return misfits

    def rename_files(self, filters, pattern, replacement):
        """
        Parameters:
        -----------
            - filters : dictionary
                pybids entities dictionary to find files to rename
            - pattern : string
                the substring of the file we would like to replace
            - replacement : string
                the substring that will replace "pattern"
        Returns
        -----------
            - None
        >>> my_bond.rename_files({"PhaseEncodingDirection": 'j-',
        ...                       "EchoTime": 0.005},
        ...                       "acq-123", "acq-12345_dir-PA"
        ...                     )
        """
        files_to_change = self.layout.get(return_type='filename', **filters)
        for bidsfile in files_to_change:
            path = Path(bidsfile.path)
            old_name = path.stem
            old_ext = path.suffix
            directory = path.parent
            new_name = old_name.replace(pattern, replacement) + old_ext
            path.rename(Path(directory, new_name))

    def get_param_groups_from_key_group(self, key_group):
        if not self.fieldmaps_cached:
            raise Exception("Fieldmaps must be cached to find parameter groups.")
        key_entities = _key_group_to_entities(key_group)
        key_entities["extension"] = ".nii[.gz]*"
        matching_files = self.layout.get(return_type="file", scope="self",
                                         regex_search=True, **key_entities)
        return _get_param_groups(matching_files, self.layout, self.fieldmap_lookup, key_group)

    def get_param_groups_dataframe(self):
        key_groups = self.get_key_groups()
        parameter_groups = []
        for key_group in key_groups:
            parameter_groups.append(
                self.get_param_groups_from_key_group(key_group))
        return pd.concat(parameter_groups)


    def get_file_params(self, key_group):
        key_entities = _key_group_to_entities(key_group)
        key_entities["extension"] = ".nii[.gz]*"
        matching_files = self.layout.get(return_type="file", scope="self",
                                         regex_search=True, **key_entities)
        return _get_file_params(matching_files, self.layout)

    def get_key_groups(self):

        key_groups = set()

        for path in Path(self.path).rglob("*.*"):

            if path.suffix == ".json" and path.stem != "dataset_description":
                key_groups.update((_file_to_key_group(path),))

                # Fill the dictionary of key group, list of filenames pairrs
                ret = _file_to_key_group(path)

                if ret not in self.keys_files.keys():

                    self.keys_files[ret] = []

                self.keys_files[ret].append(path)

        return sorted(key_groups)

    def get_filenames(self, key_group):
        # NEW - WORKS
        return self.keys_files[key_group]

    def change_filenames(self, key_group, split_params, pattern, replacement):
        # for each filename in the key group, check if it's params match split_params
        # if they match, perform the replacement acc to pattern/replacement

        # list of file paths that incorporate the replacement
        new_paths = []

        # obtain the dictionary of files, param groups
        dict_files_params = self.get_file_params(key_group)

        for filename in dict_files_params.keys():

            if dict_files_params[filename] == split_params:
                # Perform the replacement if the param dictionaries match

                path = Path(filename)
                old_name = path.stem
                old_ext = path.suffix
                directory = path.parent
                new_name = old_name.replace(pattern, replacement) + old_ext
                path.rename(Path(directory, new_name))
                new_paths.append(path)

        return new_paths

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


def _update_json(json_file, metadata):

    if _validateJSON(metadata):
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
    else:

        print("INVALID JSON DATA")
    #metadata.update


def _validateJSON(json_data):

    # TODO
    return True
    '''try:
        json.load(json_data)
    except ValueError as err:
        return False
    return True
    '''


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
    parameter_groups_df : pd.DataFrame
        A data frame with one row per file where the ParamGroup column indicates which
        group each scan is a part of.

    """
    
    dfs = []
    # path needs to be relative to the root with no leading prefix
    for path in files:
        metadata = layout.get_metadata(path)
        slice_times = metadata.get("SliceTiming", [])
        wanted_keys = metadata.keys() & IMAGING_PARAMS
        example_data = {key: metadata[key] for key in wanted_keys}
        example_data["key_group"] = key_group_name

        # Get the fieldmaps out and add their types
        fieldmap_types = sorted([fmap.entities['fmap'] for fmap in fieldmap_lookup[path]])
        for fmap_num, fmap_type in enumerate(fieldmap_types):
            example_data['FieldmapType%02d' % fmap_num] = fmap_type    

        # Add the number of slice times specified
        example_data["NSliceTimes"] = len(slice_times)
        example_data["FilePath"] = path

        dfs.append(example_data)

    # Assign each file to a ParamGroup
    df = pd.DataFrame(dfs)
    df['ParamGroup'] = df.groupby(df.columns.tolist(), sort=False).ngroup() + 1

    return df


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
