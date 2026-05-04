"""Seed inicial: carga datos mínimos de demostración.

Idempotente: se puede correr múltiples veces sin duplicar.
"""

import asyncio
import sys
from pathlib import Path

# Permitir imports desde src/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select  # noqa: E402

from sgp.core.database import AsyncSessionLocal  # noqa: E402
from sgp.modules.catalogo.models import (  # noqa: E402
    CatalogoItem,
    Criticidad,
    Familia,
    UnidadMedida,
)
from sgp.modules.empresas.models import CentroCosto, Empresa  # noqa: E402
from sgp.modules.usuarios.models import Rol, Usuario, usuario_roles_table  # noqa: E402


ROLES_INICIALES = [
    ("admin", "Administrador del sistema"),
    ("solicitante", "Usuario que crea Solicitudes de Compra"),
    ("jefe_area", "Jefe de área que aprueba SC y valorizaciones"),
    ("finanzas", "Finanzas / Control de Gestión"),
    ("abastecimiento", "Comprador / Encargado de Abastecimiento"),
    ("gerencia", "Gerencia (aprobación de OC)"),
    ("bodega", "Bodega / Almacén"),
    ("auditor", "Auditor (solo lectura)"),
]

USUARIOS_DEMO = [
    # (clerk_user_id, email, nombre, roles)
    ("user_admin", "admin@empresa.cl", "Admin Demo", ["admin"]),
    ("user_victor", "victor@empresa.cl", "Victor Cortés-Monroy", ["admin", "solicitante"]),
    ("user_jefe", "jefe@empresa.cl", "Jefe de Área Demo", ["jefe_area"]),
    ("user_finanzas", "finanzas@empresa.cl", "Finanzas Demo", ["finanzas"]),
    ("user_abast", "abast@empresa.cl", "Abastecimiento Demo", ["abastecimiento"]),
    ("user_gerente", "gerente@empresa.cl", "Gerente Demo", ["gerencia"]),
    ("user_bodega", "bodega@empresa.cl", "Bodega Demo", ["bodega"]),
]

EMPRESAS_DEMO = [
    ("76123456-7", "Empresa Demo S.A.", "DEMO"),
]

CENTROS_COSTO_DEMO = [
    # (codigo, nombre)
    ("CC-001", "Mantención"),
    ("CC-002", "Operaciones"),
    ("CC-003", "Administración"),
    ("CC-004", "TI"),
]

FAMILIAS_DEMO = [
    # (nombre, nivel, parent_idx_in_list)
    ("Mantención", 1, None),
    ("Lubricantes y Filtros", 2, 0),
    ("Aceites Hidráulicos", 3, 1),
    ("Repuestos Mecánicos", 2, 0),
    ("Servicios", 1, None),
    ("Servicio Técnico", 2, 4),
    ("Operación", 1, None),
    ("EPP", 2, 6),
    ("Administración", 1, None),
    ("Insumos Oficina", 2, 8),
    ("TI", 1, None),
    ("Hardware", 2, 10),
]

# Items vinculados al CC al que pertenecen (RN-CAT-CC). Mismo SKU puede
# aparecer en otro CC como item separado con id distinto.
# Tupla: (sku, nombre, familia_nombre, cc_codigo, unidad_medida, criticidad)
ITEMS_DEMO = [
    # CC-001 Mantención
    ("ITM-LUB-15W40-205L", "Aceite SAE 15W40 — Tambor 205L", "Aceites Hidráulicos",
     "CC-001", UnidadMedida.UN, Criticidad.ESTANDAR),
    ("ITM-LUB-FH-001", "Filtro Hidráulico HF-501", "Lubricantes y Filtros",
     "CC-001", UnidadMedida.UN, Criticidad.ESTANDAR),
    ("ITM-REP-CORREA-V40", "Correa V40 Reforzada", "Repuestos Mecánicos",
     "CC-001", UnidadMedida.UN, Criticidad.CRITICO),
    ("SVC-MTTO-PREV-CAT320", "Mantención Preventiva CAT 320 — Servicio", "Servicio Técnico",
     "CC-001", UnidadMedida.SVC, Criticidad.CRITICO),
    # CC-002 Operaciones
    ("ITM-EPP-CASCO", "Casco de seguridad clase E", "EPP",
     "CC-002", UnidadMedida.UN, Criticidad.CRITICO),
    ("ITM-EPP-GUANTES", "Guantes de cuero reforzado (par)", "EPP",
     "CC-002", UnidadMedida.UN, Criticidad.ESTANDAR),
    # CC-003 Administración
    ("ITM-OFI-PAPEL-A4", "Resma papel A4 (paquete 500 hojas)", "Insumos Oficina",
     "CC-003", UnidadMedida.UN, Criticidad.GENERICO),
    ("ITM-OFI-TINTA-HP", "Cartucho de tinta HP 664XL Negro", "Insumos Oficina",
     "CC-003", UnidadMedida.UN, Criticidad.ESTANDAR),
    # CC-004 TI
    ("ITM-TI-NB-DELL-XPS13", "Notebook Dell XPS 13", "Hardware",
     "CC-004", UnidadMedida.UN, Criticidad.ESTANDAR),
    ("ITM-TI-MON-24", "Monitor 24'' Full HD", "Hardware",
     "CC-004", UnidadMedida.UN, Criticidad.ESTANDAR),
]


async def seed_roles(db) -> dict[str, Rol]:
    """Crea roles si no existen. Devuelve dict {nombre: Rol}."""
    out = {}
    for nombre, desc in ROLES_INICIALES:
        existing = (
            await db.execute(select(Rol).where(Rol.nombre == nombre))
        ).scalar_one_or_none()
        if existing:
            out[nombre] = existing
        else:
            rol = Rol(nombre=nombre, descripcion=desc)
            db.add(rol)
            await db.flush()
            out[nombre] = rol
    return out


async def seed_empresas(db) -> dict[str, Empresa]:
    out = {}
    for rut, razon, corto in EMPRESAS_DEMO:
        existing = (
            await db.execute(select(Empresa).where(Empresa.rut == rut))
        ).scalar_one_or_none()
        if existing:
            out[corto] = existing
        else:
            emp = Empresa(rut=rut, razon_social=razon, nombre_corto=corto)
            db.add(emp)
            await db.flush()
            out[corto] = emp
    return out


async def seed_centros_costo(db, empresa: Empresa) -> dict[str, CentroCosto]:
    out = {}
    for codigo, nombre in CENTROS_COSTO_DEMO:
        existing = (
            await db.execute(
                select(CentroCosto).where(
                    CentroCosto.codigo == codigo,
                    CentroCosto.empresa_id == empresa.id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            out[codigo] = existing
        else:
            cc = CentroCosto(empresa_id=empresa.id, codigo=codigo, nombre=nombre)
            db.add(cc)
            await db.flush()
            out[codigo] = cc
    return out


async def seed_usuarios(db, roles: dict[str, Rol]) -> dict[str, Usuario]:
    out = {}
    for clerk_id, email, nombre, role_names in USUARIOS_DEMO:
        existing = (
            await db.execute(select(Usuario).where(Usuario.clerk_user_id == clerk_id))
        ).scalar_one_or_none()
        if existing:
            out[clerk_id] = existing
            continue
        u = Usuario(clerk_user_id=clerk_id, email=email, nombre=nombre, activo=True)
        db.add(u)
        await db.flush()
        # Asignar roles
        for rname in role_names:
            await db.execute(
                usuario_roles_table.insert().values(
                    usuario_id=u.id, rol_id=roles[rname].id, empresa_id=None
                )
            )
        await db.flush()
        out[clerk_id] = u
    return out


async def seed_familias(db) -> dict[str, Familia]:
    """Crea taxonomía. Resuelve parents por nombre dentro de la lista."""
    created: list[Familia] = []
    out: dict[str, Familia] = {}
    for nombre, nivel, parent_idx in FAMILIAS_DEMO:
        existing = (
            await db.execute(
                select(Familia).where(Familia.nombre == nombre, Familia.nivel == nivel)
            )
        ).scalar_one_or_none()
        if existing:
            created.append(existing)
            out[nombre] = existing
            continue
        parent = created[parent_idx] if parent_idx is not None else None
        f = Familia(
            nombre=nombre, nivel=nivel, parent_id=parent.id if parent else None
        )
        db.add(f)
        await db.flush()
        created.append(f)
        out[nombre] = f
    return out


async def seed_items(
    db,
    familias: dict[str, Familia],
    centros: dict[str, CentroCosto],
) -> None:
    for sku, nombre, fam_nombre, cc_codigo, um, crit in ITEMS_DEMO:
        cc = centros.get(cc_codigo)
        if cc is None:
            print(f"  ⚠ skip item {sku}: CC {cc_codigo} no encontrado")
            continue
        # Idempotencia: check (sku, cc_id) — el unique compuesto del modelo
        existing = (
            await db.execute(
                select(CatalogoItem).where(
                    CatalogoItem.sku == sku,
                    CatalogoItem.centro_costo_id == cc.id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue
        item = CatalogoItem(
            sku=sku,
            nombre=nombre,
            familia_id=familias[fam_nombre].id,
            centro_costo_id=cc.id,
            unidad_medida=um,
            criticidad=crit,
        )
        db.add(item)
        await db.flush()


async def main() -> None:
    print("🌱 SGP — Seed inicial")
    async with AsyncSessionLocal() as db:
        roles = await seed_roles(db)
        print(f"  ✓ Roles ({len(roles)})")

        empresas = await seed_empresas(db)
        print(f"  ✓ Empresas ({len(empresas)})")

        # Asume 1 sola empresa demo; tomamos sus CCs para vincular items.
        primera_empresa = next(iter(empresas.values()))
        ccs = await seed_centros_costo(db, primera_empresa)
        print(f"  ✓ Centros de costo de {primera_empresa.nombre_corto} ({len(ccs)})")

        usuarios = await seed_usuarios(db, roles)
        print(f"  ✓ Usuarios ({len(usuarios)})")

        familias = await seed_familias(db)
        print(f"  ✓ Familias ({len(familias)})")

        await seed_items(db, familias, ccs)
        print(f"  ✓ Items del catálogo ({len(ITEMS_DEMO)} vinculados a sus CCs)")

        await db.commit()
    print("✅ Seed completado.")
    print()
    print("Usuarios disponibles para login (header X-User-Id):")
    for clerk_id, email, nombre, roles_list in USUARIOS_DEMO:
        print(f"  - {clerk_id:20s}  {nombre:30s}  roles: {roles_list}")


if __name__ == "__main__":
    asyncio.run(main())
