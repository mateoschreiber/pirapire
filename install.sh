#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[pirapire]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

REPO="https://github.com/mateoschreiber/pirapire.git"
INSTALL_DIR="${PIrapire_HOME:-$HOME/pirapire}"

log "Pirapire auto-install"
log "Install dir: $INSTALL_DIR"

command -v git    >/dev/null 2>&1 || err "git is required"
command -v docker >/dev/null 2>&1 || err "docker is required"

docker compose version >/dev/null 2>&1 || {
    if docker compose version >/dev/null 2>&1; then
        ok "docker compose (plugin)"
    else
        err "docker compose v2 is required"
    fi
}

if [ -d "$INSTALL_DIR/.git" ]; then
    log "Updating existing repo..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    log "Cloning repo..."
    git clone "$REPO" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

if [ ! -f .env ]; then
    log "Creating .env from .env.example..."
    cp .env.example .env
    ok ".env created (edit as needed)"
fi

mkdir -p data/imports/lol_odds data/imports/oracles logs

log "Building and starting containers..."
docker compose up -d --build

sleep 5

if curl -fsS "http://localhost:${PIRAPIRE_PORT:-8090}/health" >/dev/null 2>&1; then
    ok "Pirapire is running at http://localhost:${PIRAPIRE_PORT:-8090}"
else
    log "Waiting for health check..."
    sleep 10
    curl -fsS "http://localhost:${PIRAPIRE_PORT:-8090}/health" >/dev/null 2>&1 \
        && ok "Pirapire is running at http://localhost:${PIRAPIRE_PORT:-8090}" \
        || err "Health check failed. Check logs: docker compose logs"
fi

echo ""
echo -e "${GREEN}=== Pirapire installed successfully ===${NC}"
echo "Dashboard:  http://localhost:${PIRAPIRE_PORT:-8090}"
echo "API:        http://localhost:${PIRAPIRE_PORT:-8090}/api/lol/matches/upcoming"
echo "Health:     http://localhost:${PIRAPIRE_PORT:-8090}/health"
echo "Logs:       docker compose logs -f"
echo "Stop:       docker compose down"
