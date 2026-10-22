"""Navigation skeleton with explicit, scientifically honest empty states."""

import streamlit as st

from stylometry.config import database_url
from stylometry.features import (
    EXPECTED_FEATURE_COUNT, EXPECTED_PRIMARY_COUNT, FEATURE_REGISTRY,
    find_features,
)
from stylometry.stages import STAGES, STAGE_AREAS

MODULES = ("Experiment Process", "Overview", "Features", "Sample")
EXPERIMENT_TITLE = (
    "A Data Science Approach to Measuring Stylometric Stability and Variability "
    "in EFL Student Writing"
)


def experiment_process() -> None:
    st.header("Experiment Process")
    st.caption("Nine planned stages • 0 executed • No research data loaded")
    selected = st.selectbox(
        "Experiment stage", STAGES,
        format_func=lambda stage: f"{stage.number}. {stage.name}",
    )
    st.subheader(f"{selected.number}. {selected.name}")
    st.info(f"Status: {selected.status}. This interface has not executed this stage.")
    messages = {
        "Inputs": "No inputs registered. Real student documents are not loaded.",
        "Method / parameters": "No approved method or parameters imported. Pending methodology review.",
        "Processing history": "No processing runs recorded.",
        "Outputs": "No outputs produced.",
        "Visualization": "Prototype placeholder: no visualization available without validated outputs.",
    }
    for area in STAGE_AREAS:
        with st.container(border=True):
            st.markdown(f"#### {area}")
            st.write(messages[area])


def overview() -> None:
    st.header("Overview")
    st.subheader("DASET Paper 1")
    st.write(EXPERIMENT_TITLE)
    st.markdown("#### Background and objectives")
    st.write("Planned study of stylometric stability and variability in EFL student writing.")
    st.write("Formal objectives and research questions: awaiting approved study documentation.")
    st.markdown("#### Dataset details")
    st.write("Population: EFL student writing. Sample size, collection dates, inclusion rules, "
             "consent, and anonymization protocol: unknown / not registered.")
    st.markdown("#### Publication and research metadata")
    for label in (
        "Intended publication venue", "Conference dates", "Submission status",
        "Acceptance status", "Publication status", "Researchers / affiliations",
        "Protocol version", "Ethics approval", "Preregistration", "Dataset version",
    ):
        st.write(f"{label}: unknown / unverified")


def features() -> None:
    st.header("Features")
    st.warning("Feature registry incomplete: authoritative definitions have not been imported.")
    st.caption(f"Planned: {EXPECTED_FEATURE_COUNT} engineered features, "
               f"{EXPECTED_PRIMARY_COUNT} primary features. Registered: {len(FEATURE_REGISTRY)}.")
    query = st.text_input("Search features", placeholder="Name, key, or definition")
    families = sorted({feature.family for feature in FEATURE_REGISTRY})
    family = st.selectbox("Feature family", ["All families", *families])
    matches = find_features(query, None if family == "All families" else family)
    by_key = {feature.key: feature for feature in matches}
    selected = st.selectbox("Individual feature", list(by_key),
                            disabled=not by_key, placeholder="No registered features")
    if selected:
        feature = by_key[selected]
        st.write(f"{feature.name} • {feature.family}")
        st.write(feature.definition)
        st.write(f"Primary: {'Yes' if feature.is_primary else 'No'} • Source: {feature.source}")
    compared = st.multiselect("Compare features", list(by_key), disabled=not by_key)
    if compared:
        st.dataframe([
            {"Feature": by_key[key].name, "Family": by_key[key].family,
             "Definition": by_key[key].definition, "Primary": by_key[key].is_primary,
             "Source": by_key[key].source}
            for key in compared
        ], hide_index=True)
    st.info("No feature measurements or comparison plots available. No values have been generated.")


def sample() -> None:
    st.header("Sample")
    st.selectbox("Anonymized sample", [], disabled=True, placeholder="No approved samples loaded")
    st.info("No sample text is displayed. Student documents have not been imported.")
    left, right = st.columns(2)
    with left:
        st.subheader("Original text")
        st.caption("Empty: requires an approved anonymized sample.")
    with right:
        st.subheader("Cleaned text")
        st.caption("Empty: no cleaning run recorded.")
    for label, value in (
        ("Provenance", "No source or transformation records registered"),
        ("Word count", "Not computed"), ("QC status", "Not assessed"),
        ("Feature values", "Not computed"), ("Processing history", "No runs recorded"),
    ):
        st.markdown(f"**{label}:** {value}")


def main() -> None:
    st.set_page_config(page_title="Stylometry Research Platform", layout="wide")
    st.title("Stylometry Research Platform")
    st.caption("DASET Paper 1 • Experiment process prototype • No analyses executed")
    with st.sidebar:
        st.header("Research workspace")
        module = st.radio("Module", MODULES)
        st.caption("PostgreSQL: configured, untested" if database_url()
                   else "PostgreSQL: disabled (no connection configured)")
    {
        "Experiment Process": experiment_process, "Overview": overview,
        "Features": features, "Sample": sample,
    }[module]()
