"""Smoke tests contra Postgres real.

Estos tests detectan bugs específicos del dialecto que SQLite no captura:
- Mismatches entre el enum nativo de Postgres y los enums de Python.
- Triggers PL/pgSQL (RN5: audit_log append-only).
- Tipos JSON, constraints CHECK específicos de Postgres, etc.

Pre-requisitos: `DATABASE_URL` debe apuntar a un Postgres con migraciones
y seed aplicados. Si no, la suite se salta automáticamente (ver
`tests/integration/conftest.py`).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from sgp.modules.auditoria.models import AuditLog
from sgp.modules.solicitudes.models import SolicitudCompra, TipoCompra, Urgencia
from sgp.modules.solicitudes.state_machine import SCStatus
from sgp.modules.usuarios.models import Usuario

pytestmark = pytest.mark.postgres


async def _get_user(session: AsyncSession, clerk_user_id: str) -> Usuario:
    return (
        await session.execute(select(Usuario).where(Usuario.clerk_user_id == clerk_user_id))
    ).scalar_one()


async def test_sc_status_enum_se_persiste_correctamente(pg_session: AsyncSession):
    """Detectaría el bug donde SQLAlchemy serializa el enum por .name (mayúsculas)
    pero `sc_status_enum` en Postgres existe con los .value (minúsculas)."""
    user = await _get_user(pg_session, "user_victor")

    sc = SolicitudCompra(
        numero="TEST-SMOKE-ENUM",
        empresa_id=1,
        centro_costo_id=1,
        solicitante_id=user.id,
        tipo=TipoCompra.BIEN,
        urgencia=Urgencia.NORMAL,
        descripcion="Smoke: SCStatus → .value",
        monto_estimado=Decimal("1000"),
        fecha_requerida=date(2026, 12, 31),
    )
    pg_session.add(sc)
    await pg_session.flush()  # INSERT — el bug del enum explotaba acá

    sc_id = sc.id
    pg_session.expunge_all()
    refetched = await pg_session.get(SolicitudCompra, sc_id)
    assert refetched is not None
    assert refetched.status == SCStatus.DRAFT


@pytest.mark.parametrize(
    "target_status",
    [
        SCStatus.PENDING_AREA_APPROVAL,
        SCStatus.PENDING_BUDGET,
        SCStatus.PENDING_MANAGEMENT_APPROVAL,  # nuevo estado RN-MONTO-2
        SCStatus.CLOSED,
    ],
)
async def test_sc_status_update_persiste(pg_session: AsyncSession, target_status: SCStatus):
    """Asegura que el UPDATE del status también respeta el .value, no solo el INSERT default."""
    user = await _get_user(pg_session, "user_victor")
    sc = SolicitudCompra(
        numero=f"TEST-SMOKE-{target_status.value}",
        empresa_id=1,
        centro_costo_id=1,
        solicitante_id=user.id,
        tipo=TipoCompra.BIEN,
        urgencia=Urgencia.NORMAL,
        descripcion="Smoke transition",
        monto_estimado=Decimal("1000"),
        fecha_requerida=date(2026, 12, 31),
    )
    pg_session.add(sc)
    await pg_session.flush()

    sc.status = target_status
    await pg_session.flush()

    sc_id = sc.id
    pg_session.expunge_all()
    refetched = await pg_session.get(SolicitudCompra, sc_id)
    assert refetched.status == target_status


async def test_audit_log_rn5_trigger_bloquea_update(pg_session: AsyncSession):
    """RN5: trigger `prevent_audit_log_modification` debe bloquear cualquier UPDATE."""
    admin = await _get_user(pg_session, "user_admin")
    entry = AuditLog(
        entity_type="test",
        entity_id="0",
        action="SMOKE",
        actor_id=admin.id,
        actor_role="admin",
        before_state=None,
        after_state={"smoke": True},
    )
    pg_session.add(entry)
    await pg_session.flush()

    with pytest.raises(DBAPIError, match="audit_log es append-only"):
        await pg_session.execute(
            text("UPDATE audit_log SET action = :a WHERE id = :id").bindparams(
                a="HACKED", id=entry.id
            )
        )


async def test_audit_log_rn5_trigger_bloquea_delete(pg_session: AsyncSession):
    """RN5: el mismo trigger también debe bloquear DELETE."""
    admin = await _get_user(pg_session, "user_admin")
    entry = AuditLog(
        entity_type="test",
        entity_id="0",
        action="SMOKE",
        actor_id=admin.id,
        actor_role="admin",
        before_state=None,
        after_state={"smoke": True},
    )
    pg_session.add(entry)
    await pg_session.flush()

    with pytest.raises(DBAPIError, match="audit_log es append-only"):
        await pg_session.execute(
            text("DELETE FROM audit_log WHERE id = :id").bindparams(id=entry.id)
        )
