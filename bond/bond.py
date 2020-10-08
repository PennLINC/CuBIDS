"""Main module."""
from pathlib import Path


class BOnD(object):

    def __init__(self, data_root):
        self.path = data_root

    def fieldmaps_ok(self):
        pass

    def rename_files(self, pattern, replacement):
        # @Params
            # - path: a string contianing the path to the bids directory inside which we want to change files
            # - pattern: the substring of the file we would like to replace
            # - replacement: the substring that will replace "pattern"
        # @Returns
            # - None
        files_and_dirs = Path(self.path).rglob('*')
        for path in files_and_dirs:
            old_name = path.stem
            old_ext = path.suffix
            directory = path.parent
            new_name = old_name.replace(pattern, replacement) + old_ext
            path.rename(Path(directory, new_name))

    def find_param_sets(self, pattern):
        pass

    def fill_metadata(self, pattern, metadata):
        pass
if __name__ == '__main__':
    pass
