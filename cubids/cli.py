"""Console script for cubids."""

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
    """Ensure a given path exists."""
    if path is None or not Path(path).exists():
        raise parser.error(f"Path does not exist: <{path}>.")
    return Path(path).absolute()


def _is_file(path, parser):
    """Ensure a given path exists and it is a file."""
    path = _path_exists(path, parser)
    if not path.is_file():
        raise parser.error(f"Path should point to a file (or symlink of file): <{path}>.")
    return path


def _parse_validate():
    parser = argparse.ArgumentParser(
        description="cubids-validate: Wrapper around the official BIDS Validator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
        "--container",
        action="store",
        help="Docker image tag or Singularity image file.",
        default=None,
    )
    parser.add_argument(
        "--ignore_nifti_headers",
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
    return parser


def _enter_validate(argv=None):
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
    parser = argparse.ArgumentParser(
        description="cubids bids-version: Get BIDS Validator and Schema version",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
    options = _parse_bids_version().parse_args(argv)
    args = vars(options).copy()
    workflows.bids_version(**args)


def _parse_bids_sidecar_merge():
    parser = argparse.ArgumentParser(
        description=("bids-sidecar-merge: merge critical keys from one sidecar to another"),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
    parser = argparse.ArgumentParser(
        description="cubids-group: find key and parameter groups in BIDS",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
        "--container",
        action="store",
        help="Docker image tag or Singularity image file.",
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
    warnings.warn(
        "cubids-group is deprecated and will be removed in the future. Please use cubids group.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_group().parse_args(argv)
    args = vars(options).copy()
    workflows.group(**args)


def _parse_apply():
    parser = argparse.ArgumentParser(
        description=("cubids-apply: apply the changes specified in a tsv to a BIDS directory"),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
        "--container",
        action="store",
        help="Docker image tag or Singularity image file.",
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
    warnings.warn(
        "cubids-apply is deprecated and will be removed in the future. Please use cubids apply.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_apply().parse_args(argv)
    args = vars(options).copy()
    workflows.apply(**args)


def _parse_datalad_save():
    parser = argparse.ArgumentParser(
        description=("cubids-datalad-save: perform a DataLad save on a BIDS directory"),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
    parser.add_argument(
        "--container",
        action="store",
        help="Docker image tag or Singularity image file.",
    )

    return parser


def _enter_datalad_save(argv=None):
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
    parser = argparse.ArgumentParser(
        description="cubids-undo: revert most recent commit",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
        "--container",
        action="store",
        help="Docker image tag or Singularity image file.",
    )

    return parser


def _enter_undo(argv=None):
    warnings.warn(
        "cubids-undo is deprecated and will be removed in the future. Please use cubids undo.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_undo().parse_args(argv)
    args = vars(options).copy()
    workflows.undo(**args)


def _parse_copy_exemplars():
    parser = argparse.ArgumentParser(
        description=(
            "cubids-copy-exemplars: create and save a directory with "
            "one subject from each Acquisition Group in the BIDS dataset"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
        "exemplars_dir",
        type=Path,
        action="store",
        help=(
            "absolute path to the root of a BIDS dataset "
            "containing one subject from each Acquisition Group. "
            "It should contain sub-X directories and "
            "dataset_description.json."
        ),
    )
    parser.add_argument(
        "exemplars_tsv",
        type=Path,
        action="store",
        help=(
            "absolute path to the .tsv file that lists one "
            "subject from each Acquisition Group "
            "(*_AcqGrouping.tsv from the cubids-group output)"
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
        "--container",
        action="store",
        help="Docker image tag or Singularity image file.",
    )
    parser.add_argument(
        "--force-unlock",
        action="store_true",
        default=False,
        help="unlock dataset before adding nifti info ",
    )
    return parser


def _enter_copy_exemplars(argv=None):
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
    parser = argparse.ArgumentParser(
        description=(
            "cubids-add-nifti-info: Add information from nifti"
            "files to the sidecars of each dataset"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
    parser.add_argument(
        "--container",
        action="store",
        help="Docker image tag or Singularity image file.",
    )
    return parser


def _enter_add_nifti_info(argv=None):
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
    parser = argparse.ArgumentParser(
        description="cubids-purge: purge associations from the dataset",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
    parser.add_argument(
        "--container",
        action="store",
        help="Docker image tag or Singularity image file.",
    )
    return parser


def _enter_purge(argv=None):
    warnings.warn(
        "cubids-purge is deprecated and will be removed in the future. Please use cubids purge.",
        DeprecationWarning,
        stacklevel=2,
    )
    options = _parse_purge().parse_args(argv)
    args = vars(options).copy()
    workflows.purge(**args)


def _parse_remove_metadata_fields():
    parser = argparse.ArgumentParser(
        description="cubids-remove-metadata-fields: delete fields from metadata",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
    parser.add_argument(
        "--container",
        action="store",
        help="Docker image tag or Singularity image file.",
    )

    return parser


def _enter_remove_metadata_fields(argv=None):
    """Set entrypoint for "cubids-remove-metadata-fields" CLI."""
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
    """Create the parser for the "cubids print-metadata-fields" command."""
    parser = argparse.ArgumentParser(
        description="cubids-print-metadata-fields: print all unique metadata fields",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
        "--container",
        action="store",
        help="Docker image tag or Singularity image file.",
    )

    return parser


def _enter_print_metadata_fields(argv=None):
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
    """Create the general "cubids" parser object."""
    from cubids import __version__

    parser = argparse.ArgumentParser(prog="cubids")
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
        )

    return parser


def _main(argv=None):
    """Set entrypoint for "cubids" CLI."""
    options = _get_parser().parse_args(argv)
    args = vars(options).copy()
    args.pop("func")
    options.func(**args)
