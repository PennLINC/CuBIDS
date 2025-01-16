"""Constants for CuBIDS.

This module defines various constants used throughout the CuBIDS package.

Attributes
----------
ID_VARS : set of str
    Names of identifier variables. Used to place EntitySet and ParamGroup at
    the beginning of a dataframe but both are hardcoded in the relevant function.
NON_KEY_ENTITIES : set of str
    Entities that should not be used to group parameter sets.
IMAGING_PARAMS : set of str
    List of metadata fields merged in `metadata_merge.py`.
"""
ID_VARS = set(["EntitySet", "ParamGroup", "FilePath"])
NON_KEY_ENTITIES = set(["subject", "session", "extension"])
# Multi-dimensional keys SliceTiming  XXX: what is this line about?
IMAGING_PARAMS = set(
    [
        "ParallelReductionFactorInPlane",
        "ParallelAcquisitionTechnique",
        "ParallelAcquisitionTechnique",
        "PartialFourier",
        "PhaseEncodingDirection",
        "EffectiveEchoSpacing",
        "TotalReadoutTime",
        "EchoTime",
        "SliceEncodingDirection",
        "DwellTime",
        "FlipAngle",
        "MultibandAccelerationFactor",
        "RepetitionTime",
        "VolumeTiming",
        "NumberOfVolumesDiscardedByScanner",
        "NumberOfVolumesDiscardedByUser",
        "Obliquity",
        "VoxelSizeDim1",
        "VoxelSizeDim2",
        "VoxelSizeDim3",
        "Dim1Size",
        "Dim2Size",
        "Dim3Size",
        "NumVolumes",
    ]
)
