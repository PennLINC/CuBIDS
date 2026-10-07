"""Tests for ASL/M0 renaming behavior.

Ensures that when ASL scans are renamed with variant acquisition labels:
- aslcontext files are renamed to match the ASL scan
- M0 files (nii/json) are NOT renamed
- M0 JSON IntendedFor entries are updated to point to the new ASL path
"""

import json

import pandas as pd

from cubids.workflows import apply


def test_asl_rename_keeps_m0_and_updates_intendedfor(tmp_path, build_bids_dataset):
    """Renaming an ASL scan renames its aslcontext but leaves the M0 scan in place.

    The M0 scan keeps its own name because its variability is independent of
    the ASL series; only its IntendedFor reference follows the renamed ASL file.
    """
    bids_root = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="perf_m0_dataset",
        skeleton_name="skeleton_perf_m0.yml",
    )
    perf_dir = bids_root / "sub-01" / "ses-01" / "perf"
    asl_base = perf_dir / "sub-01_ses-01_asl.nii.gz"
    m0_base = perf_dir / "sub-01_ses-01_m0scan.nii.gz"
    m0_json = perf_dir / "sub-01_ses-01_m0scan.json"
    aslcontext = perf_dir / "sub-01_ses-01_aslcontext.tsv"

    # generate_bids_skeleton creates empty files and sidecars from the YAML skeleton.
    assert asl_base.exists()
    assert m0_base.exists()
    assert m0_json.exists()

    # Add an ASL context file to ensure companion rename behavior is exercised.
    aslcontext.write_text("label\ncontrol\nlabel\ncontrol\n")

    asl_entity_set = "datatype-perf_suffix-asl"
    m0_entity_set = "datatype-perf_suffix-m0scan"
    summary = pd.DataFrame(
        {
            "RenameEntitySet": [f"{asl_entity_set}_acquisition-VARIANTTest", None],
            "KeyParamGroup": [f"{asl_entity_set}__1", f"{m0_entity_set}__1"],
            "EntitySet": [asl_entity_set, m0_entity_set],
            "ParamGroup": [1, 1],
            "MergeInto": [None, None],
        }
    )
    files = pd.DataFrame(
        {
            "FilePath": [
                f"/{asl_base.relative_to(bids_root).as_posix()}",
                f"/{m0_base.relative_to(bids_root).as_posix()}",
            ],
            "KeyParamGroup": summary["KeyParamGroup"],
            "EntitySet": summary["EntitySet"],
            "ParamGroup": [1, 1],
        }
    )
    summary_tsv = tmp_path / "summary.tsv"
    files_tsv = tmp_path / "files.tsv"
    summary.to_csv(summary_tsv, sep="\t", index=False)
    files.to_csv(files_tsv, sep="\t", index=False)

    apply(
        bids_dir=str(bids_root),
        use_datalad=False,
        acq_group_level="subject",
        config=None,
        schema=None,
        edited_summary_tsv=summary_tsv,
        files_tsv=files_tsv,
        new_tsv_prefix=tmp_path / "v1",
    )

    # The ASL scan, its sidecar, and its aslcontext were renamed together.
    new_stem = perf_dir / "sub-01_ses-01_acq-VARIANTTest"
    assert not asl_base.exists()
    assert not aslcontext.exists()
    assert (perf_dir / "sub-01_ses-01_acq-VARIANTTest_asl.nii.gz").exists()
    assert (perf_dir / "sub-01_ses-01_acq-VARIANTTest_asl.json").exists()
    assert (perf_dir / "sub-01_ses-01_acq-VARIANTTest_aslcontext.tsv").exists()
    assert not list(perf_dir.glob(f"{new_stem.name}_m0scan*"))

    # The M0 scan keeps its name, but its IntendedFor follows the renamed ASL file.
    assert m0_base.exists()
    assert m0_json.exists()
    assert json.loads(m0_json.read_text())["IntendedFor"] == [
        "ses-01/perf/sub-01_ses-01_acq-VARIANTTest_asl.nii.gz"
    ]
