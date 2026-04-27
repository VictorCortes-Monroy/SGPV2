"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-27 00:00:00

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===== Enums =====
    sc_status = sa.Enum(
        "draft",
        "pending_area_approval",
        "pending_budget",
        "budget_frozen",
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
        name="sc_status_enum",
    )
    tipo_compra = sa.Enum("BIEN", "SERVICIO", name="tipo_compra_enum")
    urgencia = sa.Enum("NORMAL", "URGENTE", "CRITICA", name="urgencia_enum")
    unidad_medida = sa.Enum(
        "UN", "KG", "LT", "M", "M2", "M3", "HR", "SVC", name="unidad_medida_enum"
    )
    criticidad = sa.Enum("CRITICO", "ESTANDAR", "GENERICO", name="criticidad_enum")

    # ===== Empresas =====
    op.create_table(
        "empresas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rut", sa.String(length=20), nullable=False),
        sa.Column("razon_social", sa.String(length=255), nullable=False),
        sa.Column("nombre_corto", sa.String(length=100), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_empresas"),
        sa.UniqueConstraint("rut", name="uq_empresas_rut"),
    )

    # ===== Centros de costo =====
    op.create_table(
        "centros_costo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=50), nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["empresa_id"],
            ["empresas.id"],
            name="fk_centros_costo_empresa_id_empresas",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_centros_costo"),
    )

    # ===== Roles =====
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=50), nullable=False),
        sa.Column("descripcion", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("nombre", name="uq_roles_nombre"),
    )

    # ===== Usuarios =====
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clerk_user_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_usuarios"),
        sa.UniqueConstraint("clerk_user_id", name="uq_usuarios_clerk_user_id"),
        sa.UniqueConstraint("email", name="uq_usuarios_email"),
    )
    op.create_index("ix_usuarios_clerk_user_id", "usuarios", ["clerk_user_id"])
    op.create_index("ix_usuarios_email", "usuarios", ["email"])

    # ===== Tabla intermedia usuario ↔ rol =====
    op.create_table(
        "usuarios_roles",
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("rol_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name="fk_usuarios_roles_usuario_id_usuarios",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rol_id"], ["roles.id"], name="fk_usuarios_roles_rol_id_roles", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"],
            ["empresas.id"],
            name="fk_usuarios_roles_empresa_id_empresas",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("usuario_id", "rol_id", name="pk_usuarios_roles"),
        sa.UniqueConstraint(
            "usuario_id", "rol_id", "empresa_id", name="uq_usuario_rol_empresa"
        ),
    )

    # ===== Familias (taxonomía) =====
    op.create_table(
        "familias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("nivel", sa.Integer(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["familias.id"],
            name="fk_familias_parent_id_familias",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_familias"),
    )

    # ===== Catálogo de items =====
    op.create_table(
        "catalogo_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("familia_id", sa.Integer(), nullable=False),
        sa.Column("unidad_medida", unidad_medida, nullable=False),
        sa.Column("especificacion_tecnica", sa.Text(), nullable=True),
        sa.Column("precio_referencia", sa.Numeric(15, 2), nullable=True),
        sa.Column(
            "criticidad", criticidad, nullable=False, server_default="ESTANDAR"
        ),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["familia_id"],
            ["familias.id"],
            name="fk_catalogo_items_familia_id_familias",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_catalogo_items"),
        sa.UniqueConstraint("sku", name="uq_catalogo_items_sku"),
    )
    op.create_index("ix_catalogo_items_sku", "catalogo_items", ["sku"])

    # ===== Solicitudes de Compra =====
    op.create_table(
        "solicitudes_compra",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.String(length=50), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("centro_costo_id", sa.Integer(), nullable=False),
        sa.Column("solicitante_id", sa.Integer(), nullable=False),
        sa.Column("tipo", tipo_compra, nullable=False),
        sa.Column("urgencia", urgencia, nullable=False, server_default="NORMAL"),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("justificacion", sa.Text(), nullable=True),
        sa.Column("monto_estimado", sa.Numeric(15, 2), nullable=False),
        sa.Column("fecha_requerida", sa.Date(), nullable=False),
        sa.Column("status", sc_status, nullable=False, server_default="draft"),
        sa.Column("recotization_cycles", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("approved_by_area_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["empresa_id"],
            ["empresas.id"],
            name="fk_solicitudes_compra_empresa_id_empresas",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["centro_costo_id"],
            ["centros_costo.id"],
            name="fk_solicitudes_compra_centro_costo_id_centros_costo",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["solicitante_id"],
            ["usuarios.id"],
            name="fk_solicitudes_compra_solicitante_id_usuarios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_area_id"],
            ["usuarios.id"],
            name="fk_solicitudes_compra_approved_by_area_id_usuarios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_solicitudes_compra"),
        sa.UniqueConstraint("numero", name="uq_solicitudes_compra_numero"),
    )
    op.create_index("ix_solicitudes_compra_numero", "solicitudes_compra", ["numero"])
    op.create_index("ix_solicitudes_compra_status", "solicitudes_compra", ["status"])

    # ===== Líneas de SC =====
    op.create_table(
        "solicitudes_compra_lineas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("solicitud_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Numeric(15, 4), nullable=False),
        sa.Column("especificacion", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["solicitud_id"],
            ["solicitudes_compra.id"],
            name="fk_solicitudes_compra_lineas_solicitud_id_solicitudes_compra",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["catalogo_items.id"],
            name="fk_solicitudes_compra_lineas_item_id_catalogo_items",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_solicitudes_compra_lineas"),
    )

    # ===== Audit log =====
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", sa.String(length=50), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("before_state", postgresql.JSON(), nullable=True),
        sa.Column("after_state", postgresql.JSON(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["usuarios.id"], name="fk_audit_log_actor_id_usuarios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_entity_type", "audit_log", ["entity_type"])
    op.create_index("ix_audit_log_entity_id", "audit_log", ["entity_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])

    # ===== Trigger PL/pgSQL: audit_log es append-only (RN5) =====
    # Cualquier UPDATE o DELETE sobre audit_log lanza excepción.
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_log es append-only (RN5): UPDATE y DELETE prohibidos. Operación: %', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_log_no_modify
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_modification();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_no_modify ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification();")

    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_entity_id", table_name="audit_log")
    op.drop_index("ix_audit_log_entity_type", table_name="audit_log")
    op.drop_index("ix_audit_log_timestamp", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_table("solicitudes_compra_lineas")
    op.drop_index("ix_solicitudes_compra_status", table_name="solicitudes_compra")
    op.drop_index("ix_solicitudes_compra_numero", table_name="solicitudes_compra")
    op.drop_table("solicitudes_compra")

    op.drop_index("ix_catalogo_items_sku", table_name="catalogo_items")
    op.drop_table("catalogo_items")
    op.drop_table("familias")

    op.drop_table("usuarios_roles")
    op.drop_index("ix_usuarios_email", table_name="usuarios")
    op.drop_index("ix_usuarios_clerk_user_id", table_name="usuarios")
    op.drop_table("usuarios")
    op.drop_table("roles")
    op.drop_table("centros_costo")
    op.drop_table("empresas")

    # Drop enums
    sa.Enum(name="criticidad_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="unidad_medida_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="urgencia_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="tipo_compra_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="sc_status_enum").drop(op.get_bind(), checkfirst=True)
