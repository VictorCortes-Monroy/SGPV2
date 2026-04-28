FROM python:3.12-slim

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar pyproject.toml + src para que hatchling encuentre el paquete
# en el editable install. Si solo cambia src/ sin tocar pyproject.toml,
# el cache de la capa de pip se reutiliza salvo el reinstall.
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --upgrade pip && \
    pip install -e ".[dev]"

# Resto del código
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY scripts/ ./scripts/
COPY tests/ ./tests/

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${APP_PORT:-8000}/health || exit 1

EXPOSE 8000

# Railway pasa $PORT — usamos shell form para que se expanda
CMD uvicorn sgp.main:app --host 0.0.0.0 --port ${PORT:-8000}
