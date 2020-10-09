"""Main module."""
from pathlib import Path
import bids
bids.config.set_option('extension_initial_dot', True)
from bids.layout import parse_file_entities

NON_KEY_ENTITIES = set(["subject", "session", "extension"])

class BOnD(object):

    def __init__(self, data_root):
        self.path = data_root

    def fieldmaps_ok(self):
        pass

    def rename_files(self, pattern, replacement):
        """
        # @Params
            # - path: a string contianing the path to the bids directory inside which we want to change files
            # - pattern: the substring of the file we would like to replace
            # - replacement: the substring that will replace "pattern"
        # @Returns
            # - None
        """
        files_and_dirs = Path(self.path).rglob('*')
        for path in files_and_dirs:
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

    def fill_metadata(self, pattern, metadata):
        pass


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
