from pathlib import Path

from streamlit.testing.v1 import AppTest

from stylometry.stages import STAGES
from stylometry.ui.dashboard import MODULES

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_navigation_and_empty_states():
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert app.radio[0].value == "Experiment Process"
    for stage in STAGES:
        app.selectbox[0].select(stage).run()
        assert not app.exception
        assert app.subheader[0].value == f"{stage.number}. {stage.name}"
        assert "Not started" in app.info[0].value
        assert len(app.markdown) >= 5
    for module in MODULES[1:]:
        app.radio[0].set_value(module).run()
        assert not app.exception
        assert app.header[0].value == module
        if module == "Features":
            assert "incomplete" in app.warning[0].value
            assert app.selectbox[1].disabled
            assert app.multiselect[0].disabled
    assert app.selectbox[0].disabled
    assert not app.dataframe
