"""First order workflows in CuBIDS."""

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

import pandas as pd
import tqdm

from cubids.cubids import CuBIDS
from cubids.metadata_merge import merge_json_into_json
from cubids.utils import BIDSError
from cubids.validator import (
    bids_validator_version,
    build_first_subject_path,
    build_subject_paths,
    build_validator_call,
    get_val_dictionary,
    parse_validator_output,
    run_validator,
)

warnings.simplefilter(action="ignore", category=FutureWarning)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cubids-cli")
GIT_CONFIG = os.path.join(os.path.expanduser("~"), ".gitconfig")
logging.getLogger("datalad").setLevel(logging.ERROR)


def validate(
    bids_dir,
    output_prefix,
    sequential,
    sequential_subjects,
    local_validator,
    ignore_nifti_headers,
    schema,
):
    """Run the bids validator.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    output_prefix : :obj:`pathlib.Path`
        Output filename prefix.
    sequential : :obj:`bool`
        Run the validator sequentially.
    sequential_subjects : :obj:`list` of :obj:`str`
        Filter the sequential run to only include the listed subjects.
    local_validator : :obj:`bool`
        Use the local bids validator.
    ignore_nifti_headers : :obj:`bool`
        Ignore NIfTI headers when validating.
    schema : :obj:`pathlib.Path` or None
        Path to the BIDS schema file.
    """
    # check status of output_prefix, absolute or relative?
    abs_path_output = True
    if "/" not in str(output_prefix):
        # not an absolute path --> put in code/CuBIDS dir
        abs_path_output = False
        # check if code/CuBIDS dir exists
        if not (bids_dir / "code" / "CuBIDS").is_dir():
            # if not, create it
            subprocess.run(["mkdir", str(bids_dir / "code")])
            subprocess.run(["mkdir", str(bids_dir / "code" / "CuBIDS")])

    # Run directly from python using subprocess
    if not sequential:
        # run on full dataset
        call = build_validator_call(
            str(bids_dir),
            local_validator,
            ignore_nifti_headers,
            schema=schema,
        )
        ret = run_validator(call)

        # parse the string output
        parsed = parse_validator_output(ret.stdout.decode("UTF-8"))
        if parsed.shape[1] < 1:
            logger.info("No issues/warnings parsed, your dataset is BIDS valid.")
            return
        else:
            logger.info("BIDS issues/warnings found in the dataset")

            if output_prefix:
                # check if absolute or relative path
                if abs_path_output:
                    # normally, write dataframe to file in CLI
                    val_tsv = str(output_prefix) + "_validation.tsv"

                else:
                    val_tsv = (
                        str(bids_dir) + "/code/CuBIDS/" + str(output_prefix) + "_validation.tsv"
                    )

                parsed.to_csv(val_tsv, sep="\t", index=False)

                # build validation data dictionary json sidecar
                val_dict = get_val_dictionary()
                val_json = val_tsv.replace("tsv", "json")
                with open(val_json, "w") as outfile:
                    json.dump(val_dict, outfile, indent=4)

                logger.info("Writing issues out to %s", val_tsv)
                return
            else:
                # user may be in python session, return dataframe
                return parsed
    else:
        # logger.info("Prepping sequential validator run...")

        # build a dictionary with {SubjectLabel: [List of files]}
        subjects_dict = build_subject_paths(bids_dir)

        # logger.info("Running validator sequentially...")
        # iterate over the dictionary

        parsed = []

        if sequential_subjects:
            subjects_dict = {k: v for k, v in subjects_dict.items() if k in sequential_subjects}
        assert len(list(subjects_dict.keys())) > 1, "No subjects found in filter"
        for subject, files_list in tqdm.tqdm(subjects_dict.items()):
            # logger.info(" ".join(["Processing subject:", subject]))
            # create a temporary directory and symlink the data
            with tempfile.TemporaryDirectory() as tmpdirname:
                for fi in files_list:
                    # cut the path down to the subject label
                    bids_start = fi.find(subject)

                    # maybe it's a single file
                    if bids_start < 1:
                        bids_folder = tmpdirname
                        fi_tmpdir = tmpdirname

                    else:
                        bids_folder = Path(fi[bids_start:]).parent
                        fi_tmpdir = tmpdirname + "/" + str(bids_folder)

                    if not os.path.exists(fi_tmpdir):
                        os.makedirs(fi_tmpdir)
                    output = fi_tmpdir + "/" + str(Path(fi).name)
                    shutil.copy2(fi, output)

                # run the validator
                nifti_head = ignore_nifti_headers
                call = build_validator_call(tmpdirname, local_validator, nifti_head, schema=schema)
                ret = run_validator(call)
                # parse output
                if ret.returncode != 0:
                    logger.error("Errors returned from validator run, parsing now")

                # parse the output and add to list if it returns a df
                decoded = ret.stdout.decode("UTF-8")
                tmp_parse = parse_validator_output(decoded)
                if tmp_parse.shape[1] > 1:
                    tmp_parse["subject"] = subject
                    parsed.append(tmp_parse)

        # concatenate the parsed data and exit
        if len(parsed) < 1:
            logger.info("No issues/warnings parsed, your dataset is BIDS valid.")
            return

        else:
            parsed = pd.concat(parsed, axis=0, ignore_index=True)
            subset = parsed.columns.difference(["subject"])
            parsed = parsed.drop_duplicates(subset=subset)

            logger.info("BIDS issues/warnings found in the dataset")

            if output_prefix:
                # normally, write dataframe to file in CLI
                if abs_path_output:
                    val_tsv = str(output_prefix) + "_validation.tsv"
                else:
                    val_tsv = (
                        str(bids_dir) + "/code/CuBIDS/" + str(output_prefix) + "_validation.tsv"
                    )

                parsed.to_csv(val_tsv, sep="\t", index=False)

                # build validation data dictionary json sidecar
                val_dict = get_val_dictionary()
                val_json = val_tsv.replace("tsv", "json")
                with open(val_json, "w") as outfile:
                    json.dump(val_dict, outfile, indent=4)

                logger.info("Writing issues out to file %s", val_tsv)
                return
            else:
                # user may be in python session, return dataframe
                return parsed


def bids_version(bids_dir, write=False, schema=None):
    """Get BIDS validator and schema version.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    write : :obj:`bool`
        If True, write to dataset_description.json. If False, print to terminal.
    schema : :obj:`pathlib.Path` or None
        Path to the BIDS schema file.
    """
    # Need to run validator to get output with schema version
    # Copy code from `validate --sequential`

    try:  # return first subject
        # Get all folders that start with "sub-"
        sub_folders = [
            name
            for name in os.listdir(bids_dir)
            if os.path.isdir(os.path.join(bids_dir, name)) and name.startswith("sub-")
        ]
        if not sub_folders:
            raise ValueError("No folders starting with 'sub-' found. Please provide a valid BIDS.")
        subject = sub_folders[0]
    except FileNotFoundError:
        raise FileNotFoundError(f"The directory {bids_dir} does not exist.")
    except ValueError as ve:
        raise ve

    # build a dictionary with {SubjectLabel: [List of files]}
    # run first subject only
    subject_dict = build_first_subject_path(bids_dir, subject)

    # iterate over the dictionary
    for subject, files_list in subject_dict.items():
        # logger.info(" ".join(["Processing subject:", subject]))
        # create a temporary directory and symlink the data
        with tempfile.TemporaryDirectory() as tmpdirname:
            for fi in files_list:
                # cut the path down to the subject label
                bids_start = fi.find(subject)

                # maybe it's a single file
                if bids_start < 1:
                    bids_folder = tmpdirname
                    fi_tmpdir = tmpdirname

                else:
                    bids_folder = Path(fi[bids_start:]).parent
                    fi_tmpdir = tmpdirname + "/" + str(bids_folder)

                if not os.path.exists(fi_tmpdir):
                    os.makedirs(fi_tmpdir)
                output = fi_tmpdir + "/" + str(Path(fi).name)
                shutil.copy2(fi, output)

            # run the validator
            call = build_validator_call(tmpdirname, schema=schema)
            ret = run_validator(call)

            # Get BIDS validator and schema version
            decoded = ret.stdout.decode("UTF-8")
            bids_validator_version(decoded, bids_dir, write=write)


def bids_sidecar_merge(from_json, to_json):
    """Merge critical keys from one sidecar to another."""
    merge_status = merge_json_into_json(from_json, to_json, raise_on_error=False)
    sys.exit(merge_status)


def group(bids_dir, acq_group_level, config, schema, output_prefix):
    """Find key and param groups.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    acq_group_level : {"subject", "session"}
        Level at which acquisition groups are created.
    config : :obj:`pathlib.Path`
        Path to the grouping config file.
    schema : :obj:`pathlib.Path`
        Path to the BIDS schema file.
    output_prefix : :obj:`pathlib.Path`
        Output filename prefix.
    """
    # Run directly from python using
    bod = CuBIDS(
        data_root=str(bids_dir),
        acq_group_level=acq_group_level,
        grouping_config=config,
        schema_json=schema,
    )
    bod.get_tsvs(
        str(output_prefix),
    )


def apply(
    bids_dir,
    use_datalad,
    acq_group_level,
    config,
    schema,
    edited_summary_tsv,
    files_tsv,
    new_tsv_prefix,
):
    """Apply the tsv changes.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    use_datalad : :obj:`bool`
        Use datalad to track changes.
    acq_group_level : {"subject", "session"}
        Level at which acquisition groups are created.
    config : :obj:`pathlib.Path`
        Path to the grouping config file.
    schema : :obj:`pathlib.Path`
        Path to the BIDS schema file.
    edited_summary_tsv : :obj:`pathlib.Path`
        Path to the edited summary tsv.
    files_tsv : :obj:`pathlib.Path`
        Path to the files tsv.
    new_tsv_prefix : :obj:`pathlib.Path`
        Path to the new tsv prefix.
    """
    # Run directly from python using
    bod = CuBIDS(
        data_root=str(bids_dir),
        use_datalad=use_datalad,
        acq_group_level=acq_group_level,
        grouping_config=config,
        schema_json=schema,
    )
    if use_datalad:
        if not bod.is_datalad_clean():
            raise Exception("Untracked change in " + str(bids_dir))
    bod.apply_tsv_changes(
        str(edited_summary_tsv),
        str(files_tsv),
        str(new_tsv_prefix),
        raise_on_error=False,
    )


def mv(source, destination, use_datalad=False, force=False, dry_run=False, verbose=False):
    """Move or rename a file, a directory, or a symlink within a BIDS dataset.

    Parameters
    ----------
    source : :obj:`pathlib.Path`
        The path to the file or directory to move.
    destination : :obj:`pathlib.Path`
        The path to the new location for the file or directory.
    use_datalad : :obj:`bool`
        Use Datalad to track the move or rename operation.
    force : :obj:`bool`
        Force the move or rename operation.
    dry_run : :obj:`bool`
        Do nothing; only show what would happen.
    verbose : :obj:`bool`
        Report the details of the move or rename operation.

    Notes
    -----
    This function is similar to git mv. It determines if a path is a BIDS dataset by looking for the
    dataset_description.json file in the current directory and all parent directories, analogous to
    how git mv looks for the .git directory.

    If the source is a file, it will be moved to the destination and associated files will be moved
    with it.

    If the source is a directory, it will be moved to the destination and all files within it will be
    moved with it. Additionally, if the directory involves changing a subject label, the subject label
    will be updated in the file names of all associated files. If the directory involves changing a
    session label, the session label will be updated in the file names of all associated files.

    Raises
    ------
    BIDSError
        If the dataset_description.json file is not found in the current directory or any parent
        directory.
    """
    # Find the BIDS dataset root. We can do this by looking for the dataset_description.json file.
    bids_dir = None
    cwd = Path.cwd()
    to_check = [cwd] + list(cwd.parents)
    for path in to_check:
        if (path / "dataset_description.json").exists():
            bids_dir = path
            break

    if bids_dir is None:
        raise BIDSError("fatal: not a BIDS dataset (or any of the parent directories)")

    # Run directly from python using
    bod = CuBIDS(data_root=str(bids_dir), use_datalad=use_datalad)
    ...


def datalad_save(bids_dir, m):
    """Perform datalad save.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    m : :obj:`str`
        Commit message.
    """
    # Run directly from python using
    bod = CuBIDS(data_root=str(bids_dir), use_datalad=True)
    bod.datalad_save(message=m)


def undo(bids_dir):
    """Revert the most recent commit.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    """
    # Run directly from python using
    bod = CuBIDS(data_root=str(bids_dir), use_datalad=True)
    bod.datalad_undo_last_commit()


def copy_exemplars(
    bids_dir,
    use_datalad,
    exemplars_dir,
    exemplars_tsv,
    min_group_size,
    force_unlock,
):
    """Create and save a directory with one subject from each acquisition group.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    use_datalad : :obj:`bool`
        Use datalad to track changes.
    exemplars_dir : :obj:`pathlib.Path`
        Path to the directory where the exemplars will be saved.
    exemplars_tsv : :obj:`pathlib.Path`
        Path to the tsv file with the exemplars.
    min_group_size : :obj:`int`
        Minimum number of subjects in a group to be considered for exemplar.
    force_unlock : :obj:`bool`
        Force unlock the dataset.
    """
    # Run directly from python using
    bod = CuBIDS(data_root=str(bids_dir), use_datalad=use_datalad, force_unlock=force_unlock)
    if use_datalad:
        if not bod.is_datalad_clean():
            raise Exception(
                "Untracked changes. Need to save " + str(bids_dir) + " before coyping exemplars"
            )
    bod.copy_exemplars(
        str(exemplars_dir),
        str(exemplars_tsv),
        min_group_size=min_group_size,
    )


def add_nifti_info(bids_dir, use_datalad, force_unlock):
    """Add information from nifti files to the dataset's sidecars.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    use_datalad : :obj:`bool`
        Use datalad to track changes.
    force_unlock : :obj:`bool`
        Force unlock the dataset.
    """
    # Run directly from python using
    bod = CuBIDS(
        data_root=str(bids_dir),
        use_datalad=use_datalad,
        force_unlock=force_unlock,
    )
    if use_datalad:
        if not bod.is_datalad_clean():
            raise Exception("Untracked change in " + str(bids_dir))
        # if bod.is_datalad_clean() and not force_unlock:
        #     raise Exception("Need to unlock " + str(bids_dir))
    bod.add_nifti_info()


def add_file_collections(bids_dir, use_datalad, force_unlock):
    """Add file collection metadata to the sidecars of each NIfTI file in the BIDS dataset.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    use_datalad : :obj:`bool`
        Use datalad to track changes.
    force_unlock : :obj:`bool`
        Force unlock the dataset.
    """
    bod = CuBIDS(
        data_root=str(bids_dir),
        use_datalad=use_datalad,
        force_unlock=force_unlock,
    )
    if use_datalad and not bod.is_datalad_clean():
        raise Exception(f"Untracked changes in {bids_dir}. Cannot continue.")

    bod.add_file_collections()


def purge(bids_dir, use_datalad, scans):
    """Purge scan associations.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    use_datalad : :obj:`bool`
        Use datalad to track changes.
    scans : :obj:`pathlib.Path`
        Path to the scans tsv.
    """
    # Run directly from python using
    bod = CuBIDS(data_root=str(bids_dir), use_datalad=use_datalad)
    if use_datalad:
        if not bod.is_datalad_clean():
            raise Exception("Untracked change in " + str(bids_dir))
    bod.purge(str(scans))


def remove_metadata_fields(bids_dir, fields):
    """Delete fields from metadata.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    fields : :obj:`list` of :obj:`str`
        List of fields to remove.
    """
    # Run directly from python
    bod = CuBIDS(data_root=str(bids_dir), use_datalad=False)
    bod.remove_metadata_fields(fields)


def print_metadata_fields(bids_dir):
    """Print unique metadata fields from a BIDS dataset.

    This function identifies and prints all unique metadata fields from
    the `dataset_description.json` file in a BIDS directory. It can run
    either directly in Python or within a specified container (Docker or
    Singularity).

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory containing the `dataset_description.json` file.

    Raises
    ------
    SystemExit
        Raised in the following cases:
        - The `dataset_description.json` file is not found in the BIDS directory.

    """
    # Check if dataset_description.json exists
    dataset_description = bids_dir / "dataset_description.json"
    if not dataset_description.exists():
        logger.error("dataset_description.json not found in the BIDS directory.")
        sys.exit(1)

    # Run directly from python
    bod = CuBIDS(data_root=str(bids_dir), use_datalad=False)
    fields = bod.get_all_metadata_fields()
    print("\n".join(fields))  # logger not printing
    # logger.info("\n".join(fields))
