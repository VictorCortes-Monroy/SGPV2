"""add pending_management_approval to sc_status_enum (RN-MONTO)

Revision ID: 0002_pending_mgmt_approval
Revises: 0001_initial
Create Date: 2026-04-28 14:00:00

Agrega el estado `pending_management_approval` al enum nativo de Postgres
para soportar la matriz de aprobación por monto (RN-MONTO):
SCs con monto_estimado > 5M requieren aprobación gerencial temprana.

Nota: ALTER TYPE ... ADD VALUE no puede correr dentro de un block transaccional.
Por eso usamos `op.execute` con `COMMIT` manual o `IF NOT EXISTS`.
"""

from alembic import op

revision: str = "0002_pending_mgmt_approval"
down_revision: str | None = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS evita reventar si la migración se reejecuta.
    op.execute(
        "ALTER TYPE sc_status_enum ADD VALUE IF NOT EXISTS "
        "'pending_management_approval' AFTER 'budget_frozen';"
    )


def downgrade() -> None:
    # Postgres no permite eliminar valores de un enum existente sin recrearlo.
    # Para downgrade real, habría que recrear el enum y re-mapear filas. Lo
    # dejamos como no-op explícito y documentado.
    pass
