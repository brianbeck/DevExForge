#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"

echo "=== DevExForge Local Development Setup ==="
echo ""

# 1. Start infrastructure
echo "Starting PostgreSQL + Keycloak..."
cd "$PROJECT_DIR"
docker compose up -d postgres
echo "Waiting for PostgreSQL to be ready..."
until docker compose exec -T postgres pg_isready -U devexforge > /dev/null 2>&1; do
    sleep 1
done
echo "PostgreSQL is ready."
docker compose up -d keycloak
echo "Keycloak starting (takes ~30s)..."

# 2. Create/activate virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# 3. Install API dependencies
echo ""
echo "Installing API dependencies..."
pip install -e "$PROJECT_DIR/api"

# 4. Run migrations
echo ""
echo "Running database migrations..."
cd "$PROJECT_DIR/api"
alembic upgrade head
echo "Migrations complete."

# 5. Install CLI
echo ""
echo "Installing CLI..."
pip install -e "$PROJECT_DIR/cli"

# 6. Install portal dependencies
echo ""
echo "Installing portal dependencies..."
cd "$PROJECT_DIR/portal"
npm install

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Activate the venv:   source .venv/bin/activate"
echo ""
echo "Keycloak:  http://localhost:8080  (admin/admin)"
echo "  Realm:   teams"
echo "  Users:   admin/admin123, teamlead1/password123, developer1/password123"
echo ""
echo "To start the API:    cd api && uvicorn app.main:app --reload"
echo "To start the portal: cd portal && npm run dev"
echo "API docs:            http://localhost:8000/docs"
echo "Portal:              http://localhost:5173"
