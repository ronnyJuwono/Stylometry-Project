"""Future analysis families; names do not supply formulas or method approval."""

from enum import StrEnum

from stylometry.pipeline.interfaces import StageInput, StageOutput, StageUnavailable


class AnalysisMethod(StrEnum):
    DESCRIPTIVE = "descriptive"
    CORRELATION = "correlation"
    PCA = "pca"
    MIXED_EFFECTS = "mixed_effects"
    ICC = "icc"
    SENSITIVITY = "sensitivity"


def execute_analysis(method: AnalysisMethod, inputs: StageInput) -> StageOutput:
    raise StageUnavailable("Analysis method is unavailable pending source validation and separate approval.")
