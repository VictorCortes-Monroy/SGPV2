"""Endpoints HTTP de adjuntos: subir / listar / descargar / eliminar."""

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from sgp.core.auth import get_current_user
from sgp.core.database import get_db
from sgp.modules.adjuntos.schemas import AdjuntoRead
from sgp.modules.adjuntos.service import AdjuntosService
from sgp.modules.usuarios.models import Usuario

router = APIRouter(prefix="/solicitudes", tags=["adjuntos"])


@router.post(
    "/{sc_id}/adjuntos",
    response_model=AdjuntoRead,
    status_code=201,
    summary="Sube un adjunto a una SC",
)
async def upload_adjunto(
    sc_id: int,
    file: UploadFile = File(..., description="Archivo a adjuntar (PDF, imagen, Office, txt/csv)"),
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    content = await file.read()
    service = AdjuntosService(db)
    adjunto = await service.upload(
        sc_id=sc_id,
        actor=user,
        filename=file.filename or "archivo",
        content_type=file.content_type or "application/octet-stream",
        content=content,
    )
    return adjunto


@router.get(
    "/{sc_id}/adjuntos",
    response_model=list[AdjuntoRead],
    summary="Lista adjuntos vigentes de una SC",
)
async def list_adjuntos(
    sc_id: int,
    db: AsyncSession = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    service = AdjuntosService(db)
    return await service.list_for_sc(sc_id)


@router.get(
    "/{sc_id}/adjuntos/{adjunto_id}/download",
    summary="Descarga el contenido binario del adjunto",
)
async def download_adjunto(
    sc_id: int,  # noqa: ARG001 — parte del path; se valida vía adjunto.solicitud_id
    adjunto_id: int,
    db: AsyncSession = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    service = AdjuntosService(db)
    adjunto, _sc = await service.get_with_sc(adjunto_id)
    content = await service.read_content(adjunto)

    def _iter():
        yield content

    return StreamingResponse(
        _iter(),
        media_type=adjunto.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{adjunto.filename}"',
            "Content-Length": str(adjunto.size_bytes),
        },
    )


@router.delete(
    "/{sc_id}/adjuntos/{adjunto_id}",
    status_code=204,
    summary="Elimina un adjunto (soft-delete + borra archivo)",
)
async def delete_adjunto(
    sc_id: int,  # noqa: ARG001
    adjunto_id: int,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    service = AdjuntosService(db)
    await service.delete(adjunto_id, user)
    return None
