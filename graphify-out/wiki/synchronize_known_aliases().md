# synchronize_known_aliases()

> God node · 17 connections · `backend/app/services/lol_team_aliases.py`

**Community:** [Match Events & Odds Models](Match_Events_%26_Odds_Models.md)

## Connections by Relation

### calls
- rebuild_series() `EXTRACTED`
- _synchronize_history() `EXTRACTED`
- LolTeamAlias `EXTRACTED`
- normalize_text() `EXTRACTED`
- lifespan() `EXTRACTED`
- test_known_aliases_reconcile_renamed_teams() `EXTRACTED`
- synchronize_aliases() `EXTRACTED`

### contains
- lol_team_aliases.py `EXTRACTED`

### imports
- sources.py `EXTRACTED`
- test_pages.py `EXTRACTED`
- main.py `EXTRACTED`

### indirect_call
- [LolMatchEvent](LolMatchEvent.md) `INFERRED`
- [LolGameHistory](LolGameHistory.md) `INFERRED`
- [LolTeamGameStat](LolTeamGameStat.md) `INFERRED`
- LolPlayerGameStat `INFERRED`

### rationale_for
- Persist verified renames and normalize affected schedule/history rows. `EXTRACTED`

### references
- Session `EXTRACTED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*