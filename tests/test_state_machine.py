"""Tests de la máquina de estados de SC.

Estos tests son críticos: garantizan que el corazón del proceso de compras
no permita transiciones inválidas. Son los tests más importantes del sistema.
"""

from decimal import Decimal

import pytest

from sgp.core.exceptions import InvalidTransitionError
from sgp.modules.solicitudes.state_machine import (
    ALLOWED_TRANSITIONS,
    MONTO_TIER_FINANZAS,
    MONTO_TIER_GERENCIA,
    SCAction,
    SCStatus,
    apply_action,
    available_actions,
    is_terminal,
    validate_transition,
)

# Atajos para tests del ruteo por monto
MONTO_BAJO = Decimal("500000")        # ≤ 1M → no requiere finanzas
MONTO_MEDIO = Decimal("3000000")      # 1M < x ≤ 5M → requiere finanzas
MONTO_ALTO = Decimal("8000000")       # > 5M → requiere finanzas + gerencia


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

    def test_approve_area_con_monto_medio_pasa_a_pending_budget(self):
        new = apply_action(
            SCStatus.PENDING_AREA_APPROVAL, SCAction.APPROVE_AREA, monto_estimado=MONTO_MEDIO
        )
        assert new == SCStatus.PENDING_BUDGET

    def test_release_budget_con_monto_medio_pasa_a_pending_quotation(self):
        new = apply_action(
            SCStatus.PENDING_BUDGET, SCAction.RELEASE_BUDGET, monto_estimado=MONTO_MEDIO
        )
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

    def test_pending_area_approval_incluye_approve_area_condicional(self):
        """available_actions debe incluir las rutas condicionales (no solo TRANSITION_BY_ACTION)."""
        actions = available_actions(SCStatus.PENDING_AREA_APPROVAL)
        assert SCAction.APPROVE_AREA in actions  # condicional
        assert SCAction.REJECT_AREA in actions   # estática

    def test_pending_management_approval_actions(self):
        actions = available_actions(SCStatus.PENDING_MANAGEMENT_APPROVAL)
        assert SCAction.APPROVE_MANAGEMENT in actions
        assert SCAction.REJECT_MANAGEMENT in actions
        assert SCAction.CANCEL in actions


class TestFlujoCompletoFelizPath:
    """Verifica que el camino feliz completo sea consistente.

    Flujo: DRAFT → ... → CLOSED sin rechazos ni recotizaciones.
    """

    def test_camino_feliz_completo_tramo_medio(self):
        """Flujo 1M < monto ≤ 5M (jefe + finanzas, sin gerencia early)."""
        monto = MONTO_MEDIO
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
            assert apply_action(from_state, action, monto_estimado=monto) == expected, (
                f"Falla en transición: {from_state} -[{action.value}]→ esperaba {expected}"
            )


class TestRNMontoRuteoCondicional:
    """Verifica que el ruteo condicional por monto (RN-MONTO-1, RN-MONTO-2)
    elija el destino correcto según el tramo del `monto_estimado`."""

    def test_approve_area_monto_bajo_salta_finanzas(self):
        """≤ 1M va directo a PENDING_QUOTATION (RN-MONTO-1)."""
        new = apply_action(
            SCStatus.PENDING_AREA_APPROVAL, SCAction.APPROVE_AREA, monto_estimado=MONTO_BAJO
        )
        assert new == SCStatus.PENDING_QUOTATION

    def test_approve_area_monto_medio_pasa_por_finanzas(self):
        """1M < monto ≤ 5M pasa por PENDING_BUDGET."""
        new = apply_action(
            SCStatus.PENDING_AREA_APPROVAL, SCAction.APPROVE_AREA, monto_estimado=MONTO_MEDIO
        )
        assert new == SCStatus.PENDING_BUDGET

    def test_approve_area_monto_alto_pasa_por_finanzas(self):
        """> 5M también pasa primero por finanzas (no se salta)."""
        new = apply_action(
            SCStatus.PENDING_AREA_APPROVAL, SCAction.APPROVE_AREA, monto_estimado=MONTO_ALTO
        )
        assert new == SCStatus.PENDING_BUDGET

    def test_approve_area_en_umbral_1m_no_requiere_finanzas(self):
        """Borde inferior del tramo medio: monto = 1M exacto NO requiere finanzas (≤)."""
        new = apply_action(
            SCStatus.PENDING_AREA_APPROVAL,
            SCAction.APPROVE_AREA,
            monto_estimado=MONTO_TIER_FINANZAS,
        )
        assert new == SCStatus.PENDING_QUOTATION

    def test_release_budget_monto_medio_va_a_quotation(self):
        """≤ 5M tras finanzas va a cotización (no requiere gerencia early)."""
        new = apply_action(
            SCStatus.PENDING_BUDGET, SCAction.RELEASE_BUDGET, monto_estimado=MONTO_MEDIO
        )
        assert new == SCStatus.PENDING_QUOTATION

    def test_release_budget_monto_alto_va_a_management(self):
        """> 5M tras finanzas requiere aprobación gerencial temprana (RN-MONTO-2)."""
        new = apply_action(
            SCStatus.PENDING_BUDGET, SCAction.RELEASE_BUDGET, monto_estimado=MONTO_ALTO
        )
        assert new == SCStatus.PENDING_MANAGEMENT_APPROVAL

    def test_release_budget_en_umbral_5m_no_requiere_gerencia(self):
        """Borde superior del tramo medio: monto = 5M exacto NO requiere gerencia (>)."""
        new = apply_action(
            SCStatus.PENDING_BUDGET,
            SCAction.RELEASE_BUDGET,
            monto_estimado=MONTO_TIER_GERENCIA,
        )
        assert new == SCStatus.PENDING_QUOTATION

    def test_accion_condicional_sin_monto_lanza(self):
        """APPROVE_AREA y RELEASE_BUDGET requieren monto_estimado para rutear."""
        with pytest.raises(ValueError, match="monto_estimado"):
            apply_action(SCStatus.PENDING_AREA_APPROVAL, SCAction.APPROVE_AREA)
        with pytest.raises(ValueError, match="monto_estimado"):
            apply_action(SCStatus.PENDING_BUDGET, SCAction.RELEASE_BUDGET)

    def test_accion_no_condicional_ignora_monto(self):
        """SUBMIT, REJECT_AREA, etc. no requieren monto."""
        new = apply_action(SCStatus.DRAFT, SCAction.SUBMIT)
        assert new == SCStatus.PENDING_AREA_APPROVAL

    def test_approve_management_pasa_a_pending_quotation(self):
        new = apply_action(SCStatus.PENDING_MANAGEMENT_APPROVAL, SCAction.APPROVE_MANAGEMENT)
        assert new == SCStatus.PENDING_QUOTATION

    def test_reject_management_pasa_a_rejected(self):
        new = apply_action(SCStatus.PENDING_MANAGEMENT_APPROVAL, SCAction.REJECT_MANAGEMENT)
        assert new == SCStatus.REJECTED


class TestCaminoFelizPorTramo:
    """Verifica las 3 trayectorias por monto desde DRAFT hasta PENDING_QUOTATION."""

    def test_tramo_bajo_salta_finanzas_y_gerencia(self):
        # DRAFT → PENDING_AREA_APPROVAL → PENDING_QUOTATION
        s = apply_action(SCStatus.DRAFT, SCAction.SUBMIT)
        s = apply_action(s, SCAction.APPROVE_AREA, monto_estimado=MONTO_BAJO)
        assert s == SCStatus.PENDING_QUOTATION

    def test_tramo_medio_pasa_por_finanzas_sin_gerencia(self):
        # DRAFT → PENDING_AREA_APPROVAL → PENDING_BUDGET → PENDING_QUOTATION
        s = apply_action(SCStatus.DRAFT, SCAction.SUBMIT)
        s = apply_action(s, SCAction.APPROVE_AREA, monto_estimado=MONTO_MEDIO)
        assert s == SCStatus.PENDING_BUDGET
        s = apply_action(s, SCAction.RELEASE_BUDGET, monto_estimado=MONTO_MEDIO)
        assert s == SCStatus.PENDING_QUOTATION

    def test_tramo_alto_pasa_por_finanzas_y_gerencia(self):
        # DRAFT → PENDING_AREA_APPROVAL → PENDING_BUDGET → PENDING_MANAGEMENT_APPROVAL → PENDING_QUOTATION
        s = apply_action(SCStatus.DRAFT, SCAction.SUBMIT)
        s = apply_action(s, SCAction.APPROVE_AREA, monto_estimado=MONTO_ALTO)
        assert s == SCStatus.PENDING_BUDGET
        s = apply_action(s, SCAction.RELEASE_BUDGET, monto_estimado=MONTO_ALTO)
        assert s == SCStatus.PENDING_MANAGEMENT_APPROVAL
        s = apply_action(s, SCAction.APPROVE_MANAGEMENT)
        assert s == SCStatus.PENDING_QUOTATION


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

    def test_destinos_condicionales_estan_en_allowed(self):
        """Cada CONDITIONAL_ROUTES debe poder devolver solo destinos válidos."""
        from sgp.modules.solicitudes.state_machine import CONDITIONAL_ROUTES

        montos_de_prueba = [
            Decimal("0"),
            MONTO_TIER_FINANZAS,
            MONTO_TIER_FINANZAS + Decimal("1"),
            MONTO_TIER_GERENCIA,
            MONTO_TIER_GERENCIA + Decimal("1"),
        ]
        for (from_status, action), router in CONDITIONAL_ROUTES.items():
            for monto in montos_de_prueba:
                destino = router(monto)
                assert destino in ALLOWED_TRANSITIONS[from_status], (
                    f"Ruta condicional {from_status} -[{action}]({monto})→ {destino} "
                    f"no está en ALLOWED_TRANSITIONS"
                )

    def test_todos_los_estados_tienen_entrada_en_allowed(self):
        for status in SCStatus:
            assert status in ALLOWED_TRANSITIONS, f"Estado {status} no tiene entrada en ALLOWED_TRANSITIONS"
