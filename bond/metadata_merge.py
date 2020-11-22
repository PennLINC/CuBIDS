"""Main module."""
from collections import defaultdict
import json
from pathlib import Path
import numpy as np
import pandas as pd
from math import isnan, nan
from .bond import IMAGING_PARAMS
DIRECT_IMAGING_PARAMS = IMAGING_PARAMS - set(["NSliceTimes"])

def check_merging_operations(action_csv):
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
    source_search_cols = ["ParamGroup", "KeyGroup"]
    sink_search_cols = ["ParamGroup", "MergeInto"]
    for _, row_needs_merge in needs_merge.iterrows():
        sink_pattern = tuple(row_needs_merge[sink_search_cols])
        sink_metadata = row_needs_merge.to_dict()
        source_row = actions.loc[
            (actions[[source_search_cols]] == sink_pattern).all(1)]
        if not source_row.shape[0] == 1:
            raise Exception("more than one possible source group")
        source_metadata = source_row.iloc[0].to_dict()
        source_pattern = tuple(source_metadata["KeyGroup"],
                               source_metadata["ParamGroup"])
        merge_id = (tuple(row_needs_merge[source_search_cols]),
                    source_pattern)
        # Check for compatible fieldmaps
        if not _check_sdc_cols(source_metadata, sink_metadata):
            sdc_incompatible.append(merge_id)
            continue

        if merge_without_overwrite(source_metadata, sink_metadata):
            overwrite_merges.append(merge_id)
            continue
        ok_merges.append(merge_id)

    error_message = "Problems were found in the requested merge.\n" \
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
                         "merges could not be completed:\n"
        error_message += print_merges(overwrite_merges)

    return ok_merges


def merge_without_overwrite(source_meta, dest_meta):
    """Performs a safe metadata copy.

    Here, "safe" means that no non-NaN values in `dest_meta` are
    overwritten by the merge. If any overwrites occur an empty
    dictionary is returned.
    """
    if not source_meta.get("NSliceTimes") == dest_meta.get("NSliceTimes"):
        return {}
    for parameter in DIRECT_IMAGING_PARAMS:
        source_value = source_meta.get(parameter, nan)
        dest_value = dest_meta.get(parameter, nan)
        if isinstance(dest_value, float) and not isnan(dest_value):
            if not source_value == dest_value:
                return {}
        dest_meta[parameter] = source_value
    return dest_meta


def print_merges(merge_list):
    """Print formatted text of merges"""
    return "\n\t".join(
        ["%s \n\t\t-> %s" % ("%s:%d" % src_id, "%s:%d" % dest_id) for
         src_id, dest_id in merge_list])


def merge_json_into_json(from_file, to_file):
    with open(from_file, "r") as fromf:
        source_metadata = json.load(from_file)

    with open(to_file, "r") as tof:
        dest_metadata = json.load(tof)

    return 0
