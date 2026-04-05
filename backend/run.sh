#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# YAAP Backend — run.sh
# One script to rule them all.
#
# Usage:
#   ./run.sh            → start the full backend (web + redis + celery)
#   ./run.sh migrate    → apply migrations only
#   ./run.sh seed       → seed voice sentences
#   ./run.sh check      → Django system check + dep audit
#   ./run.sh reset      → wipe SQLite test DB and restart fresh
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
header()  { echo -e "\n${BOLD}${BLUE}══ $* ══${NC}\n"; }

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE=".env"
VENV_DIR=".venv"
PYTHON="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"
MANAGE="${PYTHON} manage.py"

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-yaap.settings}"

# ── Helpers ───────────────────────────────────────────────────────────────────

check_command() {
    command -v "$1" &>/dev/null || { error "$1 is required but not installed."; exit 1; }
}

check_env() {
    if [ ! -f "$ENV_FILE" ]; then
        warn ".env not found — copying from .env.example"
        cp .env.example "$ENV_FILE"
        warn "Edit .env with your Supabase / Redis credentials before running the server."
    fi
}

setup_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        info "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
        success "Virtual environment created at ${VENV_DIR}"
    fi
    info "Installing Python dependencies..."
    "$PIP" install --upgrade pip --quiet
    "$PIP" install -r requirements.txt --quiet
    success "Dependencies installed."
}

run_migrations() {
    info "Running migrations..."
    $MANAGE migrate --run-syncdb 2>&1 | tail -5
    success "Migrations complete."
}

seed_data() {
    info "Seeding voice training sentences (17 languages × 5)..."
    $MANAGE load_voice_sentences 2>&1
    success "Voice sentences seeded."
}

check_redis() {
    if command -v redis-cli &>/dev/null; then
        if redis-cli ping &>/dev/null; then
            success "Redis is running."
            return 0
        fi
    fi
    warn "Redis not detected — attempting to start via Docker..."
    if command -v docker &>/dev/null; then
        docker run -d --name yaap_redis -p 6379:6379 redis:7-alpine &>/dev/null || true
        sleep 2
        success "Redis started via Docker."
    else
        error "Redis is required. Install Redis or Docker first."
        exit 1
    fi
}

# ── Commands ──────────────────────────────────────────────────────────────────

cmd_check() {
    header "System check"
    check_command python3
    check_command pip3
    check_env
    setup_venv
    $MANAGE check --deploy 2>&1 || true
    $MANAGE check 2>&1
    success "Django check passed."
}

cmd_migrate() {
    header "Migrations"
    check_env
    setup_venv
    run_migrations
}

cmd_seed() {
    header "Seed data"
    check_env
    setup_venv
    run_migrations
    seed_data
}

cmd_test() {
    warn "Automated tests are not included in this repository."
    exit 0
}

cmd_start() {
    header "Starting YAAP backend"
    check_env
    setup_venv
    check_redis
    run_migrations
    seed_data

    # Start Celery worker in background
    info "Starting Celery worker..."
    "$VENV_DIR/bin/celery" -A yaap worker \
        --loglevel=info \
        --queues=default,email,voice_training,translation \
        --concurrency=2 \
        --detach \
        --pidfile=/tmp/yaap_celery.pid \
        --logfile=/tmp/yaap_celery.log
    success "Celery worker started (log: /tmp/yaap_celery.log)"

    # Start Daphne
    info "Starting Django ASGI server on http://localhost:8000 ..."
    echo ""
    echo -e "${GREEN}  ✓ Backend running at http://localhost:8000${NC}"
    echo -e "${GREEN}  ✓ API docs at   http://localhost:8000/api/docs/${NC}"
    echo -e "${GREEN}  ✓ Admin panel   http://localhost:8000/admin/${NC}"
    echo -e "${YELLOW}  Press Ctrl+C to stop${NC}"
    echo ""
    "$VENV_DIR/bin/daphne" -b 0.0.0.0 -p 8000 yaap.asgi:application
}

cmd_reset() {
    header "Reset"
    rm -f db.sqlite3
    find . -path "*/migrations/0*.py" ! -name "__init__.py" -delete 2>/dev/null || true
    info "Regenerating migrations..."
    $MANAGE makemigrations accounts friendships messaging calls voice 2>&1
    run_migrations
    seed_data
    success "Reset complete."
}

# ── Dispatcher ────────────────────────────────────────────────────────────────

COMMAND="${1:-start}"

case "$COMMAND" in
    start)   cmd_start   "$@" ;;
    test)    cmd_test    "$@" ;;  # no-op: suite removed from repo
    migrate) cmd_migrate "$@" ;;
    seed)    cmd_seed    "$@" ;;
    check)   cmd_check   "$@" ;;
    reset)   cmd_reset   "$@" ;;
    *)
        echo "Usage: ./run.sh [start|migrate|seed|check|reset]"
        exit 1
        ;;
esac
