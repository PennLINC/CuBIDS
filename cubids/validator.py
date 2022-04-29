import subprocess
import json
import logging
import os
import glob
import pathlib
import pandas as pd

logger = logging.getLogger('cubids-cli')


def build_validator_call(path, ignore_headers=False, ignore_subject=True):
    """Build a subprocess command to the bids validator"""

    # build docker call
    command = ['bids-validator', '--verbose', '--json']

    if ignore_headers:
        command.append('--ignoreNiftiHeaders')
    if ignore_subject:
        command.append('--ignoreSubjectConsistency')

    command.append(path)

    return command


def build_subject_paths(bids_dir):
    """Build a list of BIDS dirs with 1 subject each"""

    bids_dir = str(bids_dir)
    if not bids_dir.endswith("/"):
        bids_dir += "/"

    root_files = [x for x in glob.glob(bids_dir + "*") if os.path.isfile(x)]

    bids_dir += "sub-*/"

    subjects = glob.glob(bids_dir)

    if len(subjects) < 1:

        raise ValueError("Couldn't find any subjects "
                         "in the specified directory:\n" +
                         bids_dir)

    subjects_dict = {}

    for sub in subjects:
        purepath = pathlib.PurePath(sub)
        sub_label = purepath.name

        files = [x for x in glob.glob(sub + '**', recursive=True)
                 if os.path.isfile(x)]
        files.extend(root_files)
        subjects_dict[sub_label] = files

    return subjects_dict


def run_validator(call, verbose=True):
    """Run the validator with subprocess"""
    # if verbose:
    #     logger.info("Running the validator with call:")
    #     logger.info('\"' + ' '.join(call) + '\"')

    ret = subprocess.run(call, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    return(ret)


def parse_validator_output(output):
    """Parse the JSON output of the BIDS validator into a pandas dataframe
    Parameters:
    -----------
        - path : string
            Path to JSON file of BIDS validator output
    Returns
    -----------
        - Pandas DataFrame
    """

    def get_nested(dct, *keys):
        for key in keys:
            try:
                dct = dct[key]
            except (KeyError, TypeError):
                return None
        return dct

    data = json.loads(output)

    issues = data['issues']

    def parse_issue(issue_dict):

        return_dict = {}
        return_dict['files'] = [
            get_nested(x, 'file', 'relativePath')
            for x in issue_dict.get('files', '')
            ]
        return_dict['type'] = issue_dict.get('key' '')
        return_dict['severity'] = issue_dict.get('severity', '')
        return_dict['description'] = issue_dict.get('reason', '')
        return_dict['code'] = issue_dict.get('code', '')
        return_dict['url'] = issue_dict.get('helpUrl', '')

        return(return_dict)

    df = pd.DataFrame()

    for warn in issues['warnings']:

        parsed = parse_issue(warn)
        parsed = pd.DataFrame(parsed)
        df = pd.concat([df, parsed], ignore_index=True)

    for err in issues['errors']:

        parsed = parse_issue(err)
        parsed = pd.DataFrame(parsed)
        df = pd.concat([df, parsed], ignore_index=True)

    return df
