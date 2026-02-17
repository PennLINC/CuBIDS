# BIDS Skeleton Test Scenarios

This directory contains BIDS skeleton YAML files used to generate synthetic test datasets.
The datasets are intentionally lightweight on file content (empty NIfTI placeholders) but
richer in structure and metadata, following SimBIDS-style configuration patterns.

## Scenario Index

| Skeleton file | Primary scenario | Key characteristics | Used by tests |
|---|---|---|---|
| `skeleton_apply_longitudinal_realistic.yml` | Longitudinal `IntendedFor` update paths in `apply` | Multiple subjects, multiple sessions, mixed subject/session labels, extra modalities (`anat`, `dwi`, `fmap`, `func`), fieldmaps with relative `IntendedFor` targets | `cubids/tests/test_apply.py` |
| `skeleton_apply_cross_sectional_realistic.yml` | Cross-sectional `IntendedFor` update paths in `apply` | Multiple subjects, no sessions, mixed labels, additional files/metadata beyond the renamed subset, fieldmaps targeting DWI | `cubids/tests/test_apply.py` |
| `skeleton_file_collection_01.yml` | Baseline file-collection sidecar enrichment | Two subjects, multi-echo and single-echo `func` acquisitions, deterministic metadata for strict equality assertions | `cubids/tests/test_file_collections.py` |
| `skeleton_file_collection_02.yml` | Expanded file-collection coverage under larger topology | Includes baseline patterns plus added subject/session (`sub-ABC/ses-pre`) and higher-echo collection to stress aggregation while preserving baseline assertion targets | `cubids/tests/test_file_collections.py` |
| `skeleton_perf_m0.yml` | ASL/M0 rename edge case in perf data | Sessioned perf files with `asl` + `m0scan` and `IntendedFor` linkage; validates that ASL/aslcontext rename while M0 filenames stay stable | `cubids/tests/test_perf_m0.py` |
| `skeleton_cli_commands.yml` | CLI command dataset for non-NIfTI-dependent flows | Multi-subject/session `anat` + `dwi` with metadata fields (including `Manufacturer`) for validate/group/metadata/purge command tests without relying on packaged real NIfTI data | `cubids/tests/test_cli.py` (subset) |

## Notes

- `test_apply.py` also exercises both `IntendedFor` representations:
  - relative path (native skeleton form)
  - BIDS URI (converted during test setup by shared fixture helpers)
- The generated datasets are deterministic and intended for behavior testing, not performance benchmarking.
