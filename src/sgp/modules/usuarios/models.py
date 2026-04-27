"""Modelos de datos: usuarios y roles."""

from sqlalchemy import Boolean, ForeignKey, String, Table, Column, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sgp.core.database import Base, TimestampMixin


# Tabla intermedia usuario ↔ rol con scope opcional por empresa
usuario_roles_table = Table(
    "usuarios_roles",
    Base.metadata,
    Column("usuario_id", Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
    Column("rol_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("empresa_id", Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=True),
    UniqueConstraint("usuario_id", "rol_id", "empresa_id", name="uq_usuario_rol_empresa"),
)


class Rol(Base, TimestampMixin):
    """Rol del sistema. Catálogo cerrado."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Usuario(Base, TimestampMixin):
    """Usuario del sistema. Vinculado a Clerk vía clerk_user_id."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    clerk_user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    roles: Mapped[list[Rol]] = relationship(
        secondary=usuario_roles_table,
        lazy="selectin",
    )

    def has_role(self, role_name: str) -> bool:
        return any(r.nombre == role_name for r in self.roles)
