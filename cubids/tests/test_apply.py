"""Test cubids apply."""

from pathlib import Path

import pandas as pd
import pytest

from cubids import utils
from cubids.cubids import CuBIDS


@pytest.fixture(scope="module")
def files_data():
    """Return data for a CuBIDS files TSV test.

    Returns
    -------
    dict
        A dictionary containing file data for longitudinal and cross-sectional datasets.
    """
    dict_ = {
        "longitudinal": {
            "ParamGroup": [1, 1, 1, 1],
            "EntitySet": [
                "datatype-anat_suffix-T1w",
                "datatype-dwi_direction-AP_run-01_suffix-dwi",
                "datatype-fmap_direction-AP_fmap-epi_suffix-epi",
                "datatype-fmap_direction-PA_fmap-epi_suffix-epi",
            ],
            "FilePath": [
                "/sub-01/ses-01/anat/sub-01_ses-01_T1w.nii.gz",
                "/sub-01/ses-01/dwi/sub-01_ses-01_dir-AP_run-01_dwi.nii.gz",
                "/sub-01/ses-01/fmap/sub-01_ses-01_dir-AP_epi.nii.gz",
                "/sub-01/ses-01/fmap/sub-01_ses-01_dir-PA_epi.nii.gz",
            ],
            "KeyParamGroup": [
                "datatype-anat_suffix-T1w__1",
                "datatype-dwi_direction-AP_run-01_suffix-dwi__1",
                "datatype-fmap_direction-AP_fmap-epi_suffix-epi__1",
                "datatype-fmap_direction-PA_fmap-epi_suffix-epi__1",
            ],
        },
        "cross-sectional": {
            "ParamGroup": [1, 1, 1, 1],
            "EntitySet": [
                "datatype-anat_suffix-T1w",
                "datatype-dwi_direction-AP_run-01_suffix-dwi",
                "datatype-fmap_direction-AP_fmap-epi_suffix-epi",
                "datatype-fmap_direction-PA_fmap-epi_suffix-epi",
            ],
            "FilePath": [
                "/sub-01/anat/sub-01_T1w.nii.gz",
                "/sub-01/dwi/sub-01_dir-AP_run-01_dwi.nii.gz",
                "/sub-01/fmap/sub-01_dir-AP_epi.nii.gz",
                "/sub-01/fmap/sub-01_dir-PA_epi.nii.gz",
            ],
            "KeyParamGroup": [
                "datatype-anat_suffix-T1w__1",
                "datatype-dwi_direction-AP_run-01_suffix-dwi__1",
                "datatype-fmap_direction-AP_fmap-epi_suffix-epi__1",
                "datatype-fmap_direction-PA_fmap-epi_suffix-epi__1",
            ],
        },
    }
    return dict_


@pytest.fixture(scope="module")
def summary_data():
    """Return data for a CuBIDS summary TSV test.

    Returns
    -------
    dict
        A dictionary containing summary data for CuBIDS.
    """
    dict_ = {
        "RenameEntitySet": [
            None,
            "datatype-dwi_direction-AP_run-01_suffix-dwi_acquisition-VAR",
            None,
            None,
        ],
        "KeyParamGroup": [
            "datatype-anat_suffix-T1w__1",
            "datatype-dwi_direction-AP_run-01_suffix-dwi__1",
            "datatype-fmap_direction-AP_fmap-epi_suffix-epi__1",
            "datatype-fmap_direction-PA_fmap-epi_suffix-epi__1",
        ],
        "HasFieldmap": [False, True, False, False],
        "UsedAsFieldmap": [False, False, True, True],
        "MergeInto": [None, None, None, None],
        "EntitySet": [
            "datatype-anat_suffix-T1w",
            "datatype-dwi_direction-AP_run-01_suffix-dwi",
            "datatype-fmap_direction-AP_fmap-epi_suffix-epi",
            "datatype-fmap_direction-PA_fmap-epi_suffix-epi",
        ],
        "ParamGroup": [1, 1, 1, 1],
    }
    return dict_


@pytest.mark.parametrize(
    ("name", "skeleton_name", "intended_for_mode", "intended_for", "is_longitudinal"),
    [
        (
            "relpath_long",
            "skeleton_apply_longitudinal_realistic.yml",
            "relative_path",
            "ses-01/dwi/sub-01_ses-01_acq-VAR_dir-AP_run-01_dwi.nii.gz",
            True,
        ),
        (
            "bidsuri_long",
            "skeleton_apply_longitudinal_realistic.yml",
            "bids_uri",
            "bids::sub-01/ses-01/dwi/sub-01_ses-01_acq-VAR_dir-AP_run-01_dwi.nii.gz",
            True,
        ),
        (
            "relpath_cs",
            "skeleton_apply_cross_sectional_realistic.yml",
            "relative_path",
            "dwi/sub-01_acq-VAR_dir-AP_run-01_dwi.nii.gz",
            False,
        ),
        (
            "bidsuri_cs",
            "skeleton_apply_cross_sectional_realistic.yml",
            "bids_uri",
            "bids::sub-01/dwi/sub-01_acq-VAR_dir-AP_run-01_dwi.nii.gz",
            False,
        ),
    ],
)
def test_cubids_apply_intendedfor(
    tmp_path,
    build_bids_dataset,
    summary_data,
    files_data,
    name,
    skeleton_name,
    intended_for_mode,
    intended_for,
    is_longitudinal,
):
    """Test cubids apply with different IntendedFor types.

    Parameters
    ----------
    tmpdir : LocalPath
        Temporary directory for the test.
    summary_data : dict
        Summary data fixture.
    files_data : dict
        Files data fixture.
    name : str
        Name of the test case.
    skeleton_name : str
        Name of the BIDS skeleton YAML file.
    intended_for_mode : {"relative_path", "bids_uri"}
        IntendedFor value format.
    intended_for : str
        IntendedFor field value.
    is_longitudinal : bool
        Indicate whether the data structure is longitudinal or cross-sectional.
    """
    import json

    from cubids.workflows import apply

    # Generate a BIDS dataset
    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name=name,
        skeleton_name=skeleton_name,
        intended_for_mode=intended_for_mode,
    )

    if is_longitudinal:
        fdata = files_data["longitudinal"]
        fmap_json = bids_dir / "sub-01/ses-01/fmap/sub-01_ses-01_dir-AP_epi.json"
        scans_tsv = bids_dir / "sub-01/ses-01/sub-01_ses-01_scans.tsv"
        old_scans_filename = "dwi/sub-01_ses-01_dir-AP_run-01_dwi.nii.gz"
        new_scans_filename = "dwi/sub-01_ses-01_acq-VAR_dir-AP_run-01_dwi.nii.gz"
    else:
        fdata = files_data["cross-sectional"]
        fmap_json = bids_dir / "sub-01/fmap/sub-01_dir-AP_epi.json"
        scans_tsv = bids_dir / "sub-01/sub-01_scans.tsv"
        old_scans_filename = "dwi/sub-01_dir-AP_run-01_dwi.nii.gz"
        new_scans_filename = "dwi/sub-01_acq-VAR_dir-AP_run-01_dwi.nii.gz"

    scans_tsv.write_text(
        "filename\tacq_time\tnote\n"
        f"{old_scans_filename}\t2024-01-01T00:00:00\tchanged\n"
        "dwi/not-renamed_dwi.nii.gz\t2024-01-01T00:01:00\tunchanged\n"
    )

    # Create a CuBIDS summary tsv
    summary_tsv = tmp_path / "summary.tsv"
    df = pd.DataFrame(summary_data)
    df.to_csv(summary_tsv, sep="\t", index=False)

    # Create a CuBIDS files tsv
    files_tsv = tmp_path / "files.tsv"
    df = pd.DataFrame(fdata)
    df.to_csv(files_tsv, sep="\t", index=False)

    # Run cubids apply
    apply(
        bids_dir=str(bids_dir),
        use_datalad=False,
        acq_group_level="subject",
        config=None,
        schema=None,
        edited_summary_tsv=summary_tsv,
        files_tsv=files_tsv,
        new_tsv_prefix=None,
    )

    with open(fmap_json) as f:
        metadata = json.load(f)

    assert metadata["IntendedFor"] == [intended_for]
    scans = pd.read_csv(scans_tsv, sep="\t", keep_default_na=False)
    assert scans["filename"].tolist() == [new_scans_filename, "dwi/not-renamed_dwi.nii.gz"]
    assert scans["note"].tolist() == ["changed", "unchanged"]


def test_cubids_apply_intendedfor_large_dataset(tmp_path, build_bids_dataset, summary_data):
    """Ensure IntendedFor rewriting still works in a larger realistic dataset."""
    import json

    from cubids.workflows import apply

    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="large_realistic",
        skeleton_name="skeleton_apply_longitudinal_realistic.yml",
        intended_for_mode="relative_path",
    )

    # Only one subset is renamed; additional dataset content is retained.
    files_data = {
        "ParamGroup": [1],
        "EntitySet": ["datatype-dwi_direction-AP_run-01_suffix-dwi"],
        "FilePath": ["/sub-ABC/ses-01/dwi/sub-ABC_ses-01_dir-AP_run-01_dwi.nii.gz"],
        "KeyParamGroup": ["datatype-dwi_direction-AP_run-01_suffix-dwi__1"],
    }
    summary_data_large = pd.DataFrame(summary_data).copy()
    summary_data_large = summary_data_large[
        summary_data_large["EntitySet"] == "datatype-dwi_direction-AP_run-01_suffix-dwi"
    ]

    summary_data_large.loc[:, "RenameEntitySet"] = (
        "datatype-dwi_direction-AP_run-01_suffix-dwi_acquisition-VAR"
    )

    summary_tsv = tmp_path / "summary.tsv"
    summary_data_large.to_csv(summary_tsv, sep="\t", index=False)

    files_tsv = tmp_path / "files.tsv"
    pd.DataFrame(files_data).to_csv(files_tsv, sep="\t", index=False)

    apply(
        bids_dir=str(bids_dir),
        use_datalad=False,
        acq_group_level="subject",
        config=None,
        schema=None,
        edited_summary_tsv=summary_tsv,
        files_tsv=files_tsv,
        new_tsv_prefix=None,
    )

    fmap_json = bids_dir / "sub-ABC/ses-01/fmap/sub-ABC_ses-01_dir-AP_epi.json"
    with open(fmap_json) as f:
        metadata = json.load(f)

    assert metadata["IntendedFor"] == [
        "ses-01/dwi/sub-ABC_ses-01_acq-VAR_dir-AP_run-01_dwi.nii.gz"
    ]


def _fmap_apply_tables(acquisition_ap, acquisition_pa):
    """Return matching apply tables for one cross-sectional PEPOLAR pair."""
    entities = {
        direction: utils._entities_to_entity_set(
            {"datatype": "fmap", "direction": direction, "fmap": "epi", "suffix": "epi"}
        )
        for direction in ("AP", "PA")
    }
    summary = pd.DataFrame(
        {
            "RenameEntitySet": [
                f"{entities['AP']}_acquisition-{acquisition_ap}",
                f"{entities['PA']}_acquisition-{acquisition_pa}",
            ],
            "KeyParamGroup": [f"{entities['AP']}__1", f"{entities['PA']}__1"],
            "EntitySet": [entities["AP"], entities["PA"]],
            "ParamGroup": [1, 1],
            "MergeInto": [None, None],
        }
    )
    files = pd.DataFrame(
        {
            "FilePath": [
                "/sub-01/fmap/sub-01_dir-AP_epi.nii.gz",
                "/sub-01/fmap/sub-01_dir-PA_epi.nii.gz",
            ],
            "KeyParamGroup": [f"{entities['AP']}__1", f"{entities['PA']}__1"],
            "EntitySet": [entities["AP"], entities["PA"]],
            "ParamGroup": [1, 1],
            "PhaseEncodingDirection": ["j", "j-"],
        }
    )
    return summary, files


def _add_fmap_epi_associations(bids_dir):
    """Add PEPOLAR metadata and gradient companions to the test fixture."""
    import json

    for direction, ped in [("AP", "j"), ("PA", "j-")]:
        stem = bids_dir / "sub-01/fmap" / f"sub-01_dir-{direction}_epi"
        json_path = stem.with_suffix(".json")
        metadata = json.loads(json_path.read_text())
        metadata["PhaseEncodingDirection"] = ped
        json_path.write_text(json.dumps(metadata))
        stem.with_suffix(".bval").write_text("0\n")
        stem.with_suffix(".bvec").write_text("0\n0\n0\n")


def test_get_associated_file_pairs_plan_every_bold_companion(tmp_path):
    """Rename, validation, and purge share one complete BOLD association plan."""
    source = tmp_path / "sub-01/func/sub-01_task-rest_bold.nii.gz"
    source.parent.mkdir(parents=True)
    source.touch()
    source_stem = str(source).removesuffix(".nii.gz")
    source_base = str(source).replace("_bold.nii.gz", "")
    companions = [
        source_stem + ".json",
        source_base + "_events.tsv",
        source_base + "_events.json",
        source_base + "_sbref.nii.gz",
        source_base + "_sbref.json",
        source_base + "_physio.tsv.gz",
        source_base + "_physio.json",
    ]
    for companion in companions:
        Path(companion).touch()

    destination = str(source).replace("_bold.nii.gz", "_acq-VARIANT_bold.nii.gz")
    pairs = dict(CuBIDS.get_associated_file_pairs(source, destination))

    assert pairs[str(source)] == destination
    assert pairs[source_stem + ".json"] == destination.removesuffix(".nii.gz") + ".json"
    for extension in [
        "_events.tsv",
        "_events.json",
        "_sbref.nii.gz",
        "_sbref.json",
        "_physio.tsv.gz",
        "_physio.json",
    ]:
        assert pairs[source_base + extension] == destination.replace("_bold.nii.gz", extension)
    assert all(target is None for _, target in CuBIDS.get_associated_file_pairs(source))


def test_rename_validation_checks_bold_companion_destinations(tmp_path, build_bids_dataset):
    """A pre-existing event file cannot be overwritten by a BOLD rename."""
    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="bold_companion_collision",
        skeleton_name="skeleton_apply_cross_sectional_realistic.yml",
    )
    source = next((bids_dir / "sub-01/func").glob("*_bold.nii.gz"))
    entity_set = utils._file_to_entity_set(source)
    renamed_entities = utils._entity_set_to_entities(entity_set)
    renamed_entities["acquisition"] = "VARIANT"
    renamed_entity_set = utils._entities_to_entity_set(renamed_entities)
    cubids = CuBIDS(bids_dir, use_datalad=False)
    destination = cubids.get_planned_destination(str(source), renamed_entities)
    source_event = source.with_name(source.name.removesuffix("_bold.nii.gz") + "_events.tsv")
    destination_event = Path(destination.replace("_bold.nii.gz", "_events.tsv"))
    source_event.write_text("onset\n0\n")
    destination_event.write_text("onset\n1\n")

    key_param_group = f"{entity_set}__1"
    files = pd.DataFrame(
        {
            "FilePath": [f"/{source.relative_to(bids_dir).as_posix()}"],
            "KeyParamGroup": [key_param_group],
        }
    )
    plan = cubids.plan_renames(
        files, {key_param_group: renamed_entity_set}, allow_fmap_renames=False
    )
    pairs = cubids.plan_rename_pairs(plan)

    with pytest.raises(ValueError, match="destination already exists"):
        cubids.validate_rename_destinations(pairs)

    # The same collision is safe when the occupying file is deleted first.
    cubids.validate_rename_destinations(pairs, pending_deletions=[str(destination_event)])


def test_cubids_apply_fmap_renames_epi_associations(tmp_path, build_bids_dataset):
    """--fmap renames validated PEPOLAR NIfTI, JSON, bval, and bvec files."""
    from cubids.workflows import apply

    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="fmap_apply",
        skeleton_name="skeleton_apply_cross_sectional_realistic.yml",
    )
    _add_fmap_epi_associations(bids_dir)
    summary, files = _fmap_apply_tables("VARIANTVar1", "VARIANTVar1")
    summary_tsv = tmp_path / "summary.tsv"
    files_tsv = tmp_path / "files.tsv"
    summary.to_csv(summary_tsv, sep="\t", index=False)
    files.to_csv(files_tsv, sep="\t", index=False)

    apply(
        bids_dir=str(bids_dir),
        use_datalad=False,
        acq_group_level="subject",
        config=None,
        schema=None,
        edited_summary_tsv=summary_tsv,
        files_tsv=files_tsv,
        new_tsv_prefix=tmp_path / "v1",
        allow_fmap_renames=True,
    )

    for direction in ["AP", "PA"]:
        old_stem = bids_dir / "sub-01/fmap" / f"sub-01_dir-{direction}_epi"
        new_stem = bids_dir / "sub-01/fmap" / f"sub-01_acq-VARIANTVar1_dir-{direction}_epi"
        assert not old_stem.with_suffix(".nii.gz").exists()
        for extension in [".nii.gz", ".json", ".bval", ".bvec"]:
            assert new_stem.with_suffix(extension).exists()


def test_cubids_apply_fmap_rejects_mismatched_pair_before_renaming(tmp_path, build_bids_dataset):
    """--fmap fails before writes when an AP/PA pair has different planned labels."""
    from cubids.workflows import apply

    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="fmap_reject",
        skeleton_name="skeleton_apply_cross_sectional_realistic.yml",
    )
    _add_fmap_epi_associations(bids_dir)
    summary, files = _fmap_apply_tables("VARIANTVar1", "VARIANTVar2")
    summary_tsv = tmp_path / "summary.tsv"
    files_tsv = tmp_path / "files.tsv"
    summary.to_csv(summary_tsv, sep="\t", index=False)
    files.to_csv(files_tsv, sep="\t", index=False)

    with pytest.raises(ValueError, match="matching, complete fieldmap collections"):
        apply(
            bids_dir=str(bids_dir),
            use_datalad=False,
            acq_group_level="subject",
            config=None,
            schema=None,
            edited_summary_tsv=summary_tsv,
            files_tsv=files_tsv,
            new_tsv_prefix=tmp_path / "v1",
            allow_fmap_renames=True,
        )

    assert (bids_dir / "sub-01/fmap/sub-01_dir-AP_epi.nii.gz").exists()
    assert not (bids_dir / "sub-01/fmap/sub-01_acq-VARIANTVar1_dir-AP_epi.nii.gz").exists()


def test_cubids_apply_change_rename_entity_set_writes_a_new_summary(tmp_path, build_bids_dataset):
    """--change-RenameEntitySet is an exact summary transformation with an audit copy."""
    from cubids.workflows import apply

    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="change_entity_set",
        skeleton_name="skeleton_apply_cross_sectional_realistic.yml",
    )
    old = "VARIANTEchoTimeC1TotalReadoutTimeC1"
    new = "VARIANTVar1"
    dwi_entities = {"datatype": "dwi", "direction": "AP", "run": "01", "suffix": "dwi"}
    entity_set = utils._entities_to_entity_set({**dwi_entities, "acquisition": old})
    renamed_entity_set = utils._entities_to_entity_set({**dwi_entities, "acquisition": new})
    summary = pd.DataFrame(
        {
            "RenameEntitySet": [None],
            "KeyParamGroup": [f"{entity_set}__1"],
            "EntitySet": [entity_set],
            "ParamGroup": [1],
            "MergeInto": [None],
        }
    )
    files = pd.DataFrame(
        {
            "FilePath": ["/sub-01/dwi/sub-01_dir-AP_run-01_dwi.nii.gz"],
            "KeyParamGroup": [f"{entity_set}__1"],
            "EntitySet": [entity_set],
            "ParamGroup": [1],
        }
    )
    summary_tsv = tmp_path / "summary.tsv"
    files_tsv = tmp_path / "files.tsv"
    edited_summary = tmp_path / "edited_summary.tsv"
    summary.to_csv(summary_tsv, sep="\t", index=False)
    files.to_csv(files_tsv, sep="\t", index=False)

    apply(
        bids_dir=str(bids_dir),
        use_datalad=False,
        acq_group_level="subject",
        config=None,
        schema=None,
        edited_summary_tsv=summary_tsv,
        files_tsv=files_tsv,
        new_tsv_prefix=tmp_path / "v1",
        change_rename_entity_set=[f"{entity_set}={renamed_entity_set}"],
        write_edited_summary=edited_summary,
    )

    assert pd.read_table(summary_tsv).loc[0, "RenameEntitySet"] != renamed_entity_set
    assert pd.read_table(edited_summary).loc[0, "RenameEntitySet"] == renamed_entity_set
    assert (bids_dir / "sub-01/dwi" / f"sub-01_acq-{new}_dir-AP_run-01_dwi.nii.gz").exists()


def test_cubids_apply_remove_rename_entity_set_deletes_files_and_purges_intendedfor(
    tmp_path, build_bids_dataset
):
    """--remove-RenameEntitySet derives MergeInto=0, deletes companions, purges references."""
    import json

    from cubids.workflows import apply

    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="remove_entity_set",
        skeleton_name="skeleton_apply_cross_sectional_realistic.yml",
    )
    acquisition = "VARIANTVar1"
    entity_set = utils._entities_to_entity_set(
        {
            "datatype": "dwi",
            "direction": "AP",
            "run": "01",
            "suffix": "dwi",
            "acquisition": acquisition,
        }
    )
    summary = pd.DataFrame(
        {
            "RenameEntitySet": [None],
            "KeyParamGroup": [f"{entity_set}__1"],
            "EntitySet": [entity_set],
            "ParamGroup": [1],
            "MergeInto": [None],
        }
    )
    files = pd.DataFrame(
        {
            "FilePath": ["/sub-01/dwi/sub-01_dir-AP_run-01_dwi.nii.gz"],
            "KeyParamGroup": [f"{entity_set}__1"],
            "EntitySet": [entity_set],
            "ParamGroup": [1],
        }
    )
    summary_tsv = tmp_path / "summary.tsv"
    files_tsv = tmp_path / "files.tsv"
    edited_summary = tmp_path / "remove_entity_set_summary.tsv"
    scans_tsv = bids_dir / "sub-01/sub-01_scans.tsv"
    scans_tsv.write_text(
        "filename\tacq_time\n"
        "dwi/sub-01_dir-AP_run-01_dwi.nii.gz\t2024-01-01T00:00:00\n"
        "dwi/sub-01_dir-AP_run-02_dwi.nii.gz\t2024-01-01T00:01:00\n"
    )
    summary.to_csv(summary_tsv, sep="\t", index=False)
    files.to_csv(files_tsv, sep="\t", index=False)

    apply(
        bids_dir=str(bids_dir),
        use_datalad=False,
        acq_group_level="subject",
        config=None,
        schema=None,
        edited_summary_tsv=summary_tsv,
        files_tsv=files_tsv,
        new_tsv_prefix=tmp_path / "v1",
        remove_rename_entity_set=[entity_set],
        write_edited_summary=edited_summary,
    )

    dwi_stem = bids_dir / "sub-01/dwi/sub-01_dir-AP_run-01_dwi"
    for extension in [".nii.gz", ".json", ".bval", ".bvec"]:
        assert not dwi_stem.with_suffix(extension).exists()
    assert pd.read_table(edited_summary).loc[0, "MergeInto"] == 0
    scans = pd.read_csv(scans_tsv, sep="\t", keep_default_na=False)
    assert scans["filename"].tolist() == ["dwi/sub-01_dir-AP_run-02_dwi.nii.gz"]
    for direction in ["AP", "PA"]:
        fmap_json = bids_dir / "sub-01/fmap" / f"sub-01_dir-{direction}_epi.json"
        assert json.loads(fmap_json.read_text())["IntendedFor"] == []


def test_cubids_apply_rejects_removing_part_of_an_fmap_collection(tmp_path, build_bids_dataset):
    """Deleting one PEPOLAR EPI would leave its pair unusable, so apply stops first."""
    from cubids.workflows import apply

    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="partial_fmap_removal",
        skeleton_name="skeleton_apply_cross_sectional_realistic.yml",
    )
    _add_fmap_epi_associations(bids_dir)
    summary, files = _fmap_apply_tables("VARIANTVar1", "VARIANTVar1")
    summary_tsv = tmp_path / "summary.tsv"
    files_tsv = tmp_path / "files.tsv"
    summary.to_csv(summary_tsv, sep="\t", index=False)
    files.to_csv(files_tsv, sep="\t", index=False)

    with pytest.raises(ValueError, match="Deleting part of a fieldmap collection"):
        apply(
            bids_dir=str(bids_dir),
            use_datalad=False,
            acq_group_level="subject",
            config=None,
            schema=None,
            edited_summary_tsv=summary_tsv,
            files_tsv=files_tsv,
            new_tsv_prefix=tmp_path / "v1",
            remove_rename_entity_set=[summary.loc[0, "RenameEntitySet"]],
            write_edited_summary=tmp_path / "edited_summary.tsv",
        )

    for direction in ["AP", "PA"]:
        assert (bids_dir / "sub-01/fmap" / f"sub-01_dir-{direction}_epi.nii.gz").exists()


def test_cubids_apply_writes_no_edited_summary_when_it_rejects_the_request(
    tmp_path, build_bids_dataset
):
    """A rejected apply leaves behind neither dataset changes nor an audit trail."""
    from cubids.workflows import apply

    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="rejected_edited_summary",
        skeleton_name="skeleton_apply_cross_sectional_realistic.yml",
    )
    _add_fmap_epi_associations(bids_dir)
    summary, files = _fmap_apply_tables("VARIANTVar1", "VARIANTVar1")
    summary_tsv = tmp_path / "summary.tsv"
    files_tsv = tmp_path / "files.tsv"
    edited_summary = tmp_path / "edited_summary.tsv"
    summary.to_csv(summary_tsv, sep="\t", index=False)
    files.to_csv(files_tsv, sep="\t", index=False)

    with pytest.raises(ValueError, match="Deleting part of a fieldmap collection"):
        apply(
            bids_dir=str(bids_dir),
            use_datalad=False,
            acq_group_level="subject",
            config=None,
            schema=None,
            edited_summary_tsv=summary_tsv,
            files_tsv=files_tsv,
            new_tsv_prefix=tmp_path / "v1",
            remove_rename_entity_set=[summary.loc[0, "RenameEntitySet"]],
            write_edited_summary=edited_summary,
        )

    assert not edited_summary.exists()


def test_plan_rename_pairs_deduplicates_shared_associations(tmp_path, build_bids_dataset):
    """A companion claimed by two renamed images is moved once, to the first destination."""
    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="shared_association",
        skeleton_name="skeleton_apply_cross_sectional_realistic.yml",
    )
    cubids = CuBIDS(bids_dir, use_datalad=False)
    source = next((bids_dir / "sub-01/dwi").glob("*_dwi.nii.gz"))
    entities = utils._entity_set_to_entities(utils._file_to_entity_set(source))
    first = {**entities, "acquisition": "VARIANTOne"}
    second = {**entities, "acquisition": "VARIANTTwo"}
    plan = [
        (str(source), target, cubids.get_planned_destination(str(source), target))
        for target in (first, second)
    ]

    pairs = cubids.plan_rename_pairs(plan)

    assert len(pairs) == len({source for source, _ in pairs})
    assert dict(pairs)[str(source)] == plan[0][2]


def test_cubids_apply_rejects_hand_edited_partial_fmap_deletion(tmp_path, build_bids_dataset):
    """The same guard covers a summary hand-edited with MergeInto=0."""
    from cubids.workflows import apply

    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="partial_fmap_merge_into",
        skeleton_name="skeleton_apply_cross_sectional_realistic.yml",
    )
    _add_fmap_epi_associations(bids_dir)
    summary, files = _fmap_apply_tables("VARIANTVar1", "VARIANTVar1")
    summary.loc[0, "MergeInto"] = 0
    summary_tsv = tmp_path / "summary.tsv"
    files_tsv = tmp_path / "files.tsv"
    summary.to_csv(summary_tsv, sep="\t", index=False)
    files.to_csv(files_tsv, sep="\t", index=False)

    with pytest.raises(ValueError, match="Deleting part of a fieldmap collection"):
        apply(
            bids_dir=str(bids_dir),
            use_datalad=False,
            acq_group_level="subject",
            config=None,
            schema=None,
            edited_summary_tsv=summary_tsv,
            files_tsv=files_tsv,
            new_tsv_prefix=tmp_path / "v1",
        )

    for direction in ["AP", "PA"]:
        assert (bids_dir / "sub-01/fmap" / f"sub-01_dir-{direction}_epi.nii.gz").exists()


def test_cubids_apply_remove_rename_entity_set_deletes_fmap_epi_gradient_companions(
    tmp_path, build_bids_dataset
):
    """A table of entity sets deletes a whole collection, with every EPI companion."""
    from cubids.workflows import apply

    bids_dir = build_bids_dataset(
        tmp_path=tmp_path,
        dataset_name="remove_fmap_entity_set",
        skeleton_name="skeleton_apply_cross_sectional_realistic.yml",
    )
    _add_fmap_epi_associations(bids_dir)
    summary, files = _fmap_apply_tables("VARIANTVar1", "VARIANTVar1")
    summary_tsv = tmp_path / "summary.tsv"
    files_tsv = tmp_path / "files.tsv"
    edited_summary = tmp_path / "remove_fmap_entity_set_summary.tsv"
    removals_tsv = tmp_path / "removals.tsv"
    summary.to_csv(summary_tsv, sep="\t", index=False)
    files.to_csv(files_tsv, sep="\t", index=False)
    summary[["RenameEntitySet"]].rename(columns={"RenameEntitySet": "entity_set"}).to_csv(
        removals_tsv, sep="\t", index=False
    )

    apply(
        bids_dir=str(bids_dir),
        use_datalad=False,
        acq_group_level="subject",
        config=None,
        schema=None,
        edited_summary_tsv=summary_tsv,
        files_tsv=files_tsv,
        new_tsv_prefix=tmp_path / "v1",
        remove_rename_entity_set=[removals_tsv],
        write_edited_summary=edited_summary,
    )

    for direction in ["AP", "PA"]:
        stem = bids_dir / "sub-01/fmap" / f"sub-01_dir-{direction}_epi"
        for extension in [".nii.gz", ".json", ".bval", ".bvec"]:
            assert not stem.with_suffix(extension).exists()
