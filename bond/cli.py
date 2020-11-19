"""Console script for bond."""
import argparse
import subprocess
from pathlib import Path
import os
import sys
import re
import logging
from bond import BOnD
from .validator import (check_docker, check_image, build_validator_call,
                         run, parse_validator)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bond-cli')
GIT_CONFIG = os.path.join(os.path.expanduser("~"), '.gitconfig')


def run_validator(bidsdir, output_path=None):
    """Run the BIDS validator on a BIDS directory"""

    # check for docker and the image
    if not all([check_docker(), check_image("bond")]):
        logger.error("Couldn't run validator! Please make sure you Docker"
                     " installed and the correct Docker image cloned: ")
        return 1

    # build the call and run
    call = build_validator_call(bidsdir)
    ret = run(call)

    if ret.returncode != 0:
        logger.error("Errors returned from validator run, parsing now")

    # parse the string output
    parsed = parse_validator(ret.stdout.decode('UTF-8'))
    if parsed.shape[1] < 1:
        logger.info("No issues/warnings parsed, your dataset must be valid.")
    else:
        logger.info("BIDS issues/warnings found in the dataset")

        if output_path:
            # normally, write dataframe to file in CLI
            logger.info("Writing issues out to file")
            parsed.to_csv(output_path, index=False)
        else:
            # user may be in python session, return dataframe
            return parsed


def bond_validate():
    pass


def bond_group():
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
    opts = parser.parse_args()

    # Run directly from python using
    if opts.container is None:
        bod = BOnD(data_root=str(opts.bids_dir),
                   use_datalad=opts.use_datalad)
        if opts.use_datalad and not bod.is_datalad_clean():
            raise Exception("Untracked change in " + str(opts.bids_dir))
        bod.get_CSVs(str(opts.output_prefix))
        sys.exit(0)

    # Run it through a container
    container_type = _get_container_type(opts.container)
    bids_dir_link = str(opts.bids_dir.absolute()) + ":/bids"
    output_dir_link = str(opts.output_prefix.parent.absolute()) + ":/csv:rw"
    linked_output_prefix = "/csv/" + opts.output_prefix.name
    if container_type == 'docker':
        cmd = ['docker', 'run', '--rm', '-v', bids_dir_link,
               '-v', GIT_CONFIG+":/root/.gitconfig",
               '-v', output_dir_link, '--entrypoint', 'bond-group',
               opts.container, '/bids', linked_output_prefix]
    elif container_type == 'singularity':
        cmd = ['singularity', 'exec', '--cleanenv',
               '-B', bids_dir_link,
               '-B', output_dir_link, opts.container, 'bond-group',
               '/bids', linked_output_prefix]
    if opts.use_datalad:
        cmd.append("--use-datalad")
    print("RUNNING: " + ' '.join(cmd))
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)


def bond_apply():
    pass


def param_group_merge():
    pass


def bond_datalad_save():
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


def _get_container_type(image_name):

    # If it's a file on disk, it must be a singularity image
    if Path(image_name).exists():
        return "singularity"

    # It needs to match a docker tag pattern to be docker
    if re.match(r"(?:.+\/)?([^:]+)(?::.+)?", image_name):
        return "docker"

    raise Exception("Unable to determine the container type of " + image_name)
