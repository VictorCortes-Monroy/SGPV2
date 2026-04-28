"""Tests del módulo gastos: agregación de SCs por CC/empresa/periodo."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from sgp.core.exceptions import NotFoundError
from sgp.modules.catalogo.models import (
    CatalogoItem,
    Criticidad,
    Familia,
    UnidadMedida,
)
from sgp.modules.empresas.models import CentroCosto, Empresa
from sgp.modules.gastos.service import GastosService
from sgp.modules.solicitudes.models import SolicitudCompra, TipoCompra, Urgencia
from sgp.modules.solicitudes.schemas import (
    LineaCreate,
    SolicitudCompraCreate,
    TransitionRequest,
)
from sgp.modules.solicitudes.service import SolicitudCompraService
from sgp.modules.solicitudes.state_machine import SCAction, SCStatus
from sgp.modules.usuarios.models import Rol, Usuario, usuario_roles_table


@pytest.fixture
async def setup_gastos(db_session):
    """Setup con 2 CCs en una empresa, usuarios para todas las acciones."""
    roles = {
        n: Rol(nombre=n)
        for n in [
            "solicitante", "jefe_area", "finanzas", "abastecimiento",
            "gerencia", "bodega", "admin",
        ]
    }
    for r in roles.values():
        db_session.add(r)
    await db_session.flush()

    def _user(clerk, email, names):
        u = Usuario(clerk_user_id=clerk, email=email, nombre=clerk, activo=True)
        db_session.add(u)
        return u, names

    u_sol, sol_r = _user("sol", "sol@x.cl", ["solicitante"])
    u_jefe, jefe_r = _user("jefe", "j@x.cl", ["jefe_area"])
    u_fin, fin_r = _user("fin", "f@x.cl", ["finanzas"])
    u_abast, ab_r = _user("ab", "a@x.cl", ["abastecimiento"])
    u_ger, ge_r = _user("ger", "g@x.cl", ["gerencia"])
    u_bod, bod_r = _user("bod", "bo@x.cl", ["bodega"])
    u_admin, ad_r = _user("admin", "ad@x.cl", ["admin"])
    await db_session.flush()

    for u, names in [
        (u_sol, sol_r), (u_jefe, jefe_r), (u_fin, fin_r),
        (u_abast, ab_r), (u_ger, ge_r), (u_bod, bod_r), (u_admin, ad_r),
    ]:
        for n in names:
            await db_session.execute(
                usuario_roles_table.insert().values(
                    usuario_id=u.id, rol_id=roles[n].id, empresa_id=None
                )
            )

    emp = Empresa(rut="76123456-7", razon_social="Demo SA", nombre_corto="DEMO")
    db_session.add(emp)
    await db_session.flush()
    cc1 = CentroCosto(empresa_id=emp.id, codigo="CC-001", nombre="Mantención")
    cc2 = CentroCosto(empresa_id=emp.id, codigo="CC-002", nombre="Operaciones")
    db_session.add_all([cc1, cc2])
    await db_session.flush()

    fam = Familia(nombre="Repuestos", nivel=1)
    db_session.add(fam)
    await db_session.flush()
    item = CatalogoItem(
        sku="ITM",
        nombre="Item",
        familia_id=fam.id,
        unidad_medida=UnidadMedida.UN,
        precio_referencia=Decimal("10000"),
        criticidad=Criticidad.ESTANDAR,
    )
    db_session.add(item)
    await db_session.flush()

    result = await db_session.execute(
        select(Usuario).options(selectinload(Usuario.roles))
    )
    usuarios = {u.clerk_user_id: u for u in result.scalars().all()}
    return {
        "usuarios": usuarios,
        "empresa": emp,
        "cc1": cc1,
        "cc2": cc2,
        "item": item,
    }


async def _crear_sc(
    db_session, setup_gastos, *, cc_id: int, monto_target: Decimal
) -> int:
    item = setup_gastos["item"]
    cantidad = monto_target / item.precio_referencia
    payload = SolicitudCompraCreate(
        empresa_id=setup_gastos["empresa"].id,
        centro_costo_id=cc_id,
        tipo=TipoCompra.BIEN,
        urgencia=Urgencia.NORMAL,
        descripcion="Compra para test de gastos",
        fecha_requerida=date.today() + timedelta(days=15),
        lineas=[LineaCreate(item_id=item.id, cantidad=cantidad)],
    )
    service = SolicitudCompraService(db_session)
    sc = await service.create(payload, setup_gastos["usuarios"]["sol"])
    return sc.id


async def _avanzar_sc_hasta(db_session, setup_gastos, sc_id: int, target: SCStatus):
    """Aplica las transiciones necesarias para llevar la SC a `target`.
    Soporta los estados que necesitan los tests de gastos."""
    service = SolicitudCompraService(db_session)
    u = setup_gastos["usuarios"]

    transitions: list[tuple[SCAction, str, str | None]] = [
        (SCAction.SUBMIT, "sol", None),
        (SCAction.APPROVE_AREA, "jefe", None),
    ]
    if target in {SCStatus.PENDING_QUOTATION, SCStatus.QUOTATION_RECEIVED,
                  SCStatus.PENDING_VALORIZATION, SCStatus.VALORIZATION_APPROVED,
                  SCStatus.PENDING_PO_APPROVAL, SCStatus.PO_APPROVED,
                  SCStatus.PO_SENT_TO_SUPPLIER, SCStatus.PENDING_RECEPTION,
                  SCStatus.RECEPTION_CONFORM, SCStatus.PENDING_INVOICE,
                  SCStatus.INVOICE_MATCHED, SCStatus.CLOSED, SCStatus.PENDING_BUDGET}:
        # APPROVE_AREA con monto medio (3M) lleva a PENDING_BUDGET
        pass

    for action, actor_key, comment in transitions:
        sc = await service.apply_transition(
            sc_id, TransitionRequest(action=action, comment=comment), u[actor_key]
        )
        if sc.status == target:
            return

    if target == SCStatus.PENDING_BUDGET:
        return

    # Continuar
    extra: list[tuple[SCAction, str, str | None]] = [
        (SCAction.RELEASE_BUDGET, "fin", None),
        (SCAction.REGISTER_QUOTATIONS, "ab", None),
        (SCAction.SEND_VALORIZATION, "ab", None),
        (SCAction.APPROVE_VALORIZATION, "jefe", None),
        (SCAction.EMIT_PO, "ab", None),
        (SCAction.APPROVE_PO, "ger", None),
        (SCAction.SEND_PO_TO_SUPPLIER, "ab", None),
        (SCAction.REGISTER_RECEPTION_CONFORM, "bod", None),  # → PENDING_RECEPTION
        (SCAction.REGISTER_RECEPTION_CONFORM, "bod", None),  # → RECEPTION_CONFORM
        (SCAction.RECEIVE_INVOICE, "fin", None),
        (SCAction.MATCH_INVOICE_OK, "fin", None),
        (SCAction.CLOSE, "fin", None),
    ]
    for action, actor_key, comment in extra:
        sc = await service.apply_transition(
            sc_id, TransitionRequest(action=action, comment=comment), u[actor_key]
        )
        if sc.status == target:
            return

    if sc.status != target:
        raise RuntimeError(f"No se llegó a {target}; quedó en {sc.status}")


class TestResumenGastos:
    async def test_empresa_inexistente_lanza(self, db_session, setup_gastos):
        service = GastosService(db_session)
        with pytest.raises(NotFoundError):
            await service.resumen(
                empresa_id=99999,
                periodo_desde=date.today(),
                periodo_hasta=date.today(),
            )

    async def test_sin_scs_devuelve_ceros_pero_lista_los_ccs(
        self, db_session, setup_gastos
    ):
        """Empresa con CCs pero sin SCs creadas: comprometido=0, ejecutado=0
        pero `por_centro_costo` lista los 2 CCs (útil para UI con tabla vacía)."""
        service = GastosService(db_session)
        resumen = await service.resumen(
            empresa_id=setup_gastos["empresa"].id,
            periodo_desde=date.today() - timedelta(days=30),
            periodo_hasta=date.today(),
        )
        assert resumen.comprometido_total == Decimal(0)
        assert resumen.ejecutado_total == Decimal(0)
        assert len(resumen.por_centro_costo) == 2
        for cc in resumen.por_centro_costo:
            assert cc.comprometido == Decimal(0)
            assert cc.ejecutado == Decimal(0)
            assert cc.scs_comprometidas == 0

    async def test_sc_en_draft_no_cuenta(self, db_session, setup_gastos):
        await _crear_sc(
            db_session, setup_gastos,
            cc_id=setup_gastos["cc1"].id, monto_target=Decimal("1000000"),
        )
        # Queda en DRAFT
        service = GastosService(db_session)
        resumen = await service.resumen(
            empresa_id=setup_gastos["empresa"].id,
            periodo_desde=date.today() - timedelta(days=1),
            periodo_hasta=date.today() + timedelta(days=1),
        )
        assert resumen.comprometido_total == Decimal(0)
        assert resumen.ejecutado_total == Decimal(0)

    async def test_sc_aprobada_cuenta_como_comprometida(
        self, db_session, setup_gastos
    ):
        sc_id = await _crear_sc(
            db_session, setup_gastos,
            cc_id=setup_gastos["cc1"].id, monto_target=Decimal("3000000"),
        )
        await _avanzar_sc_hasta(db_session, setup_gastos, sc_id, SCStatus.PENDING_BUDGET)

        service = GastosService(db_session)
        resumen = await service.resumen(
            empresa_id=setup_gastos["empresa"].id,
            periodo_desde=date.today() - timedelta(days=1),
            periodo_hasta=date.today() + timedelta(days=1),
        )
        assert resumen.comprometido_total == Decimal("3000000")
        assert resumen.ejecutado_total == Decimal(0)
        assert resumen.scs_comprometidas_total == 1
        assert resumen.scs_ejecutadas_total == 0

    async def test_sc_rechazada_no_cuenta(self, db_session, setup_gastos):
        sc_id = await _crear_sc(
            db_session, setup_gastos,
            cc_id=setup_gastos["cc1"].id, monto_target=Decimal("3000000"),
        )
        sc_service = SolicitudCompraService(db_session)
        u = setup_gastos["usuarios"]
        await sc_service.apply_transition(sc_id, TransitionRequest(action=SCAction.SUBMIT), u["sol"])
        await sc_service.apply_transition(
            sc_id,
            TransitionRequest(action=SCAction.REJECT_AREA, comment="Sin presupuesto"),
            u["jefe"],
        )

        service = GastosService(db_session)
        resumen = await service.resumen(
            empresa_id=setup_gastos["empresa"].id,
            periodo_desde=date.today() - timedelta(days=1),
            periodo_hasta=date.today() + timedelta(days=1),
        )
        assert resumen.comprometido_total == Decimal(0)

    async def test_sc_cerrada_cuenta_en_ambos(self, db_session, setup_gastos):
        """Una SC CLOSED suma TANTO en comprometido como en ejecutado.
        Comprometido = todo lo que no está en draft/rejected/cancelled/non_conforming.
        Ejecutado = CLOSED ⊆ comprometido."""
        sc_id = await _crear_sc(
            db_session, setup_gastos,
            cc_id=setup_gastos["cc1"].id, monto_target=Decimal("3000000"),
        )
        await _avanzar_sc_hasta(db_session, setup_gastos, sc_id, SCStatus.CLOSED)

        service = GastosService(db_session)
        resumen = await service.resumen(
            empresa_id=setup_gastos["empresa"].id,
            periodo_desde=date.today() - timedelta(days=1),
            periodo_hasta=date.today() + timedelta(days=1),
        )
        assert resumen.comprometido_total == Decimal("3000000")
        assert resumen.ejecutado_total == Decimal("3000000")
        assert resumen.scs_comprometidas_total == 1
        assert resumen.scs_ejecutadas_total == 1

    async def test_agrupacion_por_cc(self, db_session, setup_gastos):
        """SCs en distintos CCs deben aparecer como filas separadas en
        `por_centro_costo`."""
        sc1 = await _crear_sc(
            db_session, setup_gastos,
            cc_id=setup_gastos["cc1"].id, monto_target=Decimal("3000000"),
        )
        sc2 = await _crear_sc(
            db_session, setup_gastos,
            cc_id=setup_gastos["cc2"].id, monto_target=Decimal("2000000"),
        )
        await _avanzar_sc_hasta(db_session, setup_gastos, sc1, SCStatus.PENDING_BUDGET)
        await _avanzar_sc_hasta(db_session, setup_gastos, sc2, SCStatus.PENDING_BUDGET)

        service = GastosService(db_session)
        resumen = await service.resumen(
            empresa_id=setup_gastos["empresa"].id,
            periodo_desde=date.today() - timedelta(days=1),
            periodo_hasta=date.today() + timedelta(days=1),
        )
        assert resumen.comprometido_total == Decimal("5000000")
        cc1_row = next(c for c in resumen.por_centro_costo if c.centro_costo_codigo == "CC-001")
        cc2_row = next(c for c in resumen.por_centro_costo if c.centro_costo_codigo == "CC-002")
        assert cc1_row.comprometido == Decimal("3000000")
        assert cc2_row.comprometido == Decimal("2000000")

    async def test_periodo_excluye_scs_fuera_de_rango(
        self, db_session, setup_gastos
    ):
        """Una SC creada antes/después del periodo no se cuenta."""
        sc_id = await _crear_sc(
            db_session, setup_gastos,
            cc_id=setup_gastos["cc1"].id, monto_target=Decimal("3000000"),
        )
        await _avanzar_sc_hasta(db_session, setup_gastos, sc_id, SCStatus.PENDING_BUDGET)

        # Backdate manual de created_at a hace 60 días
        sc = (await db_session.execute(
            select(SolicitudCompra).where(SolicitudCompra.id == sc_id)
        )).scalar_one()
        sc.created_at = datetime.now(UTC) - timedelta(days=60)
        await db_session.flush()

        service = GastosService(db_session)
        # Periodo: últimos 30 días
        resumen = await service.resumen(
            empresa_id=setup_gastos["empresa"].id,
            periodo_desde=date.today() - timedelta(days=30),
            periodo_hasta=date.today(),
        )
        assert resumen.comprometido_total == Decimal(0)
