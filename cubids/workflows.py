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
from cubids.utils import _get_container_type
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
    container,
    sequential,
    sequential_subjects,
    ignore_nifti_headers,
):
    """Run the bids validator.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    output_prefix : :obj:`pathlib.Path`
        Output filename prefix.
    container : :obj:`str`
        Container in which to run the workflow.
    sequential : :obj:`bool`
        Run the validator sequentially.
    sequential_subjects : :obj:`list` of :obj:`str`
        Filter the sequential run to only include the listed subjects.
    ignore_nifti_headers : :obj:`bool`
        Ignore NIfTI headers when validating.
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
    if container is None:
        if not sequential:
            # run on full dataset
            call = build_validator_call(
                str(bids_dir),
                ignore_nifti_headers,
            )
            ret = run_validator(call)

            # parse the string output
            parsed = parse_validator_output(ret.stdout.decode("UTF-8"))
            if parsed.shape[1] < 1:
                logger.info(
                    "No issues/warnings parsed, your dataset is BIDS valid.")
                sys.exit(0)
            else:
                logger.info("BIDS issues/warnings found in the dataset")

                if output_prefix:
                    # check if absolute or relative path
                    if abs_path_output:
                        # normally, write dataframe to file in CLI
                        val_tsv = str(output_prefix) + "_validation.tsv"

                    else:
                        val_tsv = (
                            str(bids_dir)
                            + "/code/CuBIDS/"
                            + str(output_prefix)
                            + "_validation.tsv"
                        )

                    parsed.to_csv(val_tsv, sep="\t", index=False)

                    # build validation data dictionary json sidecar
                    val_dict = get_val_dictionary()
                    val_json = val_tsv.replace("tsv", "json")
                    with open(val_json, "w") as outfile:
                        json.dump(val_dict, outfile, indent=4)

                    logger.info("Writing issues out to %s", val_tsv)
                    sys.exit(0)
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
                subjects_dict = {
                    k: v for k, v in subjects_dict.items() if k in sequential_subjects
                }
            assert len(list(subjects_dict.keys())
                       ) > 1, "No subjects found in filter"
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
                    call = build_validator_call(tmpdirname, nifti_head)
                    ret = run_validator(call)
                    # parse output
                    if ret.returncode != 0:
                        logger.error(
                            "Errors returned from validator run, parsing now")

                    # parse the output and add to list if it returns a df
                    decoded = ret.stdout.decode("UTF-8")
                    tmp_parse = parse_validator_output(decoded)
                    if tmp_parse.shape[1] > 1:
                        tmp_parse["subject"] = subject
                        parsed.append(tmp_parse)

            # concatenate the parsed data and exit
            if len(parsed) < 1:
                logger.info(
                    "No issues/warnings parsed, your dataset is BIDS valid.")
                sys.exit(0)

            else:
                parsed = pd.concat(parsed, axis=0)
                subset = parsed.columns.difference(["subject"])
                parsed = parsed.drop_duplicates(subset=subset)

                logger.info("BIDS issues/warnings found in the dataset")

                if output_prefix:
                    # normally, write dataframe to file in CLI
                    if abs_path_output:
                        val_tsv = str(output_prefix) + "_validation.tsv"
                    else:
                        val_tsv = (
                            str(bids_dir)
                            + "/code/CuBIDS/"
                            + str(output_prefix)
                            + "_validation.tsv"
                        )

                    parsed.to_csv(val_tsv, sep="\t", index=False)

                    # build validation data dictionary json sidecar
                    val_dict = get_val_dictionary()
                    val_json = val_tsv.replace("tsv", "json")
                    with open(val_json, "w") as outfile:
                        json.dump(val_dict, outfile, indent=4)

                    logger.info("Writing issues out to file %s", val_tsv)
                    sys.exit(0)
                else:
                    # user may be in python session, return dataframe
                    return parsed

    # Run it through a container
    container_type = _get_container_type(container)
    bids_dir_link = str(bids_dir.absolute()) + ":/bids:ro"
    output_dir_link_t = str(output_prefix.parent.absolute()) + ":/tsv:rw"
    output_dir_link_j = str(output_prefix.parent.absolute()) + ":/json:rw"
    linked_output_prefix_t = "/tsv/" + output_prefix.name
    if container_type == "docker":
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            bids_dir_link,
            "-v",
            GIT_CONFIG + ":/root/.gitconfig",
            "-v",
            output_dir_link_t,
            "-v",
            output_dir_link_j,
            "--entrypoint",
            "cubids-validate",
            container,
            "/bids",
            linked_output_prefix_t,
        ]
        if ignore_nifti_headers:
            cmd.append("--ignore_nifti_headers")

    elif container_type == "singularity":
        cmd = [
            "singularity",
            "exec",
            "--cleanenv",
            "-B",
            bids_dir_link,
            "-B",
            output_dir_link_t,
            "-B",
            output_dir_link_j,
            container,
            "cubids-validate",
            "/bids",
            linked_output_prefix_t,
        ]
        if ignore_nifti_headers:
            cmd.append("--ignore_nifti_headers")

        if sequential:
            cmd.append("--sequential")

    logger.info("RUNNING: " + " ".join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def bids_version(bids_dir, write=False):
    """Get BIDS validator and schema version.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    write : :obj:`bool`
        If True, write to dataset_description.json. If False, print to terminal.
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
            raise ValueError(
                "No folders starting with 'sub-' found. Please provide a valid BIDS.")
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
            call = build_validator_call(tmpdirname)
            ret = run_validator(call)

            # Get BIDS validator and schema version
            decoded = ret.stdout.decode("UTF-8")
            bids_validator_version(decoded, bids_dir, write=write)


def bids_sidecar_merge(from_json, to_json):
    """Merge critical keys from one sidecar to another."""
    merge_status = merge_json_into_json(
        from_json, to_json, raise_on_error=False)
    sys.exit(merge_status)


def group(bids_dir, container, acq_group_level, config, output_prefix):
    """Find key and param groups.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    container : :obj:`str`
        Container in which to run the workflow.
    acq_group_level : {"subject", "session"}
        Level at which acquisition groups are created.
    config : :obj:`pathlib.Path`
        Path to the grouping config file.
    output_prefix : :obj:`pathlib.Path`
        Output filename prefix.
    """
    # Run directly from python using
    if container is None:
        bod = CuBIDS(
            data_root=str(bids_dir),
            acq_group_level=acq_group_level,
            grouping_config=config,
        )
        bod.get_tsvs(
            str(output_prefix),
        )
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(container)
    bids_dir_link = str(bids_dir.absolute()) + ":/bids"
    output_dir_link = str(output_prefix.parent.absolute()) + ":/tsv:rw"

    apply_config = config is not None
    if apply_config:
        input_config_dir_link = str(
            config.parent.absolute()) + ":/in_config:ro"
        linked_input_config = "/in_config/" + config.name

    linked_output_prefix = "/tsv/" + output_prefix.name
    if container_type == "docker":
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            bids_dir_link,
            "-v",
            GIT_CONFIG + ":/root/.gitconfig",
            "-v",
            output_dir_link,
            "--entrypoint",
            "cubids-group",
            container,
            "/bids",
            linked_output_prefix,
        ]
        if apply_config:
            cmd.insert(3, "-v")
            cmd.insert(4, input_config_dir_link)
            cmd += ["--config", linked_input_config]

    elif container_type == "singularity":
        cmd = [
            "singularity",
            "exec",
            "--cleanenv",
            "-B",
            bids_dir_link,
            "-B",
            output_dir_link,
            container,
            "cubids-group",
            "/bids",
            linked_output_prefix,
        ]
        if apply_config:
            cmd.insert(3, "-B")
            cmd.insert(4, input_config_dir_link)
            cmd += ["--config", linked_input_config]

    if acq_group_level:
        cmd.append("--acq-group-level")
        cmd.append(str(acq_group_level))

    logger.info("RUNNING: " + " ".join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def apply(
    bids_dir,
    use_datalad,
    acq_group_level,
    config,
    edited_summary_tsv,
    files_tsv,
    new_tsv_prefix,
    container,
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
    edited_summary_tsv : :obj:`pathlib.Path`
        Path to the edited summary tsv.
    files_tsv : :obj:`pathlib.Path`
        Path to the files tsv.
    new_tsv_prefix : :obj:`pathlib.Path`
        Path to the new tsv prefix.
    container : :obj:`str`
        Container in which to run the workflow.
    """
    # Run directly from python using
    if container is None:
        bod = CuBIDS(
            data_root=str(bids_dir),
            use_datalad=use_datalad,
            acq_group_level=acq_group_level,
            grouping_config=config,
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
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(container)
    bids_dir_link = str(bids_dir.absolute()) + ":/bids"
    input_summary_tsv_dir_link = str(
        edited_summary_tsv.parent.absolute()) + ":/in_summary_tsv:ro"
    input_files_tsv_dir_link = str(
        edited_summary_tsv.parent.absolute()) + ":/in_files_tsv:ro"
    output_tsv_dir_link = str(
        new_tsv_prefix.parent.absolute()) + ":/out_tsv:rw"

    # FROM BOND-GROUP
    apply_config = config is not None
    if apply_config:
        input_config_dir_link = str(
            config.parent.absolute()) + ":/in_config:ro"
        linked_input_config = "/in_config/" + config.name

    linked_output_prefix = "/tsv/" + new_tsv_prefix.name

    ####
    linked_input_summary_tsv = "/in_summary_tsv/" + edited_summary_tsv.name
    linked_input_files_tsv = "/in_files_tsv/" + files_tsv.name
    linked_output_prefix = "/out_tsv/" + new_tsv_prefix.name
    if container_type == "docker":
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            bids_dir_link,
            "-v",
            GIT_CONFIG + ":/root/.gitconfig",
            "-v",
            input_summary_tsv_dir_link,
            "-v",
            input_files_tsv_dir_link,
            "-v",
            output_tsv_dir_link,
            "--entrypoint",
            "cubids-apply",
            container,
            "/bids",
            linked_input_summary_tsv,
            linked_input_files_tsv,
            linked_output_prefix,
        ]
        if apply_config:
            cmd.insert(3, "-v")
            cmd.insert(4, input_config_dir_link)
            cmd += ["--config", linked_input_config]

    elif container_type == "singularity":
        cmd = [
            "singularity",
            "exec",
            "--cleanenv",
            "-B",
            bids_dir_link,
            "-B",
            input_summary_tsv_dir_link,
            "-B",
            input_files_tsv_dir_link,
            "-B",
            output_tsv_dir_link,
            container,
            "cubids-apply",
            "/bids",
            linked_input_summary_tsv,
            linked_input_files_tsv,
            linked_output_prefix,
        ]
        if apply_config:
            cmd.insert(3, "-B")
            cmd.insert(4, input_config_dir_link)
            cmd += ["--config", linked_input_config]

    if use_datalad:
        cmd.append("--use-datalad")

    if acq_group_level:
        cmd.append("--acq-group-level")
        cmd.append(str(acq_group_level))

    logger.info("RUNNING: " + " ".join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def datalad_save(bids_dir, container, m):
    """Perform datalad save.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    container : :obj:`str`
        Container in which to run the workflow.
    m : :obj:`str`
        Commit message.
    """
    # Run directly from python using
    if container is None:
        bod = CuBIDS(data_root=str(bids_dir), use_datalad=True)
        bod.datalad_save(message=m)
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(container)
    bids_dir_link = str(bids_dir.absolute()) + ":/bids"
    if container_type == "docker":
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            bids_dir_link,
            "-v",
            GIT_CONFIG + ":/root/.gitconfig",
            "--entrypoint",
            "cubids-datalad-save",
            container,
            "/bids",
            "-m",
            m,
        ]
    elif container_type == "singularity":
        cmd = [
            "singularity",
            "exec",
            "--cleanenv",
            "-B",
            bids_dir_link,
            container,
            "cubids-datalad-save",
            "/bids",
            "-m",
            m,
        ]
    logger.info("RUNNING: " + " ".join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def undo(bids_dir, container):
    """Revert the most recent commit.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    container : :obj:`str`
        Container in which to run the workflow.
    """
    # Run directly from python using
    if container is None:
        bod = CuBIDS(data_root=str(bids_dir), use_datalad=True)
        bod.datalad_undo_last_commit()
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(container)
    bids_dir_link = str(bids_dir.absolute()) + ":/bids"
    if container_type == "docker":
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            bids_dir_link,
            "-v",
            GIT_CONFIG + ":/root/.gitconfig",
            "--entrypoint",
            "cubids-undo",
            container,
            "/bids",
        ]
    elif container_type == "singularity":
        cmd = [
            "singularity",
            "exec",
            "--cleanenv",
            "-B",
            bids_dir_link,
            container,
            "cubids-undo",
            "/bids",
        ]
    logger.info("RUNNING: " + " ".join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def copy_exemplars(
    bids_dir,
    container,
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
    container : :obj:`str`
        Container in which to run the workflow.
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
    if container is None:
        bod = CuBIDS(data_root=str(bids_dir), use_datalad=use_datalad)
        if use_datalad:
            if not bod.is_datalad_clean():
                raise Exception(
                    "Untracked changes. Need to save "
                    + str(bids_dir)
                    + " before coyping exemplars"
                )
        bod.copy_exemplars(
            str(exemplars_dir),
            str(exemplars_tsv),
            min_group_size=min_group_size,
        )
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(container)
    bids_dir_link = str(bids_dir.absolute()) + ":/bids:ro"
    exemplars_dir_link = str(exemplars_dir.absolute()) + ":/exemplars:ro"
    exemplars_tsv_link = str(exemplars_tsv.absolute()) + ":/in_tsv:ro"
    if container_type == "docker":
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            bids_dir_link,
            "-v",
            exemplars_dir_link,
            "-v",
            GIT_CONFIG + ":/root/.gitconfig",
            "-v",
            exemplars_tsv_link,
            "--entrypoint",
            "cubids-copy-exemplars",
            container,
            "/bids",
            "/exemplars",
            "/in_tsv",
        ]

        if force_unlock:
            cmd.append("--force-unlock")

        if min_group_size:
            cmd.append("--min-group-size")

    elif container_type == "singularity":
        cmd = [
            "singularity",
            "exec",
            "--cleanenv",
            "-B",
            bids_dir_link,
            "-B",
            exemplars_dir_link,
            "-B",
            exemplars_tsv_link,
            container,
            "cubids-copy-exemplars",
            "/bids",
            "/exemplars",
            "/in_tsv",
        ]
        if force_unlock:
            cmd.append("--force-unlock")

        if min_group_size:
            cmd.append("--min-group-size")

    logger.info("RUNNING: " + " ".join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def add_nifti_info(bids_dir, container, use_datalad, force_unlock):
    """Add information from nifti files to the dataset's sidecars.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    container : :obj:`str`
        Container in which to run the workflow.
    use_datalad : :obj:`bool`
        Use datalad to track changes.
    force_unlock : :obj:`bool`
        Force unlock the dataset.
    """
    # Run directly from python using
    if container is None:
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
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(container)
    bids_dir_link = str(bids_dir.absolute()) + ":/bids:ro"
    if container_type == "docker":
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            bids_dir_link,
            "-v",
            GIT_CONFIG + ":/root/.gitconfig",
            "--entrypoint",
            "cubids-add-nifti-info",
            container,
            "/bids",
        ]

        if force_unlock:
            cmd.append("--force-unlock")
    elif container_type == "singularity":
        cmd = [
            "singularity",
            "exec",
            "--cleanenv",
            "-B",
            bids_dir_link,
            container,
            "cubids-add-nifti-info",
            "/bids",
        ]
        if force_unlock:
            cmd.append("--force-unlock")

    logger.info("RUNNING: " + " ".join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def purge(bids_dir, container, use_datalad, scans):
    """Purge scan associations.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    container : :obj:`str`
        Container in which to run the workflow.
    use_datalad : :obj:`bool`
        Use datalad to track changes.
    scans : :obj:`pathlib.Path`
        Path to the scans tsv.
    """
    # Run directly from python using
    if container is None:
        bod = CuBIDS(data_root=str(bids_dir), use_datalad=use_datalad)
        if use_datalad:
            if not bod.is_datalad_clean():
                raise Exception("Untracked change in " + str(bids_dir))
        bod.purge(str(scans))
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(container)
    bids_dir_link = str(bids_dir.absolute()) + ":/bids"
    input_scans_link = str(scans.parent.absolute()) + ":/in_scans:ro"
    if container_type == "docker":
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            bids_dir_link,
            "-v",
            GIT_CONFIG + ":/root/.gitconfig",
            "-v",
            input_scans_link,
            "--entrypoint",
            "cubids-purge",
            container,
            "/bids",
            input_scans_link,
        ]

    elif container_type == "singularity":
        cmd = [
            "singularity",
            "exec",
            "--cleanenv",
            "-B",
            bids_dir_link,
            "-B",
            input_scans_link,
            container,
            "cubids-purge",
            "/bids",
            input_scans_link,
        ]
    logger.info("RUNNING: " + " ".join(cmd))
    if use_datalad:
        cmd.append("--use-datalad")
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def remove_metadata_fields(bids_dir, container, fields):
    """Delete fields from metadata.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    container : :obj:`str`
        Container in which to run the workflow.
    fields : :obj:`list` of :obj:`str`
        List of fields to remove.
    """
    # Run directly from python
    if container is None:
        bod = CuBIDS(data_root=str(bids_dir), use_datalad=False)
        bod.remove_metadata_fields(fields)
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(container)
    bids_dir_link = str(bids_dir.absolute()) + ":/bids:rw"
    if container_type == "docker":
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            bids_dir_link,
            "--entrypoint",
            "cubids-remove-metadata-fields",
            container,
            "/bids",
            "--fields",
        ] + fields
    elif container_type == "singularity":
        cmd = [
            "singularity",
            "exec",
            "--cleanenv",
            "-B",
            bids_dir_link,
            container,
            "cubids-remove-metadata-fields",
            "/bids",
            "--fields",
        ] + fields
    logger.info("RUNNING: " + " ".join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def print_metadata_fields(bids_dir, container):
    """Print unique metadata fields.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Path to the BIDS directory.
    container : :obj:`str`
        Container in which to run the workflow.
    """
    # Run directly from python
    if container is None:
        bod = CuBIDS(data_root=str(bids_dir), use_datalad=False)
        fields = bod.get_all_metadata_fields()
        print("\n".join(fields))  # logger not printing
        # logger.info("\n".join(fields))
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(container)
    bids_dir_link = str(bids_dir.absolute()) + ":/bids:ro"
    if container_type == "docker":
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            bids_dir_link,
            "--entrypoint",
            "cubids-print-metadata-fields",
            container,
            "/bids",
        ]
    elif container_type == "singularity":
        cmd = [
            "singularity",
            "exec",
            "--cleanenv",
            "-B",
            bids_dir_link,
            container,
            "cubids-print-metadata-fields",
            "/bids",
        ]
    logger.info("RUNNING: " + " ".join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)
