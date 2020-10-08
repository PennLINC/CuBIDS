"""Main module."""

class BOnD(object):

    def __init__(self, data_root):

        # this should initialise a pybids BIDSLayout object and give us
        # access to all of its functions

        self.path = data_root

    def fieldmaps_ok(self):

        # this function should go through the files in the fmap folder
        # and open its "IntendedFor" section; then, check that each path is a file
        # that exists

        pass

    def rename_files(self, files, pattern, replacement):

        # this function should take a (list of) file(s), and do a string replace on
        # filenames

        pass

    def find_param_sets(self, pattern):

        # this function should open the json metadata for a (list of) file(s)
        # and return them as a dataframe
        pass

    def fill_metadata(self, pattern, metadata):

        # this function should take a dictionary of metadata and write this data
        # into the json file
        
        pass
