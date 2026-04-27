"""Test de integración: flujo end-to-end de una SC desde DRAFT hasta CLOSED.

Valida que el service ejecute correctamente las transiciones, persista los
cambios y registre cada acción en el audit_log. Usa SQLite en memoria.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from sgp.core.exceptions import InvalidTransitionError, PermissionDenied
from sgp.modules.auditoria.models import AuditLog
from sgp.modules.catalogo.models import (
    CatalogoItem,
    Criticidad,
    Familia,
    UnidadMedida,
)
from sgp.modules.empresas.models import CentroCosto, Empresa
from sgp.modules.solicitudes.models import TipoCompra, Urgencia
from sgp.modules.solicitudes.schemas import (
    LineaCreate,
    SolicitudCompraCreate,
    TransitionRequest,
)
from sgp.modules.solicitudes.service import SolicitudCompraService
from sgp.modules.solicitudes.state_machine import SCAction, SCStatus
from sgp.modules.usuarios.models import Rol, Usuario, usuario_roles_table


@pytest.fixture
async def setup_basico(db_session):
    """Crea datos mínimos: usuarios con roles, empresa, CC, item del catálogo."""
    # Roles
    roles = {
        nombre: Rol(nombre=nombre, descripcion=f"Rol {nombre}")
        for nombre in ["solicitante", "jefe_area", "finanzas", "abastecimiento", "gerencia"]
    }
    for r in roles.values():
        db_session.add(r)
    await db_session.flush()

    # Usuarios
    def _user(clerk_id, email, nombre, role_names):
        u = Usuario(clerk_user_id=clerk_id, email=email, nombre=nombre, activo=True)
        db_session.add(u)
        return u, role_names

    u_sol, sol_roles = _user("u_sol", "sol@x.cl", "Solicitante", ["solicitante"])
    u_jefe, jefe_roles = _user("u_jefe", "jefe@x.cl", "Jefe", ["jefe_area"])
    u_fin, fin_roles = _user("u_fin", "fin@x.cl", "Finanzas", ["finanzas"])
    u_abast, abast_roles = _user("u_abast", "ab@x.cl", "Abast", ["abastecimiento"])
    u_ger, ger_roles = _user("u_ger", "ger@x.cl", "Gerente", ["gerencia"])
    await db_session.flush()

    for u, role_names in [
        (u_sol, sol_roles),
        (u_jefe, jefe_roles),
        (u_fin, fin_roles),
        (u_abast, abast_roles),
        (u_ger, ger_roles),
    ]:
        for rn in role_names:
            await db_session.execute(
                usuario_roles_table.insert().values(
                    usuario_id=u.id, rol_id=roles[rn].id, empresa_id=None
                )
            )

    # Empresa y CC
    emp = Empresa(rut="76123456-7", razon_social="Demo", nombre_corto="DEMO")
    db_session.add(emp)
    await db_session.flush()
    cc = CentroCosto(empresa_id=emp.id, codigo="CC-001", nombre="Mantención")
    db_session.add(cc)
    await db_session.flush()

    # Catálogo
    fam = Familia(nombre="Repuestos", nivel=1)
    db_session.add(fam)
    await db_session.flush()
    item = CatalogoItem(
        sku="ITM-TEST-001",
        nombre="Item Test",
        familia_id=fam.id,
        unidad_medida=UnidadMedida.UN,
        precio_referencia=Decimal("10000"),
        criticidad=Criticidad.ESTANDAR,
    )
    db_session.add(item)
    await db_session.flush()

    # Recargar usuarios con roles eager-loaded
    from sqlalchemy.orm import selectinload
    result = await db_session.execute(
        select(Usuario).options(selectinload(Usuario.roles))
    )
    usuarios = {u.clerk_user_id: u for u in result.scalars().all()}

    return {
        "usuarios": usuarios,
        "empresa": emp,
        "cc": cc,
        "item": item,
    }


@pytest.fixture
def payload_sc(setup_basico):
    return SolicitudCompraCreate(
        empresa_id=setup_basico["empresa"].id,
        centro_costo_id=setup_basico["cc"].id,
        tipo=TipoCompra.BIEN,
        urgencia=Urgencia.NORMAL,
        descripcion="Compra de repuesto crítico para mantención preventiva",
        justificacion="Mantención programada de equipo CAT 320",
        monto_estimado=Decimal("150000"),
        fecha_requerida=date.today() + timedelta(days=30),
        lineas=[LineaCreate(item_id=setup_basico["item"].id, cantidad=Decimal("3"))],
    )


class TestCreacionSC:
    async def test_create_sc_genera_numero_correlativo(self, db_session, setup_basico, payload_sc):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        assert sc.id is not None
        assert sc.numero.startswith("SC-")
        assert sc.status == SCStatus.DRAFT
        assert sc.recotization_cycles == 0
        assert len(sc.lineas) == 1

    async def test_create_sc_registra_audit_log(self, db_session, setup_basico, payload_sc):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.entity_type == "solicitud_compra",
                AuditLog.entity_id == str(sc.id),
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) == 1
        assert logs[0].action == "CREATE"
        assert logs[0].actor_id == setup_basico["usuarios"]["u_sol"].id


class TestTransiciones:
    async def test_solicitante_puede_submit(self, db_session, setup_basico, payload_sc):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        sc = await service.apply_transition(
            sc.id,
            TransitionRequest(action=SCAction.SUBMIT),
            setup_basico["usuarios"]["u_sol"],
        )
        assert sc.status == SCStatus.PENDING_AREA_APPROVAL

    async def test_jefe_puede_aprobar(self, db_session, setup_basico, payload_sc):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )

        sc = await service.apply_transition(
            sc.id,
            TransitionRequest(action=SCAction.APPROVE_AREA, comment="Aprobado para preventiva"),
            setup_basico["usuarios"]["u_jefe"],
        )
        assert sc.status == SCStatus.PENDING_BUDGET
        assert sc.approved_by_area_id == setup_basico["usuarios"]["u_jefe"].id

    async def test_solicitante_no_puede_aprobar(self, db_session, setup_basico, payload_sc):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )

        with pytest.raises(PermissionDenied):
            await service.apply_transition(
                sc.id,
                TransitionRequest(action=SCAction.APPROVE_AREA),
                setup_basico["usuarios"]["u_sol"],
            )

    async def test_no_puede_aprobar_desde_draft(self, db_session, setup_basico, payload_sc):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        with pytest.raises(InvalidTransitionError):
            await service.apply_transition(
                sc.id,
                TransitionRequest(action=SCAction.APPROVE_AREA),
                setup_basico["usuarios"]["u_jefe"],
            )


class TestRecotizacion:
    async def test_excede_max_recotizaciones_bloquea(self, db_session, setup_basico, payload_sc):
        """RN8: máximo 2 ciclos de recotización."""
        from sgp.core.exceptions import BusinessRuleViolation

        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        # Avanzar hasta PENDING_VALORIZATION
        for action, actor in [
            (SCAction.SUBMIT, setup_basico["usuarios"]["u_sol"]),
            (SCAction.APPROVE_AREA, setup_basico["usuarios"]["u_jefe"]),
            (SCAction.RELEASE_BUDGET, setup_basico["usuarios"]["u_fin"]),
            (SCAction.REGISTER_QUOTATIONS, setup_basico["usuarios"]["u_abast"]),
            (SCAction.SEND_VALORIZATION, setup_basico["usuarios"]["u_abast"]),
        ]:
            sc = await service.apply_transition(
                sc.id, TransitionRequest(action=action), actor
            )
        assert sc.status == SCStatus.PENDING_VALORIZATION

        # 1ª recotización (queda en cycles=1, OK)
        sc = await service.apply_transition(
            sc.id,
            TransitionRequest(action=SCAction.REQUEST_RECOTIZATION, comment="Mejor precio"),
            setup_basico["usuarios"]["u_jefe"],
        )
        assert sc.recotization_cycles == 1
        assert sc.status == SCStatus.PENDING_QUOTATION

        # Volver a valorización
        for action, actor in [
            (SCAction.REGISTER_QUOTATIONS, setup_basico["usuarios"]["u_abast"]),
            (SCAction.SEND_VALORIZATION, setup_basico["usuarios"]["u_abast"]),
        ]:
            sc = await service.apply_transition(
                sc.id, TransitionRequest(action=action), actor
            )

        # 2ª recotización (cycles=2, OK)
        sc = await service.apply_transition(
            sc.id,
            TransitionRequest(action=SCAction.REQUEST_RECOTIZATION, comment="Otra opción"),
            setup_basico["usuarios"]["u_jefe"],
        )
        assert sc.recotization_cycles == 2

        # Volver a valorización
        for action, actor in [
            (SCAction.REGISTER_QUOTATIONS, setup_basico["usuarios"]["u_abast"]),
            (SCAction.SEND_VALORIZATION, setup_basico["usuarios"]["u_abast"]),
        ]:
            sc = await service.apply_transition(
                sc.id, TransitionRequest(action=action), actor
            )

        # 3ª recotización: BUSINESS RULE VIOLATION
        with pytest.raises(BusinessRuleViolation, match="máximo"):
            await service.apply_transition(
                sc.id,
                TransitionRequest(action=SCAction.REQUEST_RECOTIZATION),
                setup_basico["usuarios"]["u_jefe"],
            )


class TestAuditLogTrazabilidad:
    async def test_audit_log_tiene_todas_las_acciones(self, db_session, setup_basico, payload_sc):
        """Cada transición debe quedar registrada en el audit_log."""
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        actions = [
            (SCAction.SUBMIT, setup_basico["usuarios"]["u_sol"]),
            (SCAction.APPROVE_AREA, setup_basico["usuarios"]["u_jefe"]),
            (SCAction.RELEASE_BUDGET, setup_basico["usuarios"]["u_fin"]),
        ]
        for action, actor in actions:
            await service.apply_transition(sc.id, TransitionRequest(action=action), actor)

        result = await db_session.execute(
            select(AuditLog)
            .where(AuditLog.entity_id == str(sc.id))
            .order_by(AuditLog.timestamp)
        )
        logs = list(result.scalars().all())
        # CREATE + 3 transiciones = 4 logs
        assert len(logs) == 4
        actions_logged = [l.action for l in logs]
        assert "CREATE" in actions_logged
        assert "SUBMIT" in actions_logged
        assert "APPROVE_AREA" in actions_logged
        assert "RELEASE_BUDGET" in actions_logged
