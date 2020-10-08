"""Main module."""

import pathlib 

class BOnD(object):

    def __init__(self, data_root):
        self.path = data_root
        
    def fieldmaps_ok(self):
        pass

    def rename_files(self, path_to_dir, pattern, replacement):
        for path in pathlib.Path(path_to_dir).iterdir():
            if path.is_file():
                old_name = path.stem 
                old_ext = path.suffix
                directory = path.parent
                new_name = old_name.replace(pattern, replacement) + old_ext
                path.rename(pathlib.Path(directory, new_name))

    def find_param_sets(self, pattern):
        pass

    def fill_metadata(self, pattern, metadata):
        pass
