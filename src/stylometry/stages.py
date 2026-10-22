"""Process metadata only: this module does not execute any research methods."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Stage:
    number: int
    name: str
    status: str = "Not started"


STAGES = tuple(
    Stage(number, name)
    for number, name in enumerate(
        (
            "Data preparation",
            "Text extraction and cleaning",
            "Quality control and selection",
            "Feature engineering and transformation",
            "Exploratory data analysis",
            "Statistical stability modeling",
            "Robustness and sensitivity analysis",
            "Results interpretation",
            "Conclusions",
        ),
        start=1,
    )
)

STAGE_AREAS = (
    "Inputs", "Method / parameters", "Processing history", "Outputs", "Visualization"
)
