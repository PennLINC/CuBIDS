"""Main module."""
import bids
import json
from pathlib import Path
from bids.layout import parse_file_entities
from bids.layout import BIDSFile

bids.config.set_option('extension_initial_dot', True)

NON_KEY_ENTITIES = set(["subject", "session", "extension"])
# Multi-dimensional keys SliceTiming
IMAGING_PARAMS = set(["ParallelReductionFactorInPlane", "ParallelAcquisitionTechnique",
    "ParallelAcquisitionTechnique", "PartialFourier", "PhaseEncodingDirection",
    "EffectiveEchoSpacing", "TotalReadoutTime", "EchoTime", "SliceEncodingDirection",
    "DwellTime", "FlipAngle", "MultibandAccelerationFactor", "RepetitionTime",
    "VolumeTiming", "NumberOfVolumesDiscardedByScanner", "NumberOfVolumesDiscardedByUser"])

class BOnD(object):

    def __init__(self, data_root):
        self.path = data_root
        self.layout = bids.BIDSLayout(self.path, validate = False)

    def fieldmaps_ok(self):
        pass

    def rename_files(self, filters, pattern, replacement):
        """
        # @Params
            # - filters: pybids entities dictionary to find files to rename
            # - pattern: the substring of the file we would like to replace
            # - replacement: the substring that will replace "pattern"
        # @Returns
            # - None

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

    def get_param_groups(self, key_group):
        key_entities = _key_group_to_entities(key_group)
        matching_files = self.layout.get(return_type="file", scope="self",
                                         **key_entities)
        return _get_param_groups(matching_files)

    def get_key_groups(self):
        key_groups = set()
        for path in Path(self.path).rglob("*.*"):
            if path.suffix == ".json":
                continue
            key_groups.update(_file_to_key_group(path),)
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

            if len(json_file) is not 1:

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


def _get_param_groups(files):
    """Finds a list of *parameter groups* from a list of files.

    Parameters:
    -----------

    files : list
        List of file names

    Returns:
    --------

    parameter_groups : list
        A list of unique parameter groups

    For each file in `files`, find critical parameters for metadata. Then find
    unique sets of these critical parameters.
    """
    pass
