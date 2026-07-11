"""Kambi/ShapeGames API connector for Aposta.LA LoL events."""

import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import UTC, datetime

BASE_URL = "https://us.offering-api.kambicdn.com/offering/v2018/betplayintpy"
HEADERS = {"User-Agent": "Pirapire/1.0", "Accept": "application/json"}


def _fetch_json(url, timeout=25, retries=1):
    """Fetch JSON with CA and hostname validation; never use an insecure fallback."""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                return json.loads(response.read())
        except (ssl.SSLCertVerificationError, ssl.CertificateError):
            raise
        except (TimeoutError, urllib.error.URLError):
            if attempt >= retries:
                raise


def fetch_lol_events():
    return _fetch_json(
        f"{BASE_URL}/listView/esports/league_of_legends.json?lang=es_PY&market=PY"
    )


def fetch_event_detail(event_id):
    return _fetch_json(
        f"{BASE_URL}/betoffer/event/{event_id}.json?lang=es_PY&market=PY"
    )


def _map_market(market_name):
    """Classify only observed, unambiguous Kambi labels; unknown stays unmapped."""
    name = market_name.casefold()
    if "correct map score" in name or "correct score" in name:
        return "correct_map_score"
    if "total maps" in name:
        return "total_maps_over_under" if "over" in name or "under" in name else "total_maps"
    if "match odds" in name or re.fullmatch(r"map \d+", name):
        return "series_winner" if "match" in name else "map_winner"
    if "handicap" in name:
        return "map_handicap"
    if "total kills" in name:
        return "player_kills" if "player" in name else "total_kills"
    if "total deaths" in name:
        return "player_deaths"
    if "total minutes" in name or "duration" in name:
        return "map_duration"
    if "turret" in name or "tower" in name:
        return "total_turrets"
    if "inhibitor" in name:
        return "total_inhibitors"
    if "player with most kills" in name:
        return "player_most_kills"
    return None


def _market_dimensions(market_name, outcome_label):
    map_match = re.search(r"Map (\d+)", market_name, re.I)
    player_match = re.search(r"(?:by|the) Player\s+(.+)$", market_name, re.I)
    participant_match = re.search(r"by\s+(.+)$", market_name, re.I)
    return {
        "period": f"map_{map_match.group(1)}" if map_match else "series",
        "map_number": int(map_match.group(1)) if map_match else None,
        "player_name": player_match.group(1).strip() if player_match else None,
        "participant_name": participant_match.group(1).strip() if participant_match else None,
    }


def _normalize_selection(label, home, away):
    if label == home:
        return "home"
    if label == away:
        return "away"
    normalized = label.lower()
    if "over" in normalized or "mas" in normalized:
        return "over"
    if "under" in normalized or "menos" in normalized:
        return "under"
    if re.match(r"\d+-\d+", label):
        return label
    return normalized


def parse_kambi_to_rows(lol_data, fetch_details=True):
    rows = []
    for evt in lol_data.get("events", []):
        event = evt.get("event", {})
        event_id = event.get("id")
        if not event_id:
            continue
        if event.get("state") != "NOT_STARTED":
            continue

        home = event.get("homeName", "")
        away = event.get("awayName", "")
        group = event.get("group", "")
        start = event.get("start", "")
        event_date = None
        if start:
            try:
                event_date = datetime.fromisoformat(start.replace("Z", "+00:00"))
                if event_date.tzinfo is None:
                    event_date = event_date.replace(tzinfo=UTC)
                event_date = event_date.astimezone(UTC)
            except ValueError:
                event_date = None

        betoffers = []
        if fetch_details:
            try:
                detail = fetch_event_detail(event_id)
                betoffers = detail.get("betOffers", [])
            except Exception:
                betoffers = evt.get("betOffers", [])
        else:
            betoffers = evt.get("betOffers", [])

        for bo in betoffers:
            criterion = bo.get("criterion", {})
            market_name = criterion.get("englishLabel", "") or criterion.get(
                "label", ""
            )
            market_code = _map_market(market_name)

            for outcome in bo.get("outcomes", []):
                odds_raw = outcome.get("odds", 0)
                odds_decimal = (
                    round(odds_raw / 1000.0, 3) if odds_raw > 100 else float(odds_raw)
                )
                if odds_decimal <= 1.0:
                    continue

                label = outcome.get("label", "") or outcome.get("englishLabel", "")
                selection = _normalize_selection(label, home, away)

                dimensions = _market_dimensions(market_name, label)
                line = None
                m = re.search(r"Map (\d+)", market_name)
                if m:
                    line = float(m.group(1))
                m = re.search(r"Total Maps.*?(\d+\.?\d*)", market_name)
                if m:
                    line = float(m.group(1))

                rows.append(
                    {
                        "sport": "lol",
                        "competition": group or "League of Legends",
                        "event_date": event_date.isoformat()
                        if hasattr(event_date, "isoformat")
                        else event_date,
                        "event_date_raw": start or None,
                        "event_time_status": "confirmed_source_utc"
                        if event_date
                        else "unconfirmed",
                        "team_a": home,
                        "team_b": away,
                        "market_text": market_name,
                        "raw_market_label": market_name,
                        "market_code": market_code,
                        **dimensions,
                        "line": line,
                        "selection": selection,
                        "selection_raw": label,
                        "raw_outcome_label": label,
                        "odds_decimal": odds_decimal,
                        "bookmaker": "Aposta.LA",
                        "source_url": f"kambi:event:{event_id}",
                        "source": "kambi",
                        "source_event_id": str(event_id),
                        "source_market_id": str(bo.get("id") or criterion.get("id") or "") or None,
                        "source_outcome_id": str(outcome.get("id") or "") or None,
                        "raw_kickoff_text": start or None,
                    }
                )
    return rows
