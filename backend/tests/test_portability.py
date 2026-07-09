from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

BACKEND = Path(__file__).resolve().parents[1]
FORBIDDEN = ["192.168.1.54", "/opt/licitaciones", "licer", "8088", "mateo:admin"]


def _find_up(filename: str) -> Path | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / filename
        if candidate.exists():
            return candidate
    return None


def test_readme_has_no_server_specific_references():
    readme = _find_up("README.md")
    if readme is None:
        pytest.skip("README.md not present in this environment")
    text = readme.read_text(encoding="utf-8")
    for token in FORBIDDEN:
        assert token not in text, f"README must not contain '{token}'"


def test_docs_have_no_forbidden_references():
    root = _find_up("README.md")
    if root is None:
        pytest.skip("docs not present in this environment")
    base = root.parent
    for name in ("INSTALL.md", "DEPLOYMENT.md", "SECURITY.md"):
        doc = base / name
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            assert token not in text, f"{name} must not contain '{token}'"


def test_env_example_has_no_real_api_key():
    env = _find_up(".env.example")
    if env is None:
        pytest.skip(".env.example not present")
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("FOOTBALL_DATA_API_KEY"):
            assert line.strip() == "FOOTBALL_DATA_API_KEY="
            return
    pytest.fail("FOOTBALL_DATA_API_KEY not found in .env.example")


def test_root_docker_compose_exists_and_is_portable():
    compose = _find_up("docker-compose.yml")
    if compose is None:
        pytest.skip("docker-compose.yml not present in this environment")
    text = compose.read_text(encoding="utf-8")
    assert "PIRAPIRE_PORT" in text
    assert "./data:/app/data" in text
    assert "./logs:/app/logs" in text
    for token in FORBIDDEN:
        assert token not in text, f"docker-compose.yml must not contain '{token}'"


def test_app_js_has_no_hardcoded_ip():
    js = (BACKEND / "app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "192.168.1.54" not in js
    # UI must call the API by relative path, never an absolute LAN URL.
    assert "http://192.168." not in js
    assert "https://192.168." not in js


def test_templates_have_no_hardcoded_ip():
    for tpl in (BACKEND / "app" / "templates").rglob("*.html"):
        text = tpl.read_text(encoding="utf-8")
        assert "192.168.1.54" not in text, f"{tpl.name} has hardcoded IP"


def test_health_ok():
    assert client.get("/health").status_code == 200


def test_root_ok():
    assert client.get("/").status_code == 200
