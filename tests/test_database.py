import pytest

from stylometry import config, database


def test_database_disabled_without_configuration(monkeypatch):
    monkeypatch.setattr(database, "database_url", lambda: None)
    assert database.create_optional_engine() is None


def test_environment_configuration(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert config.database_url() is None


def test_engine_factory_is_lazy():
    engine = database.create_optional_engine("postgresql+psycopg://localhost/unconfigured_test")
    assert engine.dialect.name == "postgresql"
    assert engine.hide_parameters
    engine.dispose()


@pytest.mark.parametrize("url", ["invalid", "sqlite:///local.db"])
def test_invalid_configuration_is_rejected_without_echoing_url(url):
    with pytest.raises(ValueError) as error:
        database.create_optional_engine(url)
    assert url not in str(error.value)
