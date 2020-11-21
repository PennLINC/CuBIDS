"""Main module."""
from collections import defaultdict
import json
from pathlib import Path
import numpy as np
import pandas as pd
from tqdm import tqdm
from .bond import IMAGING_PARAMS


def check_merging_operations(action_csv):
    """Checks that the merges in an action csv are possible."""
    actions = pd.read_csv(action_csv)

    # Maps into: from
    merges = {}
    # Stores metadata in from
    source_metadata = {}

    needs_merge = actions[np.isfinite(actions['MergeInto'])]

    for _, row_needs_merge in needs_merge.iterrows():
        pass


def merge_json_into_json(from_file, to_file):
    with open(from_file, "r") as fromf:
        source_metadata = json.load(from_file)

    with open(to_file, "r") as tof:
        dest_metadata = json.load(tof)

    return 0
