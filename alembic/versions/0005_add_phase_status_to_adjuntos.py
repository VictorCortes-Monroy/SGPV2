"""add phase_status column to solicitud_adjuntos

Revision ID: 0005_phase_status
Revises: 0004_solicitud_adjuntos
Create Date: 2026-04-28 18:00:00

`phase_status` captura el estado de la SC al momento de subir el adjunto.
Permite al aprobador agrupar/filtrar los documentos por fase del workflow
("docs subidos en cotización" vs "docs subidos en recepción") sin tener
que cruzar con el audit_log.

Se almacena como String (no como enum nativo) para no acoplar la tabla
de adjuntos al ciclo de vida del enum sc_status_enum, y porque la
información es informativa, no estructural.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0005_phase_status"
down_revision: str | None = "0004_solicitud_adjuntos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "solicitud_adjuntos",
        sa.Column("phase_status", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("solicitud_adjuntos", "phase_status")
