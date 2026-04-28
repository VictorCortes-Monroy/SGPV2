"""Autenticación.

Por ahora opera en modo mock: lee el header X-User-Id y carga el usuario
desde la DB. Cuando se integre Clerk, este módulo se reemplaza por
verificación JWT real. La interfaz pública (get_current_user) se mantiene.
"""

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sgp.core.config import get_settings
from sgp.core.database import get_db
from sgp.modules.usuarios.models import Usuario

settings = get_settings()


async def get_current_user(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    """Carga el usuario autenticado desde el header X-User-Id (modo mock).

    Cuando AUTH_MODE=clerk, este endpoint debe verificar el JWT de Clerk
    y mapear clerk_user_id → Usuario.
    """
    if settings.auth_mode == "mock":
        if not x_user_id:
            raise HTTPException(
                status_code=401,
                detail="Header X-User-Id requerido en modo mock",
            )
        result = await db.execute(
            select(Usuario)
            .where(Usuario.clerk_user_id == x_user_id)
            .options(selectinload(Usuario.roles))
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=401,
                detail=f"Usuario {x_user_id} no encontrado",
            )
        if not user.activo:
            raise HTTPException(status_code=403, detail="Usuario inactivo")
        return user

    # TODO: integrar Clerk JWT verification cuando AUTH_MODE=clerk
    raise HTTPException(status_code=501, detail="Clerk auth aún no implementado")


def require_role(*allowed_roles: str, admin_override: bool = True):
    """Dependencia que requiere que el usuario tenga al menos uno de los roles.

    Por convención, `admin` puede acceder a cualquier endpoint sin importar
    los `allowed_roles`. Pasar `admin_override=False` para deshabilitar
    (raro, casos donde admin no debería ver datos).
    """

    async def _checker(user: Usuario = Depends(get_current_user)) -> Usuario:
        user_roles = {r.nombre for r in user.roles}
        if admin_override and "admin" in user_roles:
            return user
        if not user_roles.intersection(allowed_roles):
            raise HTTPException(
                status_code=403,
                detail=f"Requiere uno de los roles: {', '.join(allowed_roles)}",
            )
        return user

    return _checker
