from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import engine
from app.main import app
from app.models_football import FootballMatch
from app.models_lol import LolChampion

client = TestClient(app)

UI_PAGES = [
    "/",
    "/sports/ui",
    "/teams/ui",
    "/matches/ui",
    "/odds/ui",
    "/combo/ui",
    "/history/ui",
    "/sources/ui",
    "/source-runs/ui",
    "/data/football/ui",
    "/data/lol/ui",
    "/markets/ui",
    "/imports/ui",
    "/aposta/ui",
    "/recommendations/ui",
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


def test_dashboard_shows_normalized_counts():
    # Seed distinctive counts and confirm the dashboard renders them (no zeros).
    with Session(engine) as session:
        for i in range(3):
            session.add(
                FootballMatch(source_name="test", source_external_id=f"pg-{i}", source_rank=90)
            )
        for name in ("Zed", "Yasuo", "Lux", "Sona"):
            session.add(
                LolChampion(source_name="test", champion_id=f"pg-{name}", name=name, source_rank=100)
            )
        session.commit()

    html = client.get("/").text
    matches = [m for m in _extract_stats(html)]
    # The champion and match stat cells should reflect at least the seeded rows.
    assert 'id="stat-champions"' in html
    assert 'id="stat-matches"' in html
    champions_value = _stat_value(html, "stat-champions")
    matches_value = _stat_value(html, "stat-matches")
    assert champions_value >= 4
    assert matches_value >= 3
    assert matches  # sanity


def _extract_stats(html: str):
    import re

    return re.findall(r'id="stat-[a-z]+">(\d+)<', html)


def _stat_value(html: str, stat_id: str) -> int:
    import re

    match = re.search(r'id="' + stat_id + r'">(\d+)<', html)
    return int(match.group(1)) if match else -1
