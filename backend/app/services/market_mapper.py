"""Normalize market texts and map them to the Market Catalog via aliases."""

import unicodedata

from sqlmodel import Session, select

from ..models_markets import MarketAlias, MarketCatalog


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split())


def map_market(session: Session, sport: str, market_text: str):
    """Return (market_id, market_code) or (None, None) when unmapped."""
    normalized = normalize_text(market_text)
    if not normalized:
        return None, None

    aliases = session.exec(select(MarketAlias)).all()
    catalog = {m.id: m for m in session.exec(select(MarketCatalog)).all()}

    # Exact normalized match first.
    for alias in aliases:
        if alias.normalized_alias == normalized:
            market = catalog.get(alias.market_id)
            if market and (not sport or market.sport == sport):
                return market.id, market.market_code

    # Prefix / contains match as a fallback.
    for alias in aliases:
        if alias.normalized_alias and (
            normalized.startswith(alias.normalized_alias)
            or alias.normalized_alias in normalized
        ):
            market = catalog.get(alias.market_id)
            if market and (not sport or market.sport == sport):
                return market.id, market.market_code

    return None, None
