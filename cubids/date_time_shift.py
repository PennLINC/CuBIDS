"""Date/time anonymization utilities for BIDS datasets.

This module shifts acquisition dates in subject- and session-level
``*_scans.tsv`` files and rounds acquisition times in scans tables and JSON
sidecars.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import stat
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import TypeVar

import pandas as pd

from cubids.utils import find_json_files

logger = logging.getLogger("cubids-cli")

NEW_BASE_DATE = date(1800, 1, 1)
_COMPACT_TIME_PATTERN = (
    r"^(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})(?:\.(?P<fraction>\d{1,6}))?$"
)

_JSON_SCALAR_TIME_PATHS = (
    ("AcquisitionTime",),
    ("global", "const", "PerformedProcedureStepStartTime"),
    ("global", "const", "SeriesTime"),
    ("global", "const", "StudyTime"),
)
_JSON_TIME_ARRAY_PATHS = (
    ("time", "samples", "AcquisitionTime"),
    ("time", "samples", "ContentTime"),
)

_Input = TypeVar("_Input")
_Output = TypeVar("_Output")


@dataclass
class _ScansTable:
    """A scans table read during validation."""

    path: Path
    data: pd.DataFrame


@dataclass
class _ScansChange:
    """A planned change to one scans.tsv acquisition time."""

    row_number: int
    before: str
    after: str


@dataclass
class _ScansUpdate:
    """A validated scans.tsv rewrite and its changes."""

    path: Path
    contents: str
    changes: list[_ScansChange]


@dataclass
class _JSONChange:
    """A planned change to a JSON acquisition or DICOM-derived time value."""

    field_path: str
    before: str
    after: str


@dataclass
class _JSONUpdate:
    """A validated JSON rewrite and its acquisition-time changes."""

    path: Path
    contents: str
    changes: list[_JSONChange]


def parse_iso_datetime(value: str) -> datetime | None:
    """Parse an ISO-8601 datetime used in a scans.tsv ``acq_time`` field."""
    if value is None:
        return None

    value = str(value).strip()
    if not value or value.lower() == "n/a":
        return None

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def round_datetime_to_nearest_hour(acquisition_datetime: datetime) -> datetime:
    """Round a datetime to the nearest hour, with 30 minutes rounding up."""
    offset_microseconds = (
        acquisition_datetime.minute * 60 + acquisition_datetime.second
    ) * 1_000_000 + acquisition_datetime.microsecond
    rounded = acquisition_datetime.replace(minute=0, second=0, microsecond=0)

    if offset_microseconds >= 30 * 60 * 1_000_000:
        rounded += timedelta(hours=1)

    return rounded


def parse_time_string(value: str) -> time | None:
    """Parse supported BIDS JSON ``AcquisitionTime`` representations."""
    if value is None:
        return None

    value = str(value).strip()
    if not value:
        return None

    colon_time = re.match(
        r"^(?P<hour>\d{1,2}):(?P<minute>\d{1,2})"
        r"(?::(?P<second>\d{1,2})(?:\.(?P<fraction>\d{1,9}))?)?$",
        value,
    )
    if colon_time:
        hour = int(colon_time.group("hour"))
        minute = int(colon_time.group("minute"))
        second = int(colon_time.group("second") or 0)
        fraction = colon_time.group("fraction")
        microsecond = int(fraction[:6].ljust(6, "0")) if fraction else 0

        if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
            return time(hour=hour, minute=minute, second=second, microsecond=microsecond)
        return None

    compact_time = re.match(_COMPACT_TIME_PATTERN, value)
    if compact_time:
        hour = int(compact_time.group("hour"))
        minute = int(compact_time.group("minute"))
        second = int(compact_time.group("second"))
        fraction = compact_time.group("fraction")
        microsecond = int(fraction.ljust(6, "0")) if fraction else 0

        if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
            return time(hour=hour, minute=minute, second=second, microsecond=microsecond)

    return None


def round_time_to_nearest_hour(acquisition_time: time) -> time:
    """Round a time to the nearest hour, wrapping 23:30 to 00:00:00."""
    offset_microseconds = (
        acquisition_time.minute * 60 + acquisition_time.second
    ) * 1_000_000 + acquisition_time.microsecond
    hour = acquisition_time.hour

    if offset_microseconds >= 30 * 60 * 1_000_000:
        hour = (hour + 1) % 24

    return time(hour=hour)


def _subject_from_scans_path(path: Path) -> str:
    """Return the ``sub-*`` directory that contains a scans table."""
    for parent in path.parents:
        if parent.name.startswith("sub-"):
            return parent.name
    raise ValueError(f"Scans table is not stored below a subject directory: {path}")


def _parallel_map(
    function: Callable[[_Input], _Output], items: list[_Input], n_cpus: int
) -> list[_Output]:
    """Run independent I/O and planning operations using the requested workers."""
    if n_cpus == 1:
        return [function(item) for item in items]

    with ThreadPoolExecutor(max_workers=n_cpus) as executor:
        return list(executor.map(function, items))


def _read_scans_table(scans_file: Path) -> tuple[_ScansTable | None, str | None]:
    """Read one scans table and return a validation error rather than raising it."""
    try:
        data = pd.read_csv(
            scans_file,
            sep="\t",
            dtype=str,
            keep_default_na=False,
        )
    except (
        OSError,
        UnicodeDecodeError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
    ) as error:
        return None, f"Could not read {scans_file}: {error}"

    return _ScansTable(path=scans_file, data=data), None


def _read_scans_tables(
    scans_files: list[Path], n_cpus: int
) -> tuple[list[_ScansTable], list[str]]:
    """Read all scans tables before any output file is changed."""
    tables = []
    errors = []

    for table, error in _parallel_map(_read_scans_table, scans_files, n_cpus):
        if error:
            errors.append(error)
        elif table is not None:
            tables.append(table)

    return tables, errors


def _get_subject_anchors(tables: list[_ScansTable]) -> dict[str, date]:
    """Determine each subject's earliest rounded acquisition date."""
    subject_dates: defaultdict[str, list[date]] = defaultdict(list)

    for table in tables:
        if "acq_time" not in table.data.columns:
            continue

        subject = _subject_from_scans_path(table.path)
        for value in table.data["acq_time"]:
            acquisition_datetime = parse_iso_datetime(value)
            if acquisition_datetime is not None:
                subject_dates[subject].append(
                    round_datetime_to_nearest_hour(acquisition_datetime).date()
                )

    return {
        subject: min(acquisition_dates)
        for subject, acquisition_dates in subject_dates.items()
        if acquisition_dates
    }


def _plan_scans_update(
    table: _ScansTable, subject_anchors: dict[str, date]
) -> tuple[_ScansUpdate | None, list[str]]:
    """Plan the independent updates for one scans table."""
    if "acq_time" not in table.data.columns:
        return None, []

    subject_anchor = subject_anchors.get(_subject_from_scans_path(table.path))
    if subject_anchor is None:
        return None, []

    updated_times = table.data["acq_time"].copy()
    changes = []
    warnings = []
    for index, value in table.data["acq_time"].items():
        original_value = str(value)
        acquisition_datetime = parse_iso_datetime(original_value)
        if acquisition_datetime is None:
            if original_value.strip() and original_value.strip().lower() != "n/a":
                warnings.append(
                    f"Unparseable acq_time in {table.path}, row {index + 2}: {original_value}"
                )
            continue

        rounded_datetime = round_datetime_to_nearest_hour(acquisition_datetime)
        day_offset = (rounded_datetime.date() - subject_anchor).days
        shifted_datetime = datetime.combine(
            NEW_BASE_DATE + timedelta(days=day_offset),
            rounded_datetime.time(),
        )
        new_value = shifted_datetime.strftime("%Y-%m-%dT%H:%M:%S")

        if new_value != original_value:
            updated_times.at[index] = new_value
            changes.append(
                _ScansChange(
                    row_number=index + 2,
                    before=original_value,
                    after=new_value,
                )
            )

    if not changes:
        return None, warnings

    updated_data = table.data.copy()
    updated_data["acq_time"] = updated_times
    contents = io.StringIO()
    updated_data.to_csv(contents, sep="\t", index=False)
    return (
        _ScansUpdate(path=table.path, contents=contents.getvalue(), changes=changes),
        warnings,
    )


def _plan_scans_updates(
    tables: list[_ScansTable], n_cpus: int
) -> tuple[list[_ScansUpdate], list[str]]:
    """Create scans.tsv updates after finding each subject's rounded date anchor."""
    subject_anchors = _get_subject_anchors(tables)
    updates = []
    warnings = []

    def plan_update(table: _ScansTable) -> tuple[_ScansUpdate | None, list[str]]:
        return _plan_scans_update(table, subject_anchors)

    for update, table_warnings in _parallel_map(plan_update, tables, n_cpus):
        warnings.extend(table_warnings)
        if update is not None:
            updates.append(update)

    return updates, warnings


def _get_json_parent(data: dict, field_path: tuple[str, ...]) -> dict | None:
    """Return the mapping that owns a nested JSON field, if present."""
    parent = data
    for key in field_path[:-1]:
        value = parent.get(key)
        if not isinstance(value, dict):
            return None
        parent = value
    return parent


def _round_json_time_value(value, field_path: str) -> tuple[str | None, str | None]:
    """Round one JSON time value or return a warning when it is unparseable."""
    original_time = "" if value is None else str(value)
    acquisition_time = parse_time_string(original_time)
    if acquisition_time is None:
        return None, f"Unparseable {field_path}: {value}"

    new_value = round_time_to_nearest_hour(acquisition_time).strftime("%H:%M:%S")
    if new_value == original_time:
        return None, None
    return new_value, None


def _plan_json_scalar_time(
    data: dict, field_path: tuple[str, ...]
) -> tuple[list[_JSONChange], list[str]]:
    """Plan a top-level or nested scalar JSON time update."""
    parent = _get_json_parent(data, field_path)
    field_name = ".".join(field_path)
    if parent is None or field_path[-1] not in parent:
        return [], []

    original_value = parent[field_path[-1]]
    new_value, warning = _round_json_time_value(original_value, field_name)
    if warning:
        return [], [warning]
    if new_value is None:
        return [], []

    parent[field_path[-1]] = new_value
    return [_JSONChange(field_path=field_name, before=str(original_value), after=new_value)], []


def _plan_json_time_array(
    data: dict, field_path: tuple[str, ...]
) -> tuple[list[_JSONChange], list[str]]:
    """Plan element-wise updates for a JSON array of time values."""
    parent = _get_json_parent(data, field_path)
    field_name = ".".join(field_path)
    if parent is None or field_path[-1] not in parent:
        return [], []

    values = parent[field_path[-1]]
    if not isinstance(values, list):
        return [], [f"Expected {field_name} to be an array of time values"]

    changes = []
    warnings = []
    updated_values = values.copy()
    for index, original_value in enumerate(values):
        element_path = f"{field_name}[{index}]"
        new_value, warning = _round_json_time_value(original_value, element_path)
        if warning:
            warnings.append(warning)
            continue
        if new_value is not None:
            updated_values[index] = new_value
            changes.append(
                _JSONChange(
                    field_path=element_path,
                    before=str(original_value),
                    after=new_value,
                )
            )

    if changes:
        parent[field_path[-1]] = updated_values
    return changes, warnings


def _plan_json_update(
    json_file: Path,
) -> tuple[_JSONUpdate | None, str | None, str | None]:
    """Validate and plan the independent update for one JSON file."""
    try:
        with json_file.open(encoding="utf-8") as file_handle:
            data = json.load(file_handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, None, f"Could not read JSON {json_file}: {error}"

    if not isinstance(data, dict):
        return None, None, None

    changes = []
    warnings = []
    for field_path in _JSON_SCALAR_TIME_PATHS:
        field_changes, field_warnings = _plan_json_scalar_time(data, field_path)
        changes.extend(field_changes)
        warnings.extend(field_warnings)
    for field_path in _JSON_TIME_ARRAY_PATHS:
        field_changes, field_warnings = _plan_json_time_array(data, field_path)
        changes.extend(field_changes)
        warnings.extend(field_warnings)

    if not changes:
        return None, "\n".join(warnings) if warnings else None, None

    contents = io.StringIO()
    json.dump(data, contents, ensure_ascii=False, indent=4)
    contents.write("\n")
    return (
        _JSONUpdate(
            path=json_file,
            contents=contents.getvalue(),
            changes=changes,
        ),
        "\n".join(warnings) if warnings else None,
        None,
    )


def _plan_json_updates(
    json_files: list[Path], n_cpus: int
) -> tuple[list[_JSONUpdate], list[str], list[str]]:
    """Validate all JSON files and prepare supported acquisition-time updates."""
    updates = []
    warnings = []
    errors = []

    for update, warning, error in _parallel_map(_plan_json_update, json_files, n_cpus):
        if update is not None:
            updates.append(update)
        if warning:
            warnings.append(warning)
        if error:
            errors.append(error)

    return updates, warnings, errors


def _log_changes(
    scans_updates: list[_ScansUpdate], json_updates: list[_JSONUpdate], dry_run: bool
) -> None:
    """Report all changed values using the CLI logger."""
    action = "WOULD CHANGE" if dry_run else "CHANGED"

    for update in scans_updates:
        logger.info("[%s] %s", action, update.path)
        for change in update.changes:
            logger.info(
                "    row %d: acq_time: %s -> %s",
                change.row_number,
                change.before,
                change.after,
            )

    for update in json_updates:
        logger.info("[%s] %s", action, update.path)
        for change in update.changes:
            logger.info("    %s: %s -> %s", change.field_path, change.before, change.after)


def _write_updates(scans_updates: list[_ScansUpdate], json_updates: list[_JSONUpdate]) -> None:
    """Write validated output after preflight has completed successfully."""
    updates = [*scans_updates, *json_updates]
    for update in updates:
        if os.access(update.path, os.W_OK):
            continue
        update.path.chmod(update.path.stat().st_mode | stat.S_IWUSR)
        logger.info("Made file writable: %s", update.path)

    for update in updates:
        update.path.write_text(update.contents, encoding="utf-8")


def date_time_shift(bids_dir: Path, dry_run: bool = False, n_cpus: int = 1) -> int:
    """Shift BIDS acquisition dates and round acquisition times in place.

    Each subject's earliest rounded scans.tsv acquisition date is shifted to
    ``1800-01-01``. Calendar-day offsets are retained, and scans.tsv and JSON
    acquisition times are rounded to the nearest hour. This includes top-level
    and dcmmeta-derived JSON acquisition-time fields. Input files are all read
    and validated before any planned updates are written.

    Parameters
    ----------
    bids_dir : :obj:`pathlib.Path`
        Root of the BIDS dataset to update.
    dry_run : :obj:`bool`
        Report planned changes without writing files.
    n_cpus : :obj:`int`
        Number of workers used to read and plan independent file updates.

    Returns
    -------
    int
        Zero on success, one if metadata cannot be validated or written, and
        two when ``bids_dir`` is not a directory.
    """
    if not bids_dir.is_dir():
        logger.error("BIDS directory does not exist or is not a directory: %s", bids_dir)
        return 2

    if n_cpus < 1:
        logger.error("n_cpus must be at least 1; received %d.", n_cpus)
        return 2

    scans_files = sorted(
        path
        for pattern in ("sub-*/*_scans.tsv", "sub-*/ses-*/*_scans.tsv")
        for path in bids_dir.glob(pattern)
        if path.is_file()
    )
    json_files = find_json_files(bids_dir)
    tables, scans_errors = _read_scans_tables(scans_files, n_cpus)
    scans_updates, scans_warnings = _plan_scans_updates(tables, n_cpus)
    json_updates, json_warnings, json_errors = _plan_json_updates(json_files, n_cpus)
    validation_errors = [*scans_errors, *json_errors]

    for warning in [*scans_warnings, *json_warnings]:
        logger.warning(warning)

    if validation_errors:
        logger.error("Date/time shift validation failed; no files were modified.")
        for error in validation_errors:
            logger.error(error)
        return 1

    if dry_run:
        _log_changes(scans_updates, json_updates, dry_run=True)
    else:
        try:
            _write_updates(scans_updates, json_updates)
        except OSError as error:
            logger.error("Could not write date/time shift updates: %s", error)
            return 1
        _log_changes(scans_updates, json_updates, dry_run=False)

    scans_changes = sum(len(update.changes) for update in scans_updates)
    json_changes = sum(len(update.changes) for update in json_updates)
    logger.info(
        "%s %d scans.tsv files and %d JSON files; %d scans.tsv acq_time values and "
        "%d JSON time values %s.",
        "Checked" if dry_run else "Processed",
        len(scans_files),
        len(json_files),
        scans_changes,
        json_changes,
        "would change" if dry_run else "changed",
    )
    return 0
