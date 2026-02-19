"""Arrow-based BIDS dataset indexing for CuBIDS.

This module provides fast file discovery, entity parsing, and metadata loading
using PyArrow tables and Parquet caching. Inspired by bids2table's architecture
but self-contained (no bids2table dependency).

On first run, it performs a single ``os.walk`` pass to discover all files,
parses BIDS entities from filenames, batch-reads JSON sidecars for metadata,
and stores everything in a PyArrow table. The table is cached as a Parquet
file in ``code/CuBIDS/`` so that subsequent runs skip all filesystem I/O.
"""

import json
import os
import re
import subprocess
import time
import warnings
from collections import defaultdict
from functools import lru_cache

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

CACHE_FILENAME = ".cubids_index.parquet"

# Directories to skip during os.walk
_SKIP_DIRS = {"code", "sourcedata", "stimuli", "models", "derivatives"}

# Regex to extract datatype from path like sub-XX/ses-YY/anat/...
_DATATYPE_RE = re.compile(r"sub-[a-zA-Z0-9]+(?:[/\\]ses-[a-zA-Z0-9]+)?[/\\]([a-z]+)[/\\]")

# Fields that are always included regardless of config (relational / special).
_ALWAYS_INCLUDE = {"IntendedFor", "SliceTiming"}


# ---------------------------------------------------------------------------
# Dynamic Arrow type resolution from schema.json + config.yml
# ---------------------------------------------------------------------------


def _schema_def_to_arrow(field_def, prefer_scalar=True):
    """Convert a BIDS ``objects.metadata`` definition to a PyArrow type.

    Parameters
    ----------
    field_def : dict
        A single entry from ``schema["objects"]["metadata"]``.
    prefer_scalar : bool
        When True and the definition uses ``anyOf`` with both scalar and
        array branches, return the scalar type.  This is the right choice
        for sidecar params where CuBIDS reads one value per file.

    Returns
    -------
    pa.DataType
    """
    if "type" in field_def:
        return _json_type_to_arrow(field_def)

    if "anyOf" in field_def:
        return _anyof_to_arrow(field_def["anyOf"], prefer_scalar)

    return pa.string()


def _json_type_to_arrow(field_def):
    """Map a JSON-Schema ``type`` to a PyArrow type."""
    t = field_def["type"]
    if t == "number":
        return pa.float64()
    if t == "integer":
        return pa.int32()
    if t == "string":
        return pa.string()
    if t == "boolean":
        # Store as string to match current CuBIDS behaviour ("True"/"False")
        return pa.string()
    if t == "array":
        return _items_to_list_type(field_def.get("items", {}))
    if t == "object":
        return pa.string()
    return pa.string()


def _items_to_list_type(items_def):
    """Resolve an array's ``items`` definition to ``pa.list_(<elem>)``."""
    if "anyOf" in items_def:
        for branch in items_def["anyOf"]:
            if branch.get("type") == "number":
                return pa.list_(pa.float64())
            if branch.get("type") == "string":
                return pa.list_(pa.string())
        return pa.list_(pa.string())

    elem = items_def.get("type", "string")
    if elem == "number":
        return pa.list_(pa.float64())
    if elem == "integer":
        return pa.list_(pa.int32())
    return pa.list_(pa.string())


def _anyof_to_arrow(branches, prefer_scalar):
    """Pick an Arrow type from an ``anyOf`` list of JSON-Schema branches."""
    scalar = None
    array = None
    for branch in branches:
        btype = branch.get("type")
        if btype == "array":
            array = _items_to_list_type(branch.get("items", {}))
        elif btype == "number":
            scalar = pa.float64()
        elif btype == "integer":
            scalar = pa.int32()
        elif btype == "string":
            scalar = pa.string()
        elif btype == "boolean":
            scalar = pa.string()

    if prefer_scalar and scalar is not None:
        return scalar
    if array is not None:
        return array
    if scalar is not None:
        return scalar
    return pa.string()


def _infer_derived_type(param_name, param_props):
    """Infer an Arrow type for a CuBIDS *derived* param not in the BIDS schema.

    Uses the parameter name and its ``config.yml`` properties (tolerance,
    precision) as hints.

    Parameters
    ----------
    param_name : str
        The derived parameter name (e.g. ``"Dim1Size"``, ``"EchoTimes"``).
    param_props : dict or None
        The property dict from ``config.yml`` (may contain ``tolerance``,
        ``precision``, ``suggest_variant_rename``).

    Returns
    -------
    pa.DataType
    """
    props = param_props if isinstance(param_props, dict) else {}

    # Integer-valued dimensional / count fields (check before collection arrays)
    if re.match(r"^(Dim\dSize|NumVolumes|NSliceTimes)$", param_name):
        return pa.int32()

    # Collection arrays: plural form of a numeric BIDS field
    # (EchoTimes, FlipAngles, InversionTimes, etc.)
    if param_name.endswith(("Times", "Angles")):
        return pa.list_(pa.float64())
    if param_name.endswith("States"):
        return pa.list_(pa.string())
    if param_name == "Parts":
        return pa.list_(pa.string())

    # Fields with tolerance / precision are floats
    if "tolerance" in props or "precision" in props:
        return pa.float64()

    # Everything else (Obliquity, ImageOrientation, …) → string
    return pa.string()


def build_metadata_type_map(bids_schema, grouping_config):
    """Build the metadata-field-name → Arrow-type mapping at runtime.

    Sidecar params are resolved from ``schema.json`` ``objects.metadata``.
    Derived params (CuBIDS-specific) are inferred from ``config.yml``
    properties and naming conventions.

    Parameters
    ----------
    bids_schema : dict
        The loaded BIDS schema (``cubids.config.load_schema``).
    grouping_config : dict
        The grouping configuration (``cubids.config.load_config``).

    Returns
    -------
    dict
        Mapping of field name → ``pa.DataType``.
    """
    schema_metadata = bids_schema.get("objects", {}).get("metadata", {})
    type_map = {}

    for section in ("sidecar_params", "derived_params"):
        for _modality, params in grouping_config.get(section, {}).items():
            for param_name, param_props in params.items():
                if param_name in type_map:
                    continue

                # 1) Look up in BIDS schema
                if param_name in schema_metadata:
                    arrow_type = _schema_def_to_arrow(
                        schema_metadata[param_name],
                        prefer_scalar=(section == "sidecar_params"),
                    )
                else:
                    # 2) CuBIDS-derived: infer from config hints + name
                    arrow_type = _infer_derived_type(param_name, param_props)

                type_map[param_name] = arrow_type

    # Always-included relational / special fields
    for name in _ALWAYS_INCLUDE:
        if name not in type_map:
            if name in schema_metadata:
                # IntendedFor and SliceTiming are always stored as lists
                type_map[name] = _schema_def_to_arrow(schema_metadata[name], prefer_scalar=False)
            else:
                type_map[name] = pa.string()

    return type_map


# ---------------------------------------------------------------------------
# Schema building
# ---------------------------------------------------------------------------


def build_entity_schema(bids_schema):
    """Build an Arrow schema for the file index from schema.json.

    Entity columns are derived dynamically from the BIDS schema so that
    new entities added in future BIDS versions are picked up automatically.

    Parameters
    ----------
    bids_schema : dict
        The loaded BIDS schema (from ``cubids.config.load_schema``).

    Returns
    -------
    pa.Schema
        Arrow schema with columns: path, <entities...>, suffix, ext, datatype.
    """
    fields = [pa.field("path", pa.string())]

    for entity_name in bids_schema["rules"]["entities"]:
        entity_def = bids_schema["objects"]["entities"][entity_name]
        short_name = entity_def["name"]
        # All entity values stored as strings (indices can have leading zeros)
        fields.append(pa.field(short_name, pa.string()))

    # Non-entity path components
    fields.append(pa.field("suffix", pa.string()))
    fields.append(pa.field("ext", pa.string()))
    fields.append(pa.field("datatype", pa.string()))

    return pa.schema(fields)


def build_full_schema(bids_schema, grouping_config):
    """Build an Arrow schema covering entities AND metadata columns.

    Parameters
    ----------
    bids_schema : dict
        The loaded BIDS schema.
    grouping_config : dict
        The grouping configuration (from ``cubids.config.load_config``).

    Returns
    -------
    pa.Schema
        Combined schema: entity columns + metadata columns.
    """
    entity_schema = build_entity_schema(bids_schema)
    type_map = build_metadata_type_map(bids_schema, grouping_config)
    meta_fields = [pa.field(name, dtype) for name, dtype in type_map.items()]

    all_fields = list(entity_schema) + meta_fields
    return pa.schema(all_fields)


# ---------------------------------------------------------------------------
# Entity parsing
# ---------------------------------------------------------------------------


@lru_cache(maxsize=65536)
def parse_entities(filepath):
    """Parse BIDS entities from a relative filepath.

    This is a fast, path-only parser (no JSON reads, no pybids dependency).

    Parameters
    ----------
    filepath : str
        Relative file path from the dataset root.

    Returns
    -------
    dict
        Mapping of entity short names (e.g. ``"sub"``, ``"ses"``) to values.
    """
    filename = os.path.basename(filepath)
    entities = {}

    # Datatype from directory structure
    m = _DATATYPE_RE.search(filepath)
    if m:
        entities["datatype"] = m.group(1)

    parts = filename.split("_")

    # Last part is suffix.ext
    suffix_ext = parts.pop()
    suffix, dot, ext = suffix_ext.partition(".")
    ext = dot + ext if ext else None

    # If suffix contains a dash, it's actually an entity, not a suffix
    if "-" in suffix:
        parts.append(suffix)
        suffix = None

    for part in parts:
        if "-" in part:
            key, val = part.split("-", maxsplit=1)
            entities[key] = val

    if suffix:
        entities["suffix"] = suffix
    if ext:
        entities["ext"] = ext

    return entities


# ---------------------------------------------------------------------------
# Dataset scanning
# ---------------------------------------------------------------------------


def scan_dataset(root, arrow_schema):
    """Scan a BIDS dataset with a single ``os.walk`` pass.

    Parameters
    ----------
    root : str
        Absolute path to the BIDS dataset root.
    arrow_schema : pa.Schema
        Arrow schema (from :func:`build_entity_schema` or :func:`build_full_schema`).

    Returns
    -------
    pa.Table
        Arrow table with one row per file found under ``sub-*`` directories.
    """
    entity_col_names = {f.name for f in arrow_schema} - {"path"}
    records = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune hidden and non-BIDS directories in-place
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _SKIP_DIRS]

        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            continue
        if not rel_dir.startswith("sub-"):
            continue

        for fname in filenames:
            if fname.startswith("."):
                continue
            rel = os.path.join(rel_dir, fname)
            entities = parse_entities(rel)

            record = {"path": rel}
            for col in entity_col_names:
                record[col] = entities.get(col)
            records.append(record)

    # Use only the entity columns present in the schema for initial table
    entity_only_schema = pa.schema(
        [f for f in arrow_schema if f.name in (entity_col_names | {"path"})]
    )
    return pa.Table.from_pylist(records, schema=entity_only_schema)


def enrich_with_metadata(root, table, metadata_type_map):
    """Batch-read JSON sidecars and add metadata columns to the Arrow table.

    Parameters
    ----------
    root : str
        Absolute path to the BIDS dataset root.
    table : pa.Table
        Arrow table with entity columns (from :func:`scan_dataset`).
    metadata_type_map : dict
        Mapping of field name -> ``pa.DataType`` (from
        :func:`build_metadata_type_map`).

    Returns
    -------
    pa.Table
        Arrow table with additional metadata columns.
    """
    meta_fields = set(metadata_type_map.keys())

    paths = table.column("path").to_pylist()
    n = len(paths)

    # Initialize column data
    meta_columns = {name: [None] * n for name in meta_fields}

    for i, rel_path in enumerate(paths):
        json_path = _nifti_to_json_path(root, rel_path)
        if json_path is None:
            continue
        if not os.path.exists(json_path):
            continue

        try:
            with open(json_path) as f:
                meta = json.load(f)
        except Exception:
            continue

        for field_name in meta_fields:
            val = meta.get(field_name)
            if val is not None:
                # Normalize IntendedFor to always be a list
                if field_name == "IntendedFor" and isinstance(val, str):
                    val = [val]
                meta_columns[field_name][i] = val

    # Build Arrow arrays for each metadata column
    for field_name, values in meta_columns.items():
        arrow_type = metadata_type_map.get(field_name, pa.string())
        try:
            arr = pa.array(values, type=arrow_type)
        except (pa.ArrowInvalid, pa.ArrowTypeError, pa.ArrowNotImplementedError):
            # Fall back to string representation for problematic values
            str_values = [str(v) if v is not None else None for v in values]
            arr = pa.array(str_values, type=pa.string())
        table = table.append_column(pa.field(field_name, arr.type), arr)

    return table


def _nifti_to_json_path(root, rel_path):
    """Convert a relative file path to its JSON sidecar path.

    Returns None if the file is not a NIfTI or the JSON doesn't exist.
    """
    if rel_path.endswith(".nii.gz"):
        json_rel = rel_path[: -len(".nii.gz")] + ".json"
    elif rel_path.endswith(".nii"):
        json_rel = rel_path[: -len(".nii")] + ".json"
    elif rel_path.endswith(".json"):
        # It's already a JSON file - read it directly for its own metadata
        return os.path.join(root, rel_path)
    else:
        return None
    return os.path.join(root, json_rel)


# ---------------------------------------------------------------------------
# Parquet cache
# ---------------------------------------------------------------------------


def _is_git_repo(path):
    """Return True if *path* is inside a git working tree."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except FileNotFoundError:
        return False


def _is_gitignored(filepath):
    """Return True if *filepath* would be ignored by git.

    Works for both existing and not-yet-existing paths by using
    ``git check-ignore``.
    """
    parent = os.path.dirname(filepath) or "."
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", filepath],
            cwd=parent,
            capture_output=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _ensure_cache_not_tracked(cache_path, root):
    """Verify the cache file is not tracked by git before using it.

    If the dataset is a git repo and the cache path is **not** gitignored,
    print a warning with concrete instructions and disable disk caching for
    this invocation (returns ``False``).  Otherwise returns ``True``.
    """
    if not _is_git_repo(root):
        return True

    if _is_gitignored(cache_path):
        return True

    # The cache file would be tracked -- warn the user.
    rel = os.path.relpath(cache_path, root)
    gitignore_path = os.path.join(root, ".gitignore")
    warnings.warn(
        f"\nCuBIDS Parquet index cache ({rel}) is NOT gitignored.\n"
        f"To enable disk caching (faster repeat runs), add the following\n"
        f"line to {gitignore_path}:\n\n"
        f"    {rel}\n\n"
        f"Or, to ignore all CuBIDS caches:\n\n"
        f"    code/CuBIDS/{CACHE_FILENAME}\n\n"
        f"Disk caching is disabled for this run to avoid committing\n"
        f"a large binary file to your repository.\n",
        stacklevel=3,
    )
    return False


def load_or_build_index(root, bids_schema, grouping_config, cache_dir=None, use_cache=True):
    """Load index from Parquet cache if fresh, otherwise rebuild.

    Prints status messages so the user knows whether the cache was used.

    Parameters
    ----------
    root : str
        Absolute path to the BIDS dataset root.
    bids_schema : dict
        The loaded BIDS schema.
    grouping_config : dict
        The grouping configuration.
    cache_dir : str, optional
        Directory for the cache file. Defaults to ``<root>/code/CuBIDS``.
    use_cache : bool, optional
        Whether to persist the index as a Parquet file on disk. Defaults to True.
        Set to False when using datalad to avoid creating untracked files
        inside the dataset that would cause ``datalad run`` to fail.

    Returns
    -------
    pa.Table
        The full dataset index (entities + metadata).
    """
    if cache_dir is None:
        cache_dir = os.path.join(root, "code", "CuBIDS")

    cache_path = os.path.join(cache_dir, CACHE_FILENAME)

    # Guard: never read or write the cache if git would track it.
    if use_cache and not _ensure_cache_not_tracked(cache_path, root):
        use_cache = False

    if use_cache and os.path.exists(cache_path):
        cache_mtime = os.path.getmtime(cache_path)
        stale = False
        for entry in os.scandir(root):
            if entry.name.startswith("sub-") and entry.is_dir():
                if entry.stat().st_mtime > cache_mtime:
                    stale = True
                    break
        if not stale:
            table = pq.read_table(cache_path)
            print(f"Loaded CuBIDS index from cache ({len(table)} files). " f"Cache: {cache_path}")
            return table
        else:
            print("CuBIDS index cache is stale (dataset has been modified). " "Rebuilding...")
    else:
        print("No CuBIDS index cache found. Building index...")

    t0 = time.time()
    arrow_schema = build_entity_schema(bids_schema)
    metadata_type_map = build_metadata_type_map(bids_schema, grouping_config)
    table = scan_dataset(root, arrow_schema)
    table = enrich_with_metadata(root, table, metadata_type_map)
    elapsed = time.time() - t0

    if use_cache:
        os.makedirs(cache_dir, exist_ok=True)
        pq.write_table(table, cache_path)
        print(
            f"Built CuBIDS index: {len(table)} files indexed in {elapsed:.1f}s. "
            f"Saved to {cache_path}"
        )
    else:
        print(
            f"Built CuBIDS index: {len(table)} files indexed in {elapsed:.1f}s. "
            f"(disk cache disabled)"
        )

    return table


def invalidate_cache(root, cache_dir=None):
    """Remove cached index after dataset mutations.

    Parameters
    ----------
    root : str
        Absolute path to the BIDS dataset root.
    cache_dir : str, optional
        Directory for the cache file.
    """
    if cache_dir is None:
        cache_dir = os.path.join(root, "code", "CuBIDS")
    cache_path = os.path.join(cache_dir, CACHE_FILENAME)
    if os.path.exists(cache_path):
        os.unlink(cache_path)
        print("CuBIDS index cache invalidated (dataset was modified).")


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def get_nifti_paths(table):
    """Return relative paths of all NIfTI files in the index.

    Parameters
    ----------
    table : pa.Table
        The dataset index.

    Returns
    -------
    list of str
        Relative paths to NIfTI files.
    """
    ext = table.column("ext")
    mask = pc.or_(pc.equal(ext, ".nii"), pc.equal(ext, ".nii.gz"))
    return table.filter(mask).column("path").to_pylist()


def get_json_paths(table):
    """Return relative paths of all JSON files in the index.

    Parameters
    ----------
    table : pa.Table
        The dataset index.

    Returns
    -------
    list of str
        Relative paths to JSON files.
    """
    ext = table.column("ext")
    mask = pc.equal(ext, ".json")
    return table.filter(mask).column("path").to_pylist()


def has_sessions(table):
    """Check if the dataset is longitudinal (has session entities).

    Parameters
    ----------
    table : pa.Table
        The dataset index.

    Returns
    -------
    bool
        True if any file has a non-null ``ses`` entity.
    """
    if "ses" not in table.column_names:
        return False
    ses_col = table.column("ses")
    return ses_col.null_count < len(ses_col)


def compute_entity_sets(table, non_key_entities, entity_column_names=None):
    """Group NIfTI files by their entity set.

    An *entity set* is a string representation of all BIDS entities
    (excluding subject, session, and extension) shared by a group of files.

    Parameters
    ----------
    table : pa.Table
        The dataset index.
    non_key_entities : set
        Entity short names to exclude from entity set keys
        (e.g., ``{"sub", "ses", "ext"}``).
    entity_column_names : set, optional
        The set of column names that are entity columns (from
        :func:`build_entity_schema`).  When provided, all other columns
        are treated as metadata.  When *None*, a heuristic is used.

    Returns
    -------
    dict
        Mapping of entity set string -> list of relative file paths.
    """
    ext_col = table.column("ext")
    nifti_mask = pc.or_(pc.equal(ext_col, ".nii"), pc.equal(ext_col, ".nii.gz"))
    niftis = table.filter(nifti_mask)

    # Determine which columns form the entity set key.
    # Entity columns are: path, <entities...>, suffix, ext, datatype.
    # Everything else is a metadata column.
    skip = non_key_entities | {"path", "ext"}
    entity_cols = []
    for name in niftis.column_names:
        if name in skip:
            continue
        if entity_column_names is not None:
            if name not in entity_column_names:
                continue
        entity_cols.append(name)

    paths = niftis.column("path").to_pylist()
    result = defaultdict(list)

    for i in range(len(niftis)):
        parts = []
        for col in entity_cols:
            val = niftis.column(col)[i].as_py()
            if val is not None:
                parts.append(f"{col}-{val}")
        entity_set = "_".join(parts) if parts else ""
        result[entity_set].append(paths[i])

    return dict(result)


def get_fieldmap_intended_for(table):
    """Build an IntendedFor index from fieldmap and perf m0scan rows.

    Parameters
    ----------
    table : pa.Table
        The dataset index with metadata columns.

    Returns
    -------
    dict
        Mapping: IntendedFor entry (str) -> list of JSON file paths.
    """
    index = defaultdict(set)

    if "IntendedFor" not in table.column_names or "datatype" not in table.column_names:
        return {}

    datatype_col = table.column("datatype")
    suffix_col = table.column("suffix") if "suffix" in table.column_names else None
    ext_col = table.column("ext")
    path_col = table.column("path")
    if_col = table.column("IntendedFor")

    for i in range(len(table)):
        dt = datatype_col[i].as_py()
        ext = ext_col[i].as_py()
        suf = suffix_col[i].as_py() if suffix_col is not None else None

        is_fmap_json = dt == "fmap" and ext == ".json"
        is_m0_json = dt == "perf" and suf == "m0scan" and ext == ".json"

        if not (is_fmap_json or is_m0_json):
            continue

        if_val = if_col[i].as_py()
        if if_val is None:
            continue
        if isinstance(if_val, str):
            if_val = [if_val]

        json_path = path_col[i].as_py()
        for item in if_val:
            index[str(item)].add(json_path)

    return {k: sorted(v) for k, v in index.items()}
