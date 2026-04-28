"""Backend de almacenamiento de archivos para adjuntos.

Define un Protocol `AttachmentStorage` con la interfaz mínima que cada
backend (Railway volume hoy, Azure Blob mañana) debe implementar.

`RailwayVolumeStorage` es la implementación para MVP que escribe en un
disco persistente montado en el contenedor (Railway volume o un bind
mount local). El path raíz se configura vía `settings.storage_path`.

Cuando migremos a Azure: implementar `AzureBlobStorage` con la misma
interfaz, cambiar el factory `get_storage()` y listo.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

from sgp.core.exceptions import NotFoundError, ValidationError


class AttachmentStorage(Protocol):
    """Interfaz mínima de un backend de almacenamiento de archivos."""

    async def save(
        self, *, empresa_id: int, sc_id: int, adjunto_id: int, filename: str, content: bytes
    ) -> str:
        """Persiste el contenido y devuelve la ruta lógica (no absoluta)
        para guardar en BD."""
        ...

    async def read(self, stored_path: str) -> bytes:
        """Devuelve los bytes del archivo almacenado en `stored_path`."""
        ...

    async def delete(self, stored_path: str) -> None:
        """Elimina el archivo. Idempotente: si no existe, no falla."""
        ...


class RailwayVolumeStorage:
    """Implementación filesystem-based. Sirve para Railway volumes (Linux mount)
    y para dev local con un bind mount.

    Layout:
        {root}/{empresa_id}/{sc_id}/{adjunto_id}_{filename}

    `stored_path` que persistimos en BD es relativo al `root`, así podemos
    cambiar el root sin migrar datos.
    """

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    async def save(
        self, *, empresa_id: int, sc_id: int, adjunto_id: int, filename: str, content: bytes
    ) -> str:
        if "/" in filename or "\\" in filename or filename.startswith(".."):
            raise ValidationError(f"Nombre de archivo inválido: {filename!r}")
        rel_dir = Path(str(empresa_id)) / str(sc_id)
        rel_path = rel_dir / f"{adjunto_id}_{filename}"
        abs_path = self.root / rel_path
        # mkdir -p sync; el filesystem no tiene API async nativa de Python
        await asyncio.to_thread(abs_path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(abs_path.write_bytes, content)
        return str(rel_path).replace("\\", "/")  # consistencia cross-platform

    async def read(self, stored_path: str) -> bytes:
        abs_path = self.root / stored_path
        if not await asyncio.to_thread(abs_path.exists):
            raise NotFoundError(f"Archivo no encontrado en storage: {stored_path}")
        return await asyncio.to_thread(abs_path.read_bytes)

    async def delete(self, stored_path: str) -> None:
        abs_path = self.root / stored_path
        if await asyncio.to_thread(abs_path.exists):
            await asyncio.to_thread(abs_path.unlink)


# Factory + cache simple. La instancia es stateless (solo guarda el root).
_storage_singleton: AttachmentStorage | None = None


def get_storage() -> AttachmentStorage:
    """Devuelve la instancia configurada. Por ahora solo Railway volume."""
    global _storage_singleton
    if _storage_singleton is None:
        from sgp.core.config import get_settings

        settings = get_settings()
        _storage_singleton = RailwayVolumeStorage(root=settings.storage_path)
    return _storage_singleton
