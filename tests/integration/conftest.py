"""Fixtures para tests de integración contra Postgres real.

A diferencia de los tests unitarios (SQLite en memoria), estos tests
ejercen el ORM contra el motor real para detectar bugs específicos del
dialecto: enums nativos, triggers PL/pgSQL, tipos JSON, etc.

Requiere:
    DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
    + migraciones aplicadas (`alembic upgrade head`)
    + seed cargado (`python scripts/seed.py`)

Si DATABASE_URL no apunta a Postgres, todos los tests del módulo se
saltan automáticamente.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Importar todos los modelos para que SQLAlchemy resuelva las FKs entre tablas
# en su MetaData. Sin estos imports, mapear SolicitudCompra solo falla porque
# la FK a `centros_costo` no encuentra el modelo de empresas.
from sgp.modules.adjuntos import models as _adj  # noqa: F401
from sgp.modules.auditoria import models as _a  # noqa: F401
from sgp.modules.catalogo import models as _c  # noqa: F401
from sgp.modules.empresas import models as _e  # noqa: F401
from sgp.modules.solicitudes import models as _s  # noqa: F401
from sgp.modules.usuarios import models as _u  # noqa: F401


def _postgres_url() -> str | None:
    url = os.environ.get("DATABASE_URL", "")
    if "postgres" not in url:
        return None
    return url


@pytest.fixture(scope="session")
def pg_url() -> str:
    url = _postgres_url()
    if url is None:
        pytest.skip("DATABASE_URL no apunta a Postgres — saltando smoke tests de integración")
    return url


@pytest_asyncio.fixture
async def pg_engine(pg_url: str):
    """Engine con scope de función. Evita conflictos con el event loop
    function-scope de pytest-asyncio (asyncpg + loop cerrado)."""
    engine = create_async_engine(pg_url, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session(pg_engine) -> AsyncGenerator[AsyncSession, None]:
    """Sesión envuelta en una transacción que siempre se rolloutea al final.

    Aunque el test llame a session.commit(), eso solo libera un savepoint
    interno; la transacción exterior se descarta. Permite ejercer el flujo
    real del ORM contra Postgres sin contaminar la BD entre tests.
    """
    async with pg_engine.connect() as conn:
        outer = await conn.begin()
        Session = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        async with Session() as session:
            yield session
        await outer.rollback()
