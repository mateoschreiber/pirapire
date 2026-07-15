-- Pirapire Phase 1: LoL-only migration
-- Run this from the container: sqlite3 /app/data/pirapire.db < /app/migrate_phase1.sql
-- Or use Python sqlite3 to execute it transactionally.

BEGIN TRANSACTION;

-- Drop legacy tables (football, aposta, kambi, betting, recommendations)
DROP TABLE IF EXISTS sport;
DROP TABLE IF EXISTS team;
DROP TABLE IF EXISTS match;
DROP TABLE IF EXISTS importedodds;
DROP TABLE IF EXISTS oddssnapshot;
DROP TABLE IF EXISTS apostasyncrun;
DROP TABLE IF EXISTS apostaevent;
DROP TABLE IF EXISTS apostamarket;
DROP TABLE IF EXISTS apostaselection;
DROP TABLE IF EXISTS capturesnapshot;
DROP TABLE IF EXISTS canonicalmarket;
DROP TABLE IF EXISTS canonicaloutcome;
DROP TABLE IF EXISTS refreshqueue;
DROP TABLE IF EXISTS marketcatalog;
DROP TABLE IF EXISTS marketalias;
DROP TABLE IF EXISTS marketsourcerequirement;
DROP TABLE IF EXISTS recommendationrun;
DROP TABLE IF EXISTS betrecommendation;
DROP TABLE IF EXISTS comborecommendation;
DROP TABLE IF EXISTS comborecommendationleg;
DROP TABLE IF EXISTS predictionhistory;
DROP TABLE IF EXISTS combohistory;
DROP TABLE IF EXISTS comboleghistory;
DROP TABLE IF EXISTS footballteamstat;
DROP TABLE IF EXISTS footballplayerstat;
DROP TABLE IF EXISTS footballgame;
DROP TABLE IF EXISTS footballcompetition;
DROP TABLE IF EXISTS footballstanding;
DROP TABLE IF EXISTS sourcecredential;
DROP TABLE IF EXISTS sourcesyncstate;
DROP TABLE IF EXISTS sourcerun;
DROP TABLE IF EXISTS manualimportbatch;
DROP TABLE IF EXISTS manualimporterror;
DROP TABLE IF EXISTS eventmatch;
DROP TABLE IF EXISTS eventmatcherrun;

-- Ensure solo_kills column exists on lolplayergamestat
-- SQLite does not support ADD COLUMN IF NOT EXISTS; handle error gracefully

-- Verify integrity
PRAGMA foreign_key_check;
PRAGMA integrity_check;

COMMIT;

VACUUM;
