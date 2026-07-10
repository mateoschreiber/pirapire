"""Parser for Aposta.LA LoL/eSports pages via browser worker."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from bs4 import BeautifulSoup


def parse_lol_html(html: str, source_url: str = "") -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    
    # Strategy: eSports pages are Angular SPAs. Look for:
    # - Script tags with JSON data (__NEXT_DATA__, window.__INITIAL_STATE__, etc.)
    # - Embedded JSON objects with sport/event data
    # - Rendered text patterns for teams/odds
    
    # Try to find JSON data in script tags
    for script in soup.find_all("script"):
        text = script.string or ""
        if not text:
            continue
        
        # Look for common SPA data patterns
        patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'__NEXT_DATA__\s*=\s*({.*?});',
            r'"sportName"\s*:\s*"League of Legends"',
            r'"sportId"\s*:\s*(\d+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                print(f"Found pattern: {pattern[:50]}... in script")

    # Fallback: search text for LoL patterns
    text = soup.get_text("\n")
    
    # Look for team vs team patterns
    team_patterns = re.findall(
        r'([A-Za-z0-9 ]+?)\s+(?:vs|VS|\.vs\.|x)\s+([A-Za-z0-9 ]+?)(?:\s|$)',
        text
    )
    
    for ta, tb in team_patterns[:20]:
        ta = ta.strip()
        tb = tb.strip()
        if len(ta) > 2 and len(tb) > 2:
            rows.append({
                "sport": "lol",
                "competition": "League of Legends",
                "event_date": None,
                "team_a": ta,
                "team_b": tb,
                "market_text": "map_winner",
                "market_code": "map_winner",
                "line": None,
                "selection": "home",
                "selection_raw": ta,
                "odds_decimal": 1.0,
                "bookmaker": "Aposta.LA",
                "source_url": source_url,
            })

    return rows
