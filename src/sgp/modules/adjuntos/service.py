"""Servicio de adjuntos: validar, persistir, listar y borrar archivos
asociados a una SC."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sgp.core.audit import AuditService
from sgp.core.config import get_settings
from sgp.core.exceptions import (
    BusinessRuleViolation,
    NotFoundError,
    PermissionDenied,
    ValidationError,
)
from sgp.core.storage import AttachmentStorage, get_storage
from sgp.modules.adjuntos.models import SolicitudAdjunto
from sgp.modules.solicitudes.models import SolicitudCompra
from sgp.modules.solicitudes.state_machine import SCStatus, is_terminal
from sgp.modules.usuarios.models import Usuario


# Estados en los que NO se permite agregar/borrar adjuntos. La SC no puede
# crecer en evidencia después de cerrarse, rechazarse o cancelarse.
TERMINAL_STATUSES_FOR_ATTACHMENTS = {
    SCStatus.CLOSED,
    SCStatus.REJECTED,
    SCStatus.NON_CONFORMING,
    SCStatus.CANCELLED,
}


class AdjuntosService:
    def __init__(
        self,
        db: AsyncSession,
        storage: AttachmentStorage | None = None,
    ) -> None:
        self.db = db
        self.storage = storage or get_storage()
        self.audit = AuditService(db)
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # Lecturas
    # ------------------------------------------------------------------
    async def list_for_sc(self, sc_id: int) -> list[SolicitudAdjunto]:
        result = await self.db.execute(
            select(SolicitudAdjunto)
            .where(
                SolicitudAdjunto.solicitud_id == sc_id,
                SolicitudAdjunto.deleted_at.is_(None),
            )
            .order_by(SolicitudAdjunto.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_with_sc(self, adjunto_id: int) -> tuple[SolicitudAdjunto, SolicitudCompra]:
        """Devuelve el adjunto y su SC. Falla si no existe o está soft-deleted."""
        result = await self.db.execute(
            select(SolicitudAdjunto, SolicitudCompra)
            .join(SolicitudCompra, SolicitudCompra.id == SolicitudAdjunto.solicitud_id)
            .where(SolicitudAdjunto.id == adjunto_id)
        )
        row = result.first()
        if row is None:
            raise NotFoundError(f"Adjunto {adjunto_id} no encontrado")
        adjunto, sc = row
        if adjunto.deleted_at is not None:
            raise NotFoundError(f"Adjunto {adjunto_id} fue eliminado")
        return adjunto, sc

    async def read_content(self, adjunto: SolicitudAdjunto) -> bytes:
        return await self.storage.read(adjunto.stored_path)

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------
    async def upload(
        self,
        *,
        sc_id: int,
        actor: Usuario,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> SolicitudAdjunto:
        """Valida el archivo, lo persiste en storage y lo registra en BD."""
        sc = await self._get_sc_or_404(sc_id)
        self._authorize_modify(sc, actor)
        self._validate_file(filename, content_type, content)

        # Insertar primero la fila para obtener el id, luego escribir el archivo
        adjunto = SolicitudAdjunto(
            solicitud_id=sc.id,
            uploaded_by_id=actor.id,
            filename=filename,
            stored_path="",  # placeholder; se actualiza tras persistir
            content_type=content_type,
            size_bytes=len(content),
            phase_status=sc.status.value,  # snapshot de la fase actual (RN-ADJ-3)
        )
        self.db.add(adjunto)
        await self.db.flush()  # obtiene adjunto.id

        stored_path = await self.storage.save(
            empresa_id=sc.empresa_id,
            sc_id=sc.id,
            adjunto_id=adjunto.id,
            filename=filename,
            content=content,
        )
        adjunto.stored_path = stored_path
        await self.db.flush()

        await self.audit.log(
            entity_type="solicitud_adjunto",
            entity_id=adjunto.id,
            action="UPLOAD",
            actor_id=actor.id,
            after={
                "solicitud_id": sc.id,
                "filename": filename,
                "size_bytes": len(content),
                "content_type": content_type,
            },
            comment=f"Adjunto subido a SC {sc.numero}",
        )
        return adjunto

    # ------------------------------------------------------------------
    # Delete (soft + storage)
    # ------------------------------------------------------------------
    async def delete(self, adjunto_id: int, actor: Usuario) -> None:
        adjunto, sc = await self.get_with_sc(adjunto_id)
        self._authorize_modify(sc, actor)

        adjunto.deleted_at = datetime.now(UTC)
        await self.db.flush()
        await self.storage.delete(adjunto.stored_path)

        await self.audit.log(
            entity_type="solicitud_adjunto",
            entity_id=adjunto.id,
            action="DELETE",
            actor_id=actor.id,
            before={"filename": adjunto.filename, "size_bytes": adjunto.size_bytes},
            comment=f"Adjunto eliminado de SC {sc.numero}",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _get_sc_or_404(self, sc_id: int) -> SolicitudCompra:
        result = await self.db.execute(
            select(SolicitudCompra).where(SolicitudCompra.id == sc_id)
        )
        sc = result.scalar_one_or_none()
        if sc is None:
            raise NotFoundError(f"SC {sc_id} no encontrada")
        return sc

    @staticmethod
    def _authorize_modify(sc: SolicitudCompra, actor: Usuario) -> None:
        """Quién puede subir/borrar adjuntos:
        - admin (override).
        - el solicitante de la SC.
        - usuarios con el rol que actualmente tiene "la pelota"
          (current_assignee_role).
        Y la SC no puede estar en estado terminal."""
        if is_terminal(sc.status) or sc.status in TERMINAL_STATUSES_FOR_ATTACHMENTS:
            raise BusinessRuleViolation(
                f"No se pueden modificar adjuntos en una SC en estado terminal "
                f"({sc.status.value})."
            )

        actor_roles = {r.nombre for r in actor.roles}
        if "admin" in actor_roles:
            return
        if actor.id == sc.solicitante_id:
            return
        # Si el assignee actual es "solicitante", solo el dueño concreto vale
        # (el check anterior ya lo cubrió). Para otros roles funcionales basta
        # con que el actor tenga ese rol.
        assignee = sc.current_assignee_role
        if assignee and assignee != "solicitante" and assignee in actor_roles:
            return
        raise PermissionDenied(
            "Solo el solicitante, el rol que tiene la SC actualmente "
            f"({sc.current_assignee_role!r}), o admin pueden modificar adjuntos."
        )

    def _validate_file(self, filename: str, content_type: str, content: bytes) -> None:
        if not filename or filename.strip() == "":
            raise ValidationError("filename vacío")
        if len(filename) > 255:
            raise ValidationError("filename demasiado largo (máx 255 chars)")
        if len(content) == 0:
            raise ValidationError("archivo vacío")
        if len(content) > self.settings.storage_max_file_bytes:
            raise ValidationError(
                f"archivo excede el tamaño máximo "
                f"({self.settings.storage_max_file_mb} MB)"
            )
        if content_type not in self.settings.storage_allowed_mimes_set:
            raise ValidationError(
                f"content_type '{content_type}' no permitido. "
                f"Permitidos: {sorted(self.settings.storage_allowed_mimes_set)}"
            )
