"""Máquina de estados de la Solicitud de Compra.

Esta es la pieza más crítica del sistema: define el ciclo de vida de la SC
y las transiciones permitidas. Cualquier cambio de estado pasa por aquí
para garantizar consistencia y trazabilidad.

Diseño:
    - SCStatus: enum con todos los estados posibles
    - SCAction: enum con todas las acciones que disparan transiciones
    - ALLOWED_TRANSITIONS: mapa estado → estados destino válidos
    - TRANSITION_BY_ACTION: mapa (estado, acción) → estado destino

Las acciones son lo que el usuario hace; el estado es donde queda la SC
después de la acción. Esta separación permite que el frontend exponga
acciones en lugar de estados crudos.
"""

import enum

from sgp.core.exceptions import InvalidTransitionError


class SCStatus(str, enum.Enum):
    """Estados del ciclo de vida de una Solicitud de Compra.

    Cubre las 6 fases del proceso TO-BE definido en el PRD v2.0.
    """

    # --- Fase 1: Solicitud y aprobación inicial ---
    DRAFT = "draft"
    PENDING_AREA_APPROVAL = "pending_area_approval"
    PENDING_BUDGET = "pending_budget"
    BUDGET_FROZEN = "budget_frozen"

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
        SCStatus.PENDING_BUDGET,
        SCStatus.REJECTED,
        SCStatus.DRAFT,           # devolución para corrección
        SCStatus.CANCELLED,
    },
    SCStatus.PENDING_BUDGET: {
        SCStatus.PENDING_QUOTATION,
        SCStatus.BUDGET_FROZEN,
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


# Mapa (estado actual, acción) → estado destino
TRANSITION_BY_ACTION: dict[tuple[SCStatus, SCAction], SCStatus] = {
    # Fase 1
    (SCStatus.DRAFT, SCAction.SUBMIT): SCStatus.PENDING_AREA_APPROVAL,
    (SCStatus.PENDING_AREA_APPROVAL, SCAction.APPROVE_AREA): SCStatus.PENDING_BUDGET,
    (SCStatus.PENDING_AREA_APPROVAL, SCAction.REJECT_AREA): SCStatus.REJECTED,
    (SCStatus.PENDING_BUDGET, SCAction.RELEASE_BUDGET): SCStatus.PENDING_QUOTATION,
    (SCStatus.PENDING_BUDGET, SCAction.FREEZE_BUDGET): SCStatus.BUDGET_FROZEN,
    (SCStatus.BUDGET_FROZEN, SCAction.AUTHORIZE_FROZEN): SCStatus.PENDING_QUOTATION,

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
    (SCStatus.PENDING_QUOTATION, SCAction.CANCEL): SCStatus.CANCELLED,
    (SCStatus.QUOTATION_RECEIVED, SCAction.CANCEL): SCStatus.CANCELLED,
    (SCStatus.PENDING_VALORIZATION, SCAction.CANCEL): SCStatus.CANCELLED,
    (SCStatus.VALORIZATION_APPROVED, SCAction.CANCEL): SCStatus.CANCELLED,
    (SCStatus.PENDING_PO_APPROVAL, SCAction.CANCEL): SCStatus.CANCELLED,
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


def apply_action(current_status: SCStatus, action: SCAction) -> SCStatus:
    """Aplica una acción y devuelve el nuevo estado.

    Combina la búsqueda de la transición esperada y la validación.
    """
    new_status = TRANSITION_BY_ACTION.get((current_status, action))
    if new_status is None:
        valid_actions = [
            a.value for (s, a) in TRANSITION_BY_ACTION if s == current_status
        ]
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

    Útil para que el frontend muestre solo los botones válidos.
    """
    return [a for (s, a) in TRANSITION_BY_ACTION if s == current_status]
