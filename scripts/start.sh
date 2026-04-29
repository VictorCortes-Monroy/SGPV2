#!/bin/bash
# Entrypoint de Railway / producción.
# Aplica migraciones, opcionalmente seedea (controlado por SEED_ON_STARTUP), y
# arranca uvicorn en el puerto que Railway inyecte.
set -euo pipefail

echo "▸ Aplicando migraciones Alembic..."
alembic upgrade head

if [ "${SEED_ON_STARTUP:-false}" = "true" ]; then
    echo "▸ SEED_ON_STARTUP=true → corriendo seed (idempotente)..."
    python scripts/seed.py
else
    echo "▸ SEED_ON_STARTUP no es 'true' → seed omitido."
fi

echo "▸ Levantando uvicorn en puerto ${PORT:-8000}..."
exec uvicorn sgp.main:app --host 0.0.0.0 --port "${PORT:-8000}"
