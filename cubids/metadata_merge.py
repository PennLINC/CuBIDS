"""Tools for merging metadata."""

import json
from collections import defaultdict
from copy import deepcopy
from math import isnan, nan

import numpy as np
import pandas as pd

from cubids.constants import IMAGING_PARAMS

DIRECT_IMAGING_PARAMS = IMAGING_PARAMS - set(["NSliceTimes"])


def check_merging_operations(action_tsv, raise_on_error=False):
    """Check that the merges in an action tsv are possible.

    Parameters
    ----------
    action_tsv : :obj:`str`
        Path to the action tsv file.
    raise_on_error : :obj:`bool`, optional
        Whether to raise an exception if there are errors.

    Returns
    -------
    ok_merges : :obj:`list`
        List of tuples of ok merges.
    deletions : :obj:`list`
        List of tuples of deletions.

    Raises
    ------
    :obj:`Exception`
        If there are errors and ``raise_on_error`` is ``True``.
    """
    actions = pd.read_table(action_tsv)
    ok_merges = []
    deletions = []
    overwrite_merges = []
    sdc_incompatible = []

    sdc_cols = set(
        [
            col
            for col in actions.columns
            if col.startswith("IntendedForKey") or col.startswith("FieldmapKey")
        ]
    )

    def _check_sdc_cols(meta1, meta2):
        return {key: meta1[key] for key in sdc_cols} == {key: meta2[key] for key in sdc_cols}

    needs_merge = actions[np.isfinite(actions["MergeInto"])]
    for _, row_needs_merge in needs_merge.iterrows():
        source_param_key = tuple(row_needs_merge[["MergeInto", "EntitySet"]])
        dest_param_key = tuple(row_needs_merge[["ParamGroup", "EntitySet"]])
        dest_metadata = row_needs_merge.to_dict()
        source_row = actions.loc[(actions[["ParamGroup", "EntitySet"]] == source_param_key).all(1)]

        if source_param_key[0] == 0:
            print("going to delete ", dest_param_key)
            deletions.append(dest_param_key)
            continue

        if not source_row.shape[0] == 1:
            raise Exception("Could not identify a unique source group")

        source_metadata = source_row.iloc[0].to_dict()
        merge_id = (source_param_key, dest_param_key)
        # Check for compatible fieldmaps
        if not _check_sdc_cols(source_metadata, dest_metadata):
            sdc_incompatible.append(merge_id)
            continue

        if not merge_without_overwrite(
            source_metadata, dest_metadata, raise_on_error=raise_on_error
        ):
            overwrite_merges.append(merge_id)
            continue

        # add to the list of ok merges if there are no conflicts
        ok_merges.append(merge_id)

    error_message = (
        "\n\nProblems were found in the requested merge.\n"
        "===========================================\n\n"
    )
    if sdc_incompatible:
        error_message += (
            "Some merges are incompatible due to differing "
            "distortion correction strategies. Check that "
            "fieldmaps exist and have the correct "
            '"IntendedFor" in their sidecars. These merges '
            "could not be completed:\n"
        )
        error_message += print_merges(sdc_incompatible) + "\n\n"

    if overwrite_merges:
        error_message += (
            "Some merges are incompatible because the metadata "
            "in the destination json conflicts with the values "
            "in the source json. Merging should only be used "
            "to fill in missing metadata. The following "
            "merges could not be completed:\n\n"
        )
        error_message += print_merges(overwrite_merges)

    if overwrite_merges or sdc_incompatible:
        if raise_on_error:
            raise Exception(error_message)

        print(error_message)

    return ok_merges, deletions


def merge_without_overwrite(source_meta, dest_meta_orig, raise_on_error=False):
    """Perform a safe metadata copy.

    Here, "safe" means that no non-NaN values in `dest_meta` are
    overwritten by the merge. If any overwrites occur an empty
    dictionary is returned.

    Parameters
    ----------
    source_meta : :obj:`dict`
        The metadata to merge from.
    dest_meta_orig : :obj:`dict`
        The metadata to merge into.
    raise_on_error : :obj:`bool`, optional
        Whether to raise an exception if there are errors.

    Returns
    -------
    :obj:`dict`
        The merged metadata.

    Raises
    ------
    :obj:`Exception`
        If there are errors and ``raise_on_error`` is ``True``.
    """
    # copy the original json params
    dest_meta = deepcopy(dest_meta_orig)

    if not source_meta.get("NSliceTimes") == dest_meta.get("NSliceTimes"):
        if raise_on_error:
            raise Exception(
                "Value for NSliceTimes is %d in destination "
                "but %d in source"
                % (source_meta.get("NSliceTimes"), source_meta.get("NSliceTimes"))
            )
        return {}

    for parameter in DIRECT_IMAGING_PARAMS:
        source_value = source_meta.get(parameter, nan)
        dest_value = dest_meta.get(parameter, nan)

        # cannot merge num --> num
        # exception should only be raised
        # IF someone tries to replace a num (dest)
        # with a num (src)
        if not is_nan(source_value):
            # need to figure out if we can merge
            if not is_nan(dest_value) and source_value != dest_value:
                if raise_on_error:
                    raise Exception(
                        f"Value for {parameter} is {dest_value} in destination "
                        f"but {source_value} in source"
                    )

                return {}

        dest_meta[parameter] = source_value

    return dest_meta


def is_nan(val):
    """Return True if val is NaN."""
    if not isinstance(val, float):
        return False

    return isnan(val)


def print_merges(merge_list):
    """Print formatted text of merges."""
    merge_strings = []
    for src_id, dest_id in merge_list:
        src_id_str = f"{src_id[-1]}:{src_id[0]}"
        dest_id_str = f"{dest_id[-1]}:{dest_id[0]}"
        merge_str = f"{src_id_str} \n\t\t-> {dest_id_str}"
        merge_strings.append(merge_str)

    return "\n\t" + "\n\t".join(merge_strings)


def merge_json_into_json(from_file, to_file, raise_on_error=False):
    """Merge imaging metadata into JSON.

    Parameters
    ----------
    from_file : :obj:`str`
        Path to the JSON file to merge from.
    to_file : :obj:`str`
        Path to the JSON file to merge into.
    raise_on_error : :obj:`bool`, optional
        Whether to raise an exception if there are errors.
        Defaults to ``False``.

    Returns
    -------
    :obj:`int`
        Exit code.
        Either 255 if there was an error or 0 if there was not.
    """
    print(f"Merging imaging metadata from {from_file} to {to_file}")
    with open(from_file, "r") as fromf:
        source_metadata = json.load(fromf)

    with open(to_file, "r") as tof:
        dest_metadata = json.load(tof)
    orig_dest_metadata = deepcopy(dest_metadata)

    merged_metadata = merge_without_overwrite(
        source_metadata,
        dest_metadata,
        raise_on_error=raise_on_error,
    )

    if not merged_metadata:
        return 255

    # Only write if the data has changed
    if not merged_metadata == orig_dest_metadata:
        print("OVERWRITING", to_file)
        with open(to_file, "w") as tofw:
            json.dump(merged_metadata, tofw, indent=4)

    return 0


def get_acq_dictionary():
    """Create a BIDS data dictionary from dataframe columns.

    Parameters
    ----------
    df : :obj:`pandas.DataFrame`
        Pre export TSV that will be converted to a json dictionary.

    Returns
    -------
    acq_dict : :obj:`dict`
        Python dictionary in BIDS data dictionary format
    """
    acq_dict = {}
    acq_dict["subject"] = {"Description": "Participant ID"}
    acq_dict["session"] = {"Description": "Session ID"}
    docs = " https://cubids.readthedocs.io/en/latest/about.html#definitions"
    desc = "Acquisition Group. See Read the Docs for more information"
    acq_dict["AcqGroup"] = {"Description": desc + docs}

    return acq_dict


def group_by_acquisition_sets(files_tsv, output_prefix, acq_group_level):
    """Find unique sets of Key/Param groups across subjects.

    This writes out the following files:
    - <output_prefix>_AcqGrouping.tsv: A tsv with the mapping of subject/session to
      acquisition group.
    - <output_prefix>_AcqGrouping.json: A data dictionary for the AcqGrouping.tsv.
    - <output_prefix>_AcqGroupInfo.txt: A text file with the summary of acquisition.
    - <output_prefix>_AcqGroupInfo.json: A data dictionary for the AcqGroupInfo.txt.

    Parameters
    ----------
    files_tsv : :obj:`str`
        Path to the files tsv.
    output_prefix : :obj:`str`
        Prefix for output files.
    acq_group_level : {"subject", "session"}
        Level at which to group acquisitions.
    """
    from bids import config
    from bids.layout import parse_file_entities

    config.set_option("extension_initial_dot", True)

    files_df = pd.read_table(
        files_tsv,
    )
    acq_groups = defaultdict(list)
    for _, row in files_df.iterrows():
        file_entities = parse_file_entities(row.FilePath)

        if acq_group_level == "subject":
            acq_id = (file_entities.get("subject"), file_entities.get("session"))
            acq_groups[acq_id].append((row.EntitySet, row.ParamGroup))
        else:
            acq_id = (file_entities.get("subject"), None)
            acq_groups[acq_id].append(
                (row.EntitySet, row.ParamGroup, file_entities.get("session"))
            )

    # Map the contents to a list of subjects/sessions
    contents_to_subjects = defaultdict(list)
    for key, value in acq_groups.items():
        contents_to_subjects[tuple(sorted(value))].append(key)

    # Sort them based on how many have that group
    content_ids = []
    content_id_counts = []
    for key, value in contents_to_subjects.items():
        content_ids.append(key)
        content_id_counts.append(len(value))

    descending_order = np.argsort(content_id_counts)[::-1]

    # Create a dataframe with the subject, session, groupnum
    grouped_sub_sess = []
    acq_group_info = []
    for groupnum, content_id_row in enumerate(descending_order, start=1):
        content_id = content_ids[content_id_row]
        acq_group_info.append((groupnum, content_id_counts[content_id_row]) + content_id)
        for subject, session in contents_to_subjects[content_id]:
            grouped_sub_sess.append(
                {"subject": "sub-" + subject, "session": session, "AcqGroup": groupnum}
            )

    # Write the mapping of subject/session to
    acq_group_df = pd.DataFrame(grouped_sub_sess)
    acq_group_df.to_csv(output_prefix + "_AcqGrouping.tsv", sep="\t", index=False)

    # Create data dictionary for acq group tsv
    acq_dict = get_acq_dictionary()
    with open(output_prefix + "_AcqGrouping.json", "w") as outfile:
        json.dump(acq_dict, outfile, indent=4)

    # Write the summary of acq groups to a text file
    with open(output_prefix + "_AcqGroupInfo.txt", "w") as infotxt:
        infotxt.write("\n".join([" ".join(map(str, line)) for line in acq_group_info]))

    # Create and save AcqGroupInfo data dictionary
    header_dict = {}
    header_dict["Long Description"] = "Acquisition Group Info"
    description = "https://cubids.readthedocs.io/en/latest/usage.html"
    header_dict["Description"] = description
    header_dict["Version"] = "CuBIDS v1.0.5"

    acq_info_dict = {}
    acq_info_dict["AcqGroupInfo.txt Data Dictionary"] = header_dict

    with open(output_prefix + "_AcqGroupInfo.json", "w") as outfile:
        json.dump(acq_info_dict, outfile, indent=4)
