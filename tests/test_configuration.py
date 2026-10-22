from stylometry.features import (
    EXPECTED_FEATURE_COUNT, EXPECTED_PRIMARY_COUNT, FEATURE_REGISTRY, REGISTRY_COMPLETE,
)
from stylometry.stages import STAGES, STAGE_AREAS
from stylometry.ui.dashboard import MODULES


def test_stage_configuration():
    assert [stage.number for stage in STAGES] == list(range(1, 10))
    assert [stage.name for stage in STAGES] == [
        "Data preparation", "Text extraction and cleaning", "Quality control and selection",
        "Feature engineering and transformation", "Exploratory data analysis",
        "Statistical stability modeling", "Robustness and sensitivity analysis",
        "Results interpretation", "Conclusions",
    ]
    assert all(stage.status == "Not started" for stage in STAGES)
    assert STAGE_AREAS == (
        "Inputs", "Method / parameters", "Processing history", "Outputs", "Visualization",
    )


def test_registry_is_explicitly_incomplete():
    assert not REGISTRY_COMPLETE
    assert FEATURE_REGISTRY == ()
    assert (EXPECTED_FEATURE_COUNT, EXPECTED_PRIMARY_COUNT) == (43, 24)


def test_navigation_contract():
    assert MODULES == ("Experiment Process", "Overview", "Features", "Sample")
