import pytest


@pytest.fixture(autouse=True)
def _ephemeral_db(monkeypatch):
    monkeypatch.setenv("ARGUS_DB_PATH", ":memory:")
