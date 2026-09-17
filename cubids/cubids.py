"""Main module for CuBIDS.

This module provides the core functionalities of the CuBIDS package, including
operations for handling BIDS datasets, clustering, and metadata merging.
"""

import csv
import json
import os
import re
import subprocess
import warnings
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from shutil import copyfile, copytree

import bids
import bids.layout
import datalad.api as dlapi
import nibabel as nb
import numpy as np
import pandas as pd
from bids.layout import parse_file_entities
from bids.utils import listify
from tqdm import tqdm

from cubids import indexing, utils
from cubids.config import load_config, load_schema
from cubids.constants import NON_KEY_ENTITIES
from cubids.metadata_merge import (
    check_merging_operations,
    group_by_acquisition_sets,
    merge_json_into_json,
)

warnings.simplefilter(action="ignore", category=FutureWarning)
bids.config.set_option("extension_initial_dot", True)


FMAP_REPORT_COLUMNS = [
    "CollectionID",
    "Case",
    "FilePaths",
    "KeyParamGroups",
    "Status",
    "Message",
    "CurrentAcquisitions",
    "ProposedAcquisition",
    "ProposedRenameEntitySets",
]

# Suffixes of the BIDS B0 fieldmap types, whose files only make sense as whole
# collections. Every other suffix under fmap/ (TB1TFL, TB1map, RB1map, M0scan,
# ...) is a standalone image with no collection to keep consistent.
B0_FMAP_SUFFIXES = frozenset(
    {
        "phasediff",
        "magnitude1",
        "magnitude2",
        "phase1",
        "phase2",
        "fieldmap",
        "magnitude",
        "epi",
    }
)


class CuBIDS:
    """The main CuBIDS class.

    Parameters
    ----------
    data_root : :obj:`str`
        Path to the root of the BIDS dataset.
    use_datalad : :obj:`bool`, optional
        If True, use datalad to track changes to the BIDS dataset.
        Default is False.
    acq_group_level : :obj:`str`, optional
        The level at which to group scans. Default is "subject".
    grouping_config : :obj:`str`, optional
        Path to the grouping config file.
        Default is None, in which case the default config in CuBIDS is used.
    force_unlock : :obj:`bool`, optional
        If True, force unlock all files in the BIDS dataset.
        Default is False.
    schema_json : :obj:`str`, optional
        Path to a BIDS schema JSON file.
        Default is None, in which case the default schema in CuBIDS is used.
    ignore_entities : list[str] or None, optional
        BIDS entities to ignore when creating entity sets. Default is None.

    Attributes
    ----------
    path : :obj:`str`
        Path to the root of the BIDS dataset.
    _layout : :obj:`bids.layout.BIDSLayout`
        The BIDSLayout object.
    keys_files : :obj:`dict`
        A dictionary of entity sets and the files that belong to them.
    fieldmaps_cached : :obj:`bool`
        If True, the fieldmaps have been cached.
    datalad_ready : :obj:`bool`
        If True, the datalad dataset has been initialized.
    datalad_handle : :obj:`datalad.api.Dataset`
        The datalad dataset handle.
    old_filenames : :obj:`list`
        A list of old filenames.
    new_filenames : :obj:`list`
        A list of new filenames.
    IF_rename_paths : :obj:`list`
        A list of IntendedFor paths that have been renamed.
    grouping_config : :obj:`dict`
        The grouping config dictionary.
    acq_group_level : :obj:`str`
        The level at which to group scans.
    scans_txt : :obj:`str`
        Path to the .txt file that lists the scans
        you want to be deleted from the dataset, along
        with their associations.
    force_unlock : :obj:`bool`
        If True, force unlock all files in the BIDS dataset.
    cubids_code_dir : :obj:`bool`
        If True, the CuBIDS code directory exists.
    data_dict : :obj:`dict`
        A data dictionary for TSV outputs.
    use_datalad : :obj:`bool`
        If True, use datalad to track changes to the BIDS dataset.
    schema : :obj:`dict`
        The BIDS schema dictionary.
    is_longitudinal : :obj:`bool`
        If True, adds "ses" in filepath.
    """

    def __init__(
        self,
        data_root,
        use_datalad=False,
        acq_group_level="subject",
        grouping_config=None,
        force_unlock=False,
        schema_json=None,
        ignore_entities=None,
    ):
        self.path = os.path.abspath(data_root)
        self._layout = None
        self._index = None  # Arrow table: entities + metadata (lazy)
        self.keys_files = {}
        self.fieldmaps_cached = False
        self.datalad_ready = False
        self.datalad_handle = None
        self.old_filenames = []  # files whose entity sets changed
        self.new_filenames = []  # new filenames for files to change
        self._renamed_sources = set()  # membership index over old_filenames
        self.IF_rename_paths = []  # fmap jsons with rename intended fors
        self.grouping_config = load_config(grouping_config)
        self.acq_group_level = acq_group_level
        self.scans_txt = None  # txt file of scans to purge (for purge only)
        self.force_unlock = force_unlock  # force unlock for add-nifti-info
        self.cubids_code_dir = Path(self.path + "/code/CuBIDS").is_dir()
        self.data_dict = {}  # data dictionary for TSV outputs
        self.use_datalad = use_datalad  # True if flag set, False if flag unset
        self.schema = load_schema(schema_json)
        self.is_longitudinal = self._infer_longitudinal()  # inferred from dataset structure
        self.ignore_entities = set(ignore_entities or [])

        if self.use_datalad:
            self.init_datalad()

        if self.ignore_entities:
            NON_KEY_ENTITIES.update(self.ignore_entities)

        if self.is_longitudinal and self.acq_group_level == "session":
            NON_KEY_ENTITIES.remove("session")
        elif not self.is_longitudinal and self.acq_group_level == "session":
            raise ValueError(
                'Data is not longitudinal, so "session" is not a valid grouping level.'
            )

    @property
    def layout(self):
        """Return the BIDSLayout object.

        Returns
        -------
        BIDSLayout
            The BIDSLayout object associated with the current instance.
        """
        if self._layout is None:
            self.reset_bids_layout()
        return self._layout

    @property
    def index(self):
        """Return the Arrow index table (entities + metadata).

        The index is lazily built on first access and cached as Parquet.
        Subsequent accesses return the cached table. When datalad is active,
        disk caching is disabled to avoid creating untracked files.

        Returns
        -------
        pyarrow.Table
            Full dataset index with entity columns and metadata columns.
        """
        if self._index is None:
            self._index = indexing.load_or_build_index(
                self.path,
                bids_schema=self.schema,
                grouping_config=self.grouping_config,
                use_cache=not self.use_datalad,
            )
        return self._index

    def _invalidate_index(self):
        """Invalidate the Arrow index and its Parquet cache.

        Call this after any mutation (rename, merge, purge) so that the
        index is rebuilt on next access.
        """
        self._index = None
        if not self.use_datalad:
            indexing.invalidate_cache(self.path)
        self._layout = None

    def _infer_longitudinal(self):
        """Infer if the dataset is longitudinal based on its structure.

        Checks only the first level of subject directories for session
        subdirectories (``ses-*``), avoiding a full recursive scan.

        Returns
        -------
        bool
            True if the dataset is longitudinal (i.e., contains session identifiers),
            False otherwise.
        """
        for entry in os.scandir(self.path):
            if entry.name.startswith("sub-") and entry.is_dir():
                for sub_entry in os.scandir(entry.path):
                    if sub_entry.name.startswith("ses-") and sub_entry.is_dir():
                        return True
        return False

    def reset_bids_layout(self, validate=False):
        """Reset the BIDS layout.

        This sets the ``_layout`` attribute to a new :obj:`bids.layout.BIDSLayout` object.

        Parameters
        ----------
        validate : :obj:`bool`, optional
            If True, validate the BIDS dataset. Default is False.
        """
        # create BIDS Layout Indexer class

        ignores = [
            "code",
            "stimuli",
            "sourcedata",
            "models",
            re.compile(r"^\."),
            re.compile(r"/\."),
        ]

        indexer = bids.BIDSLayoutIndexer(validate=validate, ignore=ignores, index_metadata=False)

        self._layout = bids.BIDSLayout(self.path, validate=validate, indexer=indexer)

    def create_cubids_code_dir(self):
        """Create CuBIDS code directory.

        This creates the CuBIDS code directory at self.path/code/CuBIDS.

        Returns
        -------
        :obj:`str`
            Path to the CuBIDS code directory.
        """
        if not self.cubids_code_dir:
            os.makedirs(os.path.join(self.path, "code", "CuBIDS"), exist_ok=True)
            self.cubids_code_dir = True
        return self.cubids_code_dir

    def init_datalad(self):
        """Initialize a datalad Dataset at the specified path.

        This method creates a datalad dataset at the path specified by `self.path`.
        It sets the `datalad_ready` attribute to True and assigns the datalad.Dataset
        object to the `datalad_handle` attribute.

        Attributes
        ----------
        datalad_ready : bool
            Indicates whether the datalad dataset has been successfully initialized.
        datalad_handle : datalad.api.Dataset
            The datalad dataset object associated with the specified path.

        Notes
        -----
        If the dataset is not already installed at the specified path, this method
        will create a new dataset with the configuration process "text2git" and
        enable the annex feature.
        """
        self.datalad_ready = True

        self.datalad_handle = dlapi.Dataset(self.path)
        if not self.datalad_handle.is_installed():
            self.datalad_handle = dlapi.create(
                self.path, cfg_proc="text2git", force=True, annex=True
            )

    def datalad_save(self, message=None, jobs=None):
        """Perform a DataLad Save operation on the BIDS tree.

        This method checks for an active DataLad handle and ensures that the
        status of all objects after the save operation is "ok".

        Parameters
        ----------
        message : str or None, optional
            Commit message to use with DataLad save. If None, a default message
            "CuBIDS Save" will be used.
        jobs : int or None, optional
            Number of parallel jobs to use for the save operation (maps to
            DataLad `-J/--jobs`). If None, DataLad's default is used.

        Raises
        ------
        Exception
            If DataLad has not been initialized or if the save operation fails.
        """
        if not self.datalad_ready:
            raise Exception("DataLad has not been initialized. use datalad_init()")

        statuses = self.datalad_handle.save(message=message or "CuBIDS Save", jobs=jobs)
        saved_status = {status["status"] for status in statuses}
        if not saved_status == {"ok"}:
            raise Exception("Failed to save in DataLad")

    def is_datalad_clean(self):
        """If True, no changes are detected in the datalad dataset.

        Returns
        -------
        :obj:`bool`
            True if the datalad dataset is clean, False otherwise.

        Raises
        ------
        Exception
            If datalad has not been initialized.
        """
        if not self.datalad_ready:
            raise Exception("Datalad not initialized, can't determine status")
        statuses = {status["state"] for status in self.datalad_handle.status()}
        return statuses == {"clean"}

    def datalad_undo_last_commit(self):
        """Revert the most recent commit, remove it from history.

        Uses git reset --hard to revert to the previous commit.

        Raises
        ------
        Exception
            If there are untracked changes in the datalad dataset.
        """
        if not self.is_datalad_clean():
            raise Exception("Untracked changes present. Run clear_untracked_changes first")
        reset_proc = subprocess.run(["git", "reset", "--hard", "HEAD~1"], cwd=self.path)
        reset_proc.check_returncode()

    def add_nifti_info(self, n_cpus=1):
        """
        Add information from NIfTI files to their corresponding JSON sidecars.

        This method processes all NIfTI files in the BIDS directory specified by `self.path`.
        It extracts relevant metadata from each NIfTI file and updates the corresponding JSON
        sidecar files with this information. If `self.force_unlock` is set, it will unlock
        the dataset using `datalad` before processing the files.

        Metadata added to the JSON sidecars includes:
        - Obliquity
        - Voxel sizes (dimensions 1, 2, and 3)
        - Matrix dimensions (sizes of dimensions 1, 2, and 3)
        - Number of volumes (for 4D images)
        - Image orientation

        If `self.use_datalad` is set, the changes will be saved using `datalad`.

        Raises
        ------
        Exception
            If there is an error loading a NIfTI file or parsing a JSON sidecar file.

        Notes
        -----
        - This method assumes that the NIfTI files are organized in a BIDS-compliant
            directory structure.
        - The method will skip any files in hidden directories (directories starting with a dot).
        - If a JSON sidecar file does not exist for a NIfTI file, it will be skipped.
        Parameters
        ----------
        n_cpus : :obj:`int`
            Number of CPUs to use for parallel add-nifti-info. Default is 1 (sequential).

        """
        # Build list of NIfTI paths from the Arrow index (instant)
        nifti_rel_paths = indexing.get_nifti_paths(self.index)
        nifti_paths = [os.path.join(self.path, p) for p in nifti_rel_paths]

        # Unlock only the JSON sidecars that will be modified
        if self.force_unlock and nifti_paths:
            json_paths = [utils.img_to_new_ext(p, ".json") for p in nifti_paths]
            json_paths = [p for p in json_paths if os.path.exists(p)]
            if json_paths:
                subprocess.run(["datalad", "unlock"] + json_paths, cwd=self.path)

        # Ensure n_cpus is at least 1
        try:
            n_cpus = int(n_cpus)
        except Exception:
            n_cpus = 1
        n_cpus = max(1, n_cpus)

        if n_cpus > 1 and len(nifti_paths) > 0:
            with ProcessPoolExecutor(n_cpus) as executor:
                list(
                    tqdm(
                        executor.map(_add_metadata_single_nifti, nifti_paths),
                        total=len(nifti_paths),
                        desc="Processing NIfTI files",
                        unit="file",
                    )
                )
        else:
            for nifti_path in tqdm(nifti_paths, desc="Processing NIfTI files", unit="file"):
                _add_metadata_single_nifti(nifti_path)

        if self.use_datalad:
            if self.is_datalad_clean():
                print("nothing to save, working tree clean")
            else:
                dl_jobs = n_cpus if n_cpus and n_cpus > 1 else 1
                self.datalad_save(message="Added nifti info to sidecars", jobs=dl_jobs)

        self._invalidate_index()

    def add_file_collections(self, n_cpus=1):
        """Add file collections to the dataset.

        This method processes all files in the BIDS directory specified by `self.path`.
        It identifies file collections based on the presence of specific entities in the filenames.

        Notes
        -----
        This method uses metadata from direct sidecar JSON files,
        so it will not work with inherited metadata.
        """
        # Targeted unlock: only unlock JSON sidecars
        if self.force_unlock:
            json_rel_paths = indexing.get_json_paths(self.index)
            json_abs_paths = [os.path.join(self.path, p) for p in json_rel_paths]
            if json_abs_paths:
                subprocess.run(["datalad", "unlock"] + json_abs_paths, cwd=self.path)

        checked_files = set()

        # loop through all niftis in the bids dir
        for bids_file in self.layout.get(extension=[".nii", ".nii.gz"]):
            path = bids_file.path

            if path in checked_files:
                continue

            # Add file collection metadata to the sidecar
            files, collection_metadata = utils.collect_file_collections(self.layout, path)
            filepaths = [f.path for f in files]
            checked_files.update(filepaths)

            for collection_path in filepaths:
                # Add metadata to the sidecar
                sidecar = utils.img_to_new_ext(str(collection_path), ".json")
                if Path(sidecar).exists():
                    with open(sidecar, "r") as f:
                        data = json.load(f)
                else:
                    data = {}

                data.update(collection_metadata)
                with open(sidecar, "w") as f:
                    json.dump(data, f, sort_keys=True, indent=4)

        if self.use_datalad:
            dl_jobs = n_cpus if n_cpus and n_cpus > 1 else 1
            self.datalad_save(message="Added file collection metadata to sidecars", jobs=dl_jobs)

        self._invalidate_index()

    def get_planned_entity_set(self, summary_row):
        """Return a summary row's proposed entity set, or its current one.

        Parameters
        ----------
        summary_row : :obj:`pandas.Series`
            A row of a CuBIDS summary table.

        Returns
        -------
        :obj:`str`
            ``RenameEntitySet`` when that cell is filled in, otherwise ``EntitySet``.
        """
        rename = summary_row.get("RenameEntitySet")
        if utils.is_nonempty(rename):
            return str(rename)
        return str(summary_row["EntitySet"])

    def update_scans_tsv_filenames(self, filename_changes):
        """Update or remove exact ``filename`` entries in affected BIDS scans tables.

        Both the subject-level and session-level ``*_scans.tsv`` tables that can
        list a file are rewritten, each with the relative path it uses.

        Parameters
        ----------
        filename_changes : :obj:`dict`
            Maps an absolute NIfTI path to its new absolute path, or to None to
            drop its row from the tables.
        """
        table_changes = defaultdict(dict)
        for old_filename, new_filename in filename_changes.items():
            old_path = Path(old_filename)
            scans_dirs = []
            for parent in old_path.parents:
                if parent.name.startswith(("ses-", "sub-")):
                    scans_dirs.append(parent)
                if parent.name.startswith("sub-"):
                    break

            for scans_dir in scans_dirs:
                old_relative = old_path.relative_to(scans_dir).as_posix()
                new_relative = (
                    Path(new_filename).relative_to(scans_dir).as_posix()
                    if new_filename is not None
                    else None
                )
                for scans_tsv in scans_dir.glob("*_scans.tsv"):
                    table_changes[scans_tsv][old_relative] = new_relative

        for scans_tsv, replacements in table_changes.items():
            scans = utils.read_bids_tsv(scans_tsv)
            if (
                "filename" not in scans.columns
                or not scans["filename"].isin(replacements.keys()).any()
            ):
                continue

            renamed = {old: new for old, new in replacements.items() if new is not None}
            deleted = {old for old, new in replacements.items() if new is None}
            if renamed:
                scans["filename"] = scans["filename"].replace(renamed)
            if deleted:
                scans = scans.loc[~scans["filename"].isin(deleted)]
            utils.write_bids_tsv(scans, scans_tsv)

    @staticmethod
    def get_associated_file_pairs(filepath, new_path=None):
        """Return a NIfTI's associated files and their planned destinations.

        Covers the sidecar JSON, DWI and fmap EPI gradient tables, sbref, events,
        physio, and ASL companions. Unlike :meth:`get_nifti_associations`, which
        only matches files sharing the NIfTI's stem, this also finds companions
        that swap the BIDS suffix, such as ``_bold.nii.gz`` to ``_events.tsv``.

        Parameters
        ----------
        filepath : :obj:`str` or :obj:`pathlib.Path`
            The NIfTI being renamed or deleted.
        new_path : :obj:`str` or :obj:`pathlib.Path` or None
            Destination for ``filepath``. None produces a deletion plan, where
            every destination is None.

        Returns
        -------
        :obj:`list` of :obj:`tuple`
            ``(source, destination)`` pairs. The NIfTI itself always comes first;
            companions are listed only when they exist on disk.

        Notes
        -----
        Paths without a parseable BIDS suffix, which ``cubids purge`` can receive
        from a user-supplied scans file, yield only the NIfTI and its sidecar.
        """
        filepath = str(filepath)
        new_path = str(new_path) if new_path is not None else None
        old_suffix = parse_file_entities(filepath).get("suffix")
        extension = "".join(Path(filepath).suffixes)
        new_suffix = parse_file_entities(new_path).get("suffix") if new_path else None
        pairs = [(filepath, new_path)]
        seen = {filepath}

        def add_pair(source, destination):
            if source not in seen and Path(source).exists():
                pairs.append((source, destination))
                seen.add(source)

        extensions = [".json"]
        if "/dwi/" in filepath or ("/fmap/" in filepath and old_suffix == "epi"):
            extensions.extend([".bval", ".bvec"])
        for association_extension in extensions:
            source = utils.img_to_new_ext(filepath, association_extension)
            destination = (
                utils.img_to_new_ext(new_path, association_extension) if new_path else None
            )
            add_pair(source, destination)

        if old_suffix is None or (new_path and new_suffix is None):
            return pairs

        scan_end = f"_{old_suffix}{extension}"
        new_scan_end = f"_{new_suffix}{extension}" if new_path else None

        def add_suffix_companions(companion_extensions):
            for companion_extension in companion_extensions:
                source = filepath.replace(scan_end, companion_extension)
                destination = (
                    new_path.replace(new_scan_end, companion_extension) if new_path else None
                )
                add_pair(source, destination)

        if "/dwi/" in filepath:
            add_suffix_companions(["_sbref.nii.gz", "_sbref.json"])
        if "bold" in filepath:
            add_suffix_companions(
                [
                    "_events.tsv",
                    "_events.json",
                    "_sbref.nii.gz",
                    "_sbref.json",
                    "_physio.tsv.gz",
                    "_physio.json",
                ]
            )
        if "/perf/" in filepath and old_suffix == "asl":
            add_suffix_companions(["_aslcontext.tsv", "_asllabeling.jpg"])

        return pairs

    def get_files_to_purge(self, scans):
        """Return every file deleted when ``scans`` are purged, companions included.

        Parameters
        ----------
        scans : :obj:`list` of :obj:`str`
            Absolute paths to the NIfTIs being purged.

        Returns
        -------
        :obj:`list` of :obj:`str`
            The NIfTIs plus each of their existing associated files.
        """
        return [source for scan in scans for source, _ in self.get_associated_file_pairs(scan)]

    def get_planned_destination(self, filepath, new_entities):
        """Return the path ``filepath`` is renamed to when it takes ``new_entities``.

        Parameters
        ----------
        filepath : :obj:`str`
            Absolute path to the file being renamed.
        new_entities : :obj:`dict`
            A pybids entities dictionary describing the new name.

        Returns
        -------
        :obj:`str`
            The absolute destination path.
        """
        return utils.build_path(
            filepath=filepath,
            out_entities=new_entities,
            out_dir=str(self.path),
            schema=self.schema,
            is_longitudinal=self.is_longitudinal,
        )

    def plan_renames(self, files_df, entity_sets, allow_fmap_renames, pending_deletions=()):
        """Return the NIfTI renames ``apply`` will perform, without performing them.

        This is the single source of truth for which files a rename touches.
        :meth:`validate_rename_destinations` and :meth:`apply_tsv_changes` both
        consume it, so the plan that is validated is exactly the plan that runs.
        It is also usable on its own as a dry run.

        Parameters
        ----------
        files_df : :obj:`pandas.DataFrame`
            A CuBIDS files table.
        entity_sets : :obj:`dict`
            Maps ``KeyParamGroup`` to the entity set its files should take.
        allow_fmap_renames : :obj:`bool`
            Whether files under ``fmap/`` may be renamed.
        pending_deletions : :obj:`set` of :obj:`str`
            Files an earlier apply step removes. A group can be marked for both
            deletion and renaming, and deletion wins.

        Returns
        -------
        :obj:`list` of :obj:`tuple`
            ``(filepath, new_entities, new_path)`` for each NIfTI to rename.
        """
        pending_deletions = set(pending_deletions)
        plan = []
        for _, row in files_df.iterrows():
            filepath = self.path + str(row["FilePath"])
            if row["KeyParamGroup"] not in entity_sets or not Path(filepath).exists():
                continue
            if filepath in pending_deletions:
                continue
            if "/fmap/" in filepath and not allow_fmap_renames:
                continue
            new_entities = utils._entity_set_to_entities(entity_sets[row["KeyParamGroup"]])
            plan.append(
                (filepath, new_entities, self.get_planned_destination(filepath, new_entities))
            )
        return plan

    def plan_rename_pairs(self, rename_plan):
        """Expand a rename plan into the deduplicated moves it performs.

        Computing this once lets :meth:`validate_rename_destinations` check the
        exact moves that :meth:`apply_tsv_changes` then carries out, and keeps
        the filesystem probing in :meth:`get_associated_file_pairs` to one pass.

        Parameters
        ----------
        rename_plan : :obj:`list` of :obj:`tuple`
            A plan from :meth:`plan_renames`.

        Returns
        -------
        :obj:`list` of :obj:`tuple`
            ``(source, destination)`` for every file the plan moves. A file that
            several renamed NIfTIs claim as an association, such as an ``sbref``
            shared by a DWI series, keeps the destination of the first claim.
        """
        pairs = []
        seen = set()
        for filepath, _, new_path in rename_plan:
            for source, destination in self.get_associated_file_pairs(filepath, new_path):
                if source in seen:
                    continue
                seen.add(source)
                pairs.append((source, destination))
        return pairs

    def _record_rename_pairs(self, pairs):
        """Append moves to the old/new filename lists, skipping sources already queued.

        Private because it maintains ``_renamed_sources`` as a membership index over
        ``old_filenames``; appending to those lists directly would desynchronize it.
        """
        for source, destination in pairs:
            if source in self._renamed_sources:
                continue
            self._renamed_sources.add(source)
            self.old_filenames.append(source)
            self.new_filenames.append(destination)

    def _rewrite_intendedfor_references(self, old_path, new_path=None, intended_for_index=None):
        """Remove or rewrite ``IntendedFor`` entries that refer to one NIfTI."""
        if intended_for_index is None:
            intended_for_index = self._build_intendedfor_index()

        old_references = (
            utils._get_participant_relative_path(old_path),
            utils._get_bidsuri(old_path, self.path),
        )
        new_references = (
            (
                utils._get_participant_relative_path(new_path),
                utils._get_bidsuri(new_path, self.path),
            )
            if new_path is not None
            else None
        )
        jsons_to_update = {
            json_file
            for reference in old_references
            for json_file in intended_for_index.get(reference, [])
        }

        for json_file in jsons_to_update:
            if new_references is not None:
                self.IF_rename_paths.append(json_file)
            cached = utils.get_sidecar_metadata(json_file)
            if cached == "Erroneous sidecar":
                print("Error parsing sidecar: ", json_file)
                continue
            if "IntendedFor" not in cached:
                continue

            data = dict(cached)
            items = list(listify(data["IntendedFor"]) or [])
            had_references = [reference in items for reference in old_references]
            changed = False
            for reference in old_references:
                while reference in items:
                    items.remove(reference)
                    changed = True
            if new_references is not None:
                for had_reference, new_reference in zip(had_references, new_references):
                    if had_reference and new_reference not in items:
                        items.append(new_reference)
                        changed = True
            if changed:
                data["IntendedFor"] = items
                utils._update_json(json_file, data)
                utils.get_sidecar_metadata.cache_clear()

    def analyze_fmap_variant_consistency(self, files_df, summary, rename_cols=()):
        """Inspect BIDS B0 fieldmap collections and propose aligned variants.

        The pairing key is constructed from each individual NIfTI path. This is
        intentionally stricter than summary-level matching: subject, session,
        run, chunk, and every other filename entity must already agree before
        two files can be treated as one fieldmap collection.

        Every file whose suffix is in :data:`B0_FMAP_SUFFIXES` lands in exactly one
        record, so :meth:`validate_fmap_renames` can treat an unreported fieldmap as
        a standalone image rather than as something it failed to understand. Files
        under ``fmap/`` with any other suffix, such as ``TB1map`` or ``M0scan``, are
        not part of a collection and are left out of the report entirely.

        Parameters
        ----------
        files_df : :obj:`pandas.DataFrame`
            A CuBIDS files table.
        summary : :obj:`pandas.DataFrame`
            The matching parameter group summary.
        rename_cols : :obj:`list` of :obj:`str`
            Summary columns that variant labels are built from. Without them no
            shared label can be composed, so mismatched collections are reported
            as ``MANUAL_REVIEW`` instead of ``PROPOSED``. Callers that only gate
            on ``PASS``, such as :meth:`validate_fmap_renames`, can omit it.

        Returns
        -------
        report : :obj:`pandas.DataFrame`
            One row per fieldmap collection, with a ``Status`` of ``PASS``,
            ``PROPOSED``, or ``MANUAL_REVIEW``.
        proposals : :obj:`dict`
            Maps ``KeyParamGroup`` to the set of entity sets proposed for it.
            A group with more than one proposal is ambiguous and is not applied.
        """
        rename_cols = list(rename_cols)
        by_key = summary.set_index("KeyParamGroup", drop=False)
        records = []
        gre_groups = defaultdict(list)
        pepolar_groups = defaultdict(list)

        for _, file_row in files_df.iterrows():
            filepath = str(file_row["FilePath"])
            if "/fmap/" not in filepath or file_row["KeyParamGroup"] not in by_key.index:
                continue

            entities = parse_file_entities(filepath)
            suffix = entities.get("suffix")
            if suffix not in B0_FMAP_SUFFIXES:
                continue

            summary_row = by_key.loc[file_row["KeyParamGroup"]]
            target_entities = utils._entity_set_to_entities(
                self.get_planned_entity_set(summary_row)
            )
            item = {
                "filepath": filepath,
                "key_param_group": file_row["KeyParamGroup"],
                "source_entities": entities,
                "target_entities": target_entities,
                "summary_row": summary_row,
                "phase_encoding_direction": file_row.get("PhaseEncodingDirection"),
            }
            if suffix == "epi":
                context = utils.entity_context_key(entities, {"direction", "extension", "fmap"})
                pepolar_groups[context].append(item)
            else:
                context = utils.entity_context_key(entities, {"suffix", "extension", "fmap"})
                gre_groups[context].append(item)

        proposals = defaultdict(set)

        def add_record(case, members, status, message, proposed_acquisition="", proposed=None):
            paths = sorted(member["filepath"] for member in members)
            collection_id = f"{case}:{'|'.join(paths)}"
            acquisitions = sorted(
                {str(member["target_entities"].get("acquisition", "")) for member in members}
            )
            proposed = proposed or {}
            records.append(
                {
                    "CollectionID": collection_id,
                    "Case": case,
                    "FilePaths": "|".join(paths),
                    "KeyParamGroups": "|".join(
                        sorted({member["key_param_group"] for member in members})
                    ),
                    "Status": status,
                    "Message": message,
                    "CurrentAcquisitions": "|".join(acquisitions),
                    "ProposedAcquisition": proposed_acquisition,
                    "ProposedRenameEntitySets": "|".join(sorted(set(proposed.values()))),
                }
            )

        def assess_complete_collection(case, members, relationship_axes):
            target_contexts = [
                utils.entity_context_key(member["target_entities"], relationship_axes)
                for member in members
            ]
            if len(set(target_contexts)) == 1:
                add_record(
                    case, members, "PASS", "All paired files have matching planned entities."
                )
                return

            non_acq_contexts = [
                utils.entity_context_key(
                    member["target_entities"], relationship_axes | {"acquisition"}
                )
                for member in members
            ]
            acquisitions = [member["target_entities"].get("acquisition", "") for member in members]
            variant_bases = []
            for acquisition in acquisitions:
                if not acquisition or "VARIANT" not in str(acquisition):
                    variant_bases = []
                    break
                variant_bases.append(str(acquisition).split("VARIANT", 1)[0])

            varying_columns = set()
            for member in members:
                varying_columns.update(
                    column
                    for column, _, _, _ in utils.get_variant_components(
                        summary, member["summary_row"], rename_cols
                    )
                )
            # Preserve rename_cols order so the shared label is deterministic.
            component_names = [col for col in rename_cols if col in varying_columns]

            if (
                len(set(non_acq_contexts)) == 1
                and variant_bases
                and len(set(variant_bases)) == 1
                and component_names
            ):
                proposed_acquisition = variant_bases[0] + "VARIANT" + "".join(component_names)
                proposed = {}
                for member in members:
                    entities = dict(member["target_entities"])
                    entities["acquisition"] = proposed_acquisition
                    entity_set = utils._entities_to_entity_set(entities)
                    proposed[member["key_param_group"]] = entity_set
                    proposals[member["key_param_group"]].add(entity_set)
                add_record(
                    case,
                    members,
                    "PROPOSED",
                    "Variant labels differ; a shared fieldmap variant was proposed.",
                    proposed_acquisition,
                    proposed,
                )
                return

            add_record(
                case,
                members,
                "MANUAL_REVIEW",
                "Paired files have incompatible planned entities; "
                "no safe shared variant was proposed.",
            )

        for members in gre_groups.values():
            suffixes = {member["source_entities"]["suffix"] for member in members}
            if "phasediff" in suffixes:
                expected = {"phasediff", "magnitude1"}
                case = "phase-difference"
            elif {"phase1", "phase2"} & suffixes:
                expected = {"phase1", "phase2", "magnitude1", "magnitude2"}
                case = "two-phase"
            elif "fieldmap" in suffixes:
                expected = {"fieldmap", "magnitude"}
                case = "direct-fieldmap"
            else:
                # Magnitude images only exist as part of one of the cases above,
                # so on their own they are the remains of a broken collection.
                add_record(
                    "orphan-magnitude",
                    members,
                    "MANUAL_REVIEW",
                    "Magnitude images without a phasediff, phase, or fieldmap image.",
                )
                continue
            missing = sorted(expected - suffixes)
            if missing:
                add_record(
                    case,
                    members,
                    "MANUAL_REVIEW",
                    f"Incomplete collection; missing {', '.join(missing)}.",
                )
            else:
                assess_complete_collection(case, members, {"suffix", "fmap"})

        for members in pepolar_groups.values():
            if len(members) == 1:
                # A lone EPI fieldmap is valid BIDS, and there is no partner whose
                # label it has to match, so it is renamed like any other image.
                add_record(
                    "single-direction epi",
                    members,
                    "PASS",
                    "Only one phase-encoding direction; no paired file to match.",
                )
                continue

            directions = {member["source_entities"].get("direction") for member in members}
            peds = [member["phase_encoding_direction"] for member in members]
            valid_pair = (
                len(members) == 2
                and len(directions) == 2
                and all(utils.is_nonempty(ped) for ped in peds)
                and str(peds[0]).rstrip("-") == str(peds[1]).rstrip("-")
                and str(peds[0]).endswith("-") != str(peds[1]).endswith("-")
            )
            if not valid_pair:
                add_record(
                    "pepolar",
                    members,
                    "MANUAL_REVIEW",
                    "Expected exactly two dirs with opposite PhaseEncodingDirection values.",
                )
            else:
                assess_complete_collection("pepolar", members, {"direction", "fmap"})

        report = pd.DataFrame(records, columns=FMAP_REPORT_COLUMNS)
        return report, proposals

    def apply_fmap_variant_proposals(self, summary, proposals):
        """Write globally unambiguous fieldmap rename suggestions into a summary.

        A parameter group that drew more than one proposal is skipped, since its
        collections disagree about which shared label to use.

        Parameters
        ----------
        summary : :obj:`pandas.DataFrame`
            The summary to annotate, modified in place.
        proposals : :obj:`dict`
            Proposals from :meth:`analyze_fmap_variant_consistency`.

        Returns
        -------
        :obj:`pandas.DataFrame`
            The summary, with ``RenameEntitySet`` filled in and ``ManualCheck``
            and ``Notes`` flagged for each proposal that was applied.
        """
        for column in ["RenameEntitySet", "ManualCheck", "Notes"]:
            summary[column] = summary[column].astype("object")
        for key_param_group, entity_sets in proposals.items():
            if len(entity_sets) != 1:
                continue
            mask = summary["KeyParamGroup"] == key_param_group
            summary.loc[mask, "RenameEntitySet"] = next(iter(entity_sets))
            summary.loc[mask, "ManualCheck"] = 1
            existing = summary.loc[mask, "Notes"].fillna("").astype(str)
            summary.loc[mask, "Notes"] = existing.apply(
                lambda note: "; ".join(
                    part for part in [note, "Review proposed shared fieldmap variant."] if part
                )
            )
        return summary

    @staticmethod
    def parse_entity_set(value):
        """Validate an entity set copied from the summary and return it.

        Parameters
        ----------
        value : :obj:`str`
            A complete entity set, such as
            ``acquisition-VARIANTVar1_datatype-dwi_direction-AP_suffix-dwi``.

        Returns
        -------
        :obj:`str`
            The entity set, with surrounding whitespace removed.

        Raises
        ------
        ValueError
            If ``value`` is not a series of underscore-separated, alphanumeric
            ``entity-label`` pairs.
        """
        value = str(value).strip()
        if not re.fullmatch(r"[A-Za-z0-9]+-[A-Za-z0-9]+(?:_[A-Za-z0-9]+-[A-Za-z0-9]+)*", value):
            raise ValueError(
                "Entity sets must be complete, underscore-separated entity-label pairs as "
                "written in the summary, such as "
                "acquisition-VARIANTVar1_datatype-dwi_suffix-dwi."
            )
        return value

    @staticmethod
    def _read_entity_set_table(value, required_columns, option):
        """Read a CSV or TSV entity set table, or return None for a non-table value.

        Private because it only exists to share one table-reading rule between
        the two entity set options below.

        Parameters
        ----------
        value : :obj:`str` or :obj:`pathlib.Path`
            A command-line value that may name a table file.
        required_columns : :obj:`tuple` of :obj:`str`
            Columns the table must contain.
        option : :obj:`str`
            Option name to quote in error messages.

        Returns
        -------
        :obj:`pandas.DataFrame` or None
            The table, or None when ``value`` does not name a CSV or TSV file.

        Raises
        ------
        ValueError
            If the named file does not exist or lacks a required column.
        """
        table_path = Path(str(value))
        table_suffix = table_path.suffix.lower()
        if table_suffix not in {".csv", ".tsv"}:
            return None
        if not table_path.is_file():
            raise ValueError(f"{option} table file does not exist: {table_path}")
        table = pd.read_csv(table_path, sep="," if table_suffix == ".csv" else "\t")
        if not set(required_columns).issubset(table.columns):
            raise ValueError(
                f"{option} table files must contain these columns: " + ", ".join(required_columns)
            )
        return table

    def load_entity_set_changes(self, change_rename_entity_set):
        """Load exact entity set substitutions from CLI strings or mapping tables.

        Parameters
        ----------
        change_rename_entity_set : :obj:`list` of :obj:`str` or None
            Each item is either ``OLD_ENTITY_SET=NEW_ENTITY_SET`` or a path to a
            CSV or TSV file with ``old_entity_set`` and ``new_entity_set`` columns.
            The two forms can be mixed.

        Returns
        -------
        :obj:`dict`
            Maps each old entity set to its replacement.

        Raises
        ------
        ValueError
            If a value is malformed, a mapping file is missing or lacks the
            required columns, or two substitutions conflict.
        """
        changes = {}

        def add_change(old, new):
            old = self.parse_entity_set(old)
            new = self.parse_entity_set(new)
            existing = changes.get(old)
            if existing is not None and existing != new:
                raise ValueError(f"Conflicting substitutions were supplied for {old}.")
            changes[old] = new

        for raw_change in change_rename_entity_set or []:
            mappings = self._read_entity_set_table(
                raw_change, ("old_entity_set", "new_entity_set"), "--change-RenameEntitySet"
            )
            if mappings is not None:
                for _, mapping in mappings.iterrows():
                    add_change(mapping["old_entity_set"], mapping["new_entity_set"])
                continue

            raw_change = str(raw_change)
            if raw_change.count("=") != 1:
                raise ValueError(
                    "Each --change-RenameEntitySet value must have the form "
                    "OLD_ENTITY_SET=NEW_ENTITY_SET or be a path to a CSV or TSV mapping file."
                )
            old, new = raw_change.split("=", 1)
            add_change(old, new)

        return changes

    def load_entity_set_removals(self, remove_rename_entity_set):
        """Load exact entity sets to delete from CLI strings or table files.

        Parameters
        ----------
        remove_rename_entity_set : :obj:`list` of :obj:`str` or None
            Each item is either an entity set or a path to a CSV or TSV file with
            an ``entity_set`` column. The two forms can be mixed.

        Returns
        -------
        :obj:`set` of :obj:`str`
            The entity sets whose matching groups should be deleted.

        Raises
        ------
        ValueError
            If a value is malformed, or a table file is missing or lacks its
            required column.
        """
        removals = set()
        for raw_removal in remove_rename_entity_set or []:
            table = self._read_entity_set_table(
                raw_removal, ("entity_set",), "--remove-RenameEntitySet"
            )
            if table is not None:
                removals.update(self.parse_entity_set(value) for value in table["entity_set"])
                continue
            removals.add(self.parse_entity_set(raw_removal))

        return removals

    def _matching_entity_set_rows(self, summary, entity_sets):
        """Yield summary rows whose planned entity set is in ``entity_sets``.

        Private because the yielded triple is shaped for the two callers below,
        which mutate ``summary`` while iterating it.
        """
        for row_index, row in summary.iterrows():
            planned_entity_set = self.get_planned_entity_set(row)
            if planned_entity_set in entity_sets:
                yield row_index, row, planned_entity_set

    def apply_entity_set_changes(self, summary, changes):
        """Apply exact entity set substitutions to a summary dataframe in memory.

        Parameters
        ----------
        summary : :obj:`pandas.DataFrame`
            The summary to edit, modified in place.
        changes : :obj:`dict`
            Substitutions from :meth:`load_entity_set_changes`.

        Returns
        -------
        :obj:`pandas.DataFrame`
            The summary, with ``RenameEntitySet`` set on every matching row.

        Raises
        ------
        ValueError
            If no row's planned entity set matched, which usually means a typo.
        """
        summary["RenameEntitySet"] = summary["RenameEntitySet"].astype("object")
        changed_rows = 0
        for row_index, _, planned_entity_set in self._matching_entity_set_rows(summary, changes):
            summary.at[row_index, "RenameEntitySet"] = changes[planned_entity_set]
            changed_rows += 1

        if not changed_rows:
            supplied = ", ".join(sorted(changes))
            raise ValueError(
                f"No summary rows matched the requested entity set substitutions: {supplied}"
            )
        return summary

    def apply_entity_set_removals(self, summary, entity_sets):
        """Mark parameter groups with exact planned entity sets for deletion.

        Deletion reuses the normal ``MergeInto`` path rather than a second
        removal mechanism, so companions and ``IntendedFor`` references are
        handled the same way as for a hand-edited summary.

        Parameters
        ----------
        summary : :obj:`pandas.DataFrame`
            The summary to edit, modified in place.
        entity_sets : :obj:`set` of :obj:`str`
            Entity sets whose matching groups should be deleted.

        Returns
        -------
        :obj:`pandas.DataFrame`
            The summary, with ``MergeInto`` set to 0 on every matching row.

        Raises
        ------
        ValueError
            If no row matched, or if a matching row already carries a different
            ``MergeInto`` instruction.
        """
        if "MergeInto" not in summary.columns:
            summary["MergeInto"] = pd.NA
        summary["MergeInto"] = summary["MergeInto"].astype("object")

        matched_rows = []
        for row_index, row, _ in self._matching_entity_set_rows(summary, entity_sets):
            existing_merge = row["MergeInto"]
            if utils.is_nonempty(existing_merge) and str(existing_merge) not in {"0", "0.0"}:
                raise ValueError(
                    "--remove-RenameEntitySet cannot replace an existing MergeInto instruction "
                    f"for {row['KeyParamGroup']}."
                )
            summary.at[row_index, "MergeInto"] = 0
            matched_rows.append(row_index)

        if not matched_rows:
            supplied = ", ".join(sorted(entity_sets))
            raise ValueError(f"No summary rows matched the requested removals: {supplied}")
        return summary

    def validate_rename_destinations(self, rename_pairs, pending_deletions=()):
        """Fail before mutation when the planned file destinations are unsafe.

        Parameters
        ----------
        rename_pairs : :obj:`list` of :obj:`tuple`
            The moves from :meth:`plan_rename_pairs`.
        pending_deletions : :obj:`set` of :obj:`str`
            Files that earlier apply steps remove before any rename runs, so
            occupying a destination that is about to be deleted is not a conflict.

        Raises
        ------
        ValueError
            If two sources map to one destination, a rename chain or swap would
            overwrite a file, or a destination is already occupied.
        """
        pending_deletions = set(pending_deletions)
        pairs = list(rename_pairs)

        sources = {source for source, _ in pairs}
        destinations = defaultdict(set)
        for source, destination in pairs:
            destinations[destination].add(source)

        conflicts = []
        for destination, source_set in destinations.items():
            if len(source_set) > 1:
                conflicts.append(f"multiple sources map to {destination}")
            elif destination in pending_deletions:
                continue
            elif destination in sources and destination not in source_set:
                conflicts.append(f"rename chain or swap would overwrite {destination}")
            elif Path(destination).exists() and destination not in source_set:
                conflicts.append(f"destination already exists: {destination}")
        if conflicts:
            raise ValueError("Unsafe rename plan: " + "; ".join(conflicts))

    def validate_fmap_deletions(self, files_df, summary, deletion_keys, report=None):
        """Fail before mutation when deletions would split a fieldmap collection.

        A BIDS B0 fieldmap collection is only usable whole, so deleting some of
        its members leaves files that no distortion-correction tool can use.
        This guards every deletion, whether it came from a hand-edited
        ``MergeInto`` of 0 or from ``--remove-RenameEntitySet``.

        Parameters
        ----------
        files_df : :obj:`pandas.DataFrame`
            A CuBIDS files table.
        summary : :obj:`pandas.DataFrame`
            The matching parameter group summary.
        deletion_keys : :obj:`set` of :obj:`str`
            ``KeyParamGroup`` values whose files apply is about to delete.
        report : :obj:`pandas.DataFrame` or None
            A report from :meth:`analyze_fmap_variant_consistency` for these same
            tables, to save recomputing it. Computed here when not supplied.

        Raises
        ------
        ValueError
            If any fieldmap collection would lose some, but not all, members.
        """
        if not deletion_keys:
            return

        if report is None:
            report, _ = self.analyze_fmap_variant_consistency(files_df, summary)
        planned_entity_sets = {
            row["KeyParamGroup"]: self.get_planned_entity_set(row) for _, row in summary.iterrows()
        }

        partial_collections = []
        surviving_entity_sets = set()
        for _, record in report.iterrows():
            keys = set(filter(None, str(record["KeyParamGroups"]).split("|")))
            survivors = keys - deletion_keys
            if not keys & deletion_keys or not survivors:
                continue
            partial_collections.append(record["CollectionID"])
            surviving_entity_sets.update(planned_entity_sets.get(key, key) for key in survivors)

        if partial_collections:
            raise ValueError(
                "Deleting part of a fieldmap collection leaves it unusable; "
                f"{len(partial_collections)} would lose some, but not all, members, starting "
                f"with {partial_collections[0]}. Delete every member of each collection, or "
                "use cubids purge for individual files. Also missing: "
                + ", ".join(sorted(surviving_entity_sets))
            )

    def validate_fmap_renames(
        self, files_df, summary, entity_sets, pending_deletions=(), report=None
    ):
        """Ensure every B0 fieldmap collection being renamed has matching planned entities.

        Only ``PASS`` collections are accepted, so the analysis runs without
        ``rename_cols``: whether a mismatch would have been labelled ``PROPOSED``
        or ``MANUAL_REVIEW`` does not change the outcome.

        Only the B0 suffixes are checked. Other images under ``fmap/``, such as
        ``TB1map`` or ``M0scan``, belong to no collection and so have no sibling
        whose label they need to agree with; they are renamed like any other image.

        Parameters
        ----------
        files_df : :obj:`pandas.DataFrame`
            A CuBIDS files table.
        summary : :obj:`pandas.DataFrame`
            The matching parameter group summary.
        entity_sets : :obj:`dict`
            Maps ``KeyParamGroup`` to the entity set its files should take.
        pending_deletions : :obj:`set` of :obj:`str`
            Files an earlier apply step removes. These are never renamed, so their
            groups do not need to pass.
        report : :obj:`pandas.DataFrame` or None
            A report from :meth:`analyze_fmap_variant_consistency` for these same
            tables, to save recomputing it. Computed here when not supplied.

        Raises
        ------
        ValueError
            If any fieldmap being renamed belongs to a collection that is
            incomplete or mismatched.
        """
        pending_deletions = set(pending_deletions)
        fmap_keys = set()
        for _, row in files_df.iterrows():
            filepath = str(row["FilePath"])
            if (
                "/fmap/" not in filepath
                or row["KeyParamGroup"] not in entity_sets
                or self.path + filepath in pending_deletions
                or parse_file_entities(filepath).get("suffix") not in B0_FMAP_SUFFIXES
            ):
                continue
            fmap_keys.add(row["KeyParamGroup"])

        if not fmap_keys:
            return

        if report is None:
            report, _ = self.analyze_fmap_variant_consistency(files_df, summary)
        reported_keys = set()
        invalid_records = []
        for _, record in report.iterrows():
            keys = set(filter(None, str(record["KeyParamGroups"]).split("|")))
            reported_keys.update(keys)
            if keys & fmap_keys and record["Status"] != "PASS":
                invalid_records.append(record["CollectionID"])

        # Every B0 fieldmap reaches a record, so a gap here means the tables
        # disagree with each other rather than that the collection is unusable.
        unclassified = fmap_keys - reported_keys
        if invalid_records or unclassified:
            details = invalid_records + [f"unclassified key {key}" for key in sorted(unclassified)]
            raise ValueError(
                "--fmap requires matching, complete fieldmap collections before renaming: "
                + "; ".join(details)
            )

        print(
            "WARNING: --fmap renames fieldmaps. Matching labels do not prove AP/PA "
            "geometry is TOPUP-compatible; review the fmap report."
        )

    def apply_tsv_changes(
        self,
        summary_tsv,
        files_tsv,
        new_prefix,
        raise_on_error=True,
        n_cpus=1,
        allow_fmap_renames=False,
        change_rename_entity_set=None,
        remove_rename_entity_set=None,
        write_edited_summary=None,
    ):
        """Apply changes documented in the edited summary tsv and generate the new tsv files.

        This function looks at the RenameEntitySet and MergeInto
        columns and modifies the bids dataset according to the
        specified changs.

        Parameters
        ----------
        summary_tsv : :obj:`str`
            Path to the edited summary tsv file.
        files_tsv : :obj:`str`
            Path to the edited files tsv file.
        new_prefix : :obj:`str`
            Path prefix to the new tsv files.
        raise_on_error : :obj:`bool`
            If True, raise an error if the MergeInto column contains invalid merges.
        allow_fmap_renames : :obj:`bool`
            Allow validated fieldmap files to be renamed. Fieldmaps are skipped by default.
        change_rename_entity_set : list[str] or None
            Exact ``OLD_ENTITY_SET=NEW_ENTITY_SET`` substitutions or paths to CSV/TSV mapping
            tables with ``old_entity_set`` and ``new_entity_set`` columns.
        remove_rename_entity_set : list[str] or None
            Exact entity sets whose matching groups are deleted, or paths to CSV/TSV tables
            with an ``entity_set`` column. These are matched after the substitutions above
            have been applied, so a group that both options touch is named here by its
            substituted entity set.
        write_edited_summary : :obj:`pathlib.Path` or None
            Destination for the derived summary, written once the request has been fully
            validated. Required when entity set changes are used.
        """
        # reset lists of old and new filenames
        self.old_filenames = []
        self.new_filenames = []
        self._renamed_sources = set()

        if "/" not in str(summary_tsv):
            if not self.cubids_code_dir:
                self.create_cubids_code_dir()
            summary_tsv = self.path + "/code/CuBIDS/" + summary_tsv

        if "/" not in str(files_tsv):
            if not self.cubids_code_dir:
                self.create_cubids_code_dir()
            files_tsv = self.path + "/code/CuBIDS/" + files_tsv

        summary_df = pd.read_table(summary_tsv)
        files_df = pd.read_table(files_tsv)

        entity_set_changes = self.load_entity_set_changes(change_rename_entity_set)
        entity_set_removals = self.load_entity_set_removals(remove_rename_entity_set)
        edited_summary_path = None
        if entity_set_changes or entity_set_removals:
            if write_edited_summary is None:
                raise ValueError(
                    "--write-edited-summary is required with --change-RenameEntitySet or "
                    "--remove-RenameEntitySet."
                )
            # Substitutions run first, so a removal has to name the entity set a
            # substitution leaves behind rather than the one the summary started with.
            if entity_set_changes:
                summary_df = self.apply_entity_set_changes(summary_df, entity_set_changes)
            if entity_set_removals:
                summary_df = self.apply_entity_set_removals(summary_df, entity_set_removals)
            edited_summary_path = Path(write_edited_summary)

        # Plan and validate everything before the first mutation, so that an
        # unsafe request fails without leaving the dataset partially changed.
        change_keys_df = summary_df[summary_df["RenameEntitySet"].apply(utils.is_nonempty)]
        entity_sets = {
            row["KeyParamGroup"]: row["RenameEntitySet"] for _, row in change_keys_df.iterrows()
        }

        # Check that the MergeInto column only contains valid merges
        ok_merges, deletions = check_merging_operations(summary_df, raise_on_error=raise_on_error)

        to_remove = []
        deletion_keys = set()
        for rm_id in deletions:
            files_to_rm = files_df.loc[(files_df[["ParamGroup", "EntitySet"]] == rm_id).all(1)]
            deletion_keys.update(files_to_rm["KeyParamGroup"])

            for rm_me in files_to_rm.FilePath:
                if Path(self.path + rm_me).exists():
                    to_remove.append(self.path + rm_me)

        fmap_report = None
        if deletion_keys or (allow_fmap_renames and entity_sets):
            fmap_report, _ = self.analyze_fmap_variant_consistency(files_df, summary_df)

        self.validate_fmap_deletions(files_df, summary_df, deletion_keys, fmap_report)
        files_to_purge = self.get_files_to_purge(to_remove)
        rename_plan = self.plan_renames(files_df, entity_sets, allow_fmap_renames, files_to_purge)
        rename_pairs = self.plan_rename_pairs(rename_plan)
        if allow_fmap_renames:
            self.validate_fmap_renames(
                files_df, summary_df, entity_sets, files_to_purge, fmap_report
            )
        self.validate_rename_destinations(rename_pairs, files_to_purge)

        # Everything that could reject this request has now run, so recording the
        # derived summary here cannot leave an audit trail for an apply that never
        # happened.
        if edited_summary_path is not None:
            summary_df.to_csv(edited_summary_path, sep="\t", index=False)

        merge_commands = []
        merge_pairs = []
        for source_id, dest_id in ok_merges:
            dest_files = files_df.loc[(files_df[["ParamGroup", "EntitySet"]] == dest_id).all(1)]
            source_files = files_df.loc[
                (files_df[["ParamGroup", "EntitySet"]] == source_id).all(1)
            ]

            # Get a source json file
            img_full_path = self.path + source_files.iloc[0].FilePath
            source_json = utils.img_to_new_ext(img_full_path, ".json")
            for dest_nii in dest_files.FilePath:
                dest_json = utils.img_to_new_ext(self.path + dest_nii, ".json")
                if Path(dest_json).exists() and Path(source_json).exists():
                    merge_pairs.append((source_json, dest_json))

        # Perform merges in-process (no subprocess spawning)
        for source_json, dest_json in merge_pairs:
            merge_json_into_json(source_json, dest_json)
            merge_commands.append(f"# merged {source_json} -> {dest_json}")

        # call purge associations on list of files to remove
        self._purge_associations(to_remove)

        # Now do the file renaming
        move_ops = []
        # return if nothing to change
        if rename_pairs:
            # Queue exactly the moves that were validated above.
            self._record_rename_pairs(rename_pairs)

            # Build an index of IntendedFor references once (reused during renames)
            intended_for_index = self._build_intendedfor_index()
            for file_path, _, new_path in rename_plan:
                self._rewrite_intendedfor_references(file_path, new_path, intended_for_index)

            self.update_scans_tsv_filenames(
                {
                    old_filename: new_filename
                    for old_filename, new_filename in zip(self.old_filenames, self.new_filenames)
                    if str(old_filename).endswith((".nii", ".nii.gz"))
                }
            )

            # create string of mv command ; mv command for dlapi.run
            for from_file, to_file in zip(self.old_filenames, self.new_filenames):
                if Path(from_file).exists():
                    # if using datalad, we want to git mv instead of mv
                    if self.use_datalad:
                        move_ops.append(f"git mv {from_file} {to_file}")
                    else:
                        move_ops.append(f"mv {from_file} {to_file}")

        full_cmd = "\n".join(merge_commands + move_ops)
        if full_cmd:
            renames = str(Path(self.path) / (new_prefix + "_full_cmd.sh"))

            # write full_cmd to a .sh file
            with open(renames, "w") as fo:
                fo.write("#!/bin/bash\n")
                fo.write(full_cmd)

            if self.use_datalad:
                # first check if IntendedFor renames need to be saved
                if not self.is_datalad_clean():
                    s1 = "Renamed IntendedFor references to "
                    s2 = "Variant Group scans"
                    IF_rename_msg = s1 + s2
                    dl_jobs = n_cpus if n_cpus and n_cpus > 1 else 1
                    self.datalad_save(message=IF_rename_msg, jobs=dl_jobs)

                s1 = "Renamed Variant Group scans according to their variant "
                s2 = "parameters"

                rename_commit = s1 + s2

                # Use datalad run with --jobs for parallel get/save
                dl_jobs = n_cpus if n_cpus and n_cpus > 1 else 1
                subprocess.run(
                    [
                        "datalad",
                        "run",
                        "-m",
                        rename_commit,
                        "-J",
                        str(dl_jobs),
                        "bash",
                        renames,
                    ],
                    cwd=self.path,
                )
            else:
                subprocess.run(
                    ["bash", renames],
                    stdout=subprocess.PIPE,
                    cwd=str(Path(new_prefix).parent),
                )
        else:
            print("Not running any commands")

        self._invalidate_index()
        self.get_tsvs(new_prefix)

        # Remove the shell script created above
        if full_cmd:
            Path(renames).unlink(missing_ok=True)

    def change_filename(self, filepath, entities, intended_for_index=None):
        """Apply changes to a filename based on the renamed entity sets.

        This function takes into account the new entity set names
        and renames all files whose entity set names changed.

        Parameters
        ----------
        filepath : :obj:`str`
            Path prefix to a file in the affected entity set change.
        entities : :obj:`dict`
            A pybids dictionary of entities parsed from the new entity set name.

        Notes
        -----
        This is the function I need to spend the most time on, since it has entities hardcoded.

        :meth:`apply_tsv_changes` does not call this. It queues the moves from the
        plan it already validated, then rewrites ``IntendedFor`` for each renamed
        NIfTI, so that no rename can be discovered a second time and differ.
        """
        new_path = self.get_planned_destination(filepath, entities)
        self._record_rename_pairs(self.get_associated_file_pairs(filepath, new_path))
        self._rewrite_intendedfor_references(filepath, new_path, intended_for_index)

        # save IntendedFor purges so that you can datalad run the
        # remove association file commands on a clean dataset
        # if self.use_datalad:
        #     if not self.is_datalad_clean():
        #         self.datalad_save(message="Renamed IntendedFors")
        #         self.reset_bids_layout()
        # else:
        #     print("No IntendedFor References to Rename")

    def copy_exemplars(self, exemplars_dir, exemplars_tsv, min_group_size):
        """Copy one subject from each Acquisition Group into a new directory for testing preps.

        Raises an error if the subjects are not unlocked,
        unlocks each subject before copying if --force_unlock is set.

        Parameters
        ----------
        exemplars_dir : :obj:`str`
            path to the directory that will contain one subject
            from each Acqusition Group (*_AcqGrouping.tsv)
            example path: /Users/Covitz/tsvs/CCNP_Acq_Groups/
        exemplars_tsv : :obj:`str`
            path to the .tsv file that lists one subject
            from each Acqusition Group (*_AcqGrouping.tsv
            from the `cubids group` output)
            example path: /Users/Covitz/tsvs/CCNP_Acq_Grouping.tsv
        min_group_size : :obj:`int`
            Minimum number of subjects in an acq group for it to be included
            in the exemplar dataset.
        """
        # create the exemplar ds
        if self.use_datalad:
            subprocess.run(
                [
                    "datalad",
                    "--log-level",
                    "error",
                    "create",
                    "-c",
                    "text2git",
                    exemplars_dir,
                ]
            )
        if os.sep not in str(exemplars_tsv):
            if not self.cubids_code_dir:
                self.create_cubids_code_dir()
            exemplars_tsv = self.path + "/code/CuBIDS/" + exemplars_tsv

        # load the exemplars tsv
        subs = pd.read_table(exemplars_tsv)

        # if min group size flag set, drop acq groups with less than min
        if min_group_size > 1:
            group_counts = subs["AcqGroup"].map(subs["AcqGroup"].value_counts())
            subs = subs[group_counts >= min_group_size]

        # get one sub from each acq group
        unique = subs.drop_duplicates(subset=["AcqGroup"])

        # cast list to a set to drop duplicates, then convert back to list
        unique_subs = list(set(unique["subject"].tolist()))
        for subid in unique_subs:
            source = str(self.path) + "/" + subid
            dest = exemplars_dir + "/" + subid
            # Copy the content of source to destination
            copytree(source, dest)

        # Copy the dataset_description.json
        copyfile(
            str(self.path) + "/" + "dataset_description.json",
            exemplars_dir + "/" + "dataset_description.json",
        )

        s1 = "Copied one subject from each Acquisition Group "
        s2 = "into the Exemplar Dataset"
        msg = s1 + s2
        if self.use_datalad:
            subprocess.run(["datalad", "save", "-d", exemplars_dir, "-m", msg])

    def purge(self, scans_txt, n_cpus=1):
        """Purge all associations of desired scans from a bids dataset.

        Parameters
        ----------
        scans_txt : str
            path to the .txt file that lists the scans
            you want to be deleted from the dataset, along
            with their associations.
            example path: /Users/Covitz/CCNP/scans_to_delete.txt
        """
        self.scans_txt = scans_txt

        scans = []
        with open(scans_txt, "r") as fd:
            reader = csv.reader(fd)
            for row in reader:
                scans.append(self.path + "/" + str(row[0]))

        # check to ensure scans are all real files in the ds!

        self._purge_associations(scans, n_cpus=n_cpus)

    def _purge_associations(self, scans, n_cpus=1):
        """Purge field map JSONs' IntendedFor references.

        Parameters
        ----------
        scans : :obj:`list` of :obj:`str`
            List of file paths to remove from field map JSONs.
        """
        # Build index once; remove IntendedFor references only where present
        intended_index = self._build_intendedfor_index()

        for scan in scans:
            self._rewrite_intendedfor_references(scan, intended_for_index=intended_index)

        self.update_scans_tsv_filenames(
            {str(scan): None for scan in scans if str(scan).endswith((".nii", ".nii.gz"))}
        )

        # save IntendedFor purges so that you can datalad run the
        # remove association file commands on a clean dataset
        if self.use_datalad and not self.is_datalad_clean():
            s1 = "Purged IntendedFor references to files "
            s2 = "requested for removal"
            message = s1 + s2
            dl_jobs = n_cpus if n_cpus and n_cpus > 1 else 1
            self.datalad_save(message=message, jobs=dl_jobs)
            self._invalidate_index()

        # NOW WE WANT TO PURGE ALL ASSOCIATIONS
        to_remove = self.get_files_to_purge(scans)

        # create rm commands for all files that need to be purged
        purge_commands = []
        for rm_me in to_remove:
            if Path(rm_me).exists():
                purge_commands.append("rm " + rm_me)

        # datalad run the file deletions (purges)
        full_cmd = "\n".join(purge_commands)
        if full_cmd:
            # write full_cmd to a .sh file
            # Open file for writing

            path_prefix = str(Path(self.path).parent)

            with open(path_prefix + "/" + "_full_cmd.sh", "w") as fo:
                fo.write("#!/bin/bash\n")
                fo.write(full_cmd)

            if self.scans_txt:
                cmt = f"Purged scans listed in {self.scans_txt} from dataset"
            else:
                cmt = "Purged Parameter Groups marked for removal"

            purge_file = path_prefix + "/" + "_full_cmd.sh"
            if self.use_datalad:
                self.datalad_handle.run(cmd=["bash", purge_file], message=cmt)
            else:
                subprocess.run(
                    ["bash", path_prefix + "/" + "_full_cmd.sh"],
                    stdout=subprocess.PIPE,
                    cwd=path_prefix,
                )

            self._invalidate_index()

        else:
            print("Not running any association removals")

    def get_nifti_associations(self, nifti):
        """Get nifti associations.

        Parameters
        ----------
        nifti : str or Path
            The path to the NIfTI file for which to find associated files.

        Returns
        -------
        associations : list of str
            A list of paths to files associated with the given NIfTI file, excluding
            the NIfTI file itself.
        """
        nifti = Path(nifti)
        stem = nifti.name.split(".")[0]
        parent = nifti.parent
        associations = []
        for f in parent.iterdir():
            if f.name.startswith(stem + ".") and not f.name.endswith((".nii", ".nii.gz")):
                associations.append(str(f))
        return sorted(associations)

    def _cache_fieldmaps(self):
        """Search all fieldmaps and create a lookup for each file.

        This method scans for fieldmap files with specific suffixes and extensions,
        retrieves their metadata, and creates a lookup dictionary that maps each
        file to its corresponding fieldmap(s). If a fieldmap file does not have an
        "IntendedFor" field in its metadata, it is added to a list of misfits.

        Returns
        -------
        misfits : list
            A list of fieldmap files that do not have an "IntendedFor" field in their metadata.
        """
        suffix = "(phase1|phasediff|epi|fieldmap)"
        fmap_files = self.layout.get(
            suffix=suffix, regex_search=True, extension=[".nii.gz", ".nii"]
        )

        misfits = []
        files_to_fmaps = defaultdict(list)
        for fmap_file in tqdm(fmap_files):
            # intentions = listify(fmap_file.get_metadata().get("IntendedFor"))
            fmap_json = utils.img_to_new_ext(fmap_file.path, ".json")
            metadata = utils.get_sidecar_metadata(fmap_json)
            if metadata == "Erroneous sidecar":
                print("Error parsing sidecar: ", str(fmap_json))
                continue
            if_list = metadata.get("IntendedFor")
            intentions = listify(if_list)
            subject_prefix = f"sub-{fmap_file.entities['subject']}"

            if intentions is not None:
                for intended_for in intentions:
                    full_path = Path(self.path) / subject_prefix / intended_for
                    files_to_fmaps[str(full_path)].append(fmap_file)

            # fmap file detected, no intended for found
            else:
                misfits.append(fmap_file)

        self.fieldmap_lookup = files_to_fmaps
        self.fieldmaps_cached = True

        # return a list of all filenames where fmap file detected,
        # no intended for found
        return misfits

    def _build_intendedfor_index(self):
        """Build an index from IntendedFor entries to JSON files that declare them.

        Uses the Arrow index to read IntendedFor metadata directly,
        avoiding per-file JSON reads and rglob scans.

        Returns
        -------
        dict
            Mapping: IntendedFor entry (str) -> list of JSON file paths that include it.
        """
        raw = indexing.get_fieldmap_intended_for(self.index)
        # Convert relative paths to absolute
        return {k: [os.path.join(self.path, p) for p in v] for k, v in raw.items()}

    def get_param_groups_from_entity_set(self, entity_set):
        """Split entity sets into param groups based on json metadata.

        Parameters
        ----------
        entity_set : str
            Entity set name.

        Returns
        -------
        ret : tuple of two DataFrames
            1. A data frame with one row per file where the ParamGroup
            column indicates the group to which each scan belongs.
            2. A data frame with param group summaries
        """
        if not self.fieldmaps_cached:
            raise Exception("Fieldmaps must be cached to find parameter groups.")
        key_entities = utils._entity_set_to_entities(entity_set)
        key_entities["extension"] = ".nii[.gz]*"

        matching_files = self.layout.get(
            return_type="file", scope="self", regex_search=True, **key_entities
        )

        # ensure files who's entities contain key_entities but include other
        # entities do not also get added to matching_files
        to_include = []
        for filepath in matching_files:
            f_entity_set = utils._file_to_entity_set(filepath)

            if f_entity_set == entity_set:
                to_include.append(filepath)

        # get the modality associated with the entity set
        modalities = ["/dwi/", "/anat/", "/func/", "/perf/", "/fmap/"]
        modality = ""
        for mod in modalities:
            if mod in filepath:
                modality = mod.replace("/", "").replace("/", "")

        if modality == "":
            print(f"Unusual Modality Detected: {filepath}")
            modality = "other"

        ret = utils._get_param_groups(
            to_include,
            self.fieldmap_lookup,
            entity_set,
            self.grouping_config,
            modality,
            self.keys_files,
        )

        if ret == "erroneous sidecar found":
            return "erroneous sidecar found"

        # add modality to the return tuple
        l_ret = list(ret)
        l_ret.append(modality)
        tup_ret = tuple(l_ret)
        return tup_ret

    def create_data_dictionary(self):
        """Create a data dictionary for scanning parameters and other metadata.

        This method populates the `data_dict` attribute with descriptions for various
        scanning parameters, relational parameters, and derived parameters based on
        the `grouping_config` attribute. Additionally, it manually adds descriptions
        for non-sidecar columns.

        Attributes
        ----------
        grouping_config : dict
            Configuration dictionary containing `sidecar_params`, `relational_params`,
            and `derived_params` which are used to populate the `data_dict`.

        data_dict : dict
            Dictionary to be populated with parameter descriptions.

        Sidecar Parameters
        ------------------
        - Scanning Parameter: Parameters extracted from sidecar files.
        - NIfTI Header Parameter: Parameters derived from NIfTI headers.

        Manually Added Columns
        ----------------------
        - ManualCheck: Column where users mark groups to manually check.
        - Notes: Column to mark notes about the parameter group.
        - RenameEntitySet: Auto-generated suggested rename of Non-Dominant Groups
            based on variant scanning parameters.
        - Counts: Number of files in the parameter group.
        - Modality: MRI image type.
        - MergeInto: Column to mark groups to remove with a '0'.
        - FilePath: Location of file.
        - EntitySetCount: Number of participants in an Entity Set.
        - EntitySet: A set of scans whose filenames share all BIDS filename key-value
            pairs, excluding subject and session.
        - ParamGroup: The set of scans with identical metadata parameters in their
            sidecars (defined within an Entity Set and denoted numerically).
        - KeyParamGroup: Entity Set name and Param Group number separated by a double
            underscore.
        """
        sidecar_params = self.grouping_config.get("sidecar_params")
        for mod in sidecar_params:
            mod_dict = sidecar_params[mod]
            for s_param in mod_dict:
                if s_param not in self.data_dict:
                    self.data_dict[s_param] = {"Description": "Scanning Parameter"}

        relational_params = self.grouping_config.get("relational_params")
        for r_param in relational_params:
            if r_param not in self.data_dict:
                self.data_dict[r_param] = {"Description": "Scanning Parameter"}

        derived_params = self.grouping_config.get("derived_params")
        for mod in derived_params:
            mod_dict = derived_params[mod]
            for d_param in mod_dict:
                if d_param not in self.data_dict:
                    self.data_dict[d_param] = {"Description": "NIfTI Header Parameter"}

        # Manually add non-sidecar columns/descriptions to data_dict
        desc1 = "Column where users mark groups to manually check"
        self.data_dict["ManualCheck"] = {}
        self.data_dict["ManualCheck"]["Description"] = desc1
        desc2 = "Column to mark notes about the param group"
        self.data_dict["Notes"] = {}
        self.data_dict["Notes"]["Description"] = desc2
        desc31 = "Auto-generated suggested rename of Non-Domiannt Groups"
        desc32 = " based on variant scanning parameters"
        self.data_dict["RenameEntitySet"] = {}
        self.data_dict["RenameEntitySet"]["Description"] = desc31 + desc32
        desc4 = "Number of Files in the Parameter Group"
        self.data_dict["Counts"] = {}
        self.data_dict["Counts"]["Description"] = desc4
        self.data_dict["Modality"] = {}
        self.data_dict["Modality"]["Description"] = "MRI image type"
        desc5 = "Column to mark groups to remove with a '0'"
        self.data_dict["MergeInto"] = {}
        self.data_dict["MergeInto"]["Description"] = desc5
        self.data_dict["FilePath"] = {}
        self.data_dict["FilePath"]["Description"] = "Location of file"
        desc6 = "Number of participants in a Entity Set"
        self.data_dict["EntitySetCount"] = {}
        self.data_dict["EntitySetCount"]["Description"] = desc6
        desc71 = "A set of scans whose filenames share all BIDS filename"
        desc72 = " key-value pairs, excluding subject and session"
        self.data_dict["EntitySet"] = {}
        self.data_dict["EntitySet"]["Description"] = desc71 + desc72
        desc81 = "The set of scans with identical metadata parameters in their"
        desc82 = " sidecars (defined within a Entity Set and denoted"
        desc83 = " numerically)"
        self.data_dict["ParamGroup"] = {}
        self.data_dict["ParamGroup"]["Description"] = desc81 + desc82 + desc83
        desc91 = "Entity Set name and Param Group number separated by a double"
        desc92 = " underscore"
        self.data_dict["KeyParamGroup"] = {}
        self.data_dict["KeyParamGroup"]["Description"] = desc91 + desc92

    def get_data_dictionary(self, df):
        """Create a BIDS data dictionary from dataframe columns.

        Parameters
        ----------
        df : Pandas DataFrame
            Pre export TSV that will be converted to a json dictionary

        Returns
        -------
        data_dict : dictionary
            Python dictionary in BIDS data dictionary format
        """
        json_dict = {}

        # Build column dictionary
        col_list = df.columns.values.tolist()

        data_dict_keys = self.data_dict.keys()

        for col in data_dict_keys:
            if col in col_list:
                json_dict[col] = self.data_dict[col]

        # for col in range(len(col_list)):
        #     col_dict[col + 1] = col_list[col]

        # header_dict = {}
        # # build header dictionary
        # header_dict['Long Description'] = name
        # description = 'https://cubids.readthedocs.io/en/latest/usage.html'
        # header_dict['Description'] = description
        # header_dict['Version'] = 'CuBIDS v1.0.5'
        # header_dict['Levels'] = col_dict

        # # Build top level dictionary
        # data_dict = {}
        # data_dict[name] = header_dict

        return json_dict

    def get_param_groups_dataframes(self):
        """Create DataFrames of files x param groups and a summary.

        This method processes entity sets to generate two DataFrames:
        one containing labeled file parameters and another summarizing
        parameter groups. It also suggests renaming based on variant parameters.

        Returns
        -------
        big_df : pandas.DataFrame
            DataFrame with labeled file parameters.
        summary : pandas.DataFrame
            DataFrame summarizing parameter groups with suggested renaming.
        """
        entity_sets = self.get_entity_sets()
        labeled_files = []
        param_group_summaries = []
        for entity_set in entity_sets:
            try:
                (
                    labeled_file_params,
                    param_summary,
                    modality,
                ) = self.get_param_groups_from_entity_set(entity_set)
            except Exception:
                continue
            if labeled_file_params is None:
                continue
            param_group_summaries.append(param_summary)
            labeled_files.append(labeled_file_params)

        big_df = utils._order_columns(pd.concat(labeled_files, ignore_index=True))

        # make Filepaths relative to bids dir (vectorized)
        big_df["FilePath"] = big_df["FilePath"].str.replace(self.path, "", regex=False)

        summary = utils._order_columns(pd.concat(param_group_summaries, ignore_index=True))

        # create new col that strings key and param group together
        summary["KeyParamGroup"] = summary["EntitySet"] + "__" + summary["ParamGroup"].map(str)

        # move this column to the front of the dataframe
        key_param_col = summary.pop("KeyParamGroup")
        summary.insert(0, "KeyParamGroup", key_param_col)

        # do the same for the files df
        big_df["KeyParamGroup"] = big_df["EntitySet"] + "__" + big_df["ParamGroup"].map(str)

        # move this column to the front of the dataframe
        key_param_col = big_df.pop("KeyParamGroup")
        big_df.insert(0, "KeyParamGroup", key_param_col)

        summary.insert(0, "RenameEntitySet", np.nan)
        summary.insert(0, "MergeInto", np.nan)
        summary.insert(0, "ManualCheck", np.nan)
        summary.insert(0, "Notes", np.nan)

        # Now automate suggested rename based on variant params
        # loop though imaging and derived param keys
        summary["RenameEntitySet"] = summary["RenameEntitySet"].apply(str)
        summary = utils.assign_variants(summary, self.get_variant_rename_columns(summary))

        return big_df, summary

    def get_variant_rename_columns(self, summary):
        """Return the summary columns that variant labels are built from.

        A summary spans every modality in the dataset, so the eligible columns are
        pooled across modalities rather than read from one modality's section. A
        column that belongs to some other modality is missing for this row and for
        its dominant group alike, so it cannot contribute a spurious label.

        Parameters
        ----------
        summary : :obj:`pandas.DataFrame`
            Parameter group summary. Only columns present here are eligible.

        Returns
        -------
        :obj:`list` of :obj:`str`
            Column names, in the order their labels are concatenated.
        """
        relational = self.grouping_config.get("relational_params")

        rename_cols = []
        for sidecar in self.grouping_config.get("sidecar_params").values():
            for col, settings in sidecar.items():
                if (
                    settings.get("suggest_variant_rename")
                    and col in summary.columns
                    and col not in rename_cols
                ):
                    rename_cols.append(col)

        # deal with Fmap! and with IntendedFor Key!
        for relational_key, column in [
            ("FieldmapKey", "HasFieldmap"),
            ("IntendedForKey", "UsedAsFieldmap"),
        ]:
            settings = relational.get(relational_key, {})
            # check if 'bool' or 'columns'
            if settings.get("suggest_variant_rename") and settings.get("display_mode") == "bool":
                rename_cols.append(column)

        return rename_cols

    def get_tsvs(self, path_prefix):
        """Create the _summary and _files tsvs for the bids dataset.

        Parameters
        ----------
        path_prefix : str
            prefix of the path to the directory where you want
            to save your tsvs
            example path: /Users/Covitz/PennLINC/RBC/CCNP/
        """
        self._cache_fieldmaps()

        # check if path_prefix is absolute or relative
        # if relative, put output in BIDS_ROOT/code/CuBIDS/ dir
        if "/" not in path_prefix:
            # path is relative
            # first check if code/CuBIDS dir exits
            # if not, create it
            self.create_cubids_code_dir()
            # send outputs to code/CuBIDS in BIDS tree
            path_prefix = self.path + "/code/CuBIDS/" + path_prefix

        big_df, summary = self.get_param_groups_dataframes()
        fmap_report, fmap_proposals = self.analyze_fmap_variant_consistency(
            big_df, summary, self.get_variant_rename_columns(summary)
        )
        summary = self.apply_fmap_variant_proposals(summary, fmap_proposals)

        summary = summary.sort_values(by=["Modality", "EntitySetCount"], ascending=[True, False])
        big_df = big_df.sort_values(by=["Modality", "EntitySetCount"], ascending=[True, False])

        # Create json dictionaries for summary and files tsvs
        self.create_data_dictionary()
        files_dict = self.get_data_dictionary(big_df)
        summary_dict = self.get_data_dictionary(summary)

        # Save data dictionaires as JSONs
        files_tsv = f"{path_prefix}_files.tsv"
        files_json = f"{path_prefix}_files.json"
        summary_tsv = f"{path_prefix}_summary.tsv"
        summary_json = f"{path_prefix}_summary.json"
        fmap_report_tsv = f"{path_prefix}_fmap_variant_report.tsv"

        with open(files_json, "w") as outfile:
            json.dump(files_dict, outfile, indent=4)

        with open(summary_json, "w") as outfile:
            json.dump(summary_dict, outfile, indent=4)

        big_df.to_csv(files_tsv, sep="\t", index=False)

        summary.to_csv(summary_tsv, sep="\t", index=False)
        fmap_report.to_csv(fmap_report_tsv, sep="\t", index=False)

        # Calculate the acq groups
        group_by_acquisition_sets(files_tsv, path_prefix, self.acq_group_level)

        print(f"CuBIDS detected {len(summary)} Parameter Groups.")
        nonpassing_fmaps = len(fmap_report.loc[fmap_report["Status"] != "PASS"])
        if nonpassing_fmaps:
            print(
                f"WARNING: {nonpassing_fmaps} fmap collections have mismatched variants; "
                f"review {fmap_report_tsv}. Fieldmaps are not renamed without --fmap. "
                "Matching labels do not guarantee compatibility with downstream "
                "pipelines. For example, an AP/PA EPI fieldmap pair with different "
                "Dim3Size values may not be compatible with TOPUP."
            )
        elif len(fmap_report):
            print(f"Fieldmap variant consistency: PASS — {len(fmap_report)} collections checked.")
        print(
            "Groupings info is available in\n\n"
            f"  * {files_tsv}\n"
            f"  * {files_json}\n"
            f"  * {summary_tsv}\n"
            f"  * {summary_json}\n"
            f"  * {fmap_report_tsv}\n"
        )

    def get_entity_sets(self):
        """Identify the entity sets for the BIDS dataset.

        Uses the Arrow index for instant entity set computation instead
        of scanning the filesystem with ``rglob``.

        Returns
        -------
        list of str
            A sorted list of unique entity sets found in the dataset.
        """
        self.keys_files = {}

        # Use Arrow index for fast NIfTI file discovery
        nifti_rel_paths = indexing.get_nifti_paths(self.index)

        for rel_path in nifti_rel_paths:
            abs_path = Path(os.path.join(self.path, rel_path))
            entity_set = utils._file_to_entity_set(abs_path)

            if entity_set not in self.keys_files:
                self.keys_files[entity_set] = []
            self.keys_files[entity_set].append(abs_path)

        return sorted(self.keys_files.keys())

    def change_metadata(self, filters, metadata):
        """Change metadata of BIDS files based on provided filters.

        This method updates the metadata of BIDS files that match the given filters.
        It retrieves the associated JSON sidecar files, updates them with the provided
        metadata, and writes the changes back to the JSON files.

        Parameters
        ----------
        filters : dict
            A dictionary of filters to apply when searching for BIDS files.
            The keys should correspond to BIDS entity names (e.g., 'subject', 'session').
        metadata : dict
            A dictionary containing the metadata to update in the JSON sidecar files.
            The keys should correspond to the metadata fields to be updated.

        Raises
        ------
        FileNotFoundError
            If no JSON sidecar files are found for the BIDS files.
        ValueError
            If irregular associations are found (i.e., more than one JSON file is
            associated with a BIDS file).

        Notes
        -----
        This method appears to be unused in the current codebase.
        """
        files_to_change = self.layout.get(return_type="object", **filters)

        for bidsfile in files_to_change:
            # get the sidecar file
            # bidsjson_file = bidsfile.get_associations()
            bidsjson_file = utils.img_to_new_ext(str(bidsfile), ".json")
            if not bidsjson_file:
                print("NO JSON FILES FOUND IN ASSOCIATIONS")
                continue

            json_file = [x for x in bidsjson_file if "json" in x.filename]
            if len(json_file) != 1:
                print("FOUND IRREGULAR ASSOCIATIONS")

            else:
                # get the data from it
                json_file = json_file[0]

                sidecar = json_file.get_dict()
                sidecar.update(metadata)

                # write out
                utils._update_json(json_file.path, sidecar)

    def get_all_metadata_fields(self):
        """Return all metadata fields in a BIDS directory.

        This method searches through all JSON files in the specified BIDS directory
        and collects all unique metadata fields present in those files. It skips
        files within any ".git" directory and handles empty files and JSON decoding
        errors gracefully.

        Returns
        -------
        list of str
            A sorted list of all unique metadata fields found in the BIDS directory.

        Raises
        ------
        UserWarning
            If there is an error decoding a JSON file or any unexpected error occurs
            while processing a file.
        """
        found_fields = set()
        for json_file in utils.find_json_files(self.path):
            try:
                with open(json_file, "r", encoding="utf-8") as jsonr:
                    content = jsonr.read().strip()
                    if not content:
                        print(f"Empty file: {json_file}")
                        continue
                    metadata = json.loads(content)
                found_fields.update(metadata.keys())
            except json.JSONDecodeError as e:
                warnings.warn(f"Error decoding JSON in {json_file}: {e}")
            except Exception as e:
                warnings.warn(f"Unexpected error with file {json_file}: {e}")

        return sorted(found_fields)

    def remove_metadata_fields(self, fields_to_remove):
        """Remove specific fields from all metadata files in the directory.

        This method iterates through all JSON files in the specified directory
        and removes the specified fields from each file's metadata.

        Parameters
        ----------
        fields_to_remove : list of str
            A list of field names to be removed from the metadata files.

        Returns
        -------
        None
        """
        remove_fields = set(fields_to_remove)
        if not remove_fields:
            return

        for json_file in tqdm(utils.find_json_files(self.path)):
            with open(json_file, "r") as jsonr:
                metadata = json.load(jsonr)

            offending_keys = remove_fields.intersection(metadata.keys())
            if not offending_keys:
                continue

            for key in offending_keys:
                del metadata[key]
            with open(json_file, "w") as jsonr:
                json.dump(metadata, jsonr, indent=4)

        self._invalidate_index()

    # # # # FOR TESTING # # # #
    def get_filenames(self):
        """Get filenames."""
        return self.keys_files

    def get_fieldmap_lookup(self):
        """Get fieldmap lookup."""
        return self.fieldmap_lookup

    def get_layout(self):
        """Get layout."""
        return self.layout


def _add_metadata_single_nifti(nifti_path):
    """Extract metadata from a single NIfTI and write to its sidecar JSON.

    Parameters
    ----------
    nifti_path : :obj:`str`
        Path to a NIfTI file.
    """
    try:
        img = nb.load(str(nifti_path), mmap=False)
    except Exception:
        print("Empty Nifti File: ", str(nifti_path))
        return

    # get important info from niftis
    obliquity = np.any(nb.affines.obliquity(img.affine) > 1e-4)
    voxel_sizes = img.header.get_zooms()
    matrix_dims = img.shape
    # add nifti info to corresponding sidecars
    sidecar = utils.img_to_new_ext(str(nifti_path), ".json")
    if Path(sidecar).exists():
        try:
            with open(sidecar) as f:
                data = json.load(f)
        except Exception:
            print("Error parsing this sidecar: ", sidecar)
            return

        if "Obliquity" not in data:
            data["Obliquity"] = str(obliquity)
        if "VoxelSizeDim1" not in data:
            data["VoxelSizeDim1"] = float(voxel_sizes[0])
        if "VoxelSizeDim2" not in data:
            data["VoxelSizeDim2"] = float(voxel_sizes[1])
        if "VoxelSizeDim3" not in data:
            data["VoxelSizeDim3"] = float(voxel_sizes[2])
        if "Dim1Size" not in data:
            data["Dim1Size"] = matrix_dims[0]
        if "Dim2Size" not in data:
            data["Dim2Size"] = matrix_dims[1]
        if "Dim3Size" not in data:
            data["Dim3Size"] = matrix_dims[2]
        if "NumVolumes" not in data:
            if img.ndim == 4:
                data["NumVolumes"] = matrix_dims[3]
            elif img.ndim == 3:
                data["NumVolumes"] = 1
        if "ImageOrientation" not in data:
            orient = nb.orientations.aff2axcodes(img.affine)
            orient = [str(orientation) for orientation in orient]
            joined = "".join(orient) + "+"
            data["ImageOrientation"] = joined

        with open(sidecar, "w") as file:
            json.dump(data, file, indent=4)
