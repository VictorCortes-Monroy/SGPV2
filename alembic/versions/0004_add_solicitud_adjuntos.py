"""add solicitud_adjuntos table

Revision ID: 0004_solicitud_adjuntos
Revises: 0003_assignee_sla
Create Date: 2026-04-28 17:00:00

Tabla para tracking de adjuntos de SCs. El archivo binario vive en disco
(Railway volume hoy, Azure Blob a futuro); acá guardamos solo metadata.
`stored_path` es relativo al root del backend de storage.

Soft delete: `deleted_at` permite preservar la fila como evidencia (auditoría)
incluso después de borrar el archivo.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0004_solicitud_adjuntos"
down_revision: str | None = "0003_assignee_sla"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "solicitud_adjuntos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("solicitud_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["solicitud_id"],
            ["solicitudes_compra.id"],
            name="fk_solicitud_adjuntos_solicitud_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["usuarios.id"],
            name="fk_solicitud_adjuntos_uploaded_by_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_solicitud_adjuntos"),
    )
    op.create_index(
        "ix_solicitud_adjuntos_solicitud_id",
        "solicitud_adjuntos",
        ["solicitud_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_solicitud_adjuntos_solicitud_id", table_name="solicitud_adjuntos")
    op.drop_table("solicitud_adjuntos")
