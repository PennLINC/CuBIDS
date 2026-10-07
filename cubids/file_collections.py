"""BIDS file collections and their variant consistency.

A *file collection* is a set of files from a single acquisition that only make
sense together, such as the magnitude and phase images of a gradient-echo field
map, or the two phase-encoding directions of a PEPOLAR pair. This module holds
everything CuBIDS knows about them:

- :class:`CollectionRule` and :func:`get_collection_rules` derive, from the BIDS
  schema, which files can form one collection and along which entities their
  members are allowed to differ.
- :func:`collection_context` and :func:`collect_file_collections` group the files
  of a dataset into collections and gather their shared metadata.

The variant-consistency analysis that inspects those collections and proposes
aligned names lives alongside these rules; see the analysis functions later in
this module.
"""

from collections import defaultdict
from dataclasses import dataclass

import pandas as pd
from bids.layout import parse_file_entities

from cubids import utils

__all__ = [
    "CollectionRule",
    "get_collection_rules",
    "get_collection_rule",
    "collect_file_collections",
    "collection_context",
    "analyze_collection_variant_consistency",
    "apply_collection_variant_proposals",
    "validate_collection_deletions",
    "validate_collection_renames",
]

FILE_COLLECTION_REPORT_COLUMNS = [
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


def _split_variant(acquisition):
    """Split an acquisition label into the part before its variant and the variant.

    Both are empty strings when the label holds no variant.
    """
    base, marker, variant = str(acquisition or "").partition("VARIANT")
    if not marker:
        return "", ""

    return base, marker + variant


def entity_context_key(entities, ignored):
    """Build a hashable key that identifies everything about a file except ``ignored``.

    Two files share a key when every entity outside ``ignored`` agrees, which is
    how file collection members are matched to one another.

    Parameters
    ----------
    entities : dict
        A pybids entities dictionary.
    ignored : set of str
        Entity names to leave out of the key, typically the axes along which
        members of a collection are expected to differ.

    Returns
    -------
    :obj:`tuple`
        Sorted ``(name, value)`` pairs for the retained entities.

    Examples
    --------
    >>> entity_context_key({"subject": "01", "direction": "AP", "suffix": "epi"}, {"direction"})
    (('subject', '01'), ('suffix', 'epi'))
    """
    return tuple(
        sorted(
            (key, str(value))
            for key, value in entities.items()
            if key not in ignored and value is not None
        )
    )


@dataclass(frozen=True)
class CollectionRule:
    """One way that several files can make up a single BIDS file collection.

    Attributes
    ----------
    case : :obj:`str`
        Name for this kind of collection, used when reporting one.
    datatypes : :obj:`frozenset` of :obj:`str`
        Datatypes the rule covers. Empty when it covers every datatype.
    suffixes : :obj:`frozenset` of :obj:`str`
        Suffixes that can take part in the collection. Empty when any can.
    axes : :obj:`frozenset` of :obj:`str`
        Entities whose values distinguish the collection's members from one
        another. ``suffix`` is an axis when the members differ by suffix, and
        ``acquisition`` when they differ by acquisition label.
    """

    case: str
    datatypes: frozenset
    suffixes: frozenset
    axes: frozenset

    @property
    def is_generic(self):
        """Whether this is the fallback rule rather than one for specific files."""
        return not self.datatypes


# Entities whose values distinguish the members of an entity-linked file collection,
# mapped to the metadata field each mirrors, or None when it has no counterpart.
# These are the names pybids parses filenames into, not the BIDS schema's names.
ENTITY_LINKED_AXES = {
    "echo": "EchoTime",
    "part": None,
    "mt": "MTState",
    "inv": "InversionTime",
    "flip": "FlipAngle",
}

# The BIDS schema's names for the entities that can span a collection, mapped to the
# names pybids parses them into.
_SCHEMA_COLLECTION_AXES = {
    "direction": "direction",
    "echo": "echo",
    "flip": "flip",
    "inversion": "inv",
    "mtransfer": "mt",
    "part": "part",
}

# The schema's name for a rule group that reads better in a report. M0 scans make up
# the same kind of collection as EPI images, so they are reported the same way.
_COLLECTION_CASE_NAMES = {"pepolar_m0scan": "pepolar"}

# Prefixes that identify the role of each member of an acquisition-linked RF field
# map. Any text after the prefix identifies the use case, so acq-anatTest pairs with
# acq-fampTest rather than acq-fampRetest. The schema marks acquisition optional for
# these suffixes, so the roles come from the spec's RF field mapping section.
ACQUISITION_LINKED_PREFIXES = {
    "TB1AFI": ("tr1", "tr2"),
    "TB1TFL": ("anat", "famp"),
    "TB1RFM": ("anat", "famp"),
    "RB1COR": ("body", "head"),
}
ACQUISITION_LINKED_SUFFIXES = frozenset(ACQUISITION_LINKED_PREFIXES)

# The suffix that identifies each type of gradient-echo B0 fieldmap collection, and
# the suffixes such a collection cannot do without. The schema puts all of them in a
# single rule group, so this comes from the spec's "Types of B0 fieldmaps".
GRE_FIELDMAP_CASES = (
    (
        "phase-difference",
        frozenset({"phasediff"}),
        frozenset({"phasediff", "magnitude1"}),
    ),
    (
        "two-phase",
        frozenset({"phase1", "phase2"}),
        frozenset({"phase1", "phase2", "magnitude1", "magnitude2"}),
    ),
    (
        "direct-fieldmap",
        frozenset({"fieldmap"}),
        frozenset({"fieldmap", "magnitude"}),
    ),
)

# Applies to any file whose suffix takes part in no collection of its own.
GENERIC_COLLECTION_RULE = CollectionRule(
    case="entity-linked",
    datatypes=frozenset(),
    suffixes=frozenset(),
    axes=frozenset(ENTITY_LINKED_AXES),
)


def get_collection_rules(schema):
    """Build the file collection rules that apply to a dataset from the BIDS schema.

    A rule says which files make up one collection: the suffixes that can take part
    and the entities their values are allowed to differ along. Every file that no
    rule names falls back to :data:`GENERIC_COLLECTION_RULE`.

    Parameters
    ----------
    schema : :obj:`dict`
        The BIDS schema. This function reads ``schema["rules"]["files"]["raw"]``,
        whose groups list the suffixes of each file type and the requirement level
        of each of their entities.

    Returns
    -------
    :obj:`dict`
        Maps ``(datatype, suffix)`` to the :class:`CollectionRule` that covers it.

    Notes
    -----
    An entity that a rule group requires spans a collection only if it is one of
    :data:`_SCHEMA_COLLECTION_AXES`. Other required entities, like the task of a
    ``func`` image, distinguish separate acquisitions rather than members of one.

    Examples
    --------
    >>> import importlib
    >>> import json
    >>> from pathlib import Path
    >>> schema_file = Path(importlib.resources.files("cubids") / "data/schema.json")
    >>> with schema_file.open() as f:
    ...     rules = get_collection_rules(json.load(f))

    The phase-encoding direction spans a PEPOLAR collection, for EPI images and for
    the M0 scans that arterial spin labeling data use instead.

    >>> sorted(rules[("fmap", "epi")].axes & {"direction", "suffix"})
    ['direction']
    >>> rules[("fmap", "m0scan")].case
    'pepolar'

    Gradient-echo B0 fieldmaps are spanned by their suffixes instead.

    >>> sorted(rules[("fmap", "phasediff")].axes & {"direction", "suffix"})
    ['suffix']

    A parametric map is a standalone image, so no rule names it.

    >>> ("fmap", "TB1map") in rules
    False
    """
    rules = {}

    def add_rule(rule):
        for datatype in rule.datatypes:
            for suffix in rule.suffixes:
                rules[(datatype, suffix)] = rule

    for datatype, groups in schema["rules"]["files"]["raw"].items():
        for group_name, group in groups.items():
            axes = set()
            for entity, requirement in group.get("entities", {}).items():
                if isinstance(requirement, dict):
                    requirement = requirement.get("level")

                if requirement == "required" and entity in _SCHEMA_COLLECTION_AXES:
                    axes.add(_SCHEMA_COLLECTION_AXES[entity])

            if not axes:
                continue

            add_rule(
                CollectionRule(
                    case=_COLLECTION_CASE_NAMES.get(group_name, group_name),
                    datatypes=frozenset(group.get("datatypes", [datatype])),
                    suffixes=frozenset(group["suffixes"]),
                    axes=frozenset(axes | set(ENTITY_LINKED_AXES)),
                )
            )

    fmap_rules = schema["rules"]["files"]["raw"]["fmap"]
    add_rule(
        CollectionRule(
            case="b0-gradient-echo",
            datatypes=frozenset({"fmap"}),
            suffixes=frozenset(fmap_rules["fieldmaps"]["suffixes"]),
            axes=frozenset({"suffix"} | set(ENTITY_LINKED_AXES)),
        )
    )
    add_rule(
        CollectionRule(
            case="rf-field-map",
            datatypes=frozenset({"fmap"}),
            suffixes=ACQUISITION_LINKED_SUFFIXES,
            axes=frozenset({"acquisition"} | set(ENTITY_LINKED_AXES)),
        )
    )

    return rules


def get_collection_rule(rules, entities):
    """Return the rule for the collection a file can belong to.

    Parameters
    ----------
    rules : :obj:`dict`
        Rules from :func:`get_collection_rules`.
    entities : :obj:`dict`
        A pybids entities dictionary.

    Returns
    -------
    :class:`CollectionRule`
        The matching rule, or :data:`GENERIC_COLLECTION_RULE` when the file's
        suffix takes part in no collection of its own.
    """
    return rules.get(
        (entities.get("datatype"), entities.get("suffix")),
        GENERIC_COLLECTION_RULE,
    )


def resolve_gre_fieldmap_case(suffixes):
    """Name the kind of gradient-echo B0 fieldmap a set of suffixes makes up.

    Parameters
    ----------
    suffixes : :obj:`set` of :obj:`str`
        The suffixes of the files found in one collection.

    Returns
    -------
    case : :obj:`str`
        The name of the matching case, or ``"orphan-magnitude"`` when the
        suffixes identify none of them.
    missing : :obj:`list` of :obj:`str`
        Suffixes the case needs that the collection does not have.

    Examples
    --------
    >>> resolve_gre_fieldmap_case({"phasediff", "magnitude1"})
    ('phase-difference', [])

    >>> resolve_gre_fieldmap_case({"fieldmap"})
    ('direct-fieldmap', ['magnitude'])

    A magnitude image is only ever acquired alongside one of the maps above, so on
    its own it is the remains of a collection rather than a collection of its own.

    >>> resolve_gre_fieldmap_case({"magnitude1", "magnitude2"})
    ('orphan-magnitude', [])
    """
    for case, identifiers, required in GRE_FIELDMAP_CASES:
        if identifiers & set(suffixes):
            return case, sorted(required - set(suffixes))

    return "orphan-magnitude", []


def collection_context(entities, rule):
    """Build a key shared by exactly the files in one collection.

    Parameters
    ----------
    entities : :obj:`dict`
        A pybids entities dictionary.
    rule : :class:`CollectionRule`
        The rule the file matched.

    Returns
    -------
    :obj:`tuple`
        Sorted ``(name, value)`` pairs for every entity that members of the
        collection must agree on.

    Examples
    --------
    >>> rule = GENERIC_COLLECTION_RULE
    >>> collection_context(
    ...     {"subject": "01", "echo": "1", "suffix": "bold", "extension": ".nii.gz"}, rule
    ... )
    (('subject', '01'), ('suffix', 'bold'))
    """
    # pybids parses an extra fmap entity that mirrors the suffix of a fieldmap, and
    # a collection's members can be a mix of compressed and uncompressed images.
    context = entity_context_key(entities, rule.axes | {"extension", "fmap"})

    if "acquisition" not in rule.axes:
        return context

    # Acquisition-linked RF field maps use the start of acq- to identify a
    # member's role and the remainder to distinguish separate collections. For
    # example, anatTest/fampTest is one collection and anatRetest/fampRetest is
    # another. An unrecognized label is kept whole because its role cannot be
    # inferred safely; matching labels remain grouped along any other axes.
    acquisition = entities.get("acquisition")
    collection_label = acquisition
    if utils.is_nonempty(acquisition):
        acquisition = str(acquisition)
        for prefix in ACQUISITION_LINKED_PREFIXES.get(entities.get("suffix"), ()):
            if acquisition.startswith(prefix):
                collection_label = acquisition[len(prefix) :]
                break

    return tuple(sorted(context + (("acquisition_collection", collection_label),)))


def collect_file_collections(layout, base_file, rules):
    """Build a list of files in a file collection for a given base file.

    Parameters
    ----------
    layout : BIDSLayout
        The BIDSLayout object.
    base_file : str
        The base file to collect file collections for.
    rules : :obj:`dict`
        Rules from :func:`get_collection_rules`, which decide what the file's
        collection is spanned by: entity values, suffixes, or acquisition labels.

    Returns
    -------
    files : list of BIDSFile
        A list of files in the file collection for the given base file.
    out_metadata : dict
        A dictionary of metadata for the file collection, to be added to each file's metadata.

    Notes
    -----
    This uses metadata from direct sidecar JSON files, so it will not work with
    inherited metadata.
    """
    from bids.layout import Query

    base_file = layout.get_file(base_file)
    entities = base_file.get_entities()
    rule = get_collection_rule(rules, entities)

    # Members agree on every entity outside the collection's axes, and take any
    # value, including none at all, along them.
    query = {
        key: value for key, value in entities.items() if key not in rule.axes and key != "fmap"
    }
    query.update({axis: [Query.ANY, Query.NONE] for axis in rule.axes if axis != "suffix"})
    if "suffix" in rule.axes:
        query["suffix"] = sorted(rule.suffixes)

    context = collection_context(entities, rule)
    files = []
    for file in layout.get(**query):
        file_entities = file.get_entities()
        file_rule = get_collection_rule(rules, file_entities)
        if collection_context(file_entities, file_rule) == context:
            files.append(file)

    if len(files) <= 1:
        return files, {}

    # Get list of entities present in any of the files
    collected_entities = [list(f.get_entities().keys()) for f in files]
    # Flatten the list
    collected_entities = [item for sublist in collected_entities for item in sublist]
    # Remove duplicates
    collected_entities = sorted(set(collected_entities))

    out_metadata = {}
    # Add metadata field with BIDS URIs to all files in file collection
    out_metadata["FileCollection"] = [utils._get_bidsuri(f.path, layout.root) for f in files]

    files_metadata = [
        utils.get_sidecar_metadata(utils.img_to_new_ext(f.path, ".json")) for f in files
    ]
    assert all(bool(meta) for meta in files_metadata), files
    for ent, field in ENTITY_LINKED_AXES.items():
        if ent in collected_entities:
            if field is None:
                # If the entity is not mirrored in the metadata, like part,
                # just use the entity value from the files.
                collected_ent = ent.title() + "s"
                ent_values = [f.get_entities()[ent] for f in files]
                out_metadata[collected_ent] = ent_values

            else:
                # If the entity is mirrored in the metadata, like echo,
                # collect the values from the metadata.
                collected_field = field + "s"
                field_values = [meta[field] for meta in files_metadata]
                out_metadata[collected_field] = field_values

    return files, out_metadata


class _CollectionAnalyzer:
    """Group a dataset's files into collections and judge each one's variant consistency.

    Splitting :func:`analyze_collection_variant_consistency` across methods keeps the
    per-case logic — gradient-echo, PEPOLAR, and the generic entity-linked case —
    readable, and lets the shared ``records`` and ``proposals`` be instance state
    rather than variables captured across a stack of nested closures.
    """

    def __init__(self, collection_rules, files_df, summary, rename_cols):
        self.collection_rules = collection_rules
        self.files_df = files_df
        self.summary = summary
        self.rename_cols = list(rename_cols)
        self.records = []
        self.proposals = defaultdict(set)

    def run(self):
        """Assess every collection and return the ``(report, proposals)`` pair."""
        for (rule, _), members in self._group_members().items():
            if rule.is_generic and len(members) == 1:
                # A standalone image, such as a TB1map, belongs to no collection and
                # so has no sibling whose label it has to match.
                continue

            if rule.case == "b0-gradient-echo":
                self._assess_gradient_echo_collection(members, rule)
            elif rule.case == "pepolar":
                self._assess_pepolar_collection(members, rule)
            elif len(members) == 1:
                self._add_record(
                    rule.case,
                    members,
                    "PASS",
                    "Only one file in the collection; no other member to match.",
                )
            else:
                self._assess_complete_collection(rule.case, members, rule)

        report = pd.DataFrame(self.records, columns=FILE_COLLECTION_REPORT_COLUMNS)
        return report, self.proposals

    def _group_members(self):
        """Bucket every file that belongs to a collection by ``(rule, context)``.

        The pairing key is constructed from each individual NIfTI path. This is
        intentionally stricter than summary-level matching: subject, session, run,
        chunk, and every other filename entity outside the collection's own axes
        must already agree before two files are treated as one collection.
        """
        by_key = self.summary.set_index("KeyParamGroup", drop=False)
        collections = defaultdict(list)
        for _, file_row in self.files_df.iterrows():
            filepath = str(file_row["FilePath"])
            if file_row["KeyParamGroup"] not in by_key.index:
                continue

            entities = parse_file_entities(filepath)
            rule = get_collection_rule(self.collection_rules, entities)
            summary_row = by_key.loc[file_row["KeyParamGroup"]]
            target_entities = utils._entity_set_to_entities(
                utils.get_planned_entity_set(summary_row)
            )
            collections[(rule, collection_context(entities, rule))].append(
                {
                    "filepath": filepath,
                    "key_param_group": file_row["KeyParamGroup"],
                    "source_entities": entities,
                    "target_entities": target_entities,
                    "summary_row": summary_row,
                    "phase_encoding_direction": file_row.get("PhaseEncodingDirection"),
                }
            )
        return collections

    def _add_record(self, case, members, status, message, proposed_acquisition="", proposed=None):
        """Append one collection's outcome to the report rows."""
        paths = sorted(member["filepath"] for member in members)
        collection_id = f"{case}:{'|'.join(paths)}"
        acquisitions = sorted(
            {str(member["target_entities"].get("acquisition", "")) for member in members}
        )
        proposed = proposed or {}
        self.records.append(
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

    def _planned_context(self, member, rule, ignore_acquisition=False):
        """Identify what a member's planned name must share with its siblings."""
        entities = dict(member["target_entities"])
        ignored = rule.axes | {"fmap", "extension"}
        if ignore_acquisition:
            ignored = ignored | {"acquisition"}
        elif "acquisition" in rule.axes:
            # The acquisition label is what tells these members apart, so only
            # the variant part of it has to agree.
            ignored = ignored - {"acquisition"}
            entities["acquisition"] = _split_variant(entities.get("acquisition"))[1]

        return entity_context_key(entities, ignored)

    def _assess_complete_collection(self, case, members, rule):
        """Judge a collection whose members are all present, proposing a shared variant."""
        if len({self._planned_context(member, rule) for member in members}) == 1:
            self._add_record(
                case,
                members,
                "PASS",
                "All collection members have compatible planned entities.",
            )
            return

        non_acq_contexts = {
            self._planned_context(member, rule, ignore_acquisition=True) for member in members
        }
        variant_bases = []
        for member in members:
            base, variant = _split_variant(member["target_entities"].get("acquisition"))
            if not variant:
                # A member whose planned name holds no variant leaves the others
                # nothing to line up with.
                variant_bases = []
                break

            variant_bases.append(base)

        # Members that their acquisition labels tell apart keep their own bases.
        # Anywhere else the bases must already agree for one shared label to fit.
        bases_fit = "acquisition" in rule.axes or len(set(variant_bases)) == 1

        varying_columns = set()
        for member in members:
            varying_columns.update(
                column
                for column, _, _, _ in utils.get_variant_components(
                    self.summary, member["summary_row"], self.rename_cols
                )
            )
        # Preserve rename_cols order so the shared label is deterministic.
        component_names = [col for col in self.rename_cols if col in varying_columns]

        if len(non_acq_contexts) == 1 and variant_bases and bases_fit and component_names:
            variant = "VARIANT" + "".join(component_names)
            proposed = {}
            for member, base in zip(members, variant_bases):
                entities = dict(member["target_entities"])
                entities["acquisition"] = base + variant
                entity_set = utils._entities_to_entity_set(entities)
                proposed[member["key_param_group"]] = entity_set
                self.proposals[member["key_param_group"]].add(entity_set)
            self._add_record(
                case,
                members,
                "PROPOSED",
                "Variant labels differ; a shared file-collection variant was proposed.",
                "|".join(sorted({base + variant for base in variant_bases})),
                proposed,
            )
            return

        self._add_record(
            case,
            members,
            "MANUAL_REVIEW",
            "Collection members have incompatible planned entities; "
            "no safe shared variant was proposed.",
        )

    def _assess_gradient_echo_collection(self, members, rule):
        """Judge a gradient-echo B0 fieldmap, keyed by which suffixes are present."""
        suffixes = {member["source_entities"]["suffix"] for member in members}
        case, missing = resolve_gre_fieldmap_case(suffixes)
        if case == "orphan-magnitude":
            # Magnitude images only exist as part of one of the cases above,
            # so on their own they are the remains of a broken collection.
            self._add_record(
                case,
                members,
                "MANUAL_REVIEW",
                "Magnitude images without a phasediff, phase, or fieldmap image.",
            )
        elif missing:
            self._add_record(
                case,
                members,
                "MANUAL_REVIEW",
                f"Incomplete collection; missing {', '.join(missing)}.",
            )
        else:
            self._assess_complete_collection(case, members, rule)

    def _assess_pepolar_collection(self, members, rule):
        """Judge a PEPOLAR pair, checking the two directions truly oppose."""
        peds_by_direction = defaultdict(set)
        for member in members:
            peds_by_direction[member["source_entities"].get("direction")].add(
                member["phase_encoding_direction"]
            )

        if len(peds_by_direction) == 1:
            # A fieldmap acquired in one phase-encoding direction is valid BIDS,
            # and there is no partner whose label it has to match, so it is
            # renamed like any other image.
            self._add_record(
                f"single-direction {members[0]['source_entities']['suffix']}",
                members,
                "PASS",
                "Only one phase-encoding direction; no paired file to match.",
            )
            return

        # The report verifies the metadata rather than inferring polarity from
        # labels such as dir-AP and dir-PA. Several files can share a direction,
        # as the parts of a complex-valued image do, as long as they agree on it.
        peds = [
            str(next(iter(values)))
            for values in peds_by_direction.values()
            if len(values) == 1 and utils.is_nonempty(next(iter(values)))
        ]
        opposed = (
            len(peds_by_direction) == 2
            and len(peds) == 2
            and peds[0].rstrip("-") == peds[1].rstrip("-")
            and peds[0].endswith("-") != peds[1].endswith("-")
        )
        if not opposed:
            self._add_record(
                rule.case,
                members,
                "MANUAL_REVIEW",
                "Expected exactly two dirs with opposite PhaseEncodingDirection values.",
            )
        else:
            self._assess_complete_collection(rule.case, members, rule)


def analyze_collection_variant_consistency(collection_rules, files_df, summary, rename_cols=()):
    """Inspect file collections and propose aligned variants.

    The pairing key is constructed from each individual NIfTI path. This is
    intentionally stricter than summary-level matching: subject, session, run,
    chunk, and every other filename entity outside the collection's own axes
    must already agree before two files can be treated as one file collection.

    Which files belong to one collection comes from the BIDS schema, by way of
    ``collection_rules``. This covers entity-linked collections in every datatype,
    such as multi-echo, multi-flip, multi-inversion, and multi-part acquisitions,
    as well as B0 and RF field-map collections. A file that belongs to no
    collection is left out of the report entirely.

    Parameters
    ----------
    collection_rules : :obj:`dict`
        Rules from :func:`get_collection_rules`.
    files_df : :obj:`pandas.DataFrame`
        A CuBIDS files table.
    summary : :obj:`pandas.DataFrame`
        The matching parameter group summary.
    rename_cols : :obj:`list` of :obj:`str`
        Summary columns that variant labels are built from. Without them no
        shared label can be composed, so mismatched collections are reported
        as ``MANUAL_REVIEW`` instead of ``PROPOSED``. Callers that only gate
        on ``PASS``, such as :func:`validate_collection_renames`, can omit it.

    Returns
    -------
    report : :obj:`pandas.DataFrame`
        One row per file collection, with a ``Status`` of ``PASS``,
        ``PROPOSED``, or ``MANUAL_REVIEW``.
    proposals : :obj:`dict`
        Maps ``KeyParamGroup`` to the set of entity sets proposed for it.
        A group with more than one proposal is ambiguous and is not applied.
    """
    return _CollectionAnalyzer(collection_rules, files_df, summary, rename_cols).run()


def apply_collection_variant_proposals(summary, proposals):
    """Write globally unambiguous file-collection rename suggestions into a summary.

    A parameter group that drew more than one proposal is skipped, since its
    collections disagree about which shared label to use.

    Parameters
    ----------
    summary : :obj:`pandas.DataFrame`
        The summary to annotate, modified in place.
    proposals : :obj:`dict`
        Proposals from :func:`analyze_collection_variant_consistency`.

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
                part for part in [note, "Review proposed shared file-collection variant."] if part
            )
        )
    return summary


def validate_collection_deletions(collection_rules, files_df, summary, deletion_keys, report=None):
    """Fail before mutation when deletions would split a file collection.

    A file collection is only usable whole, so deleting some of its members
    leaves an incomplete acquisition. This guards every deletion, whether it
    came from a hand-edited ``MergeInto`` of 0 or from ``--remove-RenameEntitySet``.

    Parameters
    ----------
    collection_rules : :obj:`dict`
        Rules from :func:`get_collection_rules`.
    files_df : :obj:`pandas.DataFrame`
        A CuBIDS files table.
    summary : :obj:`pandas.DataFrame`
        The matching parameter group summary.
    deletion_keys : :obj:`set` of :obj:`str`
        ``KeyParamGroup`` values whose files apply is about to delete.
    report : :obj:`pandas.DataFrame` or None
        A report from :func:`analyze_collection_variant_consistency` for these same
        tables, to save recomputing it. Computed here when not supplied.

    Raises
    ------
    ValueError
        If any file collection would lose some, but not all, members.
    """
    if not deletion_keys:
        return

    if report is None:
        report, _ = analyze_collection_variant_consistency(collection_rules, files_df, summary)
    planned_entity_sets = {
        row["KeyParamGroup"]: utils.get_planned_entity_set(row) for _, row in summary.iterrows()
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
            "Deleting part of a file collection leaves it unusable; "
            f"{len(partial_collections)} would lose some, but not all, members, starting "
            f"with {partial_collections[0]}. Delete every member of each collection, or "
            "use cubids purge for individual files. Also missing: "
            + ", ".join(sorted(surviving_entity_sets))
        )


def validate_collection_renames(
    collection_rules,
    path,
    files_df,
    summary,
    entity_sets,
    pending_deletions=(),
    allow_fmap_renames=False,
    report=None,
):
    """Ensure every file collection being renamed has compatible planned entities.

    Only ``PASS`` collections are accepted, so the analysis runs without
    ``rename_cols``: whether a mismatch would have been labelled ``PROPOSED``
    or ``MANUAL_REVIEW`` does not change the outcome.

    Only files that belong to a collection are checked. A standalone image has
    no sibling whose label it needs to agree with, so it is renamed normally.

    Parameters
    ----------
    collection_rules : :obj:`dict`
        Rules from :func:`get_collection_rules`.
    path : :obj:`str`
        The dataset root, prefixed to each files-table ``FilePath`` so pending
        deletions can be matched by absolute path.
    files_df : :obj:`pandas.DataFrame`
        A CuBIDS files table.
    summary : :obj:`pandas.DataFrame`
        The matching parameter group summary.
    entity_sets : :obj:`dict`
        Maps ``KeyParamGroup`` to the entity set its files should take.
    pending_deletions : :obj:`set` of :obj:`str`
        Files an earlier apply step removes. These are never renamed, so their
        groups do not need to pass.
    allow_fmap_renames : :obj:`bool`
        Whether files under ``fmap/`` are part of the rename plan. They are
        excluded from this check when fieldmap renaming is disabled.
    report : :obj:`pandas.DataFrame` or None
        A report from :func:`analyze_collection_variant_consistency` for these same
        tables, to save recomputing it. Computed here when not supplied.

    Raises
    ------
    ValueError
        If any file being renamed belongs to an incomplete or mismatched
        collection.
    """
    pending_deletions = set(pending_deletions)
    rename_keys = set()
    fmap_keys = set()
    collection_keys = set()
    for _, row in files_df.iterrows():
        filepath = str(row["FilePath"])
        if (
            row["KeyParamGroup"] not in entity_sets
            or path + filepath in pending_deletions
            or ("/fmap/" in filepath and not allow_fmap_renames)
        ):
            continue

        rename_keys.add(row["KeyParamGroup"])
        if "/fmap/" in filepath:
            fmap_keys.add(row["KeyParamGroup"])
        rule = get_collection_rule(collection_rules, parse_file_entities(filepath))
        if not rule.is_generic:
            collection_keys.add(row["KeyParamGroup"])

    if not rename_keys:
        return

    if report is None:
        report, _ = analyze_collection_variant_consistency(collection_rules, files_df, summary)
    reported_keys = set()
    invalid_records = []
    for _, record in report.iterrows():
        keys = set(filter(None, str(record["KeyParamGroups"]).split("|")))
        reported_keys.update(keys)
        if keys & rename_keys and record["Status"] != "PASS":
            invalid_records.append(record["CollectionID"])

    # Every file a specific collection rule applies to reaches a record, so a
    # gap here means the tables disagree rather than that the file is standalone.
    unclassified = collection_keys - reported_keys
    if invalid_records or unclassified:
        details = invalid_records + [f"unclassified key {key}" for key in sorted(unclassified)]
        raise ValueError(
            "Renaming requires matching, complete file collections: " + "; ".join(details)
        )

    if fmap_keys:
        print(
            "WARNING: --fmap renames fieldmaps. Matching labels do not prove AP/PA "
            "geometry is TOPUP-compatible; review the file-collection report."
        )
