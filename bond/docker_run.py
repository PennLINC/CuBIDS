import subprocess
import json
import logging
import pandas as pd
from pathlib import Path

logger = logging.getLogger('bond-cli')


def check_docker():
    """Verify that docker is installed and the user has permission to
    run docker images.
    Returns
    -------
    -1  Docker can't be found
     0  Docker found, but user can't connect to daemon
     1  Test run OK
     """
    try:
        ret = subprocess.run(['docker', 'version'], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    except OSError as e:
        from errno import ENOENT
        if e.errno == ENOENT:
            logger.error("Cannot find Docker engine!")
            return -1
        raise e
    if ret.stderr.startswith(b"Cannot connect to the Docker daemon."):
        logger.error("Cannot connect to Docker daemon!")
        return 0
    return 1


def check_image(image='pennlinc/bond:latest'):
    """Check whether image is present on local system"""
    ret = subprocess.run(['docker', 'images', '-q', image],
                         stdout=subprocess.PIPE)
    return bool(ret.stdout)


def build_validator_call(path, image='pennlinc/bond:latest', shell=False):
    """Build a subprocess command to docker"""

    # build docker call
    command = ['docker', 'run', '--rm']

    # add directory to run
    path = str(Path(path).resolve())
    command.extend(['-v', ':'.join((path, '/data', 'ro'))])

    if shell:
        command.append('--entrypoint=bash')

    # finally add the image name and path
    command.append(image)
    command.append('--verbose')
    command.append('--json')
    command.append('/data')

    return command


def run(call, verbose=True):
    """Run the docker image with subprocess"""
    if verbose:
        logger.info("Running the validator with call:")
        logger.info(' '.join(call))
    ret = subprocess.run(call, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    return(ret)


def parse_validator(output):
    """Parse the JSON/dictionary output of the BIDS validator into a pandas
    dataframe.

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
        return_dict['files'] = [get_nested(x, 'file', 'relativePath')
                                for x in issue_dict.get('files', '')]
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
