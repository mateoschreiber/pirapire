import re
import unicodedata

from sqlmodel import Session, select

from ..models_lol import (
    LolGameHistory,
    LolMatchEvent,
    LolPlayerGameStat,
    LolTeamAlias,
    LolTeamGameStat,
)


KNOWN_TEAM_ALIASES = {
    "Anyone's Legend": (
        "Anyone's Legend", "AG.AL", "AG.AL International", "AG.AL International Esports",
        "All Gamers", "All Gamers Anyone's Legend",
    ),
    "LYON": ("LYON", "LYON Gaming", "LYON (2024 American Team)"),
    "Ninjas in Pyjamas": (
        "Ninjas in Pyjamas", "Ninjas in Pyjamas.CN", "NIP",
        "Shenzhen Ninjas in Pyjamas",
    ),
    "paiN Gaming": ("paiN Gaming", "PaiN Gaming", "Pain Gaming"),
}

EXHIBITION_TEAMS = (
    {
        "alias": "CNB Legends",
        "status": "exhibition",
        "reason": "Classic Showmatch: no es el roster profesional vigente de CBLOL.",
    },
    {
        "alias": "PaiN Legends",
        "status": "exhibition",
        "reason": "Classic Showmatch: no es el roster profesional vigente de paiN Gaming.",
    },
)


def normalize_text(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"(esports|e sports|gaming|team|club|lol)", " ", text)
    return " ".join(text.split())


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
    existing = session.exec(
        select(LolTeamAlias).where(
            LolTeamAlias.normalized_alias == normalized,
            LolTeamAlias.canonical_team == canonical,
        )
    ).first()
    if not existing:
        session.add(
            LolTeamAlias(
                canonical_team=canonical,
                alias=alias,
                normalized_alias=normalized,
                league_slug=league_slug,
            )
        )


def synchronize_known_aliases(session: Session) -> dict:
    """Persist verified renames and normalize affected schedule/history rows."""
    lookup = {
        normalize_text(alias): canonical
        for canonical, aliases in KNOWN_TEAM_ALIASES.items()
        for alias in aliases
    }
    aliases_updated = 0
    for canonical, aliases in KNOWN_TEAM_ALIASES.items():
        for alias in aliases:
            normalized = normalize_text(alias)
            rows = session.exec(
                select(LolTeamAlias).where(LolTeamAlias.normalized_alias == normalized)
            ).all()
            if rows:
                for row in rows:
                    if row.canonical_team != canonical or row.alias != alias:
                        row.canonical_team = canonical
                        row.alias = alias
                        row.league_slug = None
                        session.add(row)
                        aliases_updated += 1
            else:
                session.add(
                    LolTeamAlias(
                        canonical_team=canonical,
                        alias=alias,
                        normalized_alias=normalized,
                    )
                )
                aliases_updated += 1
    session.flush()

    def resolve(value: str | None) -> str | None:
        if not value:
            return value
        return lookup.get(normalize_text(value), value)

    events_updated = history_updated = stats_updated = 0
    for event in session.exec(select(LolMatchEvent)).all():
        for field in ("team_a", "team_b"):
            original = getattr(event, field)
            canonical = resolve(original)
            if canonical != original:
                setattr(event, field, canonical)
                events_updated += 1
        session.add(event)
    for game in session.exec(select(LolGameHistory)).all():
        for field in ("blue_team", "red_team", "winner_team"):
            original = getattr(game, field)
            canonical = resolve(original)
            if canonical != original:
                setattr(game, field, canonical)
                history_updated += 1
        session.add(game)
    for row in session.exec(select(LolTeamGameStat)).all():
        for field in ("team_name", "opponent_name"):
            original = getattr(row, field)
            canonical = resolve(original)
            if canonical != original:
                setattr(row, field, canonical)
                stats_updated += 1
        session.add(row)
    for row in session.exec(select(LolPlayerGameStat)).all():
        canonical = resolve(row.team_name)
        if canonical != row.team_name:
            row.team_name = canonical
            stats_updated += 1
            session.add(row)
    session.commit()
    if history_updated:
        from .series_builder import rebuild_series
        rebuild_series(session)
    return {
        "aliases_updated": aliases_updated,
        "events_updated": events_updated,
        "history_updated": history_updated,
        "stats_updated": stats_updated,
        "exhibitions": list(EXHIBITION_TEAMS),
    }


def resolve_team_alias(session: Session, name: str | None, league_slug: str | None = None) -> str | None:
    return canonical_team(session, name, league_slug)
