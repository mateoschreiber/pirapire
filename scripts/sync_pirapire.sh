#!/bin/bash
set -e
LOG_FILE="/opt/pirapire/logs/sync_cron.log"
PORT="8090"
exec >> "$LOG_FILE" 2>&1
echo "=== $(date) === Starting Pirapire sync"
echo "[1/3] Seeding sources..."
curl -sf -X POST "http://localhost:${PORT}/sources/seed" > /dev/null || { echo "FAIL: seed failed"; exit 1; }
echo "[2/3] Syncing LoL..."
curl -sf -X POST "http://localhost:${PORT}/sources/sync/lol" > /dev/null || { echo "FAIL: lol sync failed"; exit 1; }
sleep 5
echo "[3/3] Syncing Football..."
curl -sf -X POST "http://localhost:${PORT}/sources/sync/football" > /dev/null || { echo "FAIL: football sync failed"; exit 1; }
sleep 30
echo "=== $(date) === Sync completed successfully"
