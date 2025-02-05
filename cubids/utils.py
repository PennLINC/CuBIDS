"""Miscellaneous utility functions for CuBIDS.

This module provides various utility functions used throughout the CuBIDS package.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from bids.layout import parse_file_entities
from sklearn.cluster import AgglomerativeClustering

from cubids.constants import ID_VARS, NON_KEY_ENTITIES


def _compress_lists(df):
    """Compress lists in a DataFrame to strings.

    Used to prepare a DataFrame with cells containing lists for writing to a TSV file.

    Parameters
    ----------
    df : :obj:`pandas.DataFrame`
        The DataFrame to compress.

    Returns
    -------
    :obj:`pandas.DataFrame`
        The compressed DataFrame.
    """
    for col in df.columns:
        if isinstance(df[col].values[0], list):
            df[col] = df[col].apply(lambda x: "|&|".join(x))
    return df


def _expand_lists(df):
    """Expand strings in a DataFrame to lists.

    Used to prepare a DataFrame with cells containing strings for querying after loading from a
    TSV file.

    Parameters
    ----------
    df : :obj:`pandas.DataFrame`
        The DataFrame to expand.

    Returns
    -------
    :obj:`pandas.DataFrame`
        The expanded DataFrame.
    """
    for col in df.columns:
        if isinstance(df[col].values[0], str):
            df[col] = df[col].apply(lambda x: x.split("|&|"))
    return df


def _update_json(json_file, metadata):
    """Update a JSON file with the provided metadata.

    This function writes the given metadata to the specified JSON file if the
    JSON data is valid. If the JSON data is invalid, it prints an error message.

    Parameters
    ----------
    json_file : str
        The path to the JSON file to be updated.
    metadata : dict
        The metadata to be written to the JSON file.

    Returns
    -------
    None
    """
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)


def _entity_set_to_entities(entity_set):
    """Split an entity_set name into a pybids dictionary of entities.

    Parameters
    ----------
    entity_set : str
        A string representing a set of entities, where each entity is
        separated by an underscore and each key-value pair is separated by a hyphen.

    Returns
    -------
    dict
        A dictionary where the keys are entity names and the values are entity values.

    Examples
    --------
    >>> _entity_set_to_entities("sub-01_ses-02_task-rest")
    {'sub': '01', 'ses': '02', 'task': 'rest'}
    """
    return dict([group.split("-") for group in entity_set.split("_")])


def _entities_to_entity_set(entities):
    """Convert a pybids entities dictionary into an entity set name.

    Parameters
    ----------
    entities : dict
        A dictionary containing pybids entities where keys are entity names
        and values are entity values.

    Returns
    -------
    str
        A string representing the entity set name, constructed by joining
        the sorted entity keys and their corresponding values, separated by hyphens.
    """
    group_keys = sorted(entities.keys() - NON_KEY_ENTITIES)
    return "_".join([f"{key}-{entities[key]}" for key in group_keys])


def _file_to_entity_set(filename):
    """Identify and return the entity set of a BIDS valid filename.

    Parameters
    ----------
    filename : str
        The filename to parse for BIDS entities.

    Returns
    -------
    str
        A set of entities extracted from the filename.

    Examples
    --------
    >>> _file_to_entity_set("sub-01_ses-01_task-rest_bold.nii.gz")
    'session-01_suffix-bold_task-rest'
    """
    entities = parse_file_entities(str(filename))
    return _entities_to_entity_set(entities)


def _get_participant_relative_path(scan):
    """Build the relative-from-subject version of a Path to a file.

    Parameters
    ----------
    scan : str
        The full path to the scan file.

    Returns
    -------
    str
        The relative path from the subject directory.

    Raises
    ------
    ValueError
        If the subject directory cannot be found in the path.

    Examples
    --------
    >>> _get_participant_relative_path(
    ...    "/path/to/dset/sub-01/ses-01/func/sub-01_ses-01_bold.nii.gz",
    ... )
    'ses-01/func/sub-01_ses-01_bold.nii.gz'

    >>> _get_participant_relative_path(
    ...    "/path/to/dset/sub-01/func/sub-01_bold.nii.gz",
    ... )
    'func/sub-01_bold.nii.gz'

    >>> _get_participant_relative_path(
    ...    "/path/to/dset/ses-01/func/ses-01_bold.nii.gz",
    ... )
    Traceback (most recent call last):
    ValueError: Could not find subject in ...
    """
    parts = Path(scan).parts
    # Find the first part that starts with "sub-"
    for i, part in enumerate(parts):
        if part.startswith("sub-"):
            return "/".join(parts[i + 1 :])
    raise ValueError(f"Could not find subject in {scan}")


def _get_bidsuri(filename, dataset_root):
    """Convert a file path to a BIDS URI.

    Parameters
    ----------
    filename : str
        The full path to the file within the BIDS dataset.
    dataset_root : str
        The root directory of the BIDS dataset.

    Returns
    -------
    str
        The BIDS URI corresponding to the given file path.

    Raises
    ------
    ValueError
        If the filename is not within the dataset_root.

    Examples
    --------
    >>> _get_bidsuri("/path/to/bids/sub-01/ses-01/dataset_description.json", "/path/to/bids")
    'bids::sub-01/ses-01/dataset_description.json'
    >>> _get_bidsuri("/path/to/bids/sub-01/ses-01/dataset_description.json", "/path/to/other")
    Traceback (most recent call last):
    ValueError: Only local datasets are supported: ...
    """
    if dataset_root in filename:
        return filename.replace(dataset_root, "bids::").replace("bids::/", "bids::")
    raise ValueError(f"Only local datasets are supported: {filename}")


def _get_param_groups(
    files,
    fieldmap_lookup,
    entity_set_name,
    grouping_config,
    modality,
    keys_files,
):
    """Find a list of *parameter groups* from a list of files.

    For each file in `files`, find critical parameters for metadata. Then find
    unique sets of these critical parameters.

    Parameters
    ----------
    files : :obj:`list` of :obj:`str`
        List of file names
    fieldmap_lookup : :obj:`dict`
        mapping of filename strings relative to the bids root
        (e.g. "sub-X/ses-Y/func/sub-X_ses-Y_task-rest_bold.nii.gz")
    grouping_config : :obj:`dict`
        configuration for defining parameter groups

    Returns
    -------
    ordered_labeled_files : :obj:`pandas.DataFrame`
        A data frame with one row per file where the ParamGroup column
        indicates which group each scan is a part of.
    param_groups_with_counts : :obj:`pandas.DataFrame`
        A data frame with param group summaries.
    """
    if not files:
        print("WARNING: no files for", entity_set_name)
        return None, None

    # Split the config into separate parts
    imaging_params = grouping_config.get("sidecar_params", {})
    imaging_params = imaging_params[modality]

    relational_params = grouping_config.get("relational_params", {})

    derived_params = grouping_config.get("derived_params")
    derived_params = derived_params[modality]

    imaging_params.update(derived_params)

    dfs = []
    # path needs to be relative to the root with no leading prefix

    for path in files:
        # metadata = layout.get_metadata(path)
        metadata = get_sidecar_metadata(img_to_new_ext(path, ".json"))
        if metadata == "Erroneous sidecar":
            print("Error parsing sidecar: ", img_to_new_ext(path, ".json"))
        else:
            intentions = metadata.get("IntendedFor", [])
            slice_times = metadata.get("SliceTiming", [])

            wanted_keys = metadata.keys() & imaging_params
            example_data = {key: metadata[key] for key in wanted_keys}
            example_data["EntitySet"] = entity_set_name

            # Get the fieldmaps out and add their types
            if "FieldmapKey" in relational_params:
                fieldmap_types = sorted(
                    [_file_to_entity_set(fmap.path) for fmap in fieldmap_lookup[path]]
                )

                # check if config says columns or bool
                if relational_params["FieldmapKey"]["display_mode"] == "bool":
                    if len(fieldmap_types) > 0:
                        example_data["HasFieldmap"] = True
                    else:
                        example_data["HasFieldmap"] = False
                else:
                    for fmap_num, fmap_type in enumerate(fieldmap_types):
                        example_data[f"FieldmapKey{fmap_num:02d}"] = fmap_type

            # Add the number of slice times specified
            if "NSliceTimes" in derived_params:
                example_data["NSliceTimes"] = len(slice_times)

            example_data["FilePath"] = path

            # If it's a fieldmap, see what entity set it's intended to correct
            if "IntendedForKey" in relational_params:
                intended_entity_sets = sorted(
                    [_file_to_entity_set(intention) for intention in intentions]
                )

                # check if config says columns or bool
                if relational_params["IntendedForKey"]["display_mode"] == "bool":
                    if len(intended_entity_sets) > 0:
                        example_data["UsedAsFieldmap"] = True
                    else:
                        example_data["UsedAsFieldmap"] = False
                else:
                    for intention_num, intention_entity_set in enumerate(intended_entity_sets):
                        example_data[f"IntendedForKey{intention_num:02d}"] = intention_entity_set

            dfs.append(example_data)

    # Assign each file to a ParamGroup based on the unique set of parameters
    # Round numeric parameters based on precision
    df = round_params(pd.DataFrame(dfs), grouping_config, modality)

    # Cluster parameters based on tolerance
    df = cluster_single_parameters(df, grouping_config, modality)
    # param_group_cols = list(set(df.columns.to_list()) - set(["FilePath"]))

    # Create parameter group DataFrame (summary_tsv) by removing filenames
    # and dropping duplicate rows of parameters.
    # Get the subset of columns to drop duplicates by.
    check_cols = []
    for col in list(df.columns):
        if f"Cluster_{col}" not in list(df.columns) and col != "FilePath":
            check_cols.append(col)

    # Find the unique ParamGroups and assign ID numbers in "ParamGroup"
    try:
        deduped = df.drop("FilePath", axis=1)
    except Exception:
        return "erroneous sidecar found"

    deduped = deduped.drop_duplicates(subset=check_cols, ignore_index=True)
    deduped["ParamGroup"] = np.arange(deduped.shape[0]) + 1

    # add the modality as a column
    deduped["Modality"] = modality

    # add entity set count column (will delete later)
    deduped["EntitySetCount"] = len(keys_files[entity_set_name])

    # Add the ParamGroup to the whole list of files
    labeled_files = pd.merge(df, deduped, on=check_cols)

    value_counts = labeled_files.ParamGroup.value_counts()

    param_group_counts = pd.DataFrame(
        {"Counts": value_counts.to_numpy(), "ParamGroup": value_counts.index.to_numpy()}
    )

    param_groups_with_counts = pd.merge(deduped, param_group_counts, on=["ParamGroup"])

    # Sort by counts and relabel the param groups
    param_groups_with_counts.sort_values(by=["Counts"], inplace=True, ascending=False)
    param_groups_with_counts["ParamGroup"] = np.arange(param_groups_with_counts.shape[0]) + 1

    # Send the new, ordered param group ids to the files list
    ordered_labeled_files = pd.merge(
        df, param_groups_with_counts, on=check_cols, suffixes=("_x", "")
    )

    # sort ordered_labeled_files by param group
    ordered_labeled_files.sort_values(by=["Counts"], inplace=True, ascending=False)

    return ordered_labeled_files, param_groups_with_counts


def round_params(df, config, modality):
    """Round columns' values in a DataFrame according to requested precision.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing the parameters to be rounded, with one row per file.
    config : dict
        Configuration dictionary containing rounding precision information.
    modality : str
        The modality key to access the relevant rounding precision settings in the config.

    Returns
    -------
    pandas.DataFrame
        Modified DataFrame with the specified columns' values rounded to the requested precision.

    Raises
    ------
    ValueError
        If the data type of the column is not supported for rounding, such as strings.
    """
    df = df.copy()  # don't modify DataFrame in place

    to_format = config["sidecar_params"][modality]
    to_format.update(config["derived_params"][modality])

    for column_name, column_fmt in to_format.items():
        if column_name not in df:
            continue

        if "precision" in column_fmt:
            precision = column_fmt["precision"]
            if df[column_name].apply(lambda x: isinstance(x, (float, int))).any():
                df[column_name] = df[column_name].round(precision)
            elif df[column_name].apply(lambda x: isinstance(x, (list, np.ndarray))).any():
                df[column_name] = df[column_name].apply(
                    lambda x: np.round(x, precision) if isinstance(x, (list, np.ndarray)) else x
                )
            else:
                raise ValueError(f"Unsupported data type for rounding in column {column_name}")

    return df


def get_sidecar_metadata(json_file):
    """Get all metadata values in a file's sidecar.

    Transform JSON dictionary to Python dictionary.

    Parameters
    ----------
    json_file : str
        Path to the JSON sidecar file.

    Returns
    -------
    dict or str
        Returns a dictionary containing the metadata if the file is successfully read,
        otherwise returns the string "Erroneous sidecar".

    Raises
    ------
    Exception
        If there is an error loading the JSON file.
    """
    try:
        with open(json_file) as json_file:
            data = json.load(json_file)
            return data
    except Exception:
        # print("Error loading sidecar: ", json_filename)
        return "Erroneous sidecar"


def cluster_single_parameters(files_df, config, modality):
    """Run agglomerative clustering on individual parameters and add cluster columns to dataframe.

    Parameters
    ----------
    files_df : :obj:`pandas.DataFrame`
        A data frame with one row per file and separate columns for parameters to cluster.
    config : :obj:`dict`
        Configuration that defines which columns to cluster.
        This dictionary has two relevant keys: ``'sidecar_params'`` and ``'derived_params'``.
    modality : :obj:`str`
        Modality of the scan.
        This is used to select the correct configuration from the config dict.

    Returns
    -------
    files_df : :obj:`pandas.DataFrame`
        An updated version of the input data frame,
        with a new column added for each element in the modality's
        ``'sidecar_params'`` and ``'derived_params'`` dictionaries.
        The new columns will have the name ``'Cluster_' + column_name``,
        and will contain the cluster labels for each parameter group.

    Notes
    -----
    ``'sidecar_params'`` is a dictionary of dictionaries, where keys are modalities.
    The modality-wise dictionary's keys are names of BIDS fields to directly include
    in the Parameter Groupings,
    and the values describe the parameters by which those BIDS' fields are compared.
    For example,
    {"RepetitionTime": {"tolerance": 0.000001, "precision": 6, "suggest_variant_rename": True}
    means that the RepetitionTime field should be compared across files and flagged as a
    variant if it differs from others by 0.000001 or more.

    ``'derived_params'`` is a dictionary of dictionaries, where keys are modalities.
    The modality-wise dictionary's keys are names of BIDS fields to derive from the
    NIfTI header and include in the Parameter Groupings.
    """
    to_format = config["sidecar_params"][modality]
    to_format.update(config["derived_params"][modality])

    for column_name, column_fmt in to_format.items():
        if column_name not in files_df:
            continue

        if "tolerance" in column_fmt and len(files_df) > 1:
            column_data = files_df[column_name].to_numpy()

            if any(isinstance(x, list) for x in column_data):
                # For array/list data, we should first define "clusters" based on the number of
                # elements, then apply the clustering within each set of lengths.
                # For example, if there are four runs with five elements and 10 runs with three
                # elements, we should cluster the five-element runs separately from the
                # three-element runs, and account for that in the clustering labels.
                lengths = ["x".join(str(i) for i in np.array(x).shape) for x in column_data]
                unique_lengths = np.unique(lengths)
                cluster_idx = 0
                for unique_length in unique_lengths:
                    sel_rows = [i for i, x in enumerate(lengths) if x == unique_length]
                    array = np.array([np.array(x) for x in column_data[sel_rows]])

                    if array.shape[0] > 1:
                        # clustering requires at least two samples
                        array[np.isnan(array)] = -999

                        tolerance = to_format[column_name]["tolerance"]
                        clustering = AgglomerativeClustering(
                            n_clusters=None, distance_threshold=tolerance, linkage="complete"
                        ).fit(array)

                        files_df.loc[sel_rows, f"Cluster_{column_name}"] = (
                            clustering.labels_ + cluster_idx
                        )
                        cluster_idx += max(clustering.labels_) + 1
                    else:
                        # single-file cluster
                        files_df.loc[sel_rows, f"Cluster_{column_name}"] = cluster_idx
                        cluster_idx += 1
            else:
                array = column_data.reshape(-1, 1)
                array[np.isnan(array)] = -999

                tolerance = to_format[column_name]["tolerance"]
                clustering = AgglomerativeClustering(
                    n_clusters=None, distance_threshold=tolerance, linkage="complete"
                ).fit(array)

                # now add clustering_labels as a column
                files_df[f"Cluster_{column_name}"] = clustering.labels_

        else:
            # We can rely on string matching (done separately) for string-type fields,
            # but arrays of strings need to be handled differently.
            column_data = files_df[column_name].tolist()

            if any(isinstance(x, list) for x in column_data):
                cluster_idx = 0

                column_data = ["|&|".join(str(val) for val in cell) for cell in column_data]
                unique_vals = np.unique(column_data)
                for val in unique_vals:
                    sel_rows = [i for i, x in enumerate(column_data) if x == val]
                    files_df.loc[sel_rows, f"Cluster_{column_name}"] = cluster_idx
                    cluster_idx += 1

    return files_df


def _order_columns(df):
    """Organize columns of the summary and files DataFrames.

    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame whose columns need to be organized.

    Returns
    -------
    pandas.DataFrame
        The DataFrame with columns organized such that 'EntitySet' and
        'ParamGroup' are the first two columns, 'FilePath' is the last
        column (if present), and the remaining columns are sorted
        alphabetically.

    Notes
    -----
    This is the only place where the constant ID_VARS is used,
    and the strings in that constant are hardcoded here,
    so we might not need that constant at all.
    """
    cols = set(df.columns.to_list())
    non_id_cols = cols - ID_VARS
    new_columns = ["EntitySet", "ParamGroup"] + sorted(non_id_cols)
    if "FilePath" in cols:
        new_columns.append("FilePath")

    df = df[new_columns]

    return df[new_columns]


def img_to_new_ext(img_path, new_ext):
    """Convert an image file path to a new extension.

    Parameters
    ----------
    img_path : str
        The file path of the image to be converted.
    new_ext : str
        The new extension to be applied to the image file path.

    Returns
    -------
    str
        The file path with the new extension applied.

    Examples
    --------
    >>> img_to_new_ext('/path/to/file_image.nii.gz', '.tsv')
    '/path/to/file_events.tsv'

    >>> img_to_new_ext('/path/to/file_image.nii.gz', '.tsv.gz')
    '/path/to/file_physio.tsv.gz'

    >>> img_to_new_ext('/path/to/file_image.nii.gz', '.json')
    '/path/to/file_image.json'

    Notes
    -----
    The hardcoded suffix associated with each extension may not be comprehensive.
    BIDS has been extended a lot in recent years.
    """
    # handle .tsv edge case
    if new_ext == ".tsv":
        # take out suffix
        return img_path.rpartition("_")[0] + "_events" + new_ext
    elif new_ext == ".tsv.gz":
        return img_path.rpartition("_")[0] + "_physio" + new_ext
    else:
        return img_path.replace(".nii.gz", "").replace(".nii", "") + new_ext


def get_entity_value(path, key):
    """Given a filepath and BIDS key name, return the value associated with the key.

    Parameters
    ----------
    path : str
        The file path to be parsed.
    key : str
        The BIDS key name to search for in the file path.

    Returns
    -------
    str or None
        The value associated with the BIDS key if found, otherwise None.

    Examples
    --------
    >>> get_entity_value('/path/to/sub-01/ses-01/func/sub-01_ses-02_task-rest_bold.nii.gz', 'sub')
    'sub-01'
    >>> get_entity_value('/path/to/sub-01/ses-02/func/sub-01_ses-02_task-rest_bold.nii.gz', 'ses')
    'ses-02'
    """
    parts = Path(path).parts
    for part in parts:
        if part.startswith(key + "-"):
            return part


def build_path(filepath, entities, out_dir, is_longitudinal):
    """Build a new path for a file based on its BIDS entities.

    Parameters
    ----------
    filepath : str
        The original file path.
    entities : dict
        A dictionary of BIDS entities.
        This should include all of the entities in the filename *except* for subject and session.
    out_dir : str
        The output directory for the new file.
    is_longitudinal : bool
        If True, add "ses" to file path.

    Returns
    -------
    new_path : str
        The new file path.

    Examples
    --------
    >>> build_path(
    ...    "/input/sub-01/ses-01/anat/sub-01_ses-01_T1w.nii.gz",
    ...    {"acquisition": "VAR", "suffix": "T2w"},
    ...    "/output",
    ...    True,
    ... )
    '/output/sub-01/ses-01/anat/sub-01_ses-01_acq-VAR_T2w.nii.gz'

    The function does not add an extra leading zero to the run entity when it's a string.
    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_bold.nii.gz",
    ...    {"task": "rest", "run": "2", "acquisition": "VAR", "suffix": "bold"},
    ...    "/output",
    ...    True,
    ... )
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-rest_acq-VAR_run-2_bold.nii.gz'

    The function adds an extra leading zero to the run entity when it's an integer
    and the original filename has a leading zero.
    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-00001_bold.nii.gz",
    ...    {"task": "rest", "run": 2, "acquisition": "VAR", "suffix": "bold"},
    ...    "/output",
    ...    True,
    ... )
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-rest_acq-VAR_run-00002_bold.nii.gz'

    The function does not add an extra leading zero to the run entity when it's an integer
    and the original filename doesn't have a leading zero.
    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-1_bold.nii.gz",
    ...    {"task": "rest", "run": 2, "acquisition": "VAR", "suffix": "bold"},
    ...    "/output",
    ...    True,
    ... )
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-rest_acq-VAR_run-2_bold.nii.gz'

    The function doesn't add an extra leading zero to the run entity when there isn't a zero.
    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-1_bold.nii.gz",
    ...    {"task": "rest", "run": "2", "acquisition": "VAR", "suffix": "bold"},
    ...    "/output",
    ...    True,
    ... )
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-rest_acq-VAR_run-2_bold.nii.gz'

    Entities in the original path, but not the entity dictionary, are not included,
    like run in this case.
    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_bold.nii.gz",
    ...    {"task": "rest", "acquisition": "VAR", "suffix": "bold"},
    ...    "/output",
    ...    True,
    ... )
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-rest_acq-VAR_bold.nii.gz'

    Entities outside of the prescribed list are ignored, such as "subject"...
    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_bold.nii.gz",
    ...    {"subject": "02", "task": "rest", "acquisition": "VAR", "suffix": "bold"},
    ...    "/output",
    ...    True,
    ... )
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-rest_acq-VAR_bold.nii.gz'

    or "echo".
    >>> build_path(
    ...    "/input/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_bold.nii.gz",
    ...    {"task": "rest", "acquisition": "VAR", "echo": 1, "suffix": "bold"},
    ...    "/output",
    ...    True,
    ... )
    '/output/sub-01/ses-01/func/sub-01_ses-01_task-rest_acq-VAR_bold.nii.gz'

    It can change the datatype, but will warn the user.
    >>> build_path(
    ...    "/input/sub-01/ses-01/anat/sub-01_ses-01_asl.nii.gz",
    ...    {"datatype": "perf", "acquisition": "VAR", "suffix": "asl"},
    ...    "/output",
    ...    True,
    ... )
    WARNING: DATATYPE CHANGE DETECTED
    '/output/sub-01/ses-01/perf/sub-01_ses-01_acq-VAR_asl.nii.gz'

    It also works for cross-sectional filename.
    >>> build_path(
    ...    "/input/sub-01/func/sub-01_task-rest_run-01_bold.nii.gz",
    ...    {"task": "rest", "acquisition": "VAR", "suffix": "bold"},
    ...    "/output",
    ...    False,
    ... )
    '/output/sub-01/func/sub-01_task-rest_acq-VAR_bold.nii.gz'
    """
    exts = Path(filepath).suffixes
    old_ext = "".join(exts)

    suffix = entities["suffix"]
    entity_file_keys = []

    # Entities that may be in the filename?
    file_keys = ["task", "acquisition", "direction", "reconstruction", "run"]

    for key in file_keys:
        if key in list(entities.keys()):
            entity_file_keys.append(key)

    sub = get_entity_value(filepath, "sub")
    if sub is None:
        raise ValueError(f"Could not extract subject from {filepath}")

    if is_longitudinal:
        ses = get_entity_value(filepath, "ses")
        if ses is None:
            raise ValueError(f"Could not extract session from {filepath}")

    # Add leading zeros to run entity if it's an integer.
    # If it's a string, respect the value provided.
    if "run" in entities.keys() and isinstance(entities["run"], int):
        # Infer the number of leading zeros needed from the original filename
        n_leading = 2  # default to 1 leading zero
        if "_run-" in filepath:
            run_str = filepath.split("_run-")[1].split("_")[0]
            n_leading = len(run_str)
        entities["run"] = str(entities["run"]).zfill(n_leading)

    filename = "_".join([f"{key}-{entities[key]}" for key in entity_file_keys])
    filename = (
        filename.replace("acquisition", "acq")
        .replace("direction", "dir")
        .replace("reconstruction", "rec")
    )
    if len(filename) > 0:
        if is_longitudinal:
            filename = f"{sub}_{ses}_{filename}_{suffix}{old_ext}"
        elif not is_longitudinal:
            filename = f"{sub}_{filename}_{suffix}{old_ext}"
    else:
        raise ValueError(f"Could not construct new filename for {filepath}")

    # CHECK TO SEE IF DATATYPE CHANGED
    # datatype may be overridden/changed if the original file is located in the wrong folder.
    dtypes = ["anat", "func", "perf", "fmap", "dwi"]
    dtype_orig = ""
    for dtype in dtypes:
        if dtype in filepath:
            dtype_orig = dtype

    if "datatype" in entities.keys():
        dtype_new = entities["datatype"]
        if entities["datatype"] != dtype_orig:
            print("WARNING: DATATYPE CHANGE DETECTED")
    else:
        dtype_new = dtype_orig

    # Construct the new filename
    if is_longitudinal:
        new_path = str(Path(out_dir) / sub / ses / dtype_new / filename)
    elif not is_longitudinal:
        new_path = str(Path(out_dir) / sub / dtype_new / filename)

    return new_path


def assign_variants(summary, rename_cols):
    """Assign variant names to files based on differences from dominant group.

    Parameters
    ----------
    summary : pandas.DataFrame
        The summary DataFrame containing the metadata for each file.
        The columns that are used include "ParamGroup", "EntitySet",
        the columns in ``rename_cols``,
        and any columns in ``rename_cols`` that are prefixed with "Cluster_".
    rename_cols : list of str
        A list of column names to use for renaming files.
        The values in these columns will be compared against the dominant group
        and labeled with a variant name if they differ.

    Returns
    -------
    pandas.DataFrame
        The updated summary DataFrame with a new column "RenameEntitySet"
        containing the new entity set names for each file.
    """
    # loop through summary tsv and create dom_dict
    dom_dict = {}
    for row in range(len(summary)):
        # if dominant group identified
        if str(summary.loc[row, "ParamGroup"]) == "1":
            val = {}
            # grab col, all vals send to dict
            key = summary.loc[row, "EntitySet"]
            for col in rename_cols:
                summary[col] = summary[col].apply(str)
                val[col] = summary.loc[row, col]

                if f"Cluster_{col}" in summary.columns:
                    val[f"Cluster_{col}"] = summary.loc[row, f"Cluster_{col}"]

            dom_dict[key] = val

    # now loop through again and ID variance
    for row in range(len(summary)):
        # check to see if renaming has already happened
        renamed = False
        entities = _entity_set_to_entities(summary.loc[row, "EntitySet"])
        if "VARIANT" in summary.loc[row, "EntitySet"]:
            renamed = True

        if summary.loc[row, "ParamGroup"] != 1 and not renamed:
            acq_str = "VARIANT"
            # now we know we have a deviant param group
            # check if TR is same as param group 1
            entity_set = summary.loc[row, "EntitySet"]
            for col in rename_cols:
                dom_entity_set = dom_dict[entity_set]
                summary[col] = summary[col].apply(str)

                if f"Cluster_{col}" in dom_entity_set.keys():
                    if summary.loc[row, f"Cluster_{col}"] != dom_entity_set[f"Cluster_{col}"]:
                        acq_str += col
                elif summary.loc[row, col] != dom_entity_set[col]:
                    if col == "HasFieldmap":
                        if dom_entity_set[col] == "True":
                            acq_str += "NoFmap"
                        else:
                            acq_str += "HasFmap"
                    elif col == "UsedAsFieldmap":
                        if dom_entity_set[col] == "True":
                            acq_str += "Unused"
                        else:
                            acq_str += "IsUsed"
                    else:
                        acq_str += col

            if acq_str == "VARIANT":
                acq_str += "Other"

            if "acquisition" in entities.keys():
                acq = f"acquisition-{entities['acquisition'] + acq_str}"

                new_name = summary.loc[row, "EntitySet"].replace(
                    f"acquisition-{entities['acquisition']}",
                    acq,
                )
            else:
                acq = f"acquisition-{acq_str}"
                new_name = acq + "_" + summary.loc[row, "EntitySet"]

            summary.at[row, "RenameEntitySet"] = new_name

        # convert all "nan" to empty str
        # so they don't show up in the summary tsv
        if summary.loc[row, "RenameEntitySet"] == "nan":
            summary.at[row, "RenameEntitySet"] = ""

        for col in rename_cols:
            if summary.loc[row, col] == "nan":
                summary.at[row, col] = ""

    return summary
