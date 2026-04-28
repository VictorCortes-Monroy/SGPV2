"""Schemas Pydantic para adjuntos."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdjuntoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    solicitud_id: int
    uploaded_by_id: int
    filename: str
    content_type: str
    size_bytes: int
    phase_status: str | None = None
    created_at: datetime
