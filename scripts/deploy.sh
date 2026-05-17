#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[deploy]${NC} $*"; }
err() { echo -e "${RED}[deploy]${NC} $*" >&2; }

# 1. Проверка чистоты working tree
if [[ -n "$(git status --porcelain)" ]]; then
    err "Working tree is not clean. Commit, stash or discard changes first:"
    git status --short
    exit 1
fi

# 2. Сохранить текущий commit перед обновлением (для возможного rollback)
PREV_COMMIT=$(git rev-parse HEAD)
echo "${PREV_COMMIT}" > .last-deployed-commit
log "Previous commit saved: ${PREV_COMMIT:0:7}"

# 3. Pull
log "Pulling latest from origin/main..."
git pull origin main
NEW_COMMIT=$(git rev-parse HEAD)

if [[ "${PREV_COMMIT}" == "${NEW_COMMIT}" ]]; then
    log "Already up to date at ${NEW_COMMIT:0:7}. Nothing to deploy."
    exit 0
fi

log "Updating ${PREV_COMMIT:0:7} → ${NEW_COMMIT:0:7}"

# 4. Generate build info
log "Generating build info..."
bash scripts/generate_build_info.sh > /dev/null

# 5. Build images
log "Building Docker images..."
docker compose build bot worker scheduler

# 6. Run migrations (idempotent)
log "Running database migrations..."
docker compose run --rm bot alembic upgrade head

# 7. Recreate services
log "Recreating services..."
docker compose up -d bot worker scheduler

# 8. Wait for healthy
log "Waiting for services to be healthy (max 30s)..."
TIMEOUT=30
ELAPSED=0
while [[ $ELAPSED -lt $TIMEOUT ]]; do
    if docker compose ps --format json | grep -q '"Health":"healthy"'; then
        sleep 2  # Подождём ещё немного, чтобы все 3 сервиса успели
        UNHEALTHY=$(docker compose ps --format json | \
                    python3 -c "import json,sys; data=[json.loads(l) for l in sys.stdin if l]; print(sum(1 for s in data if s.get('Health') and s['Health']!='healthy'))")
        if [[ "$UNHEALTHY" == "0" ]]; then
            break
        fi
    fi
    sleep 2
    ELAPSED=$((ELAPSED+2))
done

if [[ $ELAPSED -ge $TIMEOUT ]]; then
    warn "Services did not become healthy within ${TIMEOUT}s. Check logs:"
    docker compose ps
    exit 1
fi

# 9. Health check via bot endpoint
log "Health check via HTTP..."
if ! curl -sf http://127.0.0.1:8080/health > /dev/null; then
    err "Bot /health endpoint not responding 200"
    exit 1
fi

# 10. Status
log "Deployment successful: ${PREV_COMMIT:0:7} → ${NEW_COMMIT:0:7}"
echo ""
docker compose ps
echo ""
log "Recent logs:"
docker compose logs bot --tail 10 --no-log-prefix | sed 's/^/  /'
