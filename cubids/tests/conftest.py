"""Shared pytest fixtures for CuBIDS tests."""

import json
from pathlib import Path

import pytest
from niworkflows.utils.testing import generate_bids_skeleton

from cubids.tests.utils import TEST_DATA


def _convert_relative_to_bids_uri(dataset_root: Path) -> None:
    """Convert IntendedFor sidecar values from relative paths to BIDS URIs."""
    for fmap_json in dataset_root.rglob("*_epi.json"):
        metadata = json.loads(fmap_json.read_text())
        intended_for = metadata.get("IntendedFor")
        if not intended_for:
            continue

        rel_parts = fmap_json.relative_to(dataset_root).parts
        subject = rel_parts[0]

        updated = []
        for item in intended_for:
            if item.startswith("bids::"):
                updated.append(item)
            else:
                updated.append(f"bids::{subject}/{item}")

        metadata["IntendedFor"] = updated
        fmap_json.write_text(json.dumps(metadata))


@pytest.fixture
def build_bids_dataset():
    """Build a test dataset from a skeleton YAML.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Per-test temporary directory.
    dataset_name : str
        Dataset directory name to create inside tmp_path.
    skeleton_name : str
        YAML file name under ``cubids/tests/data/skeletons``.
    intended_for_mode : {"relative_path", "bids_uri"}
        Optional conversion mode for IntendedFor values.
    """

    def _build(
        tmp_path: Path,
        dataset_name: str,
        skeleton_name: str,
        intended_for_mode: str = "relative_path",
    ) -> Path:
        bids_dir = tmp_path / dataset_name
        dset_yaml = str(TEST_DATA / "skeletons" / skeleton_name)
        generate_bids_skeleton(str(bids_dir), dset_yaml)

        if intended_for_mode == "bids_uri":
            _convert_relative_to_bids_uri(bids_dir)
        elif intended_for_mode != "relative_path":
            raise ValueError(f"Unknown intended_for_mode: {intended_for_mode}")

        return bids_dir

    return _build
