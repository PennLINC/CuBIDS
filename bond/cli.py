"""Console script for bond."""
import argparse
import subprocess
import os
import sys
import re
import logging
import tempfile
import tqdm
import shutil
import pandas as pd
from bond import BOnD
from pathlib import Path
from .validator import (build_validator_call,
                        run_validator, parse_validator_output,
                        build_subject_paths)
from .metadata_merge import merge_json_into_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bond-cli')
GIT_CONFIG = os.path.join(os.path.expanduser("~"), '.gitconfig')


def bond_validate():
    '''Command Line Interface function for running the bids validator.'''

    parser = argparse.ArgumentParser(
        description="bond-validate: Wrapper around the official "
        "BIDS Validator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('bids_dir',
                        type=Path,
                        action='store',
                        help='the root of a BIDS dataset. It should contain '
                        'sub-X directories and dataset_description.json')
    parser.add_argument('output_prefix',
                        type=Path,
                        action='store',
                        help='file prefix to which tabulated validator output '
                        'is written.')
    parser.add_argument('--sequential',
                        action='store_true',
                        default=False,
                        help='Run the BIDS validator sequentially '
                        'on each subject.',
                        required=False)
    parser.add_argument('--container',
                        action='store',
                        help='Docker image tag or Singularity image file.',
                        default=None)
    parser.add_argument('--ignore_nifti_headers',
                        action='store_true',
                        default=False,
                        help='Disregard NIfTI header content during'
                        ' validation',
                        required=False)
    parser.add_argument('--ignore_subject_consistency',
                        action='store_true',
                        default=False,
                        help='Skip checking that any given file for one'
                        ' subject is present for all other subjects',
                        required=False)
    parser.add_argument('--sequential-subjects',
                        action='store',
                        default=None,
                        help='List: Filter the sequential run to only include'
                        ' the listed subjects. e.g. --sequential-subjects '
                        'sub-01 sub-02 sub-03',
                        nargs='+',
                        required=False)
    opts = parser.parse_args()

    # Run directly from python using subprocess
    if opts.container is None:

        if not opts.sequential:
            # run on full dataset
            call = build_validator_call(str(opts.bids_dir),
                                        opts.ignore_nifti_headers,
                                        opts.ignore_subject_consistency)
            ret = run_validator(call)

            if ret.returncode != 0:
                logger.error("Errors returned from validator run, parsing now")

            # parse the string output
            parsed = parse_validator_output(ret.stdout.decode('UTF-8'))
            if parsed.shape[1] < 1:
                logger.info("No issues/warnings parsed, your dataset"
                            " is BIDS valid.")
                sys.exit(0)
            else:
                logger.info("BIDS issues/warnings found in the dataset")

                if opts.output_prefix:
                    # normally, write dataframe to file in CLI
                    logger.info("Writing issues out to file")
                    parsed.to_csv(str(opts.output_prefix) +
                                  "_validation.csv", index=False)
                    sys.exit(0)
                else:
                    # user may be in python session, return dataframe
                    return parsed
        else:
            logger.info("Prepping sequential validator run...")

            # build a dictionary with {SubjectLabel: [List of files]}
            subjects_dict = build_subject_paths(opts.bids_dir)

            logger.info("Running validator sequentially...")
            # iterate over the dictionary

            parsed = []

            if opts.sequential_subjects:
                subjects_dict = {k: v for k, v in subjects_dict.items()
                                 if k in opts.sequential_subjects}
            assert len(list(subjects_dict.keys())) > 1, ("No subjects found"
                                                         " in filter")
            for subject, files_list in tqdm.tqdm(subjects_dict.items()):

                logger.info(" ".join(["Processing subject:", subject]))
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
                            fi_tmpdir = tmpdirname + '/' + str(bids_folder)

                        if not os.path.exists(fi_tmpdir):
                            os.makedirs(fi_tmpdir)
                        output = fi_tmpdir + '/' + str(Path(fi).name)
                        shutil.copy2(fi, output)
                    # run the validator
                    nifti_head = opts.ignore_nifti_headers
                    subj_consist = opts.ignore_subject_consistency
                    call = build_validator_call(tmpdirname,
                                                nifti_head,
                                                subj_consist)
                    ret = run_validator(call)
                    # parse output
                    if ret.returncode != 0:
                        logger.error("Errors returned "
                                     "from validator run, parsing now")

                    # parse the output and add to list if it returns a df
                    decoded = ret.stdout.decode('UTF-8')
                    tmp_parse = parse_validator_output(decoded)
                    if tmp_parse.shape[1] > 1:
                        tmp_parse['subject'] = subject
                        parsed.append(tmp_parse)

            # concatenate the parsed data and exit, we're goin home fellas
            if len(parsed) < 1:
                logger.info("No issues/warnings parsed, your dataset"
                            " is BIDS valid.")
                sys.exit(0)

            else:
                parsed = pd.concat(parsed, axis=0)
                subset = parsed.columns.difference(['subject'])
                parsed = parsed.drop_duplicates(subset=subset)

                logger.info("BIDS issues/warnings found in the dataset")

                if opts.output_prefix:
                    # normally, write dataframe to file in CLI
                    logger.info("Writing issues out to file")
                    parsed.to_csv(str(opts.output_prefix) +
                                  "_validation.csv", index=False)
                    sys.exit(0)
                else:
                    # user may be in python session, return dataframe
                    return parsed

    # Run it through a container
    container_type = _get_container_type(opts.container)
    bids_dir_link = str(opts.bids_dir.absolute()) + ":/bids:ro"
    output_dir_link = str(opts.output_prefix.parent.absolute()) + ":/csv:rw"
    linked_output_prefix = "/csv/" + opts.output_prefix.name
    if container_type == 'docker':
        cmd = ['docker', 'run', '--rm', '-v', bids_dir_link,
               '-v', GIT_CONFIG+":/root/.gitconfig",
               '-v', output_dir_link, '--entrypoint', 'bond-validate',
               opts.container, '/bids', linked_output_prefix]
        if opts.ignore_nifti_headers:
            cmd.append('--ignore_nifti_headers')
        if opts.ignore_subject_consistency:
            cmd.append('--ignore_subject_consistency')
    elif container_type == 'singularity':
        cmd = ['singularity', 'exec', '--cleanenv',
               '-B', bids_dir_link,
               '-B', output_dir_link, opts.container, 'bond-validate',
               '/bids', linked_output_prefix]
        if opts.ignore_nifti_headers:
            cmd.append('--ignore_nifti_headers')
        if opts.ignore_subject_consistency:
            cmd.append('--ignore_subject_consistency')
        if opts.sequential:
            cmd.append('--sequential')

    print("RUNNING: " + ' '.join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def bids_sidecar_merge():
    parser = argparse.ArgumentParser(
        description="bids-sidecar-merge: merge critical keys from one "
        "sidecar to another",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('from_json',
                        type=Path,
                        action='store',
                        help='Source json file.')
    parser.add_argument('to_json',
                        type=Path,
                        action='store',
                        help='destination json. This file will have data '
                        'from `from_json` copied into it.')
    opts = parser.parse_args()
    merge_status = merge_json_into_json(opts.from_json, opts.to_json,
                                        raise_on_error=False)
    sys.exit(merge_status)


def bond_group():
    '''Command Line Interface function for finding key and param groups.'''

    parser = argparse.ArgumentParser(
        description="bond-group: find key and parameter groups in BIDS",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('bids_dir',
                        type=Path,
                        action='store',
                        help='the root of a BIDS dataset. It should contain '
                        'sub-X directories and dataset_description.json')
    parser.add_argument('output_prefix',
                        type=Path,
                        action='store',
                        help='file prefix to which a _summary.csv, _files.csv '
                        'and _group.csv are written.')
    parser.add_argument('--container',
                        action='store',
                        help='Docker image tag or Singularity image file.')
    parser.add_argument('--use-datalad',
                        action='store_true',
                        help='ensure that there are no untracked changes '
                        'before finding groups')
    parser.add_argument('--config',
                        action='store',
                        type=Path,
                        help='path to a config file for grouping')
    opts = parser.parse_args()

    # Run directly from python using
    if opts.container is None:
        bod = BOnD(data_root=str(opts.bids_dir),
                   use_datalad=opts.use_datalad,
                   grouping_config=opts.config)
        if opts.use_datalad and not bod.is_datalad_clean():
            raise Exception("Untracked change in " + str(opts.bids_dir))
        bod.get_CSVs(str(opts.output_prefix), )
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(opts.container)
    bids_dir_link = str(opts.bids_dir.absolute()) + ":/bids"
    output_dir_link = str(opts.output_prefix.parent.absolute()) + ":/csv:rw"

    apply_config = opts.config is not None
    if apply_config:
        input_config_dir_link = str(
            opts.config.parent.absolute()) + ":/in_config:ro"
        linked_input_config = "/in_config/" + opts.config.name

    linked_output_prefix = "/csv/" + opts.output_prefix.name
    if container_type == 'docker':
        cmd = ['docker', 'run', '--rm', '-v', bids_dir_link,
               '-v', GIT_CONFIG+":/root/.gitconfig",
               '-v', output_dir_link,
               '--entrypoint', 'bond-group',
               opts.container, '/bids', linked_output_prefix]
        if apply_config:
            cmd.insert(3, '-v')
            cmd.insert(4, input_config_dir_link)
            cmd += ['--config', linked_input_config]

    elif container_type == 'singularity':
        cmd = ['singularity', 'exec', '--cleanenv',
               '-B', bids_dir_link,
               '-B', output_dir_link,
               opts.container, 'bond-group',
               '/bids', linked_output_prefix]
        if apply_config:
            cmd.insert(3, '-B')
            cmd.insert(4, input_config_dir_link)
            cmd += ['--config', linked_input_config]

    if opts.use_datalad:
        cmd.append("--use-datalad")
    print("RUNNING: " + ' '.join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def bond_apply():
    ''' Command Line Interface funciton for applying the csv changes.'''

    parser = argparse.ArgumentParser(
        description="bond-apply: apply the changes specified in a csv "
        "to a BIDS directory",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('bids_dir',
                        type=Path,
                        action='store',
                        help='the root of a BIDS dataset. It should contain '
                        'sub-X directories and dataset_description.json')
    parser.add_argument('edited_summary_csv',
                        type=Path,
                        action='store',
                        help='the _summary.csv that has been edited in the '
                        'MergeInto and RenameKeyGroup columns.')
    parser.add_argument('files_csv',
                        type=Path,
                        action='store',
                        help='the _files.csv that the _summary.csv '
                        'corresponds to.')
    parser.add_argument('new_csv_prefix',
                        type=Path,
                        action='store',
                        help='file prefix for writing the new _summary.csv, '
                        '_files.csv and _group.csv that have been edited.')
    parser.add_argument('--use-datalad',
                        action='store_true',
                        help='ensure that there are no untracked changes '
                        'before finding groups')
    parser.add_argument('--container',
                        action='store',
                        help='Docker image tag or Singularity image file.')
    parser.add_argument('--config',
                        action='store',
                        type=Path,
                        help='path to a config file for grouping')
    opts = parser.parse_args()

    # Run directly from python using
    if opts.container is None:
        bod = BOnD(data_root=str(opts.bids_dir),
                   use_datalad=opts.use_datalad,
                   grouping_config=opts.config)
        if opts.use_datalad:
            if not bod.is_datalad_clean():
                raise Exception("Untracked change in " + str(opts.bids_dir))
        bod.apply_csv_changes(str(opts.edited_summary_csv),
                              str(opts.files_csv),
                              str(opts.new_csv_prefix),
                              raise_on_error=False)
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(opts.container)
    bids_dir_link = str(opts.bids_dir.absolute()) + ":/bids"
    input_summary_csv_dir_link = str(
        opts.edited_csv_prefix.parent.absolute()) + ":/in_summary_csv:ro"
    input_files_csv_dir_link = str(
        opts.edited_csv_prefix.parent.absolute()) + ":/in_files_csv:ro"
    output_csv_dir_link = str(
        opts.new_csv_prefix.parent.absolute()) + ":/out_csv:rw"

    # FROM BOND-GROUP
    apply_config = opts.config is not None
    if apply_config:
        input_config_dir_link = str(
            opts.config.parent.absolute()) + ":/in_config:ro"
        linked_input_config = "/in_config/" + opts.config.name

    linked_output_prefix = "/csv/" + opts.output_prefix.name

    ####

    linked_input_summary_csv = "/in_summary_csv/" \
        + opts.edited_summary_csv.name
    linked_input_files_csv = "/in_files_csv/" + opts.files_csv.name
    linked_output_prefix = "/out_csv/" + opts.new_csv_prefix.name
    if container_type == 'docker':
        cmd = ['docker', 'run', '--rm',
               '-v', bids_dir_link,
               '-v', GIT_CONFIG+":/root/.gitconfig",
               '-v', input_summary_csv_dir_link,
               '-v', input_files_csv_dir_link,
               '-v', output_csv_dir_link,
               '--entrypoint', 'bond-apply',
               opts.container, '/bids', linked_input_summary_csv,
               linked_input_files_csv, linked_output_prefix]
        if apply_config:
            cmd.insert(3, '-v')
            cmd.insert(4, input_config_dir_link)
            cmd += ['--config', linked_input_config]

    elif container_type == 'singularity':
        cmd = ['singularity', 'exec', '--cleanenv',
               '-B', bids_dir_link,
               '-B', input_summary_csv_dir_link,
               '-B', input_files_csv_dir_link,
               '-B', output_csv_dir_link,
               opts.container, 'bond-apply',
               '/bids', linked_input_summary_csv,
               linked_input_files_csv, linked_output_prefix]
        if apply_config:
            cmd.insert(3, '-B')
            cmd.insert(4, input_config_dir_link)
            cmd += ['--config', linked_input_config]

    if opts.use_datalad:
        cmd.append("--use-datalad")
    print("RUNNING: " + ' '.join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def bond_datalad_save():
    ''' Command Line Interfcae function for performing datalad save.'''

    parser = argparse.ArgumentParser(
        description="bond-datalad-save: perform a DataLad save on a BIDS "
        "directory",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('bids_dir',
                        type=Path,
                        action='store',
                        help='the root of a BIDS dataset. It should contain '
                        'sub-X directories and dataset_description.json')
    parser.add_argument('-m',
                        action='store',
                        help='message for this commit')
    parser.add_argument('--container',
                        action='store',
                        help='Docker image tag or Singularity image file.')
    opts = parser.parse_args()

    # Run directly from python using
    if opts.container is None:
        bod = BOnD(data_root=str(opts.bids_dir), use_datalad=True)
        bod.datalad_save(message=opts.m)
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(opts.container)
    bids_dir_link = str(opts.bids_dir.absolute()) + ":/bids"
    if container_type == 'docker':
        cmd = ['docker', 'run', '--rm', '-v', bids_dir_link,
               '-v', GIT_CONFIG+":/root/.gitconfig",
               '--entrypoint', 'bond-datalad-save',
               opts.container, '/bids', '-m', opts.m]
    elif container_type == 'singularity':
        cmd = ['singularity', 'exec', '--cleanenv',
               '-B', bids_dir_link,
               opts.container, 'bond-datalad-save',
               '/bids', '-m', opts.m]
    print("RUNNING: " + ' '.join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def bond_undo():
    ''' Command Line Interface function for reverting a commit.'''

    parser = argparse.ArgumentParser(
        description="bond-undo: revert most recent commit",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('bids_dir',
                        type=Path,
                        action='store',
                        help='the root of a BIDS dataset. It should contain '
                        'sub-X directories and dataset_description.json')
    parser.add_argument('--container',
                        action='store',
                        help='Docker image tag or Singularity image file.')
    opts = parser.parse_args()

    # Run directly from python using
    if opts.container is None:
        bod = BOnD(data_root=str(opts.bids_dir), use_datalad=True)
        bod.datalad_undo_last_commit()
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(opts.container)
    bids_dir_link = str(opts.bids_dir.absolute()) + ":/bids"
    if container_type == 'docker':
        cmd = ['docker', 'run', '--rm', '-v', bids_dir_link,
               '-v', GIT_CONFIG+":/root/.gitconfig",
               '--entrypoint', 'bond-undo',
               opts.container, '/bids']
    elif container_type == 'singularity':
        cmd = ['singularity', 'exec', '--cleanenv',
               '-B', bids_dir_link,
               opts.container, 'bond-undo', '/bids']
    print("RUNNING: " + ' '.join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def bond_copy_exemplars():
    ''' Command Line Interface function for purging scan associations.'''

    parser = argparse.ArgumentParser(
        description="bond-copy-exemplars: create and save a directory with "
        " one subject from each Acquisition Group in the BIDS dataset",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('bids_dir',
                        type=Path,
                        action='store',
                        help='absolute path to the root of a BIDS dataset. '
                        'It should contain sub-X directories and '
                        'dataset_description.json.')
    parser.add_argument('exemplars_dir',
                        type=Path,
                        action='store',
                        help='absolute path to the root of a BIDS dataset '
                        'containing one subject from each Acquisition Group. '
                        'It should contain sub-X directories and '
                        'dataset_description.json.')
    parser.add_argument('exemplars_csv',
                        type=Path,
                        action='store',
                        help='absolute path to the .csv file that lists one '
                        'subject from each Acqusition Group '
                        '(*_AcqGrouping.csv from the bond-group output)')
    parser.add_argument('--use-datalad',
                        action='store_true',
                        help='ensure that there are no untracked changes '
                        'before finding groups')
    parser.add_argument('--force-unlock',
                        action='store_true',
                        default=False,
                        help='unlock exemplar subjects before copying ',
                        required=False)
    parser.add_argument('--container',
                        action='store',
                        help='Docker image tag or Singularity image file.')
    opts = parser.parse_args()

    # Run directly from python using
    if opts.container is None:
        bod = BOnD(data_root=str(opts.bids_dir), use_datalad=opts.use_datalad)
        if opts.use_datalad:
            if bod.is_datalad_clean() and not opts.force_unlock:
                raise Exception("Need to unlock " + str(opts.bids_dir))
        bod.copy_exemplars(str(opts.exemplars_dir), str(opts.exemplars_csv),
                           force_unlock=opts.force_unlock,
                           raise_on_error=True)
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(opts.container)
    bids_dir_link = str(opts.bids_dir.absolute()) + ":/bids:ro"
    exemplars_dir_link = str(opts.exemplars_dir.absolute()) + ":/exemplars:ro"
    exemplars_csv_link = str(opts.exemplars_csv.absolute()) + ":/in_csv:ro"
    if container_type == 'docker':
        cmd = ['docker', 'run', '--rm', '-v', bids_dir_link,
               '-v', exemplars_dir_link,
               '-v', GIT_CONFIG+":/root/.gitconfig",
               '-v', exemplars_csv_link, '--entrypoint', 'bond-copy-exemplars',
               opts.container, '/bids', '/exemplars', '/in_csv']

        if opts.force_unlock:
            cmd.append('--force-unlock')
    elif container_type == 'singularity':
        cmd = ['singularity', 'exec', '--cleanenv',
               '-B', bids_dir_link,
               '-B', exemplars_dir_link,
               '-B', exemplars_csv_link, opts.container, 'bond-copy-exemplars',
               '/bids', '/exemplars', '/in_csv']
        if opts.force_unlock:
            cmd.append('--force-unlock')

    print("RUNNING: " + ' '.join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def bond_add_nifti_info():
    ''' Command Line Interface function for purging scan associations.'''

    parser = argparse.ArgumentParser(
        description="bond-add-nifti-info: Add information from nifti"
        "files to the sidecars of each dataset",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('bids_dir',
                        type=Path,
                        action='store',
                        help='absolute path to the root of a BIDS dataset. '
                        'It should contain sub-X directories and '
                        'dataset_description.json.')
    parser.add_argument('--use-datalad',
                        action='store_true',
                        help='ensure that there are no untracked changes '
                        'before finding groups')
    parser.add_argument('--force-unlock',
                        action='store_true',
                        default=False,
                        help='unlock dataset before adding nift info ',
                        required=False)
    parser.add_argument('--container',
                        action='store',
                        help='Docker image tag or Singularity image file.')
    opts = parser.parse_args()

    # Run directly from python using
    if opts.container is None:
        bod = BOnD(data_root=str(opts.bids_dir), use_datalad=opts.use_datalad)
        if opts.use_datalad:
            if bod.is_datalad_clean() and not opts.force_unlock:
                raise Exception("Need to unlock " + str(opts.bids_dir))
        bod.add_nifti_info(force_unlock=opts.force_unlock, raise_on_error=True)
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(opts.container)
    bids_dir_link = str(opts.bids_dir.absolute()) + ":/bids:ro"
    if container_type == 'docker':
        cmd = ['docker', 'run', '--rm', '-v', bids_dir_link,
               '-v', GIT_CONFIG+":/root/.gitconfig",
               '--entrypoint', 'bond-add-nifti-info',
               opts.container, '/bids']

        if opts.force_unlock:
            cmd.append('--force-unlock')
    elif container_type == 'singularity':
        cmd = ['singularity', 'exec', '--cleanenv',
               '-B', bids_dir_link,
               opts.container, 'bond-add-nifti-info',
               '/bids']
        if opts.force_unlock:
            cmd.append('--force-unlock')

    print("RUNNING: " + ' '.join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def bond_purge():
    ''' Command Line Interface function for purging scan associations.'''

    parser = argparse.ArgumentParser(
        description="bond-purge: purge associations from the dataset",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('bids_dir',
                        type=Path,
                        action='store',
                        help='absolute path to the root of a BIDS dataset. '
                        'It should contain sub-X directories and '
                        'dataset_description.json.')
    parser.add_argument('scans',
                        type=Path,
                        action='store',
                        help='absolute path to the txt file of scans whose '
                        'associations should be purged.')
    parser.add_argument('--use-datalad',
                        action='store_true',
                        help='ensure that there are no untracked changes '
                        'before finding groups')
    parser.add_argument('--container',
                        action='store',
                        help='Docker image tag or Singularity image file.')
    opts = parser.parse_args()

    # Run directly from python using
    if opts.container is None:
        bod = BOnD(data_root=str(opts.bids_dir), use_datalad=opts.use_datalad)
        if opts.use_datalad:
            if not bod.is_datalad_clean():
                raise Exception("Untracked change in " + str(opts.bids_dir))
        bod.purge(str(opts.scans), raise_on_error=False)
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(opts.container)
    bids_dir_link = str(opts.bids_dir.absolute()) + ":/bids"
    input_scans_link = str(
        opts.scans.parent.absolute()) + ":/in_scans:ro"
    if container_type == 'docker':
        cmd = ['docker', 'run', '--rm',
               '-v', bids_dir_link,
               '-v', GIT_CONFIG+":/root/.gitconfig",
               '-v', input_scans_link,
               '--entrypoint', 'bond-purge',
               opts.container, '/bids', input_scans_link]

    elif container_type == 'singularity':
        cmd = ['singularity', 'exec', '--cleanenv',
               '-B', bids_dir_link,
               '-B', input_scans_link,
               opts.container, 'bond-purge',
               '/bids', input_scans_link]
    print("RUNNING: " + ' '.join(cmd))
    if opts.use_datalad:
        cmd.append("--use-datalad")
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def bond_remove_metadata_fields():
    ''' Command Line Interface function for deteling fields from metadata.'''

    parser = argparse.ArgumentParser(
        description="bond-remove-metadata-fields: delete fields from "
        "metadata",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('bids_dir',
                        type=Path,
                        action='store',
                        help='the root of a BIDS dataset. It should contain '
                        'sub-X directories and dataset_description.json')
    parser.add_argument('--fields',
                        nargs='+',
                        action='store',
                        default=[],
                        help='space-separated list of metadata fields to '
                        'remove.')
    parser.add_argument('--container',
                        action='store',
                        help='Docker image tag or Singularity image file.')
    opts = parser.parse_args()

    # Run directly from python
    if opts.container is None:
        bod = BOnD(data_root=str(opts.bids_dir), use_datalad=False)
        bod.remove_metadata_fields(opts.fields)
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(opts.container)
    bids_dir_link = str(opts.bids_dir.absolute()) + ":/bids:rw"
    if container_type == 'docker':
        cmd = ['docker', 'run', '--rm', '-v', bids_dir_link,
               '--entrypoint', 'bond-remove-metadata-fields',
               opts.container, '/bids', '--fields'] + opts.fields
    elif container_type == 'singularity':
        cmd = ['singularity', 'exec', '--cleanenv',
               '-B', bids_dir_link,
               opts.container, 'bond-remove-metadata-fields',
               '/bids', '--fields'] + opts.fields
    print("RUNNING: " + ' '.join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def bond_print_metadata_fields():
    '''Command Line Interface function that prints unique metadata fields.'''

    parser = argparse.ArgumentParser(
        description="bond-print-metadata-fields: print all unique "
        "metadata fields",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('bids_dir',
                        type=Path,
                        action='store',
                        help='the root of a BIDS dataset. It should contain '
                        'sub-X directories and dataset_description.json')
    parser.add_argument('--container',
                        action='store',
                        help='Docker image tag or Singularity image file.')
    opts = parser.parse_args()

    # Run directly from python
    if opts.container is None:
        bod = BOnD(data_root=str(opts.bids_dir), use_datalad=False)
        fields = bod.get_all_metadata_fields()
        print("\n".join(fields))
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(opts.container)
    bids_dir_link = str(opts.bids_dir.absolute()) + ":/bids:ro"
    if container_type == 'docker':
        cmd = ['docker', 'run', '--rm', '-v', bids_dir_link,
               '--entrypoint', 'bond-print-metadata-fields',
               opts.container, '/bids']
    elif container_type == 'singularity':
        cmd = ['singularity', 'exec', '--cleanenv',
               '-B', bids_dir_link,
               opts.container, 'bond-print-metadata-fields',
               '/bids']
    print("RUNNING: " + ' '.join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def _get_container_type(image_name):
    '''Gets and returns the container type.'''

    # If it's a file on disk, it must be a singularity image
    if Path(image_name).exists():
        return "singularity"

    # It needs to match a docker tag pattern to be docker
    if re.match(r"(?:.+\/)?([^:]+)(?::.+)?", image_name):
        return "docker"

    raise Exception("Unable to determine the container type of "
                    + image_name)
