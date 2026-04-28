"""Test de integración: flujo end-to-end de una SC desde DRAFT hasta CLOSED.

Valida que el service ejecute correctamente las transiciones, persista los
cambios y registre cada acción en el audit_log. Usa SQLite en memoria.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

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


def _build_payload(setup_basico, monto: Decimal) -> SolicitudCompraCreate:
    return SolicitudCompraCreate(
        empresa_id=setup_basico["empresa"].id,
        centro_costo_id=setup_basico["cc"].id,
        tipo=TipoCompra.BIEN,
        urgencia=Urgencia.NORMAL,
        descripcion="Compra de repuesto crítico para mantención preventiva",
        justificacion="Mantención programada de equipo CAT 320",
        monto_estimado=monto,
        fecha_requerida=date.today() + timedelta(days=30),
        lineas=[LineaCreate(item_id=setup_basico["item"].id, cantidad=Decimal("3"))],
    )


@pytest.fixture
def payload_sc(setup_basico):
    """Payload por defecto: monto del tramo medio (1M < x ≤ 5M)
    para ejercer el flujo APPROVE_AREA → PENDING_BUDGET → PENDING_QUOTATION."""
    return _build_payload(setup_basico, Decimal("3000000"))


@pytest.fixture
def payload_sc_bajo(setup_basico):
    """Tramo bajo (≤ 1M): APPROVE_AREA salta directo a PENDING_QUOTATION."""
    return _build_payload(setup_basico, Decimal("500000"))


@pytest.fixture
def payload_sc_alto(setup_basico):
    """Tramo alto (> 5M): pasa por finanzas + gerencia (PENDING_MANAGEMENT_APPROVAL)."""
    return _build_payload(setup_basico, Decimal("8000000"))


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


class TestRNMontoFlujoPorTramo:
    """Verifica que el ruteo condicional por monto (RN-MONTO) se aplique
    correctamente desde el service layer, end-to-end."""

    async def test_tramo_bajo_salta_pending_budget(
        self, db_session, setup_basico, payload_sc_bajo
    ):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc_bajo, setup_basico["usuarios"]["u_sol"])
        await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )
        sc = await service.apply_transition(
            sc.id,
            TransitionRequest(action=SCAction.APPROVE_AREA),
            setup_basico["usuarios"]["u_jefe"],
        )
        # Tramo bajo: salta finanzas
        assert sc.status == SCStatus.PENDING_QUOTATION

    async def test_tramo_alto_requiere_aprobacion_gerencial_temprana(
        self, db_session, setup_basico, payload_sc_alto
    ):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc_alto, setup_basico["usuarios"]["u_sol"])

        for action, actor_key in [
            (SCAction.SUBMIT, "u_sol"),
            (SCAction.APPROVE_AREA, "u_jefe"),
            (SCAction.RELEASE_BUDGET, "u_fin"),
        ]:
            sc = await service.apply_transition(
                sc.id, TransitionRequest(action=action), setup_basico["usuarios"][actor_key]
            )

        # > 5M: tras finanzas debe quedar esperando a gerencia
        assert sc.status == SCStatus.PENDING_MANAGEMENT_APPROVAL

        # Solo gerencia puede aprobar
        with pytest.raises(PermissionDenied):
            await service.apply_transition(
                sc.id,
                TransitionRequest(action=SCAction.APPROVE_MANAGEMENT),
                setup_basico["usuarios"]["u_fin"],
            )

        sc = await service.apply_transition(
            sc.id,
            TransitionRequest(action=SCAction.APPROVE_MANAGEMENT, comment="OK gerencia"),
            setup_basico["usuarios"]["u_ger"],
        )
        assert sc.status == SCStatus.PENDING_QUOTATION

    async def test_tramo_alto_gerencia_puede_rechazar(
        self, db_session, setup_basico, payload_sc_alto
    ):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc_alto, setup_basico["usuarios"]["u_sol"])

        for action, actor_key in [
            (SCAction.SUBMIT, "u_sol"),
            (SCAction.APPROVE_AREA, "u_jefe"),
            (SCAction.RELEASE_BUDGET, "u_fin"),
        ]:
            sc = await service.apply_transition(
                sc.id, TransitionRequest(action=action), setup_basico["usuarios"][actor_key]
            )
        assert sc.status == SCStatus.PENDING_MANAGEMENT_APPROVAL

        sc = await service.apply_transition(
            sc.id,
            TransitionRequest(action=SCAction.REJECT_MANAGEMENT, comment="Fuera de presupuesto"),
            setup_basico["usuarios"]["u_ger"],
        )
        assert sc.status == SCStatus.REJECTED


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

    async def test_audit_log_actor_role_es_el_que_justifica_la_accion(
        self, db_session, setup_basico, payload_sc
    ):
        """Bug fix: actor_role debe ser el rol que autoriza la acción, no el primer
        rol del usuario. user_admin (que también puede ser solicitante) debería
        registrar 'admin' en SUBMIT, no 'solicitante'."""
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        # u_jefe SUBMIT no aplica (no es dueño), pero u_jefe APPROVE_AREA sí.
        # Probamos con u_jefe que tiene solo el rol jefe_area.
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


class TestRefinamientosSolicitudes:
    """Tests para los 4 refinamientos del módulo:
    1. Comments obligatorios en rechazos.
    2. Bug fix _primary_role_for_action.
    3. Scope por empresa en autorización.
    4. Validación fecha_requerida >= hoy (en schema).
    """

    # --- 1. Comments obligatorios ---

    async def test_reject_area_sin_comment_lanza(self, db_session, setup_basico, payload_sc):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )

        with pytest.raises(BusinessRuleViolation, match="comment"):
            await service.apply_transition(
                sc.id,
                TransitionRequest(action=SCAction.REJECT_AREA),  # sin comment
                setup_basico["usuarios"]["u_jefe"],
            )

    async def test_reject_area_con_comment_vacio_lanza(self, db_session, setup_basico, payload_sc):
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )

        with pytest.raises(BusinessRuleViolation, match="comment"):
            await service.apply_transition(
                sc.id,
                TransitionRequest(action=SCAction.REJECT_AREA, comment="   "),
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
            TransitionRequest(action=SCAction.REJECT_AREA, comment="Sin presupuesto disponible"),
            setup_basico["usuarios"]["u_jefe"],
        )
        assert sc.status == SCStatus.REJECTED

    async def test_approve_area_no_requiere_comment(self, db_session, setup_basico, payload_sc):
        """RN-COMMENT solo aplica a rechazos / no-conformidad, no a aprobaciones."""
        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])
        await service.apply_transition(
            sc.id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )
        sc = await service.apply_transition(
            sc.id,
            TransitionRequest(action=SCAction.APPROVE_AREA),  # sin comment, OK
            setup_basico["usuarios"]["u_jefe"],
        )
        assert sc.status == SCStatus.PENDING_BUDGET

    # --- 3. Scope por empresa ---

    async def test_jefe_de_otra_empresa_no_puede_aprobar(
        self, db_session, setup_basico, payload_sc
    ):
        """Si el rol del jefe está vinculado a otra empresa, debe ser rechazado."""
        from sgp.modules.empresas.models import Empresa
        from sgp.modules.usuarios.models import Rol, Usuario, usuario_roles_table

        # Crear una segunda empresa y un jefe con rol vinculado SOLO a esa empresa
        otra_emp = Empresa(rut="76999999-9", razon_social="Otra Empresa", nombre_corto="OTRA")
        db_session.add(otra_emp)
        await db_session.flush()

        u_jefe2 = Usuario(
            clerk_user_id="u_jefe2", email="jefe2@x.cl", nombre="Jefe Otra Empresa", activo=True
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

        # Recargar con roles eager
        from sqlalchemy.orm import selectinload
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

    async def test_jefe_con_rol_global_puede_aprobar_cualquier_empresa(
        self, db_session, setup_basico, payload_sc
    ):
        """Un rol con empresa_id=NULL aplica a SCs de cualquier empresa.
        El setup_basico crea todos los roles con NULL, así que esto debería pasar."""
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
        assert sc.status == SCStatus.PENDING_BUDGET

    # --- 4. Validación fecha_requerida >= hoy ---

    def test_payload_con_fecha_pasada_lanza(self, setup_basico):
        """El validator de Pydantic debe rechazar fecha_requerida en el pasado."""
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError, match="fecha_requerida"):
            SolicitudCompraCreate(
                empresa_id=setup_basico["empresa"].id,
                centro_costo_id=setup_basico["cc"].id,
                tipo=TipoCompra.BIEN,
                urgencia=Urgencia.NORMAL,
                descripcion="Test fecha pasada",
                monto_estimado=Decimal("1000"),
                fecha_requerida=date.today() - timedelta(days=1),
                lineas=[LineaCreate(item_id=setup_basico["item"].id, cantidad=Decimal("1"))],
            )

    def test_payload_con_fecha_hoy_pasa(self, setup_basico):
        payload = SolicitudCompraCreate(
            empresa_id=setup_basico["empresa"].id,
            centro_costo_id=setup_basico["cc"].id,
            tipo=TipoCompra.BIEN,
            urgencia=Urgencia.NORMAL,
            descripcion="Test fecha hoy",
            monto_estimado=Decimal("1000"),
            fecha_requerida=date.today(),
            lineas=[LineaCreate(item_id=setup_basico["item"].id, cantidad=Decimal("1"))],
        )
        assert payload.fecha_requerida == date.today()


class TestRepositoryFiltros:
    """Tests del nuevo método list_ con filtros enriquecidos."""

    async def test_filtro_empresa_id(self, db_session, setup_basico, payload_sc):
        """Solo devuelve SCs de la empresa especificada."""
        from sgp.modules.empresas.models import Empresa, CentroCosto
        from sgp.modules.solicitudes.repository import SolicitudCompraRepository

        # Segunda empresa con su CC
        otra_emp = Empresa(rut="76888888-8", razon_social="Otra", nombre_corto="OTRA")
        db_session.add(otra_emp)
        await db_session.flush()
        otra_cc = CentroCosto(empresa_id=otra_emp.id, codigo="O-001", nombre="Otra Op")
        db_session.add(otra_cc)
        await db_session.flush()

        service = SolicitudCompraService(db_session)
        sc1 = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        # SC de la otra empresa
        payload_otra = _build_payload(setup_basico, Decimal("3000000"))
        payload_otra = payload_otra.model_copy(
            update={"empresa_id": otra_emp.id, "centro_costo_id": otra_cc.id}
        )
        sc2 = await service.create(payload_otra, setup_basico["usuarios"]["u_sol"])

        repo = SolicitudCompraRepository(db_session)
        scs_emp1 = await repo.list_(empresa_id=setup_basico["empresa"].id)
        ids_emp1 = {s.id for s in scs_emp1}
        assert sc1.id in ids_emp1
        assert sc2.id not in ids_emp1

    async def test_filtro_rango_monto(self, db_session, setup_basico):
        """Filtra por monto_min y monto_max."""
        from sgp.modules.solicitudes.repository import SolicitudCompraRepository

        service = SolicitudCompraService(db_session)
        actor = setup_basico["usuarios"]["u_sol"]
        for monto in [Decimal("500000"), Decimal("3000000"), Decimal("8000000")]:
            await service.create(_build_payload(setup_basico, monto), actor)

        repo = SolicitudCompraRepository(db_session)
        # Solo el medio: 1M < monto < 5M
        scs = await repo.list_(monto_min=Decimal("1000001"), monto_max=Decimal("4999999"))
        assert len(scs) == 1
        assert scs[0].monto_estimado == Decimal("3000000")

    async def test_filtro_numero_substring(self, db_session, setup_basico, payload_sc):
        from sgp.modules.solicitudes.repository import SolicitudCompraRepository

        service = SolicitudCompraService(db_session)
        sc = await service.create(payload_sc, setup_basico["usuarios"]["u_sol"])

        repo = SolicitudCompraRepository(db_session)
        # Búsqueda parcial por el año
        year = sc.numero.split("-")[1]
        scs = await repo.list_(numero=year)
        assert sc.id in {s.id for s in scs}
