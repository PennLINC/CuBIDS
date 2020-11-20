import subprocess
import json
import logging
import pandas as pd
from pathlib import Path

logger = logging.getLogger('bond-cli')


def build_validator_call(path):
    """Build a subprocess command to the bids validator"""

    # build docker call
    command = ['bids-validator', '--verbose', '--json']

    command.append(path)

    return command


def run_validator(call, verbose=True):
    """Run the validator with subprocess"""
    if verbose:
        logger.info("Running the validator with call:")
        logger.info('\"' + ' '.join(call) + '\"')
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
    >>> parse_validator()
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
        return_dict['files'] = [get_nested(x, 'file', 'relativePath') for x in issue_dict.get('files', '')]
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
        df = df.append(parsed, ignore_index=True)

    for err in issues['errors']:

        parsed = parse_issue(err)
        parsed = pd.DataFrame(parsed)
        df = df.append(parsed, ignore_index=True)

    return df
