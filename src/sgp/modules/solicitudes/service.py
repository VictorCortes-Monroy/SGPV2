"""Servicio de Solicitudes de Compra.

Responsable de:
- Crear SC en estado DRAFT
- Aplicar acciones (transiciones de estado) con auditoría
- Coordinar reglas de negocio entre módulos
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sgp.core.audit import AuditService
from sgp.core.exceptions import BusinessRuleViolation, NotFoundError, PermissionDenied
from sgp.modules.catalogo.models import CatalogoItem
from sgp.modules.solicitudes.models import SolicitudCompra, SolicitudCompraLinea
from sgp.modules.solicitudes.repository import SolicitudCompraRepository
from sgp.modules.solicitudes.schemas import SolicitudCompraCreate, TransitionRequest
from sgp.modules.solicitudes.state_machine import (
    ASSIGNEE_ROLE_BY_STATUS,
    SLA_HOURS_BY_STATUS,
    SCAction,
    SCStatus,
    apply_action,
)
from sgp.modules.usuarios.models import Usuario, usuario_roles_table


# Mapeo acción → roles autorizados (OR). El rol `admin` puede ejecutar
# cualquier acción (override en _authorize_action).
REQUIRED_ROLES_BY_ACTION: dict[SCAction, set[str]] = {
    SCAction.SUBMIT: {"solicitante"},
    SCAction.APPROVE_AREA: {"jefe_area"},
    SCAction.REJECT_AREA: {"jefe_area"},
    SCAction.RELEASE_BUDGET: {"finanzas"},
    SCAction.FREEZE_BUDGET: {"finanzas"},
    SCAction.AUTHORIZE_FROZEN: {"gerencia", "finanzas"},
    SCAction.APPROVE_MANAGEMENT: {"gerencia"},
    SCAction.REJECT_MANAGEMENT: {"gerencia"},
    SCAction.REGISTER_QUOTATIONS: {"abastecimiento"},
    SCAction.SEND_VALORIZATION: {"abastecimiento"},
    SCAction.APPROVE_VALORIZATION: {"jefe_area"},
    SCAction.REQUEST_RECOTIZATION: {"jefe_area"},
    SCAction.REJECT_VALORIZATION: {"jefe_area"},
    SCAction.EMIT_PO: {"abastecimiento"},
    SCAction.APPROVE_PO: {"gerencia"},
    SCAction.REJECT_PO: {"gerencia"},
    SCAction.SEND_PO_TO_SUPPLIER: {"abastecimiento"},
    SCAction.REGISTER_RECEPTION_CONFORM: {"bodega", "solicitante"},
    SCAction.REGISTER_RECEPTION_NON_CONFORM: {"bodega", "solicitante"},
    SCAction.RECEIVE_INVOICE: {"finanzas", "abastecimiento"},
    SCAction.MATCH_INVOICE_OK: {"finanzas"},
    SCAction.MATCH_INVOICE_FAIL: {"finanzas"},
    SCAction.CLOSE: {"finanzas", "abastecimiento"},
    SCAction.CANCEL: {"solicitante", "jefe_area"},
}

# Acciones que exigen `comment` no vacío para preservar trazabilidad
# (RN-COMMENT). Aplica a todos los rechazos y a la recepción no conforme.
ACTIONS_REQUIRING_COMMENT: set[SCAction] = {
    SCAction.REJECT_AREA,
    SCAction.REJECT_VALORIZATION,
    SCAction.REJECT_PO,
    SCAction.REJECT_MANAGEMENT,
    SCAction.REGISTER_RECEPTION_NON_CONFORM,
}


class SolicitudCompraService:
    """Lógica de negocio de SC."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = SolicitudCompraRepository(db)
        self.audit = AuditService(db)

    # ------------------------------------------------------------------
    # Creación
    # ------------------------------------------------------------------
    async def create(
        self, payload: SolicitudCompraCreate, solicitante: Usuario
    ) -> SolicitudCompra:
        """Crea una SC nueva en estado DRAFT.

        El `monto_estimado` se calcula automáticamente como
        Σ(cantidad × precio_referencia) de las líneas; las líneas con
        item sin precio_referencia contribuyen 0.
        """
        numero = await self.repo.generate_next_numero()
        monto_estimado = await self._calcular_monto_estimado(payload)

        sc = SolicitudCompra(
            numero=numero,
            empresa_id=payload.empresa_id,
            centro_costo_id=payload.centro_costo_id,
            solicitante_id=solicitante.id,
            tipo=payload.tipo,
            urgencia=payload.urgencia,
            descripcion=payload.descripcion,
            justificacion=payload.justificacion,
            monto_estimado=monto_estimado,
            fecha_requerida=payload.fecha_requerida,
            status=SCStatus.DRAFT,
            recotization_cycles=0,
            lineas=[
                SolicitudCompraLinea(
                    item_id=l.item_id,
                    cantidad=l.cantidad,
                    especificacion=l.especificacion,
                )
                for l in payload.lineas
            ],
        )
        self._sync_assignee_and_sla(sc)
        await self.repo.add(sc)

        await self.audit.log(
            entity_type="solicitud_compra",
            entity_id=sc.id,
            action="CREATE",
            actor_id=solicitante.id,
            after=sc.snapshot(),
            comment=(
                f"SC creada con {len(payload.lineas)} línea(s); "
                f"monto_estimado calculado = {monto_estimado}"
            ),
        )
        return sc

    async def _calcular_monto_estimado(self, payload: SolicitudCompraCreate) -> Decimal:
        """Σ(cantidad × precio_referencia) sobre todas las líneas.

        Los items sin precio_referencia contribuyen 0. La cotización posterior
        determinará el monto real (RN-MONTO-5: re-validación pre-EMIT_PO).
        """
        item_ids = [l.item_id for l in payload.lineas]
        result = await self.db.execute(
            select(CatalogoItem).where(CatalogoItem.id.in_(item_ids))
        )
        precios_by_id = {
            i.id: (i.precio_referencia or Decimal(0)) for i in result.scalars().all()
        }
        total = Decimal(0)
        for linea in payload.lineas:
            precio = precios_by_id.get(linea.item_id, Decimal(0))
            total += Decimal(linea.cantidad) * precio
        return total

    @staticmethod
    def _sync_assignee_and_sla(sc: SolicitudCompra) -> None:
        """Recalcula `current_assignee_role` y `expected_resolution_at` según
        el `status` actual de la SC. Llamar tras cada cambio de estado."""
        sc.current_assignee_role = ASSIGNEE_ROLE_BY_STATUS.get(sc.status)
        sla_hours = SLA_HOURS_BY_STATUS.get(sc.status)
        sc.expected_resolution_at = (
            datetime.now(UTC) + timedelta(hours=sla_hours) if sla_hours else None
        )

    # ------------------------------------------------------------------
    # Transiciones
    # ------------------------------------------------------------------
    async def apply_transition(
        self,
        sc_id: int,
        request: TransitionRequest,
        actor: Usuario,
    ) -> SolicitudCompra:
        """Aplica una acción del workflow sobre una SC.

        Garantías:
            1. La transición es válida según la state machine.
            2. El actor tiene el rol requerido para esa acción.
            3. Se registra en el audit_log antes y después.
            4. Reglas de negocio específicas se ejecutan (e.g. recotization_cycles).
        """
        sc = await self.repo.get(sc_id)
        if not sc:
            raise NotFoundError(f"SC {sc_id} no encontrada")

        self._validate_required_comment(request)
        await self._authorize_action(sc, request.action, actor)
        before = sc.snapshot()

        # Aplicar transición de estado (valida automáticamente).
        # `monto_estimado` se pasa para soportar ruteo condicional (RN-MONTO).
        new_status = apply_action(
            sc.status,
            request.action,
            monto_estimado=sc.monto_estimado,
        )

        # Reglas de negocio específicas por acción
        self._apply_business_rules(sc, request.action, actor)

        sc.status = new_status
        self._sync_assignee_and_sla(sc)

        await self.audit.log(
            entity_type="solicitud_compra",
            entity_id=sc.id,
            action=request.action.value.upper(),
            actor_id=actor.id,
            actor_role=self._primary_role_for_action(actor, request.action),
            before=before,
            after=sc.snapshot(),
            comment=request.comment,
        )

        return sc

    # ------------------------------------------------------------------
    # Validaciones de payload
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_required_comment(request: TransitionRequest) -> None:
        """RN-COMMENT: las acciones de rechazo / no-conformidad exigen un comment
        no vacío para preservar trazabilidad legal y auditoría."""
        if request.action in ACTIONS_REQUIRING_COMMENT:
            if request.comment is None or not request.comment.strip():
                raise BusinessRuleViolation(
                    f"La acción '{request.action.value}' requiere un comment "
                    "explicando el motivo (no puede estar vacío)."
                )

    # ------------------------------------------------------------------
    # Autorización
    # ------------------------------------------------------------------
    async def _authorize_action(
        self, sc: SolicitudCompra, action: SCAction, actor: Usuario
    ) -> None:
        """Valida que el actor tenga rol para ejecutar la acción y que ese
        rol esté vinculado a la empresa de la SC.

        Reglas:
        1. `admin` puede ejecutar cualquier acción sin scope (override).
        2. El actor debe tener al menos uno de los roles requeridos.
        3. Ese rol debe estar vinculado a `sc.empresa_id` o ser global
           (`empresa_id IS NULL`) en la tabla `usuarios_roles`.
        4. Para SUBMIT y CANCEL, el actor debe ser el solicitante original.
        """
        required = REQUIRED_ROLES_BY_ACTION.get(action, set())
        actor_role_names = {r.nombre for r in actor.roles}

        # Admin override (sin scope)
        if "admin" in actor_role_names:
            if action in {SCAction.SUBMIT, SCAction.CANCEL} and actor.id != sc.solicitante_id:
                raise PermissionDenied(
                    "Solo el solicitante original puede ejecutar esta acción sobre su SC"
                )
            return

        # Verifica que tenga al menos uno de los roles requeridos
        if not actor_role_names.intersection(required):
            raise PermissionDenied(
                f"Acción '{action.value}' requiere uno de los roles: {sorted(required)}"
            )

        # Scope: el rol que da permiso debe estar vinculado a la empresa de la
        # SC (o a NULL = aplica globalmente).
        matching_role_ids = [r.id for r in actor.roles if r.nombre in required]
        stmt = select(usuario_roles_table).where(
            usuario_roles_table.c.usuario_id == actor.id,
            usuario_roles_table.c.rol_id.in_(matching_role_ids),
            or_(
                usuario_roles_table.c.empresa_id == sc.empresa_id,
                usuario_roles_table.c.empresa_id.is_(None),
            ),
        )
        result = await self.db.execute(stmt)
        if result.first() is None:
            raise PermissionDenied(
                f"El rol del actor para '{action.value}' no está vinculado a la "
                f"empresa {sc.empresa_id} de la SC."
            )

        # Solicitante / dueño: SUBMIT y CANCEL solo por el creador
        if action in {SCAction.SUBMIT, SCAction.CANCEL}:
            if actor.id != sc.solicitante_id:
                raise PermissionDenied(
                    "Solo el solicitante original puede ejecutar esta acción sobre su SC"
                )

    @staticmethod
    def _primary_role_for_action(actor: Usuario, action: SCAction) -> str | None:
        """Devuelve el nombre del rol que justifica la acción.

        Busca el primer rol del actor que esté en `REQUIRED_ROLES_BY_ACTION[action]`.
        Si el actor es admin, devuelve "admin" (override). Útil para popular
        `actor_role` en audit_log con info significativa.
        """
        actor_role_names = {r.nombre for r in actor.roles}
        if "admin" in actor_role_names:
            return "admin"
        required = REQUIRED_ROLES_BY_ACTION.get(action, set())
        for role in actor.roles:
            if role.nombre in required:
                return role.nombre
        return None

    # ------------------------------------------------------------------
    # Reglas de negocio
    # ------------------------------------------------------------------
    @staticmethod
    def _apply_business_rules(sc: SolicitudCompra, action: SCAction, actor: Usuario) -> None:
        """Ejecuta side-effects sobre la SC según la acción."""
        # RN8: Ciclos máximos de recotización (default 2)
        MAX_RECOTIZATION_CYCLES = 2

        if action == SCAction.REQUEST_RECOTIZATION:
            sc.recotization_cycles += 1
            if sc.recotization_cycles > MAX_RECOTIZATION_CYCLES:
                raise BusinessRuleViolation(
                    f"Excedido máximo de {MAX_RECOTIZATION_CYCLES} ciclos de recotización. "
                    "Requiere aprobación gerencial explícita."
                )

        if action == SCAction.APPROVE_AREA:
            sc.approved_by_area_id = actor.id
