import pytest
from fastapi.testclient import TestClient

KEY = "test-key"


@pytest.fixture(autouse=True)
def isolated_platform(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PLATFORM_API_KEY", KEY)
    monkeypatch.delenv("RELEASE", raising=False)


@pytest.fixture
def api():
    from grok_invoices.entrypoints.http import app

    with TestClient(app, headers={"Authorization": f"Bearer {KEY}"}) as client:
        yield client
