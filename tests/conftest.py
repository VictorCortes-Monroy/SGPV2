"""Fixtures globales de pytest.

Para tests de integración usamos SQLite en memoria. Los modelos son agnósticos
del dialecto (excepto el JSON que en SQLite se serializa como TEXT, lo cual
es transparente).

NOTA: el trigger PL/pgSQL del audit_log no se aplica en SQLite (es PostgreSQL
específico). Para tests que requieran validar la inmutabilidad real, hay que
correr contra una DB Postgres real.
"""

import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

# Por defecto SQLite ANTES de importar la app. setdefault para que la suite
# de integración (tests/integration/) pueda inyectar un DATABASE_URL de
# Postgres desde el entorno sin que esto lo pise.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("AUTH_MODE", "mock")

# Path src/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sgp.core.database import Base


@pytest_asyncio.fixture
async def db_engine():
    """Engine en memoria para cada test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    # Importa los modelos para que Base.metadata los conozca
    from sgp.modules.auditoria import models as _a  # noqa: F401
    from sgp.modules.catalogo import models as _c  # noqa: F401
    from sgp.modules.empresas import models as _e  # noqa: F401
    from sgp.modules.solicitudes import models as _s  # noqa: F401
    from sgp.modules.usuarios import models as _u  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Sesión de DB para un test. Rollback automático al final."""
    async_session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def fixed_now():
    """Devuelve un timestamp fijo para tests deterministas."""
    from datetime import UTC, datetime
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
