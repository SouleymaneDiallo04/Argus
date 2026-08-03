import pytest


@pytest.fixture(autouse=True)
def _ephemeral_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("ARGUS_DB_PATH", ":memory:")
    monkeypatch.setenv("ARGUS_SNAPSHOT_DIR", str(tmp_path / "snapshots"))
