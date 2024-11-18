"""Methods for validating BIDS datasets."""

import glob
import json
import logging
import os
import pathlib
import subprocess

import pandas as pd

logger = logging.getLogger("cubids-cli")


def build_validator_call(path, ignore_headers=False):
    """Build a subprocess command to the bids validator."""
    # New schema BIDS validator doesn't have option to ignore subject consistency.
    # Build the deno command to run the BIDS validator.
    command = ["deno", "run", "-A", "jsr:@bids/validator", path, "--verbose", "--json"]

    if ignore_headers:
        command.append("--ignoreNiftiHeaders")

    return command


def build_subject_paths(bids_dir):
    """Build a list of BIDS dirs with 1 subject each."""
    bids_dir = str(bids_dir)
    if not bids_dir.endswith("/"):
        bids_dir += "/"

    root_files = [x for x in glob.glob(bids_dir + "*") if os.path.isfile(x)]

    bids_dir += "sub-*/"

    subjects = glob.glob(bids_dir)

    if len(subjects) < 1:
        raise ValueError("Couldn't find any subjects in the specified directory:\n" + bids_dir)

    subjects_dict = {}

    for sub in subjects:
        purepath = pathlib.PurePath(sub)
        sub_label = purepath.name

        files = [x for x in glob.glob(sub + "**", recursive=True) if os.path.isfile(x)]
        files.extend(root_files)
        subjects_dict[sub_label] = files

    return subjects_dict


def run_validator(call):
    """Run the validator with subprocess.

    Parameters
    ----------
    call : :obj:`list`
        List of strings to pass to subprocess.run().

    Returns
    -------
    :obj:`subprocess.CompletedProcess`
        The result of the subprocess call.
    """
    # if verbose:
    #     logger.info("Running the validator with call:")
    #     logger.info('\"' + ' '.join(call) + '\"')

    ret = subprocess.run(call, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return ret


def parse_validator_output(output):
    """Parse the JSON output of the BIDS validator into a pandas dataframe.

    Parameters
    ----------
    output : :obj:`str`
        Path to JSON file of BIDS validator output

    Returns
    -------
    df : :obj:`pandas.DataFrame`
        Dataframe of validator output.
    """

    def parse_issue(issue_dict):
        """Parse a single issue from the validator output.

        Parameters
        ----------
        issue_dict : :obj:`dict`
            Dictionary of issue.

        Returns
        -------
        return_dict : :obj:`dict`
            Dictionary of parsed issue.
        """
        return {
            "location": issue_dict.get("location", ""),
            "code": issue_dict.get("code", ""),
            "subCode": issue_dict.get("subCode", ""),
            "severity": issue_dict.get("severity", ""),
            "rule": issue_dict.get("rule", ""),
        }

    # Load JSON data
    data = json.loads(output)

    # Extract issues
    issues = data.get("issues", {}).get("issues", [])
    if not issues:
        return pd.DataFrame(columns=["location", "code", "subCode", "severity", "rule"])

    # Parse all issues
    parsed_issues = [parse_issue(issue) for issue in issues]

    # Convert to DataFrame
    df = pd.DataFrame(parsed_issues)
    return df


def get_val_dictionary():
    """Get value dictionary.

    Returns
    -------
    val_dict : dict
        Dictionary of values.
    """
    return {
        "location": {"Description": "File with the validation issue."},
        "code": {"Description": "Code of the validation issue."},
        "subCode": {"Description": "Subcode providing additional issue details."},
        "severity": {"Description": "Severity of the issue (e.g., warning, error)."},
        "rule": {"Description": "Validation rule that triggered the issue."},
    }
