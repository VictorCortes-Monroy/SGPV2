"""Schemas Pydantic para Solicitudes de Compra."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sgp.modules.solicitudes.models import TipoCompra, Urgencia
from sgp.modules.solicitudes.state_machine import SCAction, SCStatus


# ===== Líneas =====
class LineaCreate(BaseModel):
    item_id: int = Field(..., gt=0)
    cantidad: Decimal = Field(..., gt=0)
    especificacion: str | None = None


class LineaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    item_sku: str
    item_nombre: str
    cantidad: Decimal
    especificacion: str | None = None


# ===== SC =====
class SolicitudCompraCreate(BaseModel):
    """Payload para crear una SC en estado DRAFT.

    Nota: el solicitante NO ingresa `monto_estimado`. El sistema lo calcula
    como Σ(cantidad × precio_referencia) de las líneas. Las líneas cuyo item
    no tiene precio_referencia contribuyen 0 al monto estimado (la cotización
    posterior corregirá el monto real).
    """

    empresa_id: int = Field(..., gt=0)
    centro_costo_id: int = Field(..., gt=0)
    tipo: TipoCompra
    urgencia: Urgencia = Urgencia.NORMAL
    descripcion: str = Field(..., min_length=10, max_length=2000)
    justificacion: str | None = Field(None, max_length=2000)
    fecha_requerida: date
    lineas: list[LineaCreate] = Field(..., min_length=1)

    @field_validator("fecha_requerida")
    @classmethod
    def _fecha_no_en_pasado(cls, v: date) -> date:
        """RN-DAT-3: la fecha requerida no puede ser anterior a hoy."""
        if v < date.today():
            raise ValueError(
                f"fecha_requerida ({v.isoformat()}) no puede ser anterior a hoy"
            )
        return v


class SolicitudCompraRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: str
    empresa_id: int
    centro_costo_id: int
    solicitante_id: int
    tipo: TipoCompra
    urgencia: Urgencia
    descripcion: str
    justificacion: str | None
    monto_estimado: Decimal
    fecha_requerida: date
    status: SCStatus
    recotization_cycles: int
    current_assignee_role: str | None = None
    expected_resolution_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    lineas: list[LineaRead] = []
    available_actions: list[SCAction] = []


class TransitionRequest(BaseModel):
    """Payload para ejecutar una acción sobre una SC."""

    action: SCAction
    comment: str | None = Field(None, max_length=2000)
