"""Servicio de Solicitudes de Compra.

Responsable de:
- Crear SC en estado DRAFT
- Aplicar acciones (transiciones de estado) con auditoría
- Coordinar reglas de negocio entre módulos
"""

from sqlalchemy.ext.asyncio import AsyncSession

from sgp.core.audit import AuditService
from sgp.core.exceptions import BusinessRuleViolation, NotFoundError, PermissionDenied
from sgp.modules.solicitudes.models import SolicitudCompra, SolicitudCompraLinea
from sgp.modules.solicitudes.repository import SolicitudCompraRepository
from sgp.modules.solicitudes.schemas import SolicitudCompraCreate, TransitionRequest
from sgp.modules.solicitudes.state_machine import (
    SCAction,
    SCStatus,
    apply_action,
)
from sgp.modules.usuarios.models import Usuario


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
        """Crea una SC nueva en estado DRAFT."""
        numero = await self.repo.generate_next_numero()

        sc = SolicitudCompra(
            numero=numero,
            empresa_id=payload.empresa_id,
            centro_costo_id=payload.centro_costo_id,
            solicitante_id=solicitante.id,
            tipo=payload.tipo,
            urgencia=payload.urgencia,
            descripcion=payload.descripcion,
            justificacion=payload.justificacion,
            monto_estimado=payload.monto_estimado,
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
        await self.repo.add(sc)

        await self.audit.log(
            entity_type="solicitud_compra",
            entity_id=sc.id,
            action="CREATE",
            actor_id=solicitante.id,
            after=sc.snapshot(),
            comment=f"SC creada con {len(payload.lineas)} línea(s)",
        )
        return sc

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

        self._authorize_action(sc, request.action, actor)
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
    # Autorización
    # ------------------------------------------------------------------
    @staticmethod
    def _authorize_action(sc: SolicitudCompra, action: SCAction, actor: Usuario) -> None:
        """Valida que el actor tenga rol para ejecutar la acción.

        Por simplicidad, este es el mapeo inicial. En producción, esto se
        cruza con el scope del usuario (su área, su empresa, su CC).
        """
        required_roles_by_action: dict[SCAction, set[str]] = {
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
        required = required_roles_by_action.get(action, set())
        actor_roles = {r.nombre for r in actor.roles}

        # El admin puede todo
        if "admin" in actor_roles:
            return

        if not actor_roles.intersection(required):
            raise PermissionDenied(
                f"Acción '{action.value}' requiere uno de los roles: {sorted(required)}"
            )

        # Solicitante: además debe ser el dueño de la SC
        if action in {SCAction.SUBMIT, SCAction.CANCEL} and "admin" not in actor_roles:
            if actor.id != sc.solicitante_id:
                raise PermissionDenied(
                    "Solo el solicitante original puede ejecutar esta acción sobre su SC"
                )

    @staticmethod
    def _primary_role_for_action(actor: Usuario, action: SCAction) -> str | None:
        """Devuelve el rol que justifica la acción (primer match)."""
        for r in actor.roles:
            return r.nombre
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
