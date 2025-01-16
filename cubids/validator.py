"""Methods for validating BIDS datasets."""

import glob
import json
import logging
import os
import pathlib
import re
import subprocess
import warnings

import pandas as pd

logger = logging.getLogger("cubids-cli")


def build_validator_call(path, local_validator=False, ignore_headers=False):
    """Build a subprocess command to the bids validator.

    Parameters
    ----------
    path : :obj:`str`
        Path to the BIDS dataset.
    local_validator : :obj:`bool`
        If provided, use the local bids-validator.
    ignore_headers : :obj:`bool`
        If provided, ignore NIfTI headers.

    Returns
    -------
    command : :obj:`list`
        List of strings to pass to subprocess.run().
    """
    if local_validator:
        command = ["bids-validator", path, "--verbose", "--json"]
    else:
        command = ["deno", "run", "-A", "jsr:@bids/validator", path, "--verbose", "--json"]

    if ignore_headers:
        command.append("--ignoreNiftiHeaders")

    return command


def get_bids_validator_version():
    """Get the version of the BIDS validator.

    Returns
    -------
    version : :obj:`str`
        Version of the BIDS validator.
    """
    command = ["deno", "run", "-A", "jsr:@bids/validator", "--version"]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stdout.decode("utf-8").strip()
    version = output.split()[-1]
    # Remove ANSI color codes
    clean_ver = re.sub(r"\x1b\[[0-9;]*m", "", version)
    return {"ValidatorVersion": clean_ver}


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


def build_first_subject_path(bids_dir, subject):
    """Build a list of BIDS dirs with 1 subject each."""
    bids_dir = str(bids_dir)
    if not bids_dir.endswith("/"):
        bids_dir += "/"

    root_files = [x for x in glob.glob(bids_dir + "*") if os.path.isfile(x)]

    subject_dict = {}

    purepath = pathlib.PurePath(subject)
    sub_label = purepath.name

    files = [x for x in glob.glob(subject + "**", recursive=True) if os.path.isfile(x)]
    files.extend(root_files)
    subject_dict[sub_label] = files

    return subject_dict


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
            "issueMessage": issue_dict.get("issueMessage", ""),
            "subCode": issue_dict.get("subCode", ""),
            "severity": issue_dict.get("severity", ""),
            "rule": issue_dict.get("rule", ""),
        }

    # Load JSON data
    data = json.loads(output)

    # Extract issues
    issues = data.get("issues", {}).get("issues", [])
    if not issues:
        return pd.DataFrame(
            columns=["location", "code", "issueMessage", "subCode", "severity", "rule"]
        )

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
        "issueMessage": {"Description": "Validation issue message."},
        "subCode": {"Description": "Subcode providing additional issue details."},
        "severity": {"Description": "Severity of the issue (e.g., warning, error)."},
        "rule": {"Description": "Validation rule that triggered the issue."},
    }


def extract_summary_info(output):
    """Extract summary information from the JSON output.

    Parameters
    ----------
    output : str
        JSON string of BIDS validator output.

    Returns
    -------
    dict
        Dictionary containing SchemaVersion and other summary info.
    """
    try:
        data = json.loads(output)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON provided to get SchemaVersion.") from e

    summary = data.get("summary", {})

    return {"SchemaVersion": summary.get("schemaVersion", "")}


def update_dataset_description(path, new_info):
    """Update or append information to dataset_description.json.

    Parameters
    ----------
    path : :obj:`str`
        Path to the dataset.
    new_info : :obj:`dict`
        Information to add or update.
    """
    description_path = os.path.join(path, "dataset_description.json")

    # Load existing data if the file exists
    if os.path.exists(description_path):
        with open(description_path, "r") as f:
            existing_data = json.load(f)
    else:
        existing_data = {}

    # Update the existing data with the new info
    existing_data.update(new_info)

    # Write the updated data back to the file
    with open(description_path, "w") as f:
        json.dump(existing_data, f, indent=4)
    print(f"Updated dataset_description.json at: {description_path}")

    # Check if .datalad directory exists before running the DataLad save command
    datalad_dir = os.path.join(path, ".datalad")
    if os.path.exists(datalad_dir) and os.path.isdir(datalad_dir):
        try:
            subprocess.run(
                [
                    "datalad",
                    "save",
                    "-m",
                    "Save BIDS validator and schema version to dataset_description",
                    description_path,
                ],
                check=True,
            )
            print("Changes saved with DataLad.")
        except subprocess.CalledProcessError as e:
            warnings.warn(f"Error running DataLad save: {e}")


def bids_validator_version(output, path, write=False):
    """Save BIDS validator and schema version.

    Parameters
    ----------
    output : :obj:`str`
        Path to JSON file of BIDS validator output.
    path : :obj:`str`
        Path to the dataset.
    write : :obj:`bool`
        If True, write to dataset_description.json. If False, print to terminal.
    """
    # Get the BIDS validator version
    validator_version = get_bids_validator_version()
    # Extract schemaVersion
    summary_info = extract_summary_info(output)

    combined_info = {**validator_version, **summary_info}

    if write:
        # Update the dataset_description.json file
        update_dataset_description(path, combined_info)
    elif not write:
        print(combined_info)
