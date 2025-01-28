"""Console script for cubids.

This module provides command-line interface (CLI) tools for CuBIDS, a BIDS dataset
validation and manipulation toolkit. The CLI tools include functionalities for
validating BIDS datasets, merging sidecar JSON files, grouping acquisition parameters,
applying changes, purging associations, adding NIfTI information, copying exemplar
subjects, undoing changes, saving with DataLad, and managing metadata fields.

Each function that serves as an entry point for a CLI command in the format of `cubids-function`
is marked as deprecated and will be removed in the future. Users are advised to use the
corresponding `cubids function` commands instead.
"""

import argparse
import logging
import os
import warnings
from functools import partial
from pathlib import Path

from cubids import workflows

warnings.simplefilter(action="ignore", category=FutureWarning)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cubids-cli")
GIT_CONFIG = os.path.join(os.path.expanduser("~"), ".gitconfig")
logging.getLogger("datalad").setLevel(logging.ERROR)


def _path_exists(path, parser):
    """Ensure a given path exists.

    Parameters
    ----------
    path : str or None
        The path to check for existence. If None or the path does not exist, an error is raised.
    parser : argparse.ArgumentParser
        The argument parser instance used to raise an error if the path does not exist.

    Returns
    -------
    pathlib.Path
        The absolute path if it exists.

    Raises
    ------
    argparse.ArgumentError
        If the path does not exist or is None.
    """
    if path is not None:
        path = Path(path)

    if path is None or not path.exists():
        raise parser.error(f"Path does not exist: <{path.absolute()}>.")
    return path.absolute()


def _is_file(path, parser):
    """Ensure a given path exists and it is a file.

    Parameters
    ----------
    path : str or Path
        The path to check.
    parser : argparse.ArgumentParser
        The argument parser instance to use for error reporting.

    Returns
    -------
    Path
        The validated path as a Path object.

    Raises
    ------
    argparse.ArgumentError
        If the path does not exist or is not a file.
    """
    path = _path_exists(path, parser)
    if not path.is_file():
        raise parser.error(
            f"Path should point to a file (or symlink of file): <{path.absolute()}>."
        )
    return path


def _parse_validate():
    """Create and configure the argument parser for the `cubids validate` command.

    This function sets up an argument parser with various options for running
    the BIDS validator, including specifying the BIDS dataset directory, output
    file prefix, and additional validation options.

    Parameters
    ----------
    None

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser for the `cubids validate` command.

    Notes
    -----
    The following arguments are added to the parser:

    - bids_dir: The root of a BIDS dataset. It should contain sub-X directories
      and dataset_description.json.
    - output_prefix: File prefix to which tabulated validator output is written.
      If a filename prefix is provided, the output will be placed in
      bids_dir/code/CuBIDS. If a full path is provided, the output files will
      go to the specified location.
    - --sequential: Run the BIDS validator sequentially on each subject.
    - --container: Docker image tag or Singularity image file.
    - --ignore-nifti-headers: Disregard NIfTI header content during validation.
    - --sequential-subjects: Filter the sequential run to only include the
      listed subjects.
    """
    parser = argparse.ArgumentParser(
        description="cubids validate: Wrapper around the official BIDS Validator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
    )
    PathExists = partial(_path_exists, parser=parser)

    parser.add_argument(
        "bids_dir",
        type=PathExists,
        action="store",
        help=(
            "The root of a BIDS dataset. It should contain "
            "sub-X directories and dataset_description.json"
        ),
    )
    parser.add_argument(
        "output_prefix",
        type=Path,
        action="store",
        help=(
            "file prefix to which tabulated validator output "
            "is written. If users pass in just a filename prefix "
            "e.g. V1, then CuBIDS will put the validation "
            "output in bids_dir/code/CuBIDS. If the user "
            "specifies a path (e.g. /Users/scovitz/BIDS/V1) "
            "then output files will go to the specified location."
        ),
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        default=False,
        help="Run the BIDS validator sequentially on each subject.",
        required=False,
    )
    parser.add_argument(
        "--ignore-nifti-headers",
        action="store_true",
        default=False,
        help="Disregard NIfTI header content during validation",
        required=False,
    )
    parser.add_argument(
        "--sequential-subjects",
        action="store",
        default=None,
        help=(
            "List: Filter the sequential run to only include "
            "the listed subjects. e.g. --sequential-subjects "
            "sub-01 sub-02 sub-03"
        ),
        nargs="+",
        required=False,
    )
    parser.add_argument(
        "--local-validator",
        action="store_true",
        default=False,
        help="Lets user run a locally installed BIDS validator. Default is set to False ",
        required=False,
    )
    return parser


def _enter_validate(argv=None):
    """Entry point for the `cubids-validate` command.

    This function is deprecated and will be removed in the future.
    Please use 'cubids validate' instead.

    Parameters
    ----------
    argv : list, optional
        List of command-line arguments. If None, defaults to sys.argv.

    Warns
    -----
    DeprecationWarning
        Indicates that this function is deprecated.

    Notes
    -----
    This function parses the command-line arguments and calls the
    `workflows.validate` function with the parsed arguments.
    """
    warnings.warn(
        "cubids-validate is deprecated and will be removed in the future. "
        "Please use cubids validate.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_validate().parse_args(argv)
    args = vars(options).copy()
    workflows.validate(**args)


def _parse_bids_version():
    """Parse command-line arguments for the `cubids bids-version` command.

    This function sets up an argument parser for the `cubids bids-version` command,
    which retrieves the BIDS Validator and Schema version for a given BIDS dataset.

    Parameters
    ----------
    None

    Returns
    -------
    argparse.ArgumentParser
        The argument parser configured for the `cubids bids-version` command.

    Notes
    -----
    The parser includes the following arguments:

    - `bids_dir`: The root directory of a BIDS dataset, which should contain
      sub-X directories and a dataset_description.json file.
    - `--write`: A flag to save the validator and schema version to
      'dataset_description.json'. If not provided, the versions are printed
      to the terminal.
    """
    parser = argparse.ArgumentParser(
        description="cubids bids-version: Get BIDS Validator and Schema version",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
    )
    PathExists = partial(_path_exists, parser=parser)

    parser.add_argument(
        "bids_dir",
        type=PathExists,
        action="store",
        help=(
            "The root of a BIDS dataset. It should contain "
            "sub-X directories and dataset_description.json"
        ),
    )
    parser.add_argument(
        "--write",
        action="store_true",
        default=False,
        help=(
            "Save the validator and schema version to 'dataset_description.json' "
            "when using `cubids bids-version /bids/path --write`. "
            "By default, `cubids bids-version /bids/path` prints to the terminal."
        ),
    )
    return parser


def _enter_bids_version(argv=None):
    """Entry point for the deprecated `cubids-bids-version`.

    This function serves as the entry point for the BIDS version command-line
    functionality. It parses command-line arguments, issues a deprecation
    warning, and invokes the corresponding workflow.

    Parameters
    ----------
    argv : list, optional
        List of command-line arguments. If None, defaults to `sys.argv`.

    Returns
    -------
    None

    Warns
    -----
    DeprecationWarning
        Indicates that the `cubids-bids-version` command is deprecated and
        will be removed in the future.
    """
    warnings.warn(
        "cubids-bids-version is deprecated and will be removed in the future. "
        "Please use cubids bids-version.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_bids_version().parse_args(argv)
    args = vars(options).copy()
    workflows.bids_version(**args)


def _parse_bids_sidecar_merge():
    """Create an argument parser for the `cubids bids-sidecar-merge` command.

    This function sets up an argument parser for the `cubids bids-sidecar-merge` command-line tool,
    which merges critical keys from one BIDS sidecar JSON file into another.

    Parameters
    ----------
    from_json : str
        Source JSON file path. This file contains the data to be copied.
    to_json : str
        Destination JSON file path. This file will have data from `from_json` copied into it.

    Returns
    -------
    argparse.ArgumentParser
        The argument parser with the necessary arguments configured.

    Notes
    -----
    The `IsFile` partial function is used to validate that the provided file paths exist.
    """
    parser = argparse.ArgumentParser(
        description=("bids-sidecar-merge: merge critical keys from one sidecar to another"),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
    )
    IsFile = partial(_is_file, parser=parser)

    parser.add_argument(
        "from_json",
        type=IsFile,
        action="store",
        help="Source json file.",
    )
    parser.add_argument(
        "to_json",
        type=IsFile,
        action="store",
        help="destination json. This file will have data from `from_json` copied into it.",
    )
    return parser


def _enter_bids_sidecar_merge(argv=None):
    """Entry point for the deprecated `cubids-bids-sidecar-merge command`.

    This function serves as the entry point for the `cubids-bids-sidecar-merge`.
    It parses command-line arguments, issues a deprecation
    warning, and invokes the corresponding workflow.

    Parameters
    ----------
    argv : list, optional
        List of command-line arguments. If None, defaults to `sys.argv`.

    Warns
    -----
    DeprecationWarning
        Indicates that the `bids-sidecar-merge` command is deprecated and
        will be removed in the future.
    """
    warnings.warn(
        "bids-sidecar-merge is deprecated and will be removed in the future. "
        "Please use cubids bids-sidecar-merge.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_bids_sidecar_merge().parse_args(argv)
    args = vars(options).copy()
    workflows.bids_sidecar_merge(**args)


def _parse_group():
    """Parse command-line arguments for the `cubids group` command.

    This function sets up an argument parser for the `cubids group` command,
    which is used to find key and parameter groups in a BIDS dataset.

    Parameters
    ----------
    None

    Returns
    -------
    argparse.ArgumentParser
        The argument parser with the defined arguments.

    Arguments
    ---------
    bids_dir : str
        The root of a BIDS dataset. It should contain sub-X directories and
        dataset_description.json.
    output_prefix : str
        File prefix to which a _summary.tsv, _files.tsv, _AcqGrouping.tsv, and
        _AcqGroupInfo.txt are written. If a filename prefix is provided (e.g., V1),
        the outputs will be placed in bids_dir/code/CuBIDS. If a path is specified
        (e.g., /Users/scovitz/BIDS/V1), the output files will go to the specified location.
    --container : str, optional
        Docker image tag or Singularity image file.
    --acq-group-level : {'subject', 'session'}, optional
        Level at which acquisition groups are created. Options are 'subject' or 'session'.
        Default is 'subject'.
    --config : str, optional
        Path to a config file for grouping. If not provided, the default config file from
        CuBIDS will be used.
    """
    parser = argparse.ArgumentParser(
        description="cubids group: find key and parameter groups in BIDS",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
    )
    PathExists = partial(_path_exists, parser=parser)

    parser.add_argument(
        "bids_dir",
        type=PathExists,
        action="store",
        help=(
            "The root of a BIDS dataset. It should contain "
            "sub-X directories and dataset_description.json"
        ),
    )
    parser.add_argument(
        "output_prefix",
        type=Path,
        action="store",
        help=(
            "file prefix to which a _summary.tsv, _files.tsv "
            "_AcqGrouping.tsv, and _AcqGroupInfo.txt, are "
            "written. If users pass in just a filename prefix "
            "e.g. V1, then CuBIDS will put the four grouping "
            "outputs in bids_dir/code/CuBIDS. If the user "
            "specifies a path (e.g. /Users/scovitz/BIDS/V1 "
            "then output files will go to the specified location."
        ),
    )
    parser.add_argument(
        "--acq-group-level",
        default="subject",
        choices=["subject", "session"],
        action="store",
        help=("Level at which acquisition groups are created options: 'subject' or 'session'"),
    )
    parser.add_argument(
        "--config",
        action="store",
        type=PathExists,
        default=None,
        help=(
            "Path to a config file for grouping. "
            "If not provided, then the default config file from CuBIDS will be used."
        ),
    )
    return parser


def _enter_group(argv=None):
    """Entry point for the deprecated `cubids-group` command.

    This function issues a deprecation warning indicating that `cubids-group`
    is deprecated and will be removed in the future. It then parses the
    command-line arguments and invokes the `group` workflow with the parsed
    arguments.

    Parameters
    ----------
    argv : list, optional
        List of command-line arguments. If None, defaults to sys.argv.

    Warns
    -----
    DeprecationWarning
        Indicates that 'cubids-group' is deprecated and will be removed in
        the future.

    Returns
    -------
    None
    """
    warnings.warn(
        "cubids-group is deprecated and will be removed in the future. Please use cubids group.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_group().parse_args(argv)
    args = vars(options).copy()
    workflows.group(**args)


def _parse_apply():
    """Parse command-line arguments for the `cubids apply` command.

    This function sets up an argument parser for the `cubids apply` command,
    which applies changes specified in a TSV file to a BIDS directory.

    Parameters
    ----------
    bids_dir : str
        The root of a BIDS dataset. It should contain sub-X directories and
        dataset_description.json.
    edited_summary_tsv : str
        Path to the _summary.tsv that has been edited in the MergeInto and
        RenameEntitySet columns.
    files_tsv : str
        Path to the _files.tsv that has been edited in the MergeInto and
        RenameEntitySet columns.
    new_tsv_prefix : str
        File prefix for writing the post-apply grouping outputs.
    --use-datalad : bool, optional
        Ensure that there are no untracked changes before finding groups
        (default is False).
    --container : str, optional
        Docker image tag or Singularity image file.
    --acq-group-level : {'subject', 'session'}, optional
        Level at which acquisition groups are created (default is 'subject').
    --config : str, optional
        Path to a config file for grouping. If not provided, the default config
        file from CuBIDS will be used.

    Returns
    -------
    argparse.ArgumentParser
        The argument parser with the defined arguments.
    """
    parser = argparse.ArgumentParser(
        description=("cubids apply: apply the changes specified in a tsv to a BIDS directory"),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
    )
    PathExists = partial(_path_exists, parser=parser)
    IsFile = partial(_is_file, parser=parser)

    parser.add_argument(
        "bids_dir",
        type=PathExists,
        action="store",
        help=(
            "The root of a BIDS dataset. It should contain "
            "sub-X directories and dataset_description.json"
        ),
    )
    parser.add_argument(
        "edited_summary_tsv",
        type=Path,
        action="store",
        help=(
            "path to the _summary.tsv that has been edited "
            "in the MergeInto and RenameEntitySet columns. If the "
            " summary table is located in the code/CuBIDS "
            "directory, then users can just pass the summary tsv "
            "filename instead of the full path to the tsv"
        ),
    )
    parser.add_argument(
        "files_tsv",
        type=Path,
        action="store",
        help=(
            "path to the _files.tsv that has been edited "
            "in the MergeInto and RenameEntitySet columns. If the "
            "files table is located in the code/CuBIDS "
            "directory, then users can just pass the files tsv "
            "filename instead of the full path to the tsv"
        ),
    )
    parser.add_argument(
        "new_tsv_prefix",
        type=Path,
        action="store",
        help=(
            "file prefix for writing the post-apply grouping "
            "outputs. If users pass in just a filename prefix "
            "e.g. V2, then CuBIDS will put the four grouping "
            "outputs in bids_dir/code/CuBIDS. If the user "
            "specifies a path (e.g. /Users/scovitz/BIDS/V2 "
            "then output files will go to the specified location."
        ),
    )
    parser.add_argument(
        "--use-datalad",
        action="store_true",
        default=False,
        help="ensure that there are no untracked changes before finding groups",
    )
    parser.add_argument(
        "--acq-group-level",
        default="subject",
        choices=["subject", "session"],
        action="store",
        help=("Level at which acquisition groups are created options: 'subject' or 'session'"),
    )
    parser.add_argument(
        "--config",
        action="store",
        type=IsFile,
        default=None,
        help=(
            "Path to a config file for grouping. "
            "If not provided, then the default config file from CuBIDS will be used."
        ),
    )

    return parser


def _enter_apply(argv=None):
    """Entry point for the deprecated `cubids-apply` command.

    This function serves as a wrapper for the `cubids-apply` command and issues a
    deprecation warning. It parses the command-line arguments and invokes the
    `apply` workflow with the parsed arguments.

    Parameters
    ----------
    argv : list, optional
        List of command-line arguments. If None, the arguments will be taken from `sys.argv`.

    Warns
    -----
    DeprecationWarning
        Indicates that `cubids-apply` is deprecated and will be removed in the future.
    """
    warnings.warn(
        "cubids-apply is deprecated and will be removed in the future. Please use cubids apply.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_apply().parse_args(argv)
    args = vars(options).copy()
    workflows.apply(**args)


def _parse_datalad_save():
    """Create an argument parser for the `cubids datalad-save` command.

    This function sets up an argument parser for performing a DataLad save on a BIDS directory.
    It includes arguments for specifying the BIDS directory, a commit message, and an optional
    container image.

    Parameters
    ----------
    None

    Returns
    -------
    argparse.ArgumentParser
        The configured argument parser.

    Notes
    -----
    The `bids_dir` argument is required and should point to the root of a BIDS dataset, which
    must contain sub-X directories and a dataset_description.json file. The `-m` argument is
    used to provide a commit message, and the `--container` argument allows specifying a Docker
    image tag or Singularity image file.
    """
    parser = argparse.ArgumentParser(
        description=("cubids datalad-save: perform a DataLad save on a BIDS directory"),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
    )
    PathExists = partial(_path_exists, parser=parser)

    parser.add_argument(
        "bids_dir",
        type=PathExists,
        action="store",
        help=(
            "The root of a BIDS dataset. It should contain "
            "sub-X directories and dataset_description.json"
        ),
    )
    parser.add_argument(
        "-m",
        action="store",
        help="message for this commit",
    )

    return parser


def _enter_datalad_save(argv=None):
    """Entry point for the deprecated `cubids-datalad-save` command.

    This function serves as a warning that the `cubids-datalad-save` command is deprecated
    and will be removed in the future. It parses the command-line arguments and calls
    the `datalad_save` workflow with the parsed arguments.

    Parameters
    ----------
    argv : list, optional
        List of command-line arguments. If not provided, defaults to None.

    Warns
    -----
    DeprecationWarning
        Indicates that the `cubids-datalad-save` command is deprecated and
        will be removed in the future.

    See Also
    --------
    _parse_datalad_save : Function to parse command-line arguments for the datalad save operation.
    workflows.datalad_save : Function to perform the datalad save operation.
    """
    warnings.warn(
        "cubids-datalad-save is deprecated and will be removed in the future. "
        "Please use cubids datalad-save.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_datalad_save().parse_args(argv)
    args = vars(options).copy()
    workflows.datalad_save(**args)


def _parse_undo():
    """Create an argument parser for the `cubids undo` command.

    This function sets up an argument parser for the `cubids undo` command,
    which is used to revert the most recent commit in a BIDS dataset. It
    defines the required and optional arguments for the command.

    Parameters
    ----------
    None

    Returns
    -------
    argparse.ArgumentParser
        The argument parser for the `cubids undo` command.

    Notes
    -----
    The parser includes the following arguments:

    - bids_dir: The root of a BIDS dataset, which should contain sub-X directories
      and dataset_description.json.
    - container: Docker image tag or Singularity image file.
    """
    parser = argparse.ArgumentParser(
        description="cubids undo: revert most recent commit",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
    )
    PathExists = partial(_path_exists, parser=parser)

    parser.add_argument(
        "bids_dir",
        type=PathExists,
        action="store",
        help=(
            "The root of a BIDS dataset. It should contain "
            "sub-X directories and dataset_description.json"
        ),
    )

    return parser


def _enter_undo(argv=None):
    """Entry point for the deprecated `cubids-undo` command.

    This function is called when the `cubids-undo` command is executed.
    It displays a deprecation warning and then parses the command-line
    arguments to execute the undo workflow.

    Parameters
    ----------
    argv : list, optional
        List of command-line arguments. If None, the arguments from
        sys.argv are used.

    Warns
    -----
    DeprecationWarning
        Indicates that `cubids-undo` is deprecated and will be removed
        in the future. Users should use `cubids undo` instead.

    Returns
    -------
    None
    """
    warnings.warn(
        "cubids-undo is deprecated and will be removed in the future. Please use cubids undo.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_undo().parse_args(argv)
    args = vars(options).copy()
    workflows.undo(**args)


def _parse_copy_exemplars():
    """Parse command-line arguments for the `cubids copy-exemplars` script.

    This function sets up an argument parser for the `cubids copy-exemplars` script,
    which creates and saves a directory with one subject from each Acquisition Group
    in the BIDS dataset.

    Parameters
    ----------
    bids_dir : str
        Path to the root of a BIDS dataset. It should contain sub-X directories and
        dataset_description.json.
    exemplars_dir : str
        Name of the directory to create where to store the exemplar dataset. It will
        include one subject from each Acquisition Group. It should contain sub-X
        directories and dataset_description.json.
    exemplars_tsv : str
        Path to the .tsv file that lists one subject from each Acquisition Group
        (*_AcqGrouping.tsv from the cubids-group output). If the file is located in
        the code/CuBIDS directory, then users can just pass the .tsv filename instead
        of the full path.
    use_datalad : bool, optional
        Check exemplar dataset into DataLad (default is False).
    min_group_size : int, optional
        Minimum number of subjects an Acquisition Group must have in order to be
        included in the exemplar dataset (default is 1).
    container : str, optional
        Docker image tag or Singularity image file.
    force_unlock : bool, optional
        Unlock dataset before adding nifti info (default is False).

    Returns
    -------
    argparse.ArgumentParser
        The argument parser with the defined arguments.
    """
    parser = argparse.ArgumentParser(
        description=(
            "cubids copy-exemplars: create and save a directory with "
            "one subject from each Acquisition Group in the BIDS dataset"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
    )
    PathExists = partial(_path_exists, parser=parser)
    # IsFile = partial(_is_file, parser=parser)

    parser.add_argument(
        "bids_dir",
        type=PathExists,
        action="store",
        help=(
            "path to the root of a BIDS dataset. "
            "It should contain sub-X directories and "
            "dataset_description.json."
        ),
    )
    parser.add_argument(
        "exemplars_dir",
        type=Path,
        action="store",
        help=(
            "name of the directory to create where to store exemplar dataset. "
            "It will include one subject from each Acquisition Group. "
            "It should contain sub-X directories and "
            "dataset_description.json."
        ),
    )
    parser.add_argument(
        "exemplars_tsv",
        type=Path,
        action="store",
        help=(
            "path to the .tsv that lists one "
            "subject from each Acquisition Group "
            "(*_AcqGrouping.tsv from the cubids-group output). "
            "If the file is located in the code/CuBIDS "
            "directory, then users can just pass the .tsv "
            "filename instead of the full path "
        ),
    )
    parser.add_argument(
        "--use-datalad",
        action="store_true",
        default=False,
        help="check exemplar dataset into DataLad",
    )
    parser.add_argument(
        "--min-group-size",
        action="store",
        default=1,
        type=int,
        help=(
            "minimum number of subjects an Acquisition Group "
            "must have in order to be included in the exemplar "
            "dataset "
        ),
        required=False,
    )
    # parser.add_argument('--include-groups',
    #                     action='store',
    #                     nargs='+',
    #                     default=[],
    #                     help='only include an exemplar subject from these '
    #                     'listed Acquisition Groups in the exemplar dataset ',
    #                     required=False)
    parser.add_argument(
        "--force-unlock",
        action="store_true",
        default=False,
        help="unlock dataset before adding nifti info ",
    )
    return parser


def _enter_copy_exemplars(argv=None):
    """Entry point for the deprecated `cubids-copy-exemplars` command.

    This function is deprecated and will be removed in the future.
    It parses command-line arguments and invokes the `copy_exemplars`
    workflow with the parsed arguments.

    Parameters
    ----------
    argv : list, optional
        List of command-line arguments. If None, defaults to `sys.argv`.

    Warns
    -----
    DeprecationWarning
        Indicates that this function is deprecated and will be removed in the future.
    """
    warnings.warn(
        "cubids-copy-exemplars is deprecated and will be removed in the future. "
        "Please use cubids copy-exemplars.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_copy_exemplars().parse_args(argv)
    args = vars(options).copy()
    workflows.copy_exemplars(**args)


def _parse_add_nifti_info():
    """Parse command-line arguments for the `cubids add-nifti-info` command.

    This function sets up an argument parser for the `cubids add-nifti-info` command,
    which adds information from NIfTI files to the sidecars of each dataset in a BIDS
    directory.

    Parameters
    ----------
    bids_dir : str
        Absolute path to the root of a BIDS dataset. It should contain sub-X directories
        and dataset_description.json.
    use_datalad : bool, optional
        Ensure that there are no untracked changes before finding groups (default is False).
    force_unlock : bool, optional
        Unlock dataset before adding NIfTI info (default is False).
    container : str, optional
        Docker image tag or Singularity image file.

    Returns
    -------
    argparse.ArgumentParser
        The argument parser with the defined arguments.
    """
    parser = argparse.ArgumentParser(
        description=(
            "cubids add-nifti-info: Add information from nifti"
            "files to the sidecars of each dataset"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
    )
    PathExists = partial(_path_exists, parser=parser)

    parser.add_argument(
        "bids_dir",
        type=PathExists,
        action="store",
        help=(
            "absolute path to the root of a BIDS dataset. "
            "It should contain sub-X directories and "
            "dataset_description.json."
        ),
    )
    parser.add_argument(
        "--use-datalad",
        action="store_true",
        default=False,
        help="ensure that there are no untracked changes before finding groups",
    )
    parser.add_argument(
        "--force-unlock",
        action="store_true",
        default=False,
        help="unlock dataset before adding nifti info ",
    )
    return parser


def _enter_add_nifti_info(argv=None):
    """Entry point for the deprecated `cubids-add-nifti-info` command.

    This function is deprecated and will be removed in the future.
    Please use `cubids add-nifti-info` instead.

    Parameters
    ----------
    argv : list, optional
        List of command line arguments. If None, defaults to `sys.argv`.

    Warns
    -----
    DeprecationWarning
        Indicates that this function is deprecated.

    Notes
    -----
    This function parses command line arguments and invokes the
    `add_nifti_info` workflow with the parsed arguments.
    """
    warnings.warn(
        "cubids-add-nifti-info is deprecated and will be removed in the future. "
        "Please use cubids add-nifti-info.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_add_nifti_info().parse_args(argv)
    args = vars(options).copy()
    workflows.add_nifti_info(**args)


def _parse_purge():
    """Parse command-line arguments for the `cubids purge` command.

    This function sets up an argument parser for the `cubids purge` command,
    which is used to purge associations from a BIDS dataset. It defines the
    required arguments and options for the command.

    Parameters
    ----------
    None

    Returns
    -------
    argparse.ArgumentParser
        The argument parser with the defined arguments and options.

    Notes
    -----
    The following arguments are defined:

    - `bids_dir`: The root of a BIDS dataset. It should contain sub-X directories
        and dataset_description.json.
    - `scans`: Path to the txt file of scans whose associations should be purged.
    - `--use-datalad`: Ensure that there are no untracked changes before finding groups.
    - `--container`: Docker image tag or Singularity image file.
    """
    parser = argparse.ArgumentParser(
        description="cubids purge: purge associations from the dataset",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
    )
    PathExists = partial(_path_exists, parser=parser)
    IsFile = partial(_is_file, parser=parser)

    parser.add_argument(
        "bids_dir",
        type=PathExists,
        action="store",
        help=(
            "path to the root of a BIDS dataset. "
            "It should contain sub-X directories and "
            "dataset_description.json."
        ),
    )
    parser.add_argument(
        "scans",
        type=IsFile,
        action="store",
        help=(
            "path to the txt file of scans whose associations should be purged. "
            "When specifying files in this txt file, "
            "always use relative paths starting from your BIDS directory. "
            "e.g., ``sub-01/ses-01/func/sub-01_ses-01_task-rest_bold.nii.gz``"
        ),
    )
    parser.add_argument(
        "--use-datalad",
        action="store_true",
        default=False,
        help="ensure that there are no untracked changes before finding groups",
    )
    return parser


def _enter_purge(argv=None):
    """Entry point for the deprecated `cubids-purge` command.

    This function is deprecated and will be removed in the future.
    Please use `cubids purge` instead.

    Parameters
    ----------
    argv : list, optional
        List of command-line arguments. If None, defaults to sys.argv.

    Warns
    -----
    DeprecationWarning
        Indicates that this function is deprecated.

    Notes
    -----
    This function parses the command-line arguments and calls the
    `workflows.purge` function with the parsed arguments.
    """
    warnings.warn(
        "cubids-purge is deprecated and will be removed in the future. Please use cubids purge.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_purge().parse_args(argv)
    args = vars(options).copy()
    workflows.purge(**args)


def _parse_remove_metadata_fields():
    """Create an argument parser for the `cubids remove-metadata-fields` command.

    This function sets up an argument parser for the command-line interface (CLI)
    tool `cubids remove-metadata-fields`, which is used to delete specified fields
    from the metadata of a BIDS dataset.

    Parameters
    ----------
    None

    Returns
    -------
    argparse.ArgumentParser
        The argument parser configured for the `cubids remove-metadata-fields` CLI tool.

    Notes
    ---------
    The parser includes the following arguments:

    bids_dir : str
        The root directory of a BIDS dataset. It should contain sub-X directories and
        a dataset_description.json file.
    --fields : list of str, optional
        A space-separated list of metadata fields to remove. Defaults to an empty list.
    --container : str, optional
        Docker image tag or Singularity image file.
    """
    parser = argparse.ArgumentParser(
        description="cubids remove-metadata-fields: delete fields from metadata",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
    )
    PathExists = partial(_path_exists, parser=parser)

    parser.add_argument(
        "bids_dir",
        type=PathExists,
        action="store",
        help=(
            "The root of a BIDS dataset. It should contain "
            "sub-X directories and dataset_description.json"
        ),
    )
    parser.add_argument(
        "--fields",
        nargs="+",
        action="store",
        default=[],
        help="space-separated list of metadata fields to remove.",
    )

    return parser


def _enter_remove_metadata_fields(argv=None):
    """Entry point for the deprecated `cubids-remove-metadata-fields` command.

    This function serves as the entry point for the deprecated
    `cubids-remove-metadata-fields` command-line interface (CLI). It issues a
    deprecation warning and then parses the provided arguments to execute the
    `remove_metadata_fields` workflow.

    Parameters
    ----------
    argv : list, optional
        List of command-line arguments. If None, the default arguments will be used.

    Warns
    -----
    DeprecationWarning
        Indicates that the `cubids-remove-metadata-fields` CLI is deprecated and
        will be removed in the future. Users are advised to use
        `cubids remove-metadata-fields` instead.

    See Also
    --------
    _parse_remove_metadata_fields : Function to parse the command-line arguments.
    workflows.remove_metadata_fields : Workflow to remove metadata fields.
    """
    warnings.warn(
        "cubids-remove-metadata-fields is deprecated and will be removed in the future. "
        "Please use cubids remove-metadata-fields.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_remove_metadata_fields().parse_args(argv)
    args = vars(options).copy()
    workflows.remove_metadata_fields(**args)


def _parse_print_metadata_fields():
    """Create the parser for the `cubids print-metadata-fields` command.

    This function sets up an argument parser for the command that prints all
    unique metadata fields in a BIDS dataset. It defines the required arguments
    and their types, as well as optional arguments.

    Parameters
    ----------
    None

    Returns
    -------
    argparse.ArgumentParser
        The argument parser for the `cubids print-metadata-fields` command.

    Notes
    -----
    The parser includes the following arguments:

    - bids_dir: The root of a BIDS dataset, which should contain sub-X directories
        and dataset_description.json.
    - container: An optional argument specifying a Docker image tag or Singularity
        image file.
    """
    parser = argparse.ArgumentParser(
        description="cubids print-metadata-fields: print all unique metadata fields",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
    )
    PathExists = partial(_path_exists, parser=parser)

    parser.add_argument(
        "bids_dir",
        type=PathExists,
        action="store",
        help=(
            "The root of a BIDS dataset. It should contain "
            "sub-X directories and dataset_description.json"
        ),
    )

    return parser


def _enter_print_metadata_fields(argv=None):
    """Entry point for the deprecated `cubids-print-metadata-fields` command.

    This function parses the command-line arguments for `cubids-print-metadata-fields`,
    issues a deprecation warning, and then calls the `print_metadata_fields`
    function from the `workflows` module with the parsed arguments.

    Parameters
    ----------
    argv : list, optional
        List of command-line arguments. If None, the arguments will be taken from
        `sys.argv`.

    Warns
    -----
    DeprecationWarning
        Indicates that the `cubids-print-metadata-fields` command is deprecated
        and will be removed in the future.

    See Also
    --------
    workflows.print_metadata_fields : Function that prints metadata fields.
    """
    options = _parse_print_metadata_fields().parse_args(argv)
    args = vars(options).copy()
    warnings.warn(
        "cubids-print-metadata-fields is deprecated and will be removed in the future. "
        "Please use cubids print-metadata-fields.",
        DeprecationWarning,
        stacklevel=2,
    )
    workflows.print_metadata_fields(**args)


COMMANDS = [
    ("validate", _parse_validate, workflows.validate),
    ("bids-version", _parse_bids_version, workflows.bids_version),
    ("sidecar-merge", _parse_bids_sidecar_merge, workflows.bids_sidecar_merge),
    ("group", _parse_group, workflows.group),
    ("apply", _parse_apply, workflows.apply),
    ("purge", _parse_purge, workflows.purge),
    ("add-nifti-info", _parse_add_nifti_info, workflows.add_nifti_info),
    ("copy-exemplars", _parse_copy_exemplars, workflows.copy_exemplars),
    ("undo", _parse_undo, workflows.undo),
    ("datalad-save", _parse_datalad_save, workflows.datalad_save),
    ("print-metadata-fields", _parse_print_metadata_fields, workflows.print_metadata_fields),
    ("remove-metadata-fields", _parse_remove_metadata_fields, workflows.remove_metadata_fields),
]


def _get_parser():
    """Create the general `cubids` parser object.

    This function sets up the argument parser for the `cubids` command-line interface.
    It includes a version argument and dynamically adds subparsers for each command
    defined in the COMMANDS list.

    Returns
    -------
    argparse.ArgumentParser
        The argument parser for the "cubids" CLI.
    """
    from cubids import __version__

    parser = argparse.ArgumentParser(prog="cubids", allow_abbrev=False)
    parser.add_argument("-v", "--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(help="CuBIDS commands")

    for command, parser_func, run_func in COMMANDS:
        subparser = parser_func()
        subparser.set_defaults(func=run_func)
        subparsers.add_parser(
            command,
            parents=[subparser],
            help=subparser.description,
            add_help=False,
            allow_abbrev=False,
        )

    return parser


def _main(argv=None):
    """Entry point for `cubids` CLI.

    Parameters
    ----------
    argv : list, optional
        List of command-line arguments. If None, defaults to `sys.argv`.

    Returns
    -------
    None
    """
    options = _get_parser().parse_args(argv)
    args = vars(options).copy()
    args.pop("func")
    options.func(**args)
