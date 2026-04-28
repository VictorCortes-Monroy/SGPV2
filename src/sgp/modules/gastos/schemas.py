"""Schemas para el resumen de gastos."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class GastoPorCentroCosto(BaseModel):
    centro_costo_id: int
    centro_costo_codigo: str
    centro_costo_nombre: str
    comprometido: Decimal           # SCs no rechazadas/canceladas/draft
    ejecutado: Decimal              # SCs CLOSED
    scs_comprometidas: int
    scs_ejecutadas: int


class ResumenGastos(BaseModel):
    """Resumen de gasto comprometido vs ejecutado para un periodo y empresa.

    - **Comprometido**: SCs aprobadas/avanzando que ya generaron expectativa de
      gasto (excluye DRAFT, REJECTED, CANCELLED, NON_CONFORMING).
    - **Ejecutado**: SCs en estado CLOSED (gasto completado y cerrado).
    - Filtrado por `created_at` de la SC contra el periodo. La distinción
      "fecha aprobación" vs "fecha creación" se omite en MVP.
    """

    empresa_id: int
    empresa_nombre: str
    periodo_desde: date
    periodo_hasta: date
    comprometido_total: Decimal
    ejecutado_total: Decimal
    scs_comprometidas_total: int
    scs_ejecutadas_total: int
    por_centro_costo: list[GastoPorCentroCosto]
