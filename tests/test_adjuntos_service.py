"""Tests del módulo adjuntos.

Cubre validaciones (tamaño, MIME, filename), permisos, soft-delete y la
abstracción de storage. Para el storage usamos `RailwayVolumeStorage`
apuntando a un directorio temporal.
"""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from sgp.core.exceptions import (
    BusinessRuleViolation,
    NotFoundError,
    PermissionDenied,
    ValidationError,
)
from sgp.core.storage import RailwayVolumeStorage
from sgp.modules.adjuntos.models import SolicitudAdjunto
from sgp.modules.adjuntos.service import AdjuntosService
from sgp.modules.catalogo.models import (
    CatalogoItem,
    Criticidad,
    Familia,
    UnidadMedida,
)
from sgp.modules.empresas.models import CentroCosto, Empresa
from sgp.modules.solicitudes.models import TipoCompra, Urgencia
from sgp.modules.solicitudes.schemas import (
    LineaCreate,
    SolicitudCompraCreate,
    TransitionRequest,
)
from sgp.modules.solicitudes.service import SolicitudCompraService
from sgp.modules.solicitudes.state_machine import SCAction, SCStatus
from sgp.modules.usuarios.models import Rol, Usuario, usuario_roles_table


@pytest.fixture
def tmp_storage(tmp_path: Path):
    """Storage que escribe a un dir temporal del test."""
    return RailwayVolumeStorage(root=str(tmp_path))


@pytest.fixture
async def setup_basico(db_session):
    """Setup mínimo: roles, usuarios, empresa+CC, item del catálogo."""
    roles = {
        n: Rol(nombre=n, descripcion=f"Rol {n}")
        for n in ["solicitante", "jefe_area", "finanzas", "abastecimiento", "gerencia", "admin"]
    }
    for r in roles.values():
        db_session.add(r)
    await db_session.flush()

    def _user(clerk_id, email, nombre, role_names):
        u = Usuario(clerk_user_id=clerk_id, email=email, nombre=nombre, activo=True)
        db_session.add(u)
        return u, role_names

    u_sol, sol_roles = _user("u_sol", "sol@x.cl", "Sol", ["solicitante"])
    u_jefe, jefe_roles = _user("u_jefe", "jefe@x.cl", "Jefe", ["jefe_area"])
    u_admin, admin_roles = _user("u_admin", "adm@x.cl", "Admin", ["admin"])
    u_otro, otro_roles = _user("u_otro", "ot@x.cl", "Otro", ["solicitante"])
    await db_session.flush()

    for u, role_names in [
        (u_sol, sol_roles),
        (u_jefe, jefe_roles),
        (u_admin, admin_roles),
        (u_otro, otro_roles),
    ]:
        for rn in role_names:
            await db_session.execute(
                usuario_roles_table.insert().values(
                    usuario_id=u.id, rol_id=roles[rn].id, empresa_id=None
                )
            )

    emp = Empresa(rut="76123456-7", razon_social="Demo", nombre_corto="DEMO")
    db_session.add(emp)
    await db_session.flush()
    cc = CentroCosto(empresa_id=emp.id, codigo="CC-001", nombre="Mant")
    db_session.add(cc)
    await db_session.flush()
    fam = Familia(nombre="Repuestos", nivel=1)
    db_session.add(fam)
    await db_session.flush()
    item = CatalogoItem(
        sku="ITM-X",
        nombre="Item",
        familia_id=fam.id,
        centro_costo_id=cc.id,
        unidad_medida=UnidadMedida.UN,
        criticidad=Criticidad.ESTANDAR,
    )
    db_session.add(item)
    await db_session.flush()

    result = await db_session.execute(
        select(Usuario).options(selectinload(Usuario.roles))
    )
    usuarios = {u.clerk_user_id: u for u in result.scalars().all()}

    return {"usuarios": usuarios, "empresa": emp, "cc": cc, "item": item}


async def _crear_sc_en_draft(db_session, setup_basico) -> int:
    """Crea una SC nueva en DRAFT. Devuelve sc_id."""
    payload = SolicitudCompraCreate(
        empresa_id=setup_basico["empresa"].id,
        centro_costo_id=setup_basico["cc"].id,
        tipo=TipoCompra.BIEN,
        urgencia=Urgencia.NORMAL,
        descripcion="SC de prueba para adjuntos",
        fecha_requerida=date.today() + timedelta(days=7),
        lineas=[LineaCreate(item_id=setup_basico["item"].id, cantidad=Decimal("3"))],
    )
    service = SolicitudCompraService(db_session)
    sc = await service.create(payload, setup_basico["usuarios"]["u_sol"])
    return sc.id


PDF_CONTENT = b"%PDF-1.4 fake content"


class TestUploadHappyPath:
    async def test_solicitante_sube_pdf_a_su_sc_en_draft(
        self, db_session, setup_basico, tmp_storage, tmp_path
    ):
        sc_id = await _crear_sc_en_draft(db_session, setup_basico)
        service = AdjuntosService(db_session, storage=tmp_storage)
        adjunto = await service.upload(
            sc_id=sc_id,
            actor=setup_basico["usuarios"]["u_sol"],
            filename="cotizacion.pdf",
            content_type="application/pdf",
            content=PDF_CONTENT,
        )
        assert adjunto.id is not None
        assert adjunto.filename == "cotizacion.pdf"
        assert adjunto.size_bytes == len(PDF_CONTENT)
        # Archivo en disco
        on_disk = tmp_path / adjunto.stored_path
        assert on_disk.exists()
        assert on_disk.read_bytes() == PDF_CONTENT

    async def test_list_devuelve_solo_no_eliminados(
        self, db_session, setup_basico, tmp_storage
    ):
        sc_id = await _crear_sc_en_draft(db_session, setup_basico)
        service = AdjuntosService(db_session, storage=tmp_storage)

        a1 = await service.upload(
            sc_id=sc_id,
            actor=setup_basico["usuarios"]["u_sol"],
            filename="a.pdf",
            content_type="application/pdf",
            content=PDF_CONTENT,
        )
        await service.upload(
            sc_id=sc_id,
            actor=setup_basico["usuarios"]["u_sol"],
            filename="b.pdf",
            content_type="application/pdf",
            content=PDF_CONTENT,
        )

        adjuntos = await service.list_for_sc(sc_id)
        assert len(adjuntos) == 2

        await service.delete(a1.id, setup_basico["usuarios"]["u_sol"])

        adjuntos = await service.list_for_sc(sc_id)
        assert len(adjuntos) == 1


class TestValidaciones:
    async def test_tamano_excedido_lanza(
        self, db_session, setup_basico, tmp_storage
    ):
        from sgp.core.config import get_settings

        max_bytes = get_settings().storage_max_file_bytes
        sc_id = await _crear_sc_en_draft(db_session, setup_basico)
        service = AdjuntosService(db_session, storage=tmp_storage)

        with pytest.raises(ValidationError, match="tamaño"):
            await service.upload(
                sc_id=sc_id,
                actor=setup_basico["usuarios"]["u_sol"],
                filename="big.pdf",
                content_type="application/pdf",
                content=b"x" * (max_bytes + 1),
            )

    async def test_mime_no_permitido_lanza(
        self, db_session, setup_basico, tmp_storage
    ):
        sc_id = await _crear_sc_en_draft(db_session, setup_basico)
        service = AdjuntosService(db_session, storage=tmp_storage)

        with pytest.raises(ValidationError, match="content_type"):
            await service.upload(
                sc_id=sc_id,
                actor=setup_basico["usuarios"]["u_sol"],
                filename="malware.exe",
                content_type="application/x-msdownload",
                content=b"MZ executable",
            )

    async def test_archivo_vacio_lanza(self, db_session, setup_basico, tmp_storage):
        sc_id = await _crear_sc_en_draft(db_session, setup_basico)
        service = AdjuntosService(db_session, storage=tmp_storage)

        with pytest.raises(ValidationError, match="vacío"):
            await service.upload(
                sc_id=sc_id,
                actor=setup_basico["usuarios"]["u_sol"],
                filename="vacio.pdf",
                content_type="application/pdf",
                content=b"",
            )


class TestPermisos:
    async def test_otro_solicitante_no_puede_subir(
        self, db_session, setup_basico, tmp_storage
    ):
        """Solo el dueño, el rol con la pelota o admin pueden subir."""
        sc_id = await _crear_sc_en_draft(db_session, setup_basico)
        service = AdjuntosService(db_session, storage=tmp_storage)

        with pytest.raises(PermissionDenied):
            await service.upload(
                sc_id=sc_id,
                actor=setup_basico["usuarios"]["u_otro"],
                filename="hack.pdf",
                content_type="application/pdf",
                content=PDF_CONTENT,
            )

    async def test_jefe_puede_subir_cuando_sc_en_pending_area(
        self, db_session, setup_basico, tmp_storage
    ):
        """Cuando la SC está en PENDING_AREA_APPROVAL, jefe_area tiene la pelota."""
        sc_id = await _crear_sc_en_draft(db_session, setup_basico)
        sc_service = SolicitudCompraService(db_session)
        await sc_service.apply_transition(
            sc_id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )
        # Ahora current_assignee_role = "jefe_area"
        service = AdjuntosService(db_session, storage=tmp_storage)
        adjunto = await service.upload(
            sc_id=sc_id,
            actor=setup_basico["usuarios"]["u_jefe"],
            filename="aprobacion.pdf",
            content_type="application/pdf",
            content=PDF_CONTENT,
        )
        assert adjunto.id is not None

    async def test_admin_puede_subir_a_cualquier_sc(
        self, db_session, setup_basico, tmp_storage
    ):
        sc_id = await _crear_sc_en_draft(db_session, setup_basico)
        service = AdjuntosService(db_session, storage=tmp_storage)
        adjunto = await service.upload(
            sc_id=sc_id,
            actor=setup_basico["usuarios"]["u_admin"],
            filename="audit.pdf",
            content_type="application/pdf",
            content=PDF_CONTENT,
        )
        assert adjunto.id is not None

    async def test_no_se_puede_subir_a_sc_terminal(
        self, db_session, setup_basico, tmp_storage
    ):
        """Una SC en REJECTED no acepta más adjuntos."""
        sc_id = await _crear_sc_en_draft(db_session, setup_basico)
        sc_service = SolicitudCompraService(db_session)
        await sc_service.apply_transition(
            sc_id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )
        await sc_service.apply_transition(
            sc_id,
            TransitionRequest(action=SCAction.REJECT_AREA, comment="No autorizado"),
            setup_basico["usuarios"]["u_jefe"],
        )

        service = AdjuntosService(db_session, storage=tmp_storage)
        with pytest.raises(BusinessRuleViolation, match="terminal"):
            await service.upload(
                sc_id=sc_id,
                actor=setup_basico["usuarios"]["u_sol"],
                filename="late.pdf",
                content_type="application/pdf",
                content=PDF_CONTENT,
            )


class TestSoftDelete:
    async def test_delete_marca_deleted_at_y_borra_archivo(
        self, db_session, setup_basico, tmp_storage, tmp_path
    ):
        sc_id = await _crear_sc_en_draft(db_session, setup_basico)
        service = AdjuntosService(db_session, storage=tmp_storage)
        adjunto = await service.upload(
            sc_id=sc_id,
            actor=setup_basico["usuarios"]["u_sol"],
            filename="x.pdf",
            content_type="application/pdf",
            content=PDF_CONTENT,
        )
        on_disk = tmp_path / adjunto.stored_path
        assert on_disk.exists()

        await service.delete(adjunto.id, setup_basico["usuarios"]["u_sol"])

        # Fila preservada con timestamp
        result = await db_session.execute(
            select(SolicitudAdjunto).where(SolicitudAdjunto.id == adjunto.id)
        )
        marked = result.scalar_one()
        assert marked.deleted_at is not None
        # Archivo eliminado del disco
        assert not on_disk.exists()

    async def test_get_de_eliminado_lanza_404(
        self, db_session, setup_basico, tmp_storage
    ):
        sc_id = await _crear_sc_en_draft(db_session, setup_basico)
        service = AdjuntosService(db_session, storage=tmp_storage)
        adjunto = await service.upload(
            sc_id=sc_id,
            actor=setup_basico["usuarios"]["u_sol"],
            filename="x.pdf",
            content_type="application/pdf",
            content=PDF_CONTENT,
        )
        await service.delete(adjunto.id, setup_basico["usuarios"]["u_sol"])

        with pytest.raises(NotFoundError):
            await service.get_with_sc(adjunto.id)


class TestPhaseStatus:
    """RN-ADJ-3: cada adjunto guarda el `status` de la SC al momento de subirlo,
    para que el aprobador agrupe documentos por fase."""

    async def test_upload_en_draft_captura_phase_draft(
        self, db_session, setup_basico, tmp_storage
    ):
        sc_id = await _crear_sc_en_draft(db_session, setup_basico)
        service = AdjuntosService(db_session, storage=tmp_storage)
        adjunto = await service.upload(
            sc_id=sc_id,
            actor=setup_basico["usuarios"]["u_sol"],
            filename="cot.pdf",
            content_type="application/pdf",
            content=PDF_CONTENT,
        )
        assert adjunto.phase_status == SCStatus.DRAFT.value

    async def test_upload_tras_submit_captura_pending_area(
        self, db_session, setup_basico, tmp_storage
    ):
        sc_id = await _crear_sc_en_draft(db_session, setup_basico)
        sc_service = SolicitudCompraService(db_session)
        await sc_service.apply_transition(
            sc_id, TransitionRequest(action=SCAction.SUBMIT), setup_basico["usuarios"]["u_sol"]
        )
        # Ahora SC está en PENDING_AREA_APPROVAL → assignee jefe
        service = AdjuntosService(db_session, storage=tmp_storage)
        adjunto = await service.upload(
            sc_id=sc_id,
            actor=setup_basico["usuarios"]["u_jefe"],
            filename="aprobacion.pdf",
            content_type="application/pdf",
            content=PDF_CONTENT,
        )
        assert adjunto.phase_status == SCStatus.PENDING_AREA_APPROVAL.value


class TestStorage:
    """Tests directos del storage adapter."""

    async def test_save_layout_es_empresa_sc_idfilename(self, tmp_storage, tmp_path):
        path = await tmp_storage.save(
            empresa_id=42, sc_id=7, adjunto_id=99, filename="doc.pdf", content=b"data"
        )
        assert path == "42/7/99_doc.pdf"
        assert (tmp_path / path).read_bytes() == b"data"

    async def test_save_rechaza_filename_con_path(self, tmp_storage):
        with pytest.raises(ValidationError, match="inválido"):
            await tmp_storage.save(
                empresa_id=1, sc_id=1, adjunto_id=1,
                filename="../escape.pdf", content=b"x",
            )

    async def test_delete_es_idempotente(self, tmp_storage):
        # Borrar algo que no existe no debe explotar
        await tmp_storage.delete("nonexistent/path.pdf")

    async def test_read_de_inexistente_lanza_not_found(self, tmp_storage):
        with pytest.raises(NotFoundError):
            await tmp_storage.read("missing.pdf")
