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
    clean_name = name.strip()
    exact_rows = session.exec(select(LolTeamAlias).where(LolTeamAlias.alias == clean_name)).all()
    identity = next((row for row in exact_rows if row.canonical_team == clean_name), None)
    if identity:
        return clean_name
    if exact_rows:
        return exact_rows[0].canonical_team
    normalized = normalize_text(clean_name)
    compact = normalized.replace(" ", "")
    query = select(LolTeamAlias).where(
        (LolTeamAlias.normalized_alias == normalized) | (LolTeamAlias.normalized_alias == compact)
    )
    if league_slug:
        query = query.where((LolTeamAlias.league_slug == league_slug) | (LolTeamAlias.league_slug == None))  # noqa: E711
    rows = session.exec(query).all()
    identity = next((row for row in rows if row.canonical_team == clean_name), None)
    row = identity or (rows[0] if rows else None)
    return row.canonical_team if row else clean_name


def upsert_alias(session: Session, canonical: str, alias: str, league_slug: str | None = None) -> None:
    normalized = normalize_text(alias)
    existing = session.exec(select(LolTeamAlias).where(LolTeamAlias.normalized_alias == normalized, LolTeamAlias.canonical_team == canonical)).first()
    if existing:
        return
    session.add(LolTeamAlias(canonical_team=canonical, alias=alias, normalized_alias=normalized, league_slug=league_slug))


def resolve_team_alias(session: Session, name: str | None, league_slug: str | None = None) -> str | None:
    """Backward-compatible public name used by the odds importer."""
    return canonical_team(session, name, league_slug)
