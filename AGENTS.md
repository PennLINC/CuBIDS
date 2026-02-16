# Project Instructions

CuBIDS is a Python package for curating Brain Imaging Data Structure (BIDS) datasets.
The input dataset is assumed to be valid BIDS, and the primary goals of CuBIDS are to
(1) identify and summarize the heterogeneity in the dataset,
(2) apply groupings to the dataset to facilitate downstream analysis,
and (3) anonymize the dataset in preparation for open sharing.

The package is designed to be used as a command-line tool, but it can also be used as a Python library.
However, it does rely on non-Python dependencies, particularly `datalad` and `deno`.

## Code Style

- Follow the PEP 8 style guide and the Black code formatter.
- Follow the Numpydoc style guide for docstrings.
- Emphasize performance and readability over brevity.
- Use meaningful variable and function names.
- Use meaningful comments.
- Write code like an expert Python developer.

## Development

- When fixing a bug, start by writing a test that fails, then write the code to fix the bug.
- Always plan first.
- Think harder in the planning phase.
- When proposing tasks, highlight potential critical points that could lead to side effects.

## Testing

- Use pytest for testing.
- Tests should be organized by module and function/class.

## Linting

The repository is linted with `pipx run black`.
