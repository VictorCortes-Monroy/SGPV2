"""Test de integración: flujo end-to-end de una SC desde DRAFT hasta CLOSED.

Valida que el service ejecute correctamente las transiciones, persista los
cambios y registre cada acción en el audit_log. Usa SQLite en memoria.

Sin info económica (montos eliminados del modelo). Items del catálogo
viven vinculados a un único CC (RN-CAT-CC).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from sgp.core.exceptions import (
    BusinessRuleViolation,
    InvalidTransitionError,
    PermissionDenied,
)
from sgp.modules.auditoria.models import AuditLog
from sgp.modules.catalogo.models import (
    CatalogoItem,
    Criticidad,
    Familia,
    UnidadMedida,
)
from sgp.modules.empresas.models import CentroCosto, Empresa
from sgp.modules.solicitudes.models import TipoCompra, Urgencia
from sgp.modules.solicitudes.repository import SolicitudCompraRepository
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
    """Crea datos mínimos: usuarios con roles, empresa, CC, item del catálogo
    vinculado al CC (RN-CAT-CC)."""
    roles = {
        nombre: Rol(nombre=nombre, descripcion=f"Rol {nombre}")
        for nombre in [
            "solicitante", "jefe_area", "finanzas",
            "abastecimiento", "gerencia", "bodega",
        ]
    }
    for r in roles.values():
        db_session.add(r)
    await db_session.flush()

    def _user(clerk_id, email, nombre, role_names):
        u = Usuario(clerk_user_id=clerk_id, email=email, nombre=nombre, activo=True)
        db_session.add(u)
        return u, role_names

    u_sol, sol_roles = _user("u_sol", "sol@x.cl", "Solicitante", ["solicitante"])
    u_jefe, jefe_roles = _user("u_jefe", "jefe@x.cl", "Jefe", ["jefe_area"])
    u_fin, fin_roles = _user("u_fin", "fin@x.cl", "Finanzas", ["finanzas"])
    u_abast, abast_roles = _user("u_abast", "ab@x.cl", "Abast", ["abastecimiento"])
    u_ger, ger_roles = _user("u_ger", "ger@x.cl", "Gerente", ["gerencia"])
    u_bod, bod_roles = _user("u_bod", "bo@x.cl", "Bodega", ["bodega"])
    await db_session.flush()

    for u, role_names in [
        (u_sol, sol_roles), (u_jefe, jefe_roles), (u_fin, fin_roles),
        (u_abast, abast_roles), (u_ger, ger_roles), (u_bod, bod_roles),
    ]:
        for rn in role_names:
            await db_session.execute(
                usuario_roles_table.insert().values(
                    usuario_id=u.id, rol_id=roles[rn].id, empresa_id=None
                )
            )

    emp = Empresa(rut="76123456-7", razon_social="Demo", nombre_corto="DEMO")
    db_session.add(emp)
    await db_session.flush()
    cc = CentroCosto(empresa_id=emp.id, codigo="CC-001", nombre="Mantención")
    db_session.add(cc)
    await db_session.flush()

    fam = Familia(nombre="Repuestos", nivel=1)
    db_session.add(fam)
    await db_session.flush()
    item = CatalogoItem(
        sku="ITM-TEST-001",
        nombre="Item Test",
        familia_id=fam.id,
        centro_costo_id=cc.id,
        unidad_medida=UnidadMedida.UN,
        criticidad=Criticidad.ESTANDAR,
    )
    db_session.add(item)
    await db_session.flush()

    result = await db_session.execute(
        select(Usuario).options(selectinload(Usuario.roles))
    )
    usuarios = {u.clerk_user_id: u for u in result.scalars().all()}

    return {"usuarios": usuarios, "empresa": emp, "cc": cc, "item": item}


def _build_payload(setup_basico, *, cantidad: Decimal = Decimal("3")) -> SolicitudCompraCreate:
    """Construye un payload de SC sobre el item del seed (vinculado al CC)."""
    return SolicitudCompraCreate(
        empresa_id=setup_basico["empresa"].id,
        centro_costo_id=setup_basico["cc"].id,
        tipo=TipoCompra.BIEN,
        urgencia=Urgencia.NORMAL,
        descripcion="Compra de repuesto crítico para mantención preventiva",
        justificacion="Mantención programada de equipo CAT 320",
        fecha_requerida=date.today() + timedelta(days=30),
        lineas=[LineaCreate(item_id=setup_basico["item"].id, cantidad=cantidad)],
    )


@pytest.fixture
def payload_sc(setup_basico):
    return _build_payload(setup_basico)


# ─────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────
class TestRNCATCC:
    """RN-CAT-CC: las líneas solo pueden referenciar items del mismo CC de la SC."""

    async def test_item_de_otro_cc_rebota(self, db_session, setup_basico):
        """Crear un segundo CC + item allí; usar ese item en una SC del primer CC → 422."""
        otro_cc = CentroCosto(
            empresa_id=setup_basico["empresa"].id, codigo="CC-OTRO", nombre="Otro"
        )
        db_session.add(otro_cc)
        await db_session.flush()

        item_otro_cc = CatalogoItem(
            sku="ITM-OTRO",
            nombre="Item del otro CC",
            familia_id=setup_basico["item"].familia_id,
            centro_costo_id=otro_cc.id,
            unidad_medida=UnidadMedida.UN,
            criticidad=Criticidad.ESTANDAR,
        )
        db_session.add(item_otro_cc)
        await db_session.flush()

        payload = SolicitudCompraCreate(
            empresa_id=setup_basico["empresa"].id,
            centro_costo_id=setup_basico["cc"].id,  # CC original
            tipo=TipoCompra.BIEN,
            urgencia=Urgencia.NORMAL,
            descripcion="Intento usar item de otro CC",
            fecha_requerida=date.today() + timedelta(days=10),
            lineas=[LineaCreate(item_id=item_otro_cc.id, cantidad=Decimal("1"))],
        )
        service = SolicitudCompraService(db_session)
        with pytest.raises(BusinessRuleViolation, match="otro centro de costo"):
            await service.create(payload, setup_basico["usuarios"]["u_sol"])

    async def test_item_inexistente_rebota(self, db_session, setup_basico):
        payload = SolicitudCompraCreate(
            empresa_id=setup_basico["empresa"].id,
            centro_costo_id=setup_basico["cc"].id,
            tipo=TipoCompra.BIEN,
            urgencia=Urgencia.NORMAL,
            descripcion="Item id que no existe",
            fecha_requerida=date.today() + timedelta(days=10),
            lineas=[LineaCreate(item_id=99999, cantidad=Decimal("1"))],
        )
        service = SolicitudCompraService(db_session)
        with pytest.raises(BusinessRuleViolation, match="no encontrados"):
            await service.create(payload, setup_basico["usuarios"]["u_sol"])


# ─────────────────────────────────────────────────────────────────────────
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

    async def test_jefe_aprueba_va_directo_a_quotation(
        self, db_session, setup_basico, payload_sc
    ):
        """Sin RN-MONTO: APPROVE_AREA → PENDING_QUOTATION (no más PENDING_BUDGET)."""
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )
        sc = await service.apply_transition(
            sc.id,
            TransitionRequest(action=SCAction.APPROVE_AREA, comment="OK"),
            setup_basico["usuarios"]["u_jefe"],
        )
        assert sc.status == SCStatus.PENDING_QUOTATION
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


# ─────────────────────────────────────────────────────────────────────────
class TestRecotizacion:
    async def test_excede_max_recotizaciones_bloquea(
        self, db_session, setup_basico, payload_sc
    ):
        """RN8: máximo 2 ciclos de recotización."""
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        # Avanzar hasta PENDING_VALORIZATION (sin pasar por PENDING_BUDGET)
        for action, actor in [
            (SCAction.SUBMIT, setup_basico["usuarios"]["u_sol"]),
            (SCAction.APPROVE_AREA, setup_basico["usuarios"]["u_jefe"]),
            (SCAction.REGISTER_QUOTATIONS, setup_basico["usuarios"]["u_abast"]),
            (SCAction.SEND_VALORIZATION, setup_basico["usuarios"]["u_abast"]),
        ]:
            sc = await service.apply_transition(
                sc.id, TransitionRequest(action=action), actor
            )
        assert sc.status == SCStatus.PENDING_VALORIZATION

        # 1ª y 2ª recotización: OK
        for _ in range(2):
            sc = await service.apply_transition(
                sc.id,
                TransitionRequest(action=SCAction.REQUEST_RECOTIZATION, comment="Otra opción"),
                setup_basico["usuarios"]["u_jefe"],
            )
            for action, actor in [
                (SCAction.REGISTER_QUOTATIONS, setup_basico["usuarios"]["u_abast"]),
                (SCAction.SEND_VALORIZATION, setup_basico["usuarios"]["u_abast"]),
            ]:
                sc = await service.apply_transition(
                    sc.id, TransitionRequest(action=action), actor
                )
        assert sc.recotization_cycles == 2

        # 3ª recotización: BUSINESS RULE VIOLATION
        with pytest.raises(BusinessRuleViolation, match="máximo"):
            await service.apply_transition(
                sc.id,
                TransitionRequest(action=SCAction.REQUEST_RECOTIZATION, comment="Otra"),
                setup_basico["usuarios"]["u_jefe"],
            )


# ─────────────────────────────────────────────────────────────────────────
class TestAuditLogTrazabilidad:
    async def test_audit_log_tiene_todas_las_acciones(
        self, db_session, setup_basico, payload_sc
    ):
        """Cada transición debe quedar registrada en el audit_log."""
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        actions = [
            (SCAction.SUBMIT, setup_basico["usuarios"]["u_sol"]),
            (SCAction.APPROVE_AREA, setup_basico["usuarios"]["u_jefe"]),
            (SCAction.REGISTER_QUOTATIONS, setup_basico["usuarios"]["u_abast"]),
        ]
        for action, actor in actions:
            await service.apply_transition(sc.id, TransitionRequest(action=action), actor)

        result = await db_session.execute(
            select(AuditLog)
            .where(AuditLog.entity_id == str(sc.id))
            .order_by(AuditLog.timestamp)
        )
        logs = list(result.scalars().all())
        assert len(logs) == 4  # CREATE + 3 transitions
        actions_logged = [l.action for l in logs]
        assert "CREATE" in actions_logged
        assert "SUBMIT" in actions_logged
        assert "APPROVE_AREA" in actions_logged
        assert "REGISTER_QUOTATIONS" in actions_logged

    async def test_audit_log_actor_role_es_el_que_justifica_la_accion(
        self, db_session, setup_basico, payload_sc
    ):
        """actor_role del audit_log es el rol que autorizó la acción, no el primero."""
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )
        await service.apply_transition(
            sc.id,
            TransitionRequest(action=SCAction.APPROVE_AREA, comment="OK"),
            setup_basico["usuarios"]["u_jefe"],
        )

        result = await db_session.execute(
            select(AuditLog)
            .where(AuditLog.entity_id == str(sc.id), AuditLog.action == "APPROVE_AREA")
        )
        log = result.scalar_one()
        assert log.actor_role == "jefe_area"


# ─────────────────────────────────────────────────────────────────────────
class TestSLAyAssignee:
    """current_assignee_role y expected_resolution_at se sincronizan en cada transición."""

    async def test_create_setea_assignee_solicitante(
        self, db_session, setup_basico, payload_sc
    ):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        assert sc.current_assignee_role == "solicitante"
        assert sc.expected_resolution_at is None  # DRAFT no tiene SLA

    async def test_submit_setea_assignee_jefe_con_sla(
        self, db_session, setup_basico, payload_sc
    ):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        sc = await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )
        assert sc.current_assignee_role == "jefe_area"
        assert sc.expected_resolution_at is not None
        from datetime import UTC, datetime
        delta = sc.expected_resolution_at - datetime.now(UTC)
        assert timedelta(hours=23, minutes=55) <= delta <= timedelta(hours=24, minutes=5)

    async def test_estado_terminal_limpia_assignee_y_sla(
        self, db_session, setup_basico, payload_sc
    ):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )
        sc = await service.apply_transition(
            sc.id,
            TransitionRequest(action=SCAction.REJECT_AREA, comment="Sin presupuesto"),
            setup_basico["usuarios"]["u_jefe"],
        )
        assert sc.status == SCStatus.REJECTED
        assert sc.current_assignee_role is None
        assert sc.expected_resolution_at is None

    async def test_assignee_cambia_con_cada_transicion(
        self, db_session, setup_basico, payload_sc
    ):
        """Sin RN-MONTO: solicitante → jefe_area → abastecimiento."""
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        assert sc.current_assignee_role == "solicitante"

        sc = await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )
        assert sc.current_assignee_role == "jefe_area"

        sc = await service.apply_transition(
            sc.id,
            TransitionRequest(action=SCAction.APPROVE_AREA),
            setup_basico["usuarios"]["u_jefe"],
        )
        # Sin RN-MONTO: APPROVE_AREA → PENDING_QUOTATION → abastecimiento
        assert sc.current_assignee_role == "abastecimiento"


# ─────────────────────────────────────────────────────────────────────────
class TestRefinamientosSolicitudes:
    """Comments obligatorios + scope por empresa + fecha_requerida >= hoy."""

    # --- Comments obligatorios ---
    async def test_reject_area_sin_comment_lanza(self, db_session, setup_basico, payload_sc):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )
        with pytest.raises(BusinessRuleViolation, match="comment"):
            await service.apply_transition(
                sc.id,
                TransitionRequest(action=SCAction.REJECT_AREA),
                setup_basico["usuarios"]["u_jefe"],
            )

    async def test_reject_area_con_comment_pasa(self, db_session, setup_basico, payload_sc):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )
        sc = await service.apply_transition(
            sc.id,
            TransitionRequest(action=SCAction.REJECT_AREA, comment="Sin presupuesto"),
            setup_basico["usuarios"]["u_jefe"],
        )
        assert sc.status == SCStatus.REJECTED

    async def test_approve_area_no_requiere_comment(self, db_session, setup_basico, payload_sc):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )
        sc = await service.apply_transition(
            sc.id,
            TransitionRequest(action=SCAction.APPROVE_AREA),
            setup_basico["usuarios"]["u_jefe"],
        )
        assert sc.status == SCStatus.PENDING_QUOTATION

    # --- Scope por empresa ---
    async def test_jefe_de_otra_empresa_no_puede_aprobar(
        self, db_session, setup_basico, payload_sc
    ):
        otra_emp = Empresa(rut="76999999-9", razon_social="Otra Empresa", nombre_corto="OTRA")
        db_session.add(otra_emp)
        await db_session.flush()

        u_jefe2 = Usuario(
            clerk_user_id="u_jefe2", email="jefe2@x.cl", nombre="Jefe Otra", activo=True
        )
        db_session.add(u_jefe2)
        await db_session.flush()

        rol_jefe = (
            await db_session.execute(select(Rol).where(Rol.nombre == "jefe_area"))
        ).scalar_one()
        await db_session.execute(
            usuario_roles_table.insert().values(
                usuario_id=u_jefe2.id, rol_id=rol_jefe.id, empresa_id=otra_emp.id
            )
        )

        u_jefe2 = (
            await db_session.execute(
                select(Usuario)
                .options(selectinload(Usuario.roles))
                .where(Usuario.id == u_jefe2.id)
            )
        ).scalar_one()

        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )

        with pytest.raises(PermissionDenied, match="empresa"):
            await service.apply_transition(
                sc.id,
                TransitionRequest(action=SCAction.APPROVE_AREA, comment="OK"),
                u_jefe2,
            )

    # --- Fecha pasada ---
    def test_payload_con_fecha_pasada_lanza(self, setup_basico):
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError, match="fecha_requerida"):
            SolicitudCompraCreate(
                empresa_id=setup_basico["empresa"].id,
                centro_costo_id=setup_basico["cc"].id,
                tipo=TipoCompra.BIEN,
                urgencia=Urgencia.NORMAL,
                descripcion="Test fecha pasada",
                fecha_requerida=date.today() - timedelta(days=1),
                lineas=[LineaCreate(item_id=setup_basico["item"].id, cantidad=Decimal("1"))],
            )


# ─────────────────────────────────────────────────────────────────────────
class TestRepositoryFiltros:
    async def test_filtro_empresa_id(self, db_session, setup_basico, payload_sc):
        otra_emp = Empresa(rut="76888888-8", razon_social="Otra", nombre_corto="OTRA")
        db_session.add(otra_emp)
        await db_session.flush()
        otra_cc = CentroCosto(empresa_id=otra_emp.id, codigo="O-001", nombre="Otra Op")
        db_session.add(otra_cc)
        await db_session.flush()

        # Necesitamos un item en el otro CC para no romper RN-CAT-CC
        item_otra = CatalogoItem(
            sku="ITM-OTRA",
            nombre="Item otra empresa",
            familia_id=setup_basico["item"].familia_id,
            centro_costo_id=otra_cc.id,
            unidad_medida=UnidadMedida.UN,
            criticidad=Criticidad.ESTANDAR,
        )
        db_session.add(item_otra)
        await db_session.flush()

        service = SolicitudCompraService(db_session)
        sc1 = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        payload_otra = SolicitudCompraCreate(
            empresa_id=otra_emp.id,
            centro_costo_id=otra_cc.id,
            tipo=TipoCompra.BIEN,
            urgencia=Urgencia.NORMAL,
            descripcion="SC en otra empresa",
            fecha_requerida=date.today() + timedelta(days=10),
            lineas=[LineaCreate(item_id=item_otra.id, cantidad=Decimal("1"))],
        )
        sc2 = await service.create(payload_otra, setup_basico["usuarios"]["u_sol"])

        repo = SolicitudCompraRepository(db_session)
        scs_emp1 = await repo.list_(empresa_id=setup_basico["empresa"].id)
        ids_emp1 = {s.id for s in scs_emp1}
        assert sc1.id in ids_emp1
        assert sc2.id not in ids_emp1

    async def test_filtro_numero_substring(self, db_session, setup_basico, payload_sc):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        repo = SolicitudCompraRepository(db_session)
        year = sc.numero.split("-")[1]
        scs = await repo.list_(numero=year)
        assert sc.id in {s.id for s in scs}

    async def test_filtro_item_id(self, db_session, setup_basico, payload_sc):
        otro_item = CatalogoItem(
            sku="ITM-OTRO",
            nombre="Otro item",
            familia_id=setup_basico["item"].familia_id,
            centro_costo_id=setup_basico["cc"].id,
            unidad_medida=UnidadMedida.UN,
            criticidad=Criticidad.ESTANDAR,
        )
        db_session.add(otro_item)
        await db_session.flush()

        service = SolicitudCompraService(db_session)
        sc1 = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        payload_otro = SolicitudCompraCreate(
            empresa_id=setup_basico["empresa"].id,
            centro_costo_id=setup_basico["cc"].id,
            tipo=TipoCompra.BIEN,
            urgencia=Urgencia.NORMAL,
            descripcion="SC con otro item para filtrar",
            fecha_requerida=date.today() + timedelta(days=15),
            lineas=[LineaCreate(item_id=otro_item.id, cantidad=Decimal("1"))],
        )
        sc2 = await service.create(payload_otro, setup_basico["usuarios"]["u_sol"])

        repo = SolicitudCompraRepository(db_session)
        scs = await repo.list_(item_id=setup_basico["item"].id)
        ids = {s.id for s in scs}
        assert sc1.id in ids
        assert sc2.id not in ids


# ─────────────────────────────────────────────────────────────────────────
class TestDuplicateSC:
    async def test_duplicate_clona_lineas_y_campos(
        self, db_session, setup_basico, payload_sc
    ):
        service = SolicitudCompraService(db_session)
        original = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        original_id = original.id

        copia = await service.duplicate(original_id, setup_basico["usuarios"]["u_sol"])

        assert copia.id != original_id
        assert copia.numero != original.numero
        assert copia.status == SCStatus.DRAFT
        assert copia.empresa_id == original.empresa_id
        assert copia.centro_costo_id == original.centro_costo_id
        assert copia.descripcion == original.descripcion
        assert len(copia.lineas) == len(original.lineas)
