from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

UI_PAGES = [
    "/",
    "/sports/ui",
    "/teams/ui",
    "/matches/ui",
    "/odds/ui",
    "/combo/ui",
    "/history/ui",
    "/settings/ui",
]


def test_root_returns_html_dashboard():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Pirapire" in response.text
    assert "Dashboard" in response.text


def test_all_ui_pages_load():
    for path in UI_PAGES:
        response = client.get(path)
        assert response.status_code == 200, path
        assert "text/html" in response.headers["content-type"], path


def test_odds_ui():
    assert client.get("/odds/ui").status_code == 200


def test_combo_ui():
    assert client.get("/combo/ui").status_code == 200


def test_static_css_served():
    response = client.get("/static/css/styles.css")
    assert response.status_code == 200
    assert "box-sizing" in response.text
