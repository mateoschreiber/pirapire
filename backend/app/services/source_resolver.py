"""Resolve which data source to use for a given sport + data_type.

Rules:
- Only enabled sources (see source_registry.is_enabled) are considered.
- Sources are ordered by rank (desc); the first is the primary source.
- The rest form the fallback chain, used only when the primary does not
  provide a valid value for a specific datum.
- A value produced by a higher-rank source must never be overwritten by a
  lower-rank source (see should_update).
"""

from . import source_registry as registry


def resolve(sport: str, data_type: str, sources: list | None = None) -> list:
    pool = sources if sources is not None else registry.all_sources()
    matches = [
        s
        for s in pool
        if s.get("sport") == sport
        and data_type in s.get("use_for", [])
        and registry.is_enabled(s)
    ]
    return sorted(matches, key=lambda s: s.get("rank", 0), reverse=True)


def pick_primary(sport: str, data_type: str, sources: list | None = None):
    ordered = resolve(sport, data_type, sources)
    return ordered[0] if ordered else None


def fallback_chain(sport: str, data_type: str, sources: list | None = None) -> list:
    ordered = resolve(sport, data_type, sources)
    return ordered[1:]


def should_update(existing_rank, new_rank, existing_has_value: bool) -> bool:
    """Whether a new value from `new_rank` should replace the stored one.

    - If there is no existing value, always store it.
    - If there is an existing value, only promote it when the new source has a
      strictly higher rank than the source that produced the current value.
    """
    if not existing_has_value:
        return True
    if existing_rank is None:
        return True
    return new_rank > existing_rank
