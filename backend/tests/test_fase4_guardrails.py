from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

BACKEND = Path(__file__).resolve().parents[1]


def test_no_playwright_in_requirements():
    req = (BACKEND / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "playwright" not in req
    assert "selenium" not in req


def test_no_playwright_imports_in_app_source():
    for path in (BACKEND / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert "import playwright" not in text
        assert "from playwright" not in text


def test_no_setinterval_polling_in_app_js():
    js = (BACKEND / "app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "setInterval" not in js


def test_dashboard_has_best_bets_section():
    html = client.get("/").text
    assert "Mejores apuestas" in html
    assert "Mejores combinadas" in html
