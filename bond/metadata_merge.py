"""Main module."""
import json
import numpy as np
import pandas as pd
from copy import deepcopy
from math import isnan, nan
from .constants import IMAGING_PARAMS
DIRECT_IMAGING_PARAMS = IMAGING_PARAMS - set(["NSliceTimes"])


def check_merging_operations(action_csv, raise_on_error=False):
    """Checks that the merges in an action csv are possible.

    To be mergable the
    """
    actions = pd.read_csv(action_csv)
    ok_merges = []
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
    return ok_merges


def merge_without_overwrite(source_meta, dest_meta, raise_on_error=False):
    """Performs a safe metadata copy.

    Here, "safe" means that no non-NaN values in `dest_meta` are
    overwritten by the merge. If any overwrites occur an empty
    dictionary is returned.
    """
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
        if isinstance(dest_value, float) and not isnan(dest_value):
            if not source_value == dest_value:
                if raise_on_error:
                    raise Exception("Value for %s is %.3f in destination "
                                    "but %.3f in source"
                                    % (parameter, dest_value, source_value))
                return {}
        dest_meta[parameter] = source_value
    return dest_meta


def print_merges(merge_list):
    """Print formatted text of merges"""
    return "\n\t".join(
        ["%s \n\t\t-> %s" % ("%s:%d" % src_id[::-1],
         "%s:%d" % dest_id[::-1]) for
         src_id, dest_id in merge_list])


def merge_json_into_json(from_file, to_file,
                         exception_on_error=False):
    print("Merging imaging metadata from %s to %s"
          % (from_file, to_file))
    with open(from_file, "r") as fromf:
        source_metadata = json.load(fromf)

    with open(to_file, "r") as tof:
        dest_metadata = json.load(tof)
    orig_dest_metadata = deepcopy(dest_metadata)

    merged_metadata = merge_without_overwrite(
        source_metadata, dest_metadata, raise_on_error=exception_on_error)

    if not merged_metadata:
        return 255

    # Only write if the data has changed
    if not merged_metadata == orig_dest_metadata:
        print("OVERWRITING", to_file)
        with open(to_file, "w") as tofw:
            json.dump(merged_metadata, tofw, indent=4)

    return 0
