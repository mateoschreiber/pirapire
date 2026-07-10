from sqlmodel import Session

from ..models_markets import MarketAlias, MarketCatalog

from .text_normalizer import normalize


def market_mapping_status(session: Session, sport: str, market_text: str) -> str:
    if not market_text:
        return 'unsupported'

    normalized = normalize(market_text)
    if not normalized:
        return 'unsupported'

    aliases = session.query(MarketAlias).all()

    for alias in aliases:
        if alias.normalized_alias == normalized:
            return 'mapped'

    for alias in aliases:
        if alias.normalized_alias and (
            normalized.startswith(alias.normalized_alias)
            or alias.normalized_alias in normalized
        ):
            return 'mapped'

    return 'unmapped'
