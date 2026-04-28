"""Máquina de estados de la Solicitud de Compra.

Esta es la pieza más crítica del sistema: define el ciclo de vida de la SC
y las transiciones permitidas. Cualquier cambio de estado pasa por aquí
para garantizar consistencia y trazabilidad.

Diseño:
    - SCStatus: enum con todos los estados posibles
    - SCAction: enum con todas las acciones que disparan transiciones
    - ALLOWED_TRANSITIONS: mapa estado → estados destino válidos
    - TRANSITION_BY_ACTION: mapa (estado, acción) → estado destino (estático)
    - CONDITIONAL_ROUTES: mapa (estado, acción) → función router(monto) → destino
      para los casos donde el destino depende del monto de la SC (RN-MONTO).

Las acciones son lo que el usuario hace; el estado es donde queda la SC
después de la acción. Esta separación permite que el frontend exponga
acciones en lugar de estados crudos.

Ver `docs/transiciones_sc.md` para la spec canónica.
"""

import enum
from collections.abc import Callable
from decimal import Decimal

from sgp.core.exceptions import InvalidTransitionError

# RN-MONTO — umbrales de la matriz de aprobación (CLP)
MONTO_TIER_FINANZAS = Decimal("1000000")   # > este monto requiere finanzas
MONTO_TIER_GERENCIA = Decimal("5000000")   # > este monto requiere gerencia (early)


class SCStatus(str, enum.Enum):
    """Estados del ciclo de vida de una Solicitud de Compra.

    Cubre las 6 fases del proceso TO-BE definido en el PRD v2.0.
    """

    # --- Fase 1: Solicitud y aprobación inicial ---
    DRAFT = "draft"
    PENDING_AREA_APPROVAL = "pending_area_approval"
    PENDING_BUDGET = "pending_budget"
    BUDGET_FROZEN = "budget_frozen"
    PENDING_MANAGEMENT_APPROVAL = "pending_management_approval"  # RN-MONTO: > 5M

    # --- Fase 2: Cotización ---
    PENDING_QUOTATION = "pending_quotation"
    QUOTATION_RECEIVED = "quotation_received"

    # --- Fase 3: Valorización ---
    PENDING_VALORIZATION = "pending_valorization"
    VALORIZATION_APPROVED = "valorization_approved"

    # --- Fase 4: Orden de Compra ---
    PENDING_PO_EMISSION = "pending_po_emission"
    PENDING_PO_APPROVAL = "pending_po_approval"
    PO_APPROVED = "po_approved"
    PO_SENT_TO_SUPPLIER = "po_sent_to_supplier"

    # --- Fase 5: Recepción ---
    PENDING_RECEPTION = "pending_reception"
    RECEPTION_CONFORM = "reception_conform"

    # --- Fase 6: Factura y CxP ---
    PENDING_INVOICE = "pending_invoice"
    INVOICE_MATCHED = "invoice_matched"

    # --- Estados terminales ---
    CLOSED = "closed"
    REJECTED = "rejected"
    NON_CONFORMING = "non_conforming"
    CANCELLED = "cancelled"


class SCAction(str, enum.Enum):
    """Acciones que disparan transiciones de estado.

    Lo que un usuario "hace" (perspectiva de UX), distinto del estado al que
    llega la SC (perspectiva de dominio).
    """

    # Fase 1
    SUBMIT = "submit"                              # Solicitante envía SC para aprobación
    APPROVE_AREA = "approve_area"                  # Jefe de área aprueba
    REJECT_AREA = "reject_area"                    # Jefe de área rechaza
    RELEASE_BUDGET = "release_budget"              # Finanzas libera presupuesto
    FREEZE_BUDGET = "freeze_budget"                # Finanzas congela por falta de presupuesto
    AUTHORIZE_FROZEN = "authorize_frozen"          # Autorización superior libera congelada
    APPROVE_MANAGEMENT = "approve_management"      # Gerencia aprueba (RN-MONTO: > 5M)
    REJECT_MANAGEMENT = "reject_management"        # Gerencia rechaza (RN-MONTO: > 5M)

    # Fase 2 + 3
    REGISTER_QUOTATIONS = "register_quotations"    # Abastecimiento registra cotizaciones
    SEND_VALORIZATION = "send_valorization"        # Abastecimiento envía valorización al jefe área
    APPROVE_VALORIZATION = "approve_valorization"  # Jefe área aprueba valorización
    REQUEST_RECOTIZATION = "request_recotization"  # Jefe área pide recotización
    REJECT_VALORIZATION = "reject_valorization"    # Jefe área rechaza valorización

    # Fase 4
    EMIT_PO = "emit_po"                            # Abastecimiento emite OC
    APPROVE_PO = "approve_po"                      # Gerencia aprueba OC
    REJECT_PO = "reject_po"                        # Gerencia rechaza OC
    SEND_PO_TO_SUPPLIER = "send_po_to_supplier"    # Se envía OC al proveedor

    # Fase 5
    REGISTER_RECEPTION_CONFORM = "register_reception_conform"
    REGISTER_RECEPTION_NON_CONFORM = "register_reception_non_conform"

    # Fase 6
    RECEIVE_INVOICE = "receive_invoice"            # Llega DTE desde SII
    MATCH_INVOICE_OK = "match_invoice_ok"          # Matching 3-way exitoso
    MATCH_INVOICE_FAIL = "match_invoice_fail"      # Matching falla → reclamo
    CLOSE = "close"                                # Cierre formal del proceso

    # Cualquier fase
    CANCEL = "cancel"


# Mapa de transiciones permitidas: estado actual → estados destino válidos
ALLOWED_TRANSITIONS: dict[SCStatus, set[SCStatus]] = {
    SCStatus.DRAFT: {SCStatus.PENDING_AREA_APPROVAL, SCStatus.CANCELLED},
    SCStatus.PENDING_AREA_APPROVAL: {
        SCStatus.PENDING_BUDGET,           # > 1M (RN-MONTO-1)
        SCStatus.PENDING_QUOTATION,        # ≤ 1M (RN-MONTO-1)
        SCStatus.REJECTED,
        SCStatus.DRAFT,                    # devolución para corrección
        SCStatus.CANCELLED,
    },
    SCStatus.PENDING_BUDGET: {
        SCStatus.PENDING_QUOTATION,             # ≤ 5M (RN-MONTO-2)
        SCStatus.PENDING_MANAGEMENT_APPROVAL,   # > 5M (RN-MONTO-2)
        SCStatus.BUDGET_FROZEN,
        SCStatus.REJECTED,
        SCStatus.CANCELLED,
    },
    SCStatus.PENDING_MANAGEMENT_APPROVAL: {
        SCStatus.PENDING_QUOTATION,
        SCStatus.REJECTED,
        SCStatus.CANCELLED,
    },
    SCStatus.BUDGET_FROZEN: {
        SCStatus.PENDING_QUOTATION,   # con autorización superior
        SCStatus.REJECTED,
        SCStatus.CANCELLED,
    },
    SCStatus.PENDING_QUOTATION: {
        SCStatus.QUOTATION_RECEIVED,
        SCStatus.REJECTED,
        SCStatus.CANCELLED,
    },
    SCStatus.QUOTATION_RECEIVED: {
        SCStatus.PENDING_VALORIZATION,
        SCStatus.CANCELLED,
    },
    SCStatus.PENDING_VALORIZATION: {
        SCStatus.VALORIZATION_APPROVED,
        SCStatus.PENDING_QUOTATION,    # recotización
        SCStatus.REJECTED,
        SCStatus.CANCELLED,
    },
    SCStatus.VALORIZATION_APPROVED: {
        SCStatus.PENDING_PO_APPROVAL,
        SCStatus.CANCELLED,
    },
    SCStatus.PENDING_PO_EMISSION: {
        SCStatus.PENDING_PO_APPROVAL,
        SCStatus.CANCELLED,
    },
    SCStatus.PENDING_PO_APPROVAL: {
        SCStatus.PO_APPROVED,
        SCStatus.PENDING_PO_EMISSION,  # devuelta para corrección
        SCStatus.REJECTED,
        SCStatus.CANCELLED,
    },
    SCStatus.PO_APPROVED: {
        SCStatus.PO_SENT_TO_SUPPLIER,
        SCStatus.CANCELLED,
    },
    SCStatus.PO_SENT_TO_SUPPLIER: {
        SCStatus.PENDING_RECEPTION,
        SCStatus.CANCELLED,
    },
    SCStatus.PENDING_RECEPTION: {
        SCStatus.RECEPTION_CONFORM,
        SCStatus.NON_CONFORMING,
        SCStatus.CANCELLED,
    },
    SCStatus.RECEPTION_CONFORM: {
        SCStatus.PENDING_INVOICE,
    },
    SCStatus.PENDING_INVOICE: {
        SCStatus.INVOICE_MATCHED,
        SCStatus.PENDING_INVOICE,       # reclamo + reemisión
    },
    SCStatus.INVOICE_MATCHED: {
        SCStatus.CLOSED,
    },
    # Estados terminales: sin salidas
    SCStatus.CLOSED: set(),
    SCStatus.REJECTED: set(),
    SCStatus.NON_CONFORMING: set(),
    SCStatus.CANCELLED: set(),
}


# Mapa (estado actual, acción) → estado destino para transiciones SIN dependencia de monto.
# Las transiciones condicionales por monto viven en CONDITIONAL_ROUTES (más abajo).
TRANSITION_BY_ACTION: dict[tuple[SCStatus, SCAction], SCStatus] = {
    # Fase 1
    (SCStatus.DRAFT, SCAction.SUBMIT): SCStatus.PENDING_AREA_APPROVAL,
    (SCStatus.PENDING_AREA_APPROVAL, SCAction.REJECT_AREA): SCStatus.REJECTED,
    (SCStatus.PENDING_BUDGET, SCAction.FREEZE_BUDGET): SCStatus.BUDGET_FROZEN,
    (SCStatus.BUDGET_FROZEN, SCAction.AUTHORIZE_FROZEN): SCStatus.PENDING_QUOTATION,
    (SCStatus.PENDING_MANAGEMENT_APPROVAL, SCAction.APPROVE_MANAGEMENT): SCStatus.PENDING_QUOTATION,
    (SCStatus.PENDING_MANAGEMENT_APPROVAL, SCAction.REJECT_MANAGEMENT): SCStatus.REJECTED,

    # Fase 2 + 3
    (SCStatus.PENDING_QUOTATION, SCAction.REGISTER_QUOTATIONS): SCStatus.QUOTATION_RECEIVED,
    (SCStatus.QUOTATION_RECEIVED, SCAction.SEND_VALORIZATION): SCStatus.PENDING_VALORIZATION,
    (SCStatus.PENDING_VALORIZATION, SCAction.APPROVE_VALORIZATION): SCStatus.VALORIZATION_APPROVED,
    (SCStatus.PENDING_VALORIZATION, SCAction.REQUEST_RECOTIZATION): SCStatus.PENDING_QUOTATION,
    (SCStatus.PENDING_VALORIZATION, SCAction.REJECT_VALORIZATION): SCStatus.REJECTED,

    # Fase 4
    (SCStatus.VALORIZATION_APPROVED, SCAction.EMIT_PO): SCStatus.PENDING_PO_APPROVAL,
    (SCStatus.PENDING_PO_APPROVAL, SCAction.APPROVE_PO): SCStatus.PO_APPROVED,
    (SCStatus.PENDING_PO_APPROVAL, SCAction.REJECT_PO): SCStatus.REJECTED,
    (SCStatus.PO_APPROVED, SCAction.SEND_PO_TO_SUPPLIER): SCStatus.PO_SENT_TO_SUPPLIER,
    (SCStatus.PO_SENT_TO_SUPPLIER, SCAction.REGISTER_RECEPTION_CONFORM): SCStatus.PENDING_RECEPTION,

    # Fase 5
    (SCStatus.PENDING_RECEPTION, SCAction.REGISTER_RECEPTION_CONFORM): SCStatus.RECEPTION_CONFORM,
    (SCStatus.PENDING_RECEPTION, SCAction.REGISTER_RECEPTION_NON_CONFORM): SCStatus.NON_CONFORMING,
    (SCStatus.RECEPTION_CONFORM, SCAction.RECEIVE_INVOICE): SCStatus.PENDING_INVOICE,

    # Fase 6
    (SCStatus.PENDING_INVOICE, SCAction.MATCH_INVOICE_OK): SCStatus.INVOICE_MATCHED,
    (SCStatus.INVOICE_MATCHED, SCAction.CLOSE): SCStatus.CLOSED,

    # Cancelación: disponible desde varios estados (no terminales)
    (SCStatus.DRAFT, SCAction.CANCEL): SCStatus.CANCELLED,
    (SCStatus.PENDING_AREA_APPROVAL, SCAction.CANCEL): SCStatus.CANCELLED,
    (SCStatus.PENDING_BUDGET, SCAction.CANCEL): SCStatus.CANCELLED,
    (SCStatus.BUDGET_FROZEN, SCAction.CANCEL): SCStatus.CANCELLED,
    (SCStatus.PENDING_MANAGEMENT_APPROVAL, SCAction.CANCEL): SCStatus.CANCELLED,
    (SCStatus.PENDING_QUOTATION, SCAction.CANCEL): SCStatus.CANCELLED,
    (SCStatus.QUOTATION_RECEIVED, SCAction.CANCEL): SCStatus.CANCELLED,
    (SCStatus.PENDING_VALORIZATION, SCAction.CANCEL): SCStatus.CANCELLED,
    (SCStatus.VALORIZATION_APPROVED, SCAction.CANCEL): SCStatus.CANCELLED,
    (SCStatus.PENDING_PO_APPROVAL, SCAction.CANCEL): SCStatus.CANCELLED,
}


# RN-MONTO — Transiciones cuyo destino depende del `monto_estimado` de la SC.
# El service llama `apply_action(...)` pasando `monto_estimado`; el router decide.
def _route_approve_area(monto_estimado: Decimal) -> SCStatus:
    """RN-MONTO-1: ≤ 1M salta finanzas; > 1M pasa por PENDING_BUDGET."""
    if monto_estimado <= MONTO_TIER_FINANZAS:
        return SCStatus.PENDING_QUOTATION
    return SCStatus.PENDING_BUDGET


def _route_release_budget(monto_estimado: Decimal) -> SCStatus:
    """RN-MONTO-2: > 5M requiere aprobación gerencial temprana."""
    if monto_estimado > MONTO_TIER_GERENCIA:
        return SCStatus.PENDING_MANAGEMENT_APPROVAL
    return SCStatus.PENDING_QUOTATION


CONDITIONAL_ROUTES: dict[tuple[SCStatus, SCAction], Callable[[Decimal], SCStatus]] = {
    (SCStatus.PENDING_AREA_APPROVAL, SCAction.APPROVE_AREA): _route_approve_area,
    (SCStatus.PENDING_BUDGET, SCAction.RELEASE_BUDGET): _route_release_budget,
}


# RN-SLA — horas esperadas por estado antes de quedar fuera de SLA. Útil para
# que el solicitante vea "deadline esperado" y para alertas futuras.
SLA_HOURS_BY_STATUS = {
    SCStatus.DRAFT: None,                              # controlado por el solicitante
    SCStatus.PENDING_AREA_APPROVAL: 24,
    SCStatus.PENDING_BUDGET: 48,
    SCStatus.BUDGET_FROZEN: 168,                        # 1 semana — espera autorización superior
    SCStatus.PENDING_MANAGEMENT_APPROVAL: 72,
    SCStatus.PENDING_QUOTATION: 120,                    # 5 días para cotizar
    SCStatus.QUOTATION_RECEIVED: 24,
    SCStatus.PENDING_VALORIZATION: 48,
    SCStatus.VALORIZATION_APPROVED: 24,                 # esperando emit_po
    SCStatus.PENDING_PO_EMISSION: 24,
    SCStatus.PENDING_PO_APPROVAL: 48,
    SCStatus.PO_APPROVED: 24,                           # esperando envío
    SCStatus.PO_SENT_TO_SUPPLIER: 720,                  # 30 días — esperando entrega
    SCStatus.PENDING_RECEPTION: 168,
    SCStatus.RECEPTION_CONFORM: 720,                    # esperando factura del proveedor
    SCStatus.PENDING_INVOICE: 168,
    SCStatus.INVOICE_MATCHED: 24,
    SCStatus.CLOSED: None,
    SCStatus.REJECTED: None,
    SCStatus.NON_CONFORMING: None,
    SCStatus.CANCELLED: None,
}


# RN-ASSIGNEE — rol responsable de actuar en cada estado. Denormalizado en
# `SolicitudCompra.current_assignee_role` para que el solicitante (y futuros
# dashboards) vean a quién están esperando sin queries adicionales.
ASSIGNEE_ROLE_BY_STATUS = {
    SCStatus.DRAFT: "solicitante",
    SCStatus.PENDING_AREA_APPROVAL: "jefe_area",
    SCStatus.PENDING_BUDGET: "finanzas",
    SCStatus.BUDGET_FROZEN: "gerencia",
    SCStatus.PENDING_MANAGEMENT_APPROVAL: "gerencia",
    SCStatus.PENDING_QUOTATION: "abastecimiento",
    SCStatus.QUOTATION_RECEIVED: "abastecimiento",
    SCStatus.PENDING_VALORIZATION: "jefe_area",
    SCStatus.VALORIZATION_APPROVED: "abastecimiento",
    SCStatus.PENDING_PO_EMISSION: "abastecimiento",
    SCStatus.PENDING_PO_APPROVAL: "gerencia",
    SCStatus.PO_APPROVED: "abastecimiento",
    SCStatus.PO_SENT_TO_SUPPLIER: "bodega",
    SCStatus.PENDING_RECEPTION: "bodega",
    SCStatus.RECEPTION_CONFORM: "finanzas",
    SCStatus.PENDING_INVOICE: "finanzas",
    SCStatus.INVOICE_MATCHED: "finanzas",
    SCStatus.CLOSED: None,
    SCStatus.REJECTED: None,
    SCStatus.NON_CONFORMING: None,
    SCStatus.CANCELLED: None,
}


def validate_transition(from_status: SCStatus, to_status: SCStatus) -> None:
    """Valida que la transición esté permitida. Lanza InvalidTransitionError si no."""
    allowed = ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise InvalidTransitionError(
            f"Transición {from_status.value} → {to_status.value} no permitida. "
            f"Transiciones válidas desde {from_status.value}: "
            f"{sorted(s.value for s in allowed)}"
        )


def apply_action(
    current_status: SCStatus,
    action: SCAction,
    *,
    monto_estimado: Decimal | None = None,
) -> SCStatus:
    """Aplica una acción y devuelve el nuevo estado.

    Para acciones cuyo destino depende del monto (CONDITIONAL_ROUTES, RN-MONTO),
    `monto_estimado` es obligatorio. Para el resto se ignora.
    """
    key = (current_status, action)

    if key in CONDITIONAL_ROUTES:
        if monto_estimado is None:
            raise ValueError(
                f"La acción '{action.value}' desde '{current_status.value}' tiene "
                "ruteo condicional por monto (RN-MONTO) y requiere `monto_estimado`."
            )
        new_status = CONDITIONAL_ROUTES[key](monto_estimado)
    else:
        new_status = TRANSITION_BY_ACTION.get(key)

    if new_status is None:
        valid_actions = sorted(_actions_from_status(current_status, by_value=True))
        raise InvalidTransitionError(
            f"Acción '{action.value}' no aplicable en estado '{current_status.value}'. "
            f"Acciones válidas en este estado: {valid_actions}"
        )
    validate_transition(current_status, new_status)
    return new_status


def is_terminal(status: SCStatus) -> bool:
    """Indica si un estado es terminal (sin transiciones de salida)."""
    return len(ALLOWED_TRANSITIONS.get(status, set())) == 0


def available_actions(current_status: SCStatus) -> list[SCAction]:
    """Devuelve las acciones disponibles desde el estado actual.

    Útil para que el frontend muestre solo los botones válidos. Incluye
    tanto las transiciones estáticas como las condicionales por monto.
    """
    return list(_actions_from_status(current_status))


def _actions_from_status(
    current_status: SCStatus, *, by_value: bool = False
) -> list[SCAction] | list[str]:
    """Helper interno: enumera acciones disponibles uniendo static + conditional."""
    static = [a for (s, a) in TRANSITION_BY_ACTION if s == current_status]
    conditional = [a for (s, a) in CONDITIONAL_ROUTES if s == current_status]
    actions = static + conditional
    if by_value:
        return [a.value for a in actions]
    return actions
