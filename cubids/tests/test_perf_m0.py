"""Tests for ASL/M0 renaming behavior.

Ensures that when ASL scans are renamed with variant acquisition labels:
- aslcontext files are renamed to match the ASL scan
- M0 files (nii/json) are NOT renamed
- M0 JSON IntendedFor entries are updated to point to the new ASL path
"""

import json
from pathlib import Path

from cubids.cubids import CuBIDS


def _write(path: Path, content: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_m0_not_renamed_but_aslcontext_is_and_intendedfor_updated(tmp_path, build_bids_dataset):
    bids_root = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="perf_m0_dataset",
        skeleton_name="skeleton_perf_m0.yml",
    )
    sub = "sub-01"
    ses = "ses-01"

    perf_dir = bids_root / sub / ses / "perf"

    asl_base = perf_dir / f"{sub}_{ses}_asl.nii.gz"
    m0_base = perf_dir / f"{sub}_{ses}_m0scan.nii.gz"
    m0_json = perf_dir / f"{sub}_{ses}_m0scan.json"
    aslcontext = perf_dir / f"{sub}_{ses}_aslcontext.tsv"

    # Generate_bids_skeleton creates empty files and sidecars from the YAML skeleton.
    assert asl_base.exists()
    assert m0_base.exists()
    assert m0_json.exists()

    # Add ASL context file to ensure companion rename behavior is exercised.
    intended_for_rel = f"{ses}/perf/{sub}_{ses}_asl.nii.gz"
    _write(aslcontext, "label\ncontrol\nlabel\ncontrol\n")

    c = CuBIDS(str(bids_root))

    # Rename the ASL scan by adding a variant acquisition
    entities = {"suffix": "asl", "acquisition": "VARIANTTest"}
    c.change_filename(str(asl_base), entities)

    # Old/new filenames prepared for ASL and aslcontext, but NOT for M0
    assert str(asl_base) in c.old_filenames
    assert any(fn.endswith("_asl.json") for fn in c.old_filenames)
    assert any(fn.endswith("_aslcontext.tsv") for fn in c.old_filenames)

    assert not any(fn.endswith("_m0scan.nii.gz") for fn in c.old_filenames)
    assert not any(fn.endswith("_m0scan.json") for fn in c.old_filenames)

    # Compute expected new ASL path and aslcontext path
    expected_new_asl = perf_dir / f"{sub}_{ses}_acq-VARIANTTest_asl.nii.gz"
    expected_new_aslcontext = perf_dir / f"{sub}_{ses}_acq-VARIANTTest_aslcontext.tsv"

    assert str(expected_new_asl) in c.new_filenames
    assert str(expected_new_aslcontext) in c.new_filenames

    # M0 files remain with original names
    assert m0_base.exists()
    assert m0_json.exists()

    # But M0 IntendedFor should now point to the new ASL relative path
    with open(m0_json, "r") as f:
        m0_meta = json.load(f)

    new_rel = f"{ses}/perf/{sub}_{ses}_acq-VARIANTTest_asl.nii.gz"
    assert "IntendedFor" in m0_meta
    assert new_rel in m0_meta["IntendedFor"]
    # Ensure old reference removed
    assert intended_for_rel not in m0_meta["IntendedFor"]
