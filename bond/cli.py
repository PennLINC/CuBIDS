"""Console script for bond."""
import argparse
import sys
import docker
import logging
from .docker_run import check_docker, check_image, build_validator_call, run, parse_validator


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bond-cli')


def run_validator(bidsdir, output_path=None):
    """Run the BIDS validator on a BIDS directory"""

    #check for docker and the image
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


def main():
    """Console script for bond."""
    parser = argparse.ArgumentParser()
    parser.add_argument('_', nargs='*')
    args = parser.parse_args()

    print("Arguments: " + str(args._))
    print("Replace this message by putting your code into "
          "bond.cli.main")
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
