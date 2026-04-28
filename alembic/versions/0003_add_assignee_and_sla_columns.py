"""add current_assignee_role and expected_resolution_at to solicitudes_compra

Revision ID: 0003_assignee_sla
Revises: 0002_pending_mgmt_approval
Create Date: 2026-04-28 16:00:00

Campos denormalizados para que el frontend muestre:
- a quién está esperando la SC (`current_assignee_role`)
- hasta cuándo se espera respuesta (`expected_resolution_at`, calculado por SLA)

Sin estos campos, el frontend tendría que mirar el `status` y replicar
las tablas SLA/ASSIGNEE de state_machine.py — peor.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0003_assignee_sla"
down_revision: str | None = "0002_pending_mgmt_approval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "solicitudes_compra",
        sa.Column("current_assignee_role", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "solicitudes_compra",
        sa.Column("expected_resolution_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("solicitudes_compra", "expected_resolution_at")
    op.drop_column("solicitudes_compra", "current_assignee_role")
