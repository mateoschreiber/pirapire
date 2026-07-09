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


def test_root_has_theme_toggle_button():
    html = client.get("/").text
    assert 'id="themeToggle"' in html


def test_root_references_app_js():
    html = client.get("/").text
    assert "/static/js/app.js" in html


def test_root_has_theme_persistence_bootstrap():
    html = client.get("/").text
    assert "pirapire.theme" in html
    assert "data-theme" in html
    assert "localStorage" in html


def test_app_js_persists_theme():
    js = client.get("/static/js/app.js").text
    assert "localStorage.setItem" in js
    assert "pirapire.theme" in js
    assert "storage" in js


def test_all_ui_pages_have_theme_toggle():
    for path in UI_PAGES:
        html = client.get(path).text
        assert 'id="themeToggle"' in html, path
