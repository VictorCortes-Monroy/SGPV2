"""Tests de la máquina de estados de SC.

Estos tests son críticos: garantizan que el corazón del proceso de compras
no permita transiciones inválidas. Son los tests más importantes del sistema.
"""

import pytest

from sgp.core.exceptions import InvalidTransitionError
from sgp.modules.solicitudes.state_machine import (
    ALLOWED_TRANSITIONS,
    SCAction,
    SCStatus,
    apply_action,
    available_actions,
    is_terminal,
    validate_transition,
)


class TestValidateTransition:
    def test_transicion_valida_no_lanza(self):
        validate_transition(SCStatus.DRAFT, SCStatus.PENDING_AREA_APPROVAL)

    def test_transicion_invalida_lanza(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition(SCStatus.DRAFT, SCStatus.CLOSED)

    def test_estado_terminal_sin_salidas(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition(SCStatus.CLOSED, SCStatus.PENDING_AREA_APPROVAL)


class TestApplyAction:
    def test_submit_desde_draft_pasa_a_pending_area(self):
        new = apply_action(SCStatus.DRAFT, SCAction.SUBMIT)
        assert new == SCStatus.PENDING_AREA_APPROVAL

    def test_approve_area_pasa_a_pending_budget(self):
        new = apply_action(SCStatus.PENDING_AREA_APPROVAL, SCAction.APPROVE_AREA)
        assert new == SCStatus.PENDING_BUDGET

    def test_release_budget_pasa_a_pending_quotation(self):
        new = apply_action(SCStatus.PENDING_BUDGET, SCAction.RELEASE_BUDGET)
        assert new == SCStatus.PENDING_QUOTATION

    def test_request_recotization_vuelve_a_pending_quotation(self):
        new = apply_action(SCStatus.PENDING_VALORIZATION, SCAction.REQUEST_RECOTIZATION)
        assert new == SCStatus.PENDING_QUOTATION

    def test_reject_area_pasa_a_rejected(self):
        new = apply_action(SCStatus.PENDING_AREA_APPROVAL, SCAction.REJECT_AREA)
        assert new == SCStatus.REJECTED

    def test_freeze_budget_pasa_a_budget_frozen(self):
        new = apply_action(SCStatus.PENDING_BUDGET, SCAction.FREEZE_BUDGET)
        assert new == SCStatus.BUDGET_FROZEN

    def test_authorize_frozen_libera(self):
        new = apply_action(SCStatus.BUDGET_FROZEN, SCAction.AUTHORIZE_FROZEN)
        assert new == SCStatus.PENDING_QUOTATION

    def test_accion_no_aplicable_lanza(self):
        with pytest.raises(InvalidTransitionError) as exc_info:
            apply_action(SCStatus.DRAFT, SCAction.APPROVE_AREA)
        assert "no aplicable" in str(exc_info.value).lower()

    def test_close_solo_desde_invoice_matched(self):
        new = apply_action(SCStatus.INVOICE_MATCHED, SCAction.CLOSE)
        assert new == SCStatus.CLOSED

        with pytest.raises(InvalidTransitionError):
            apply_action(SCStatus.PENDING_RECEPTION, SCAction.CLOSE)


class TestEstadosTerminales:
    @pytest.mark.parametrize(
        "status",
        [
            SCStatus.CLOSED,
            SCStatus.REJECTED,
            SCStatus.NON_CONFORMING,
            SCStatus.CANCELLED,
        ],
    )
    def test_estados_sin_salida_son_terminales(self, status):
        assert is_terminal(status) is True
        assert ALLOWED_TRANSITIONS[status] == set()

    @pytest.mark.parametrize(
        "status",
        [
            SCStatus.DRAFT,
            SCStatus.PENDING_AREA_APPROVAL,
            SCStatus.PENDING_QUOTATION,
        ],
    )
    def test_estados_intermedios_no_son_terminales(self, status):
        assert is_terminal(status) is False


class TestAvailableActions:
    def test_draft_tiene_acciones(self):
        actions = available_actions(SCStatus.DRAFT)
        assert SCAction.SUBMIT in actions
        assert SCAction.CANCEL in actions

    def test_terminal_no_tiene_acciones(self):
        # Las acciones disponibles vienen de TRANSITION_BY_ACTION,
        # los terminales no tienen entradas como origen.
        actions = available_actions(SCStatus.CLOSED)
        assert actions == []

    def test_pending_valorization_tiene_tres_caminos(self):
        actions = available_actions(SCStatus.PENDING_VALORIZATION)
        assert SCAction.APPROVE_VALORIZATION in actions
        assert SCAction.REQUEST_RECOTIZATION in actions
        assert SCAction.REJECT_VALORIZATION in actions


class TestFlujoCompletoFelizPath:
    """Verifica que el camino feliz completo sea consistente.

    Flujo: DRAFT → ... → CLOSED sin rechazos ni recotizaciones.
    """

    def test_camino_feliz_completo(self):
        sc_actions_path = [
            (SCStatus.DRAFT, SCAction.SUBMIT, SCStatus.PENDING_AREA_APPROVAL),
            (SCStatus.PENDING_AREA_APPROVAL, SCAction.APPROVE_AREA, SCStatus.PENDING_BUDGET),
            (SCStatus.PENDING_BUDGET, SCAction.RELEASE_BUDGET, SCStatus.PENDING_QUOTATION),
            (SCStatus.PENDING_QUOTATION, SCAction.REGISTER_QUOTATIONS, SCStatus.QUOTATION_RECEIVED),
            (SCStatus.QUOTATION_RECEIVED, SCAction.SEND_VALORIZATION, SCStatus.PENDING_VALORIZATION),
            (SCStatus.PENDING_VALORIZATION, SCAction.APPROVE_VALORIZATION, SCStatus.VALORIZATION_APPROVED),
            (SCStatus.VALORIZATION_APPROVED, SCAction.EMIT_PO, SCStatus.PENDING_PO_APPROVAL),
            (SCStatus.PENDING_PO_APPROVAL, SCAction.APPROVE_PO, SCStatus.PO_APPROVED),
            (SCStatus.PO_APPROVED, SCAction.SEND_PO_TO_SUPPLIER, SCStatus.PO_SENT_TO_SUPPLIER),
            (SCStatus.PO_SENT_TO_SUPPLIER, SCAction.REGISTER_RECEPTION_CONFORM, SCStatus.PENDING_RECEPTION),
            (SCStatus.PENDING_RECEPTION, SCAction.REGISTER_RECEPTION_CONFORM, SCStatus.RECEPTION_CONFORM),
            (SCStatus.RECEPTION_CONFORM, SCAction.RECEIVE_INVOICE, SCStatus.PENDING_INVOICE),
            (SCStatus.PENDING_INVOICE, SCAction.MATCH_INVOICE_OK, SCStatus.INVOICE_MATCHED),
            (SCStatus.INVOICE_MATCHED, SCAction.CLOSE, SCStatus.CLOSED),
        ]
        for from_state, action, expected in sc_actions_path:
            assert apply_action(from_state, action) == expected, (
                f"Falla en transición: {from_state} -[{action.value}]→ esperaba {expected}"
            )


class TestCoherenciaDelMapa:
    """Verifica la integridad del mapa de transiciones."""

    def test_todos_los_destinos_de_acciones_estan_en_allowed(self):
        """Cada (estado, acción) → destino debe estar en ALLOWED_TRANSITIONS."""
        from sgp.modules.solicitudes.state_machine import TRANSITION_BY_ACTION

        for (from_status, action), to_status in TRANSITION_BY_ACTION.items():
            assert to_status in ALLOWED_TRANSITIONS[from_status], (
                f"Transición {from_status} -[{action}]→ {to_status} declarada en "
                f"TRANSITION_BY_ACTION pero no en ALLOWED_TRANSITIONS"
            )

    def test_todos_los_estados_tienen_entrada_en_allowed(self):
        for status in SCStatus:
            assert status in ALLOWED_TRANSITIONS, f"Estado {status} no tiene entrada en ALLOWED_TRANSITIONS"
