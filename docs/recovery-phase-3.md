# Recovery phase 3 — canonical markets and safe no-vig

## Baseline

Phase 2 second controlled sync completed successfully: run 126, 940 odds, 4 events, 0 errors. SQLite integrity was `ok` before backup and in `backups/pirapire-phase3-pre-migration-20260711.db`.

Active baseline: 1,880 odds and 456 provider market IDs. Legacy rows without IDs remain fallback-labelled and are not falsely classified.

## Market identity

New provider odds preserve `source_market_id`/`source_outcome_id`, raw market/outcome labels, canonical `market_key`/`outcome_key`, map, period, player, participant and role dimensions. Provider IDs take precedence; canonical hashes are deterministic fallback. Market count is distinct market keys; odds count is separate.

## Mapping and no-vig

Kambi has no `map_winner` fallback: unknown labels stay `None` / Sin clasificar. Explicit observed classifications include series/map winner, score, totals, handicap, kills/deaths, duration, turrets, inhibitors and player props. No-vig is only available for complete football 1X2 or two-outcome O/U / double-chance groups. Grouping is by canonical/provider market key; LoL remains disabled with a displayed reason.

## Validation

Focused test suite: 9 passed (Phase 2 + Phase 3). Ruff for modified files, compileall, node check and diff check passed. The app, worker and browser containers were healthy after migration.

The Phase 3 controlled syncs are intentionally left for the running scheduled window; no concurrent sync was started during implementation.


## 3B final verification

| Feed | current snapshot | active odds | events | outcomes |
| --- | ---: | ---: | ---: | ---: |
| aposta_la | 23 | 5 | 1 | 5 |
| kambi | 24 | 935 | 3 | 935 |

The former 1,880 active rows were exactly 940 legacy rows without a capture plus 940 captured rows. The legacy rows were marked non-current, retained as history, and the scheduled sync confirmed **940** active captured odds thereafter.

Two sequential controlled syncs completed: run 132 and run 133, each parsed 940 odds / 4 events with zero errors. Before run 132 and after run 133: events 421, canonical markets 796, canonical outcomes 1,631, active odds 940. Current active rows have zero null snapshot IDs and zero references to non-current snapshots; there is exactly one current snapshot per feed.

LoL groups with four outcomes are inspected as raw correct-score markets; no-vig remains disabled for all LoL groups, so none is normalized or mixed. Football no-vig is limited to the validated complete groups. Detail endpoints were verified in Phase 2 for the World Cup and LoL event keys; their active odds now originate only from snapshots 23/24.
