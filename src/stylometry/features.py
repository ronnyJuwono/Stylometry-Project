"""Registry contract; authoritative definitions have not yet been imported."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    key: str
    name: str
    family: str
    definition: str
    is_primary: bool
    source: str


EXPECTED_FEATURE_COUNT = 43
EXPECTED_PRIMARY_COUNT = 24
REGISTRY_COMPLETE = False
FEATURE_REGISTRY: tuple[Feature, ...] = ()


def find_features(query: str = "", family: str | None = None) -> tuple[Feature, ...]:
    query = query.casefold().strip()
    return tuple(
        feature for feature in FEATURE_REGISTRY
        if (family is None or feature.family == family)
        and query in f"{feature.key} {feature.name} {feature.definition}".casefold()
    )
