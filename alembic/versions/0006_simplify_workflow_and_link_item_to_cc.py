"""drop monto, drop estados de monto, link catalogo_items a CC

Revision ID: 0006_simplify_and_link_item_cc
Revises: 0005_phase_status
Create Date: 2026-04-30 18:00:00

Refactor mayor del módulo de Solicitudes:

1. Drop info económica:
   - solicitudes_compra.monto_estimado
   - catalogo_items.precio_referencia

2. Drop estados de la matriz de monto del enum sc_status_enum:
   - pending_budget
   - budget_frozen
   - pending_management_approval
   El enum se recrea (Postgres no permite DROP VALUE). Las SCs en esos
   estados no pueden existir tras este refactor; intentamos migrarlas a
   pending_quotation, y si persisten, abortamos para forzar revisión manual.

3. Link CatalogoItem ↔ CentroCosto:
   - Agrega catalogo_items.centro_costo_id NOT NULL FK
   - SKU pasa de unique global a UNIQUE(sku, centro_costo_id)
   - Para datos existentes, asigna CC=1 (Mantención) como default; el seed
     post-migración se reescribe para distribuir por CCs reales.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0006_simplify_and_link_item_cc"
down_revision: str | None = "0005_phase_status"
branch_labels = None
depends_on = None


# Estados que sobreviven al refactor (los 3 eliminados se quitan del enum).
NEW_STATUS_VALUES = (
    "draft",
    "pending_area_approval",
    "pending_quotation",
    "quotation_received",
    "pending_valorization",
    "valorization_approved",
    "pending_po_emission",
    "pending_po_approval",
    "po_approved",
    "po_sent_to_supplier",
    "pending_reception",
    "reception_conform",
    "pending_invoice",
    "invoice_matched",
    "closed",
    "rejected",
    "non_conforming",
    "cancelled",
)


def upgrade() -> None:
    # --- 1. Drop columnas con info económica -------------------------------
    op.drop_column("solicitudes_compra", "monto_estimado")
    op.drop_column("catalogo_items", "precio_referencia")

    # --- 2. Recrear enum sc_status_enum sin estados de monto ---------------
    # Migrar SCs en estados eliminados a 'pending_quotation' como fallback.
    op.execute(
        "UPDATE solicitudes_compra "
        "SET status = 'pending_quotation' "
        "WHERE status IN ('pending_budget', 'budget_frozen', 'pending_management_approval')"
    )
    # Crear el enum nuevo
    new_enum = sa.Enum(*NEW_STATUS_VALUES, name="sc_status_enum_v2")
    new_enum.create(op.get_bind(), checkfirst=False)
    # Drop the column default BEFORE changing type — PostgreSQL cannot
    # auto-cast the existing default ('draft'::sc_status_enum) to the new type.
    op.execute(
        "ALTER TABLE solicitudes_compra "
        "ALTER COLUMN status DROP DEFAULT"
    )
    # Cambiar la columna al nuevo tipo (cast vía text)
    op.execute(
        "ALTER TABLE solicitudes_compra "
        "ALTER COLUMN status TYPE sc_status_enum_v2 "
        "USING status::text::sc_status_enum_v2"
    )
    # Drop del enum viejo, rename del nuevo
    op.execute("DROP TYPE sc_status_enum")
    op.execute("ALTER TYPE sc_status_enum_v2 RENAME TO sc_status_enum")
    # Restore the column default now that the enum has been renamed back
    op.execute(
        "ALTER TABLE solicitudes_compra "
        "ALTER COLUMN status SET DEFAULT 'draft'"
    )

    # --- 3. Link CatalogoItem a CentroCosto --------------------------------
    # Agregar columna con DEFAULT 1 para los items existentes (asignados a
    # Mantención = CC con id=1, asume que el seed lo creó). El default se
    # remueve después para que la columna sea explícitamente requerida.
    op.add_column(
        "catalogo_items",
        sa.Column(
            "centro_costo_id",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.create_foreign_key(
        "fk_catalogo_items_centro_costo_id_centros_costo",
        "catalogo_items",
        "centros_costo",
        ["centro_costo_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_catalogo_items_centro_costo_id",
        "catalogo_items",
        ["centro_costo_id"],
    )
    op.alter_column("catalogo_items", "centro_costo_id", server_default=None)

    # SKU: pasa de unique global a unique compuesto
    op.execute(
        "ALTER TABLE catalogo_items DROP CONSTRAINT IF EXISTS catalogo_items_sku_key"
    )
    # Pueden existir índices auto-generados; intentar drop por convención
    op.execute("DROP INDEX IF EXISTS ix_catalogo_items_sku")
    op.create_index("ix_catalogo_items_sku", "catalogo_items", ["sku"])
    op.create_unique_constraint(
        "uq_catalogo_items_sku_cc",
        "catalogo_items",
        ["sku", "centro_costo_id"],
    )


def downgrade() -> None:
    # Downgrade no implementado: el refactor elimina datos (montos, estados)
    # que no pueden reconstruirse. Para volver atrás, restaurar desde backup.
    raise NotImplementedError(
        "Downgrade no soportado: este refactor elimina datos económicos que "
        "no pueden reconstruirse. Restaurar desde backup si se necesita."
    )
