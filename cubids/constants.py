"""Constants for CuBIDS."""

# Names of identifier variables.
# Used to place KeyGroup and ParamGroup at the beginning of a dataframe,
# but both are hardcoded in the relevant function.
ID_VARS = set(["KeyGroup", "ParamGroup", "FilePath"])
# Entities that should not be used to group parameter sets
FILE_COLLECTION_ENTITIES = set(["echo", "part", "flip", "mt", "inv"])
NON_KEY_ENTITIES = set(["subject", "session", "run", "extension"]).union(FILE_COLLECTION_ENTITIES)
# Multi-dimensional keys SliceTiming  XXX: what is this line about?
# List of metadata fields and parameters (calculated by CuBIDS)
# Not sure what this specific list is used for.
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
