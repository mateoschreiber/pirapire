import re
import unicodedata

from sqlmodel import Session, select

from ..models_lol import LolTeamAlias


def normalize_text(value: str | None) -> str:
    text = (value or '').strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^a-z0-9 ]+', ' ', text)
    text = re.sub(r'\b(esports|e sports|gaming|team|club|lol)\b', ' ', text)
    return ' '.join(text.split())


def canonical_team(session: Session, name: str | None, league_slug: str | None = None) -> str | None:
    if not name:
        return None
    normalized = normalize_text(name)
    query = select(LolTeamAlias).where(LolTeamAlias.normalized_alias == normalized)
    if league_slug:
        query = query.where((LolTeamAlias.league_slug == league_slug) | (LolTeamAlias.league_slug == None))  # noqa: E711
    row = session.exec(query).first()
    return row.canonical_team if row else name.strip()


def upsert_alias(session: Session, canonical: str, alias: str, league_slug: str | None = None) -> None:
    normalized = normalize_text(alias)
    existing = session.exec(select(LolTeamAlias).where(LolTeamAlias.normalized_alias == normalized, LolTeamAlias.canonical_team == canonical)).first()
    if existing:
        return
    session.add(LolTeamAlias(canonical_team=canonical, alias=alias, normalized_alias=normalized, league_slug=league_slug))
