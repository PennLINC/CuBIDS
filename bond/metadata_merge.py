"""Main module."""
import json
from collections import defaultdict
import numpy as np
import pandas as pd
from copy import deepcopy
from math import nan, isnan
from .constants import IMAGING_PARAMS
DIRECT_IMAGING_PARAMS = IMAGING_PARAMS - set(["NSliceTimes"])


def check_merging_operations(action_csv, raise_on_error=False):
    """Checks that the merges in an action csv are possible.

    To be mergable the
    """
    actions = pd.read_csv(action_csv)
    ok_merges = []
    deletions = []
    overwrite_merges = []
    sdc_incompatible = []

    sdc_cols = set([col for col in actions.columns if
                    col.startswith("IntendedForKey") or
                    col.startswith("FieldmapKey")])

    def _check_sdc_cols(meta1, meta2):
        return {key: meta1[key] for key in sdc_cols} == \
               {key: meta2[key] for key in sdc_cols}

    needs_merge = actions[np.isfinite(actions['MergeInto'])]
    for _, row_needs_merge in needs_merge.iterrows():
        source_param_key = tuple(row_needs_merge[["MergeInto", "KeyGroup"]])
        dest_param_key = tuple(row_needs_merge[["ParamGroup", "KeyGroup"]])
        dest_metadata = row_needs_merge.to_dict()
        source_row = actions.loc[
            (actions[["ParamGroup", "KeyGroup"]] == source_param_key).all(1)]

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

        if not merge_without_overwrite(source_metadata, dest_metadata,
                                       raise_on_error=raise_on_error):
            overwrite_merges.append(merge_id)
            continue
        # add to the list of ok merges if there are no conflicts
        ok_merges.append(merge_id)

    error_message = "\n\nProblems were found in the requested merge.\n" \
                    "===========================================\n\n"
    if sdc_incompatible:
        error_message += "Some merges are incompatible due to differing " \
                         "distortion correction strategies. Check that " \
                         "fieldmaps exist and have the correct " \
                         "\"IntendedFor\" in their sidecars. These merges " \
                         "could not be completed:\n"
        error_message += print_merges(sdc_incompatible) + "\n\n"

    if overwrite_merges:
        error_message += "Some merges are incompatible because the metadata " \
                         "in the destination json conflicts with the values " \
                         "in the source json. Merging should only be used " \
                         "to fill in missing metadata. The following " \
                         "merges could not be completed:\n\n"
        error_message += print_merges(overwrite_merges)

    if overwrite_merges or sdc_incompatible:
        if raise_on_error:
            raise Exception(error_message)
        print(error_message)
    return ok_merges, deletions


def merge_without_overwrite(source_meta, dest_meta_orig, raise_on_error=False):
    """Performs a safe metadata copy.

    Here, "safe" means that no non-NaN values in `dest_meta` are
    overwritten by the merge. If any overwrites occur an empty
    dictionary is returned.
    """
    # copy the original json params
    dest_meta = deepcopy(dest_meta_orig)

    if not source_meta.get("NSliceTimes") == dest_meta.get("NSliceTimes"):
        if raise_on_error:
            raise Exception("Value for NSliceTimes is %d in destination "
                            "but %d in source"
                            % (source_meta.get("NSliceTimes"),
                               source_meta.get("NSliceTimes")))
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
                    raise Exception("Value for %s is %s in destination "
                                    "but %s in source"
                                    % (parameter, str(dest_value),
                                       str(source_value)))
                return {}
        dest_meta[parameter] = source_value
    return dest_meta


def is_nan(val):
    '''Returns True if val is nan'''
    if not isinstance(val, float):
        return False
    return isnan(val)


def print_merges(merge_list):
    """Print formatted text of merges"""
    return "\n\t" + "\n\t".join(
        ["%s \n\t\t-> %s" % ("%s:%d" % src_id[::-1],
         "%s:%d" % dest_id[::-1]) for
         src_id, dest_id in merge_list])


def merge_json_into_json(from_file, to_file,
                         raise_on_error=False):
    print("Merging imaging metadata from %s to %s"
          % (from_file, to_file))
    with open(from_file, "r") as fromf:
        source_metadata = json.load(fromf)

    with open(to_file, "r") as tof:
        dest_metadata = json.load(tof)
    orig_dest_metadata = deepcopy(dest_metadata)

    merged_metadata = merge_without_overwrite(
        source_metadata, dest_metadata, raise_on_error=raise_on_error)

    if not merged_metadata:
        return 255

    # Only write if the data has changed
    if not merged_metadata == orig_dest_metadata:
        print("OVERWRITING", to_file)
        with open(to_file, "w") as tofw:
            json.dump(merged_metadata, tofw, indent=4)

    return 0


def group_by_acquisition_sets(files_csv, output_prefix, acq_group_level):
    '''Finds unique sets of Key/Param groups across subjects.
    '''
    from bids.layout import parse_file_entities
    from bids import config
    config.set_option('extension_initial_dot', True)

    files_df = pd.read_csv(files_csv)
    acq_groups = defaultdict(list)
    for _, row in files_df.iterrows():
        file_entities = parse_file_entities(row.FilePath)

        if acq_group_level == 'subject':
            acq_id = (file_entities.get("subject"),
                      file_entities.get("session"))
            acq_groups[acq_id].append((row.KeyGroup, row.ParamGroup))
        else:
            acq_id = (file_entities.get("subject"), None)
            acq_groups[acq_id].append((row.KeyGroup, row.ParamGroup,
                                       file_entities.get("session")))

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
        acq_group_info.append(
            (groupnum, content_id_counts[content_id_row]) + content_id)
        for subject, session in contents_to_subjects[content_id]:
            grouped_sub_sess.append(
                {"subject": 'sub-' + subject,
                 "session": session,
                 "AcqGroup": groupnum})

    # Write the mapping of subject/session to
    acq_group_df = pd.DataFrame(grouped_sub_sess)
    acq_group_df.to_csv(output_prefix + "_AcqGrouping.csv", index=False)

    # Write the summary of acq groups to a text file
    with open(output_prefix + "_AcqGroupInfo.txt", "w") as infotxt:
        infotxt.write(
            "\n".join([" ".join(map(str, line)) for line in acq_group_info]))
