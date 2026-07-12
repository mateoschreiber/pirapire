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

# Kambi/Aposta.LA team aliases
KAMBI_ALIASES = [('Malvinas', 'Malvinas Gaming'), ('9z Team', '9z Globant'), ('Maze Gaming', 'Maze Gaming'), ('Volticons', 'Volticons'), ('Docta Esports Club', 'Docta Esports'), ('Golden Lions', 'Golden Lions'), ('ZEN Esports', 'ZEN Esports (Argentinian Team)'), ('Seven Dark', 'Seven Dark'), ('Playtime', 'Playtime'), ('Aurora Gaming', 'Aurora Gaming')]

# Phase 4B2: confirmed Aposta/Kambi -> Leaguepedia resolutions for active
# participants. Each tuple is (leaguepedia_canonical, aposta_alias). The
# Leaguepedia team name is the canonical/source label; aliases were confirmed
# against Leaguepedia ScoreboardGames Team1/Team2 by live probe.
LEAGUEPEDIA_CONFIRMED_ALIASES = [
    ("Bilibili Gaming", "Bilibili Gaming"),
    ("Bilibili Gaming", "BLG"),
    ("Hanwha Life Esports", "Hanwha Life Esports"),
    ("Hanwha Life Esports", "HLE"),
    ("NCG Esports", "NCG Esports"),
    ("Zeu5 Esports", "Zeu5 Esports"),
    ("SDM Tigres", "SDM Tigres"),
    ("Fuego", "Fuego"),
]
# Ambiguous / unresolved aliases stay out of the confirmed map on purpose.
LEAGUEPEDIA_PENDING_ALIASES: list[str] = []


def seed_leaguepedia_aliases(session: Session) -> int:
    """Register confirmed Aposta/Kambi -> Leaguepedia team resolutions."""
    added = 0
    for canonical, alias in LEAGUEPEDIA_CONFIRMED_ALIASES:
        before = session.exec(
            select(LolTeamAlias).where(
                LolTeamAlias.normalized_alias == normalize_text(alias),
                LolTeamAlias.canonical_team == canonical,
            )
        ).first()
        if before is None:
            upsert_alias(session, canonical, alias, league_slug="leaguepedia")
            added += 1
    session.commit()
    return added


def leaguepedia_query_names(session: Session, aposta_name: str) -> list[str]:
    """All registered Leaguepedia source names to search for a participant.

    Returns the canonical Leaguepedia name(s) plus the input, de-duplicated.
    Never returns an unregistered text alias on its own.
    """
    names: list[str] = []
    normalized = normalize_text(aposta_name)
    rows = session.exec(
        select(LolTeamAlias).where(LolTeamAlias.normalized_alias == normalized)
    ).all()
    for row in rows:
        if row.canonical_team and row.canonical_team not in names:
            names.append(row.canonical_team)
    # The direct name is included only if it is itself a registered alias.
    direct = session.exec(
        select(LolTeamAlias).where(LolTeamAlias.normalized_alias == normalized)
    ).first()
    if direct and aposta_name not in names:
        names.append(aposta_name)
    return names
