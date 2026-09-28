"""Scripted edits to a CuBIDS summary's entity sets.

``cubids apply`` normally reads the ``RenameEntitySet`` and ``MergeInto`` columns
a user hand-edited into a summary. These helpers let the same edits be requested
from the command line instead, by naming an exact entity set:

- :func:`load_entity_set_changes` / :func:`apply_entity_set_changes` back
  ``--change-RenameEntitySet``, filling in ``RenameEntitySet``.
- :func:`load_entity_set_removals` / :func:`apply_entity_set_removals` back
  ``--remove-RenameEntitySet``, marking groups for deletion through the same
  ``MergeInto`` path a hand edit would use.

The ``load_*`` functions turn raw command-line values (or CSV/TSV tables) into
plain Python structures; the ``apply_*`` functions write those into a summary
DataFrame in memory. Keeping them apart lets the whole request be validated
before the first change is made.
"""

import re
from pathlib import Path

import pandas as pd

from cubids import utils

__all__ = [
    "load_entity_set_changes",
    "load_entity_set_removals",
    "apply_entity_set_changes",
    "apply_entity_set_removals",
]


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


def load_entity_set_changes(change_rename_entity_set):
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
        old = parse_entity_set(old)
        new = parse_entity_set(new)
        existing = changes.get(old)
        if existing is not None and existing != new:
            raise ValueError(f"Conflicting substitutions were supplied for {old}.")
        changes[old] = new

    for raw_change in change_rename_entity_set or []:
        mappings = _read_entity_set_table(
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


def load_entity_set_removals(remove_rename_entity_set):
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
        table = _read_entity_set_table(raw_removal, ("entity_set",), "--remove-RenameEntitySet")
        if table is not None:
            removals.update(parse_entity_set(value) for value in table["entity_set"])
            continue
        removals.add(parse_entity_set(raw_removal))

    return removals


def _matching_entity_set_rows(summary, entity_sets):
    """Yield summary rows whose planned entity set is in ``entity_sets``.

    Private because the yielded triple is shaped for the two callers below,
    which mutate ``summary`` while iterating it.
    """
    for row_index, row in summary.iterrows():
        planned_entity_set = utils.get_planned_entity_set(row)
        if planned_entity_set in entity_sets:
            yield row_index, row, planned_entity_set


def apply_entity_set_changes(summary, changes):
    """Apply exact entity set substitutions to a summary dataframe in memory.

    Parameters
    ----------
    summary : :obj:`pandas.DataFrame`
        The summary to edit, modified in place.
    changes : :obj:`dict`
        Substitutions from :func:`load_entity_set_changes`.

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
    for row_index, _, planned_entity_set in _matching_entity_set_rows(summary, changes):
        summary.at[row_index, "RenameEntitySet"] = changes[planned_entity_set]
        changed_rows += 1

    if not changed_rows:
        supplied = ", ".join(sorted(changes))
        raise ValueError(
            f"No summary rows matched the requested entity set substitutions: {supplied}"
        )
    return summary


def apply_entity_set_removals(summary, entity_sets):
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
    for row_index, row, _ in _matching_entity_set_rows(summary, entity_sets):
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
