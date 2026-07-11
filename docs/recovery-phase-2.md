# Recovery phase 2 — stable event identity, snapshots and Paraguay time

## Scope

Phase 2 replaces public `ImportedOdds.id` event identity with `event_key`; it does not alter the LoL no-vig algorithm, models, or recommendations.

## Migration and rollback

`aposta_snapshot.run_migrations` is expand-only and idempotent. Before the first SQLite expansion it runs `PRAGMA integrity_check`, creates `pirapire.db.phase2-pre-migration.bak`, and verifies the backup integrity. An operational pre-migration copy was also made at `backups/pirapire-phase2-pre-migration-20260711.db`.

Rollback is application rollback plus restoring that verified SQLite copy while the services are stopped. No historical odds, old batches, snapshots, or events are deleted.

## Identity matrix

| Source | source_event_id | event_key method |
| --- | --- | --- |
| Kambi | published event id | SHA-256 of `native, source, source_event_id` |
| Aposta HTML / CSV | unavailable | SHA-256 of `derived, source, sport, canonical teams, competition, kickoff UTC` |

Both teams, sport, and UTC kickoff are mandatory in derived keys. Quotas, run/batch/snapshot IDs and `ImportedOdds.id` are excluded. A derived-key collision raises an explicit error.

## Capture graph

Each source response has an immutable `CaptureSnapshot` with source, start/end, status, raw SHA-256 and row count. Imported odds point to that snapshot and to canonical event, market and outcome rows. Only the newest successful snapshot per source is current; a changed price produces another historical odd version. Events absent from a current source capture become `expired`, never deleted.

## Time handling

Raw kickoff text is retained. Relative Aposta labels are resolved in `America/Asuncion`, converted to UTC once, then stored in `kickoff_utc`. Kambi timestamps are parsed as UTC. `event_time_display` is the single dashboard/calendar/detail/API formatter and displays in Paraguay time.

## Compatibility

Public HTML is `/events/{event_key}` and JSON uses `/api/events/{event_key}` plus `/statistics`. A legacy numeric ID redirects with 308 only when it maps to exactly one event key; missing and ambiguous IDs return 404/409.

## Verification evidence

- SQLite integrity before backup: `ok`; backup integrity: `ok`.
- Three containers were healthy after migration build.
- Automated test, lint, compile, browser capture, sync and final counts are recorded after the controlled double sync in this report's final update.
