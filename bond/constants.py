ID_VARS = set(["KeyGroup", "ParamGroup", "FilePath"])
NON_KEY_ENTITIES = set(["subject", "session", "extension"])
# Multi-dimensional keys SliceTiming
IMAGING_PARAMS = set([
    "ParallelReductionFactorInPlane", "ParallelAcquisitionTechnique",
    "ParallelAcquisitionTechnique", "PartialFourier", "PhaseEncodingDirection",
    "EffectiveEchoSpacing", "TotalReadoutTime", "EchoTime",
    "SliceEncodingDirection", "DwellTime", "FlipAngle",
    "MultibandAccelerationFactor", "RepetitionTime",
    "VolumeTiming", "NumberOfVolumesDiscardedByScanner",
    "NumberOfVolumesDiscardedByUser"])