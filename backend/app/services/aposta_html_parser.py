"""Parser for Aposta.LA server-rendered HTML pages."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from bs4 import BeautifulSoup


def _parse_aposta_datetime(day_text: str, time_text: str, ref_date: datetime | None = None) -> datetime | None:
    if ref_date is None:
        ref_date = datetime.utcnow()
    day = day_text.strip().lower()
    time = time_text.strip().lower()
    full = f"{day} {time}"

    m = re.search(r"(\d{1,2})[h:](\d{0,2})", time)
    if not m:
        m = re.search(r"(\d{1,2})[h:](\d{0,2})", day)
    if not m:
        return None

    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0

    if "mañana" in day or "amanha" in day:
        base = ref_date + timedelta(days=1)
    elif "hoy" in day or "hoje" in day:
        base = ref_date
    else:
        dm = re.search(r"(\d{1,2})/(\d{1,2})", full)
        if dm:
            d, mo = int(dm.group(1)), int(dm.group(2))
            y = ref_date.year
            dt = datetime(y, mo, d, hour, minute, 0)
            if dt < ref_date - timedelta(days=7):
                dt = dt.replace(year=y + 1)
            return dt
        return None

    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _classify_market(text: str) -> tuple[str | None, str]:
    t = text.strip().lower()
    if "partido" in t and ("reglamentario" in t or "tiempo" in t):
        return "match_winner", "match_winner"
    if ("mas" in t and "menos" in t) or ("más" in t and "menos" in t):
        return "total_goals_over_under", "total_goals_over_under"
    if "ambos" in t and "marcan" in t:
        return "both_teams_to_score", "both_teams_to_score"
    if "doble" in t and "oportunidad" in t:
        return "double_chance", "double_chance"
    if "handicap" in t or "hándicap" in t:
        return "handicap", "handicap"
    if "goles" in t:
        return "team_goals_over_under", "team_goals_over_under"
    if "tarjetas" in t:
        return "cards", "cards"
    if "corners" in t or "córners" in t:
        return "corners", "corners"
    if "campeón" in t or "campeon" in t:
        return "outright_winner", "outright_winner"
    return None, t


def _normalize_selection(text: str) -> tuple[str, float | None]:
    t = text.strip().lower()
    line = None

    # Extract line from selection if present
    m = re.search(r"(\d+[.,]\d+)", t)
    if m:
        line = float(m.group(1).replace(",", "."))

    if "equipo a" in t:
        return "home", line
    if "equipo b" in t:
        return "away", line
    if "empate" in t and "equipo" not in t:
        return "draw", line
    if "más" in t or "mas" in t:
        return "over", line
    if "menos" in t:
        return "under", line
    if t in ("sí", "si", "yes"):
        return "yes", line
    if t == "no":
        return "no", line
    return t, line


def parse_aposta_html(html: str, source_url: str = "") -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    ref_date = datetime.utcnow()

    text = soup.get_text("\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    competition = ""
    markets = []  # list of (display_name, internal_code)
    rows = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Competition: "Internacional - Copa del Mundo" or similar
        if re.search(r'[-–]\s+[\w]', line) and any(kw in line.lower() for kw in ['copa', 'liga', 'champions', 'mundial', 'serie', 'friendly', 'clausura', 'apertura', 'torneo', 'super', 'league', 'cup', 'primera', 'segunda', 'internacional', 'clubes']):
            if len(line) < 150 and not re.match(r'^\d+[.,]\d{2}', line) and line.lower() not in ('más / menos', 'mas / menos'):
                competition = line
                markets = []
                i += 1
                continue

        # Market header detection - must come after competition
        if competition:
            code, _ = _classify_market(line)
            if code and len(line) < 80 and code not in [m[1] for m in markets]:
                markets.append((line, code))
                i += 1
                continue

        # Day detection: "Hoy" or "Mañana"
        if line.lower() in ("hoy", "hoje", "mañana", "amanhã", "amanha"):
            day_line = line
            i += 1
            if i >= len(lines):
                break

            time_line = lines[i]
            # Check next line is time (contains digits and h/H)
            if re.search(r'\d{1,2}[h:]\d{0,2}', time_line, re.I):
                event_date = _parse_aposta_datetime(day_line, time_line, ref_date)
                i += 1
                if i >= len(lines) or not event_date:
                    continue

                # Team A
                team_a = lines[i]
                i += 1
                if i >= len(lines):
                    break

                # Team B
                team_b = lines[i]
                i += 1
                if i >= len(lines):
                    break

                # Now parse market selections
                # Structure: for each market, we get ODDS \n SELECTION pairs
                if not markets:
                    continue

                # Calculate how many selections we expect
                # Market 1 (match_winner): 3 pairs = 6 lines
                # Market 2 (over_under): 2 pairs = 4 lines
                total_expected = sum(
                    3 if m[1] == "match_winner" else
                    3 if m[1] == "double_chance" else
                    2 for m in markets
                )

                collected_pairs = []
                j = i
                while j < len(lines) and j < i + (total_expected * 2) + 10:
                    candidate = lines[j]
                    # Check if it's a new date line
                    if candidate.lower() in ("hoy", "hoje", "mañana", "amanhã", "amanha"):
                        break
                    # Check if it's a new competition
                    if re.search(r'[-–]\s+[\w]', candidate) and any(kw in candidate.lower() for kw in ['copa', 'liga', 'champions', 'mundial', 'serie']):
                        if len(candidate) < 150:
                            break
                    # Check if it's an odds line
                    if re.match(r'^\d+[.,]\d{2,3}$', candidate):
                        if j + 1 < len(lines):
                            odds_val = float(candidate.replace(",", "."))
                            sel_raw = lines[j + 1]
                            collected_pairs.append((odds_val, sel_raw))
                            j += 2
                            continue
                    j += 1

                # Distribute pairs to markets
                pair_idx = 0
                for mkt_display, mkt_code in markets:
                    n_pairs = 3 if mkt_code in ("match_winner", "double_chance") else 2
                    for p in range(n_pairs):
                        if pair_idx >= len(collected_pairs):
                            break
                        odds_decimal, sel_raw = collected_pairs[pair_idx]
                        pair_idx += 1

                        selection, line_from_sel = _normalize_selection(sel_raw)
                        line_val = line_from_sel
                        if line_val is None:
                            m = re.search(r"(\d+[.,]\d+)", mkt_display)
                            if m:
                                line_val = float(m.group(1).replace(",", "."))

                        if odds_decimal > 1.0:
                            rows.append({
                                "sport": "football",
                                "competition": competition,
                                "event_date": event_date.isoformat(),
                                "team_a": team_a,
                                "team_b": team_b,
                                "market_text": mkt_display,
                                "market_code": mkt_code,
                                "line": line_val,
                                "selection": selection,
                                "selection_raw": sel_raw,
                                "odds_decimal": odds_decimal,
                                "bookmaker": "Aposta.LA",
                                "source_url": source_url,
                            })

                i = j
                continue

        i += 1

    return rows
