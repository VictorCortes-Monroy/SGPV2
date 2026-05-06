# Arquitectura del SGP

Documento de referencia para entender cómo está armado el sistema, qué módulos existen y cómo se relacionan.

---

## Vista de 30 segundos

**Stack:** FastAPI + SQLAlchemy 2.0 async + PostgreSQL 16 + Alembic. Frontend prototipo HTML + JSX + Babel CDN (sin build step) servido por la misma API en `/`. Deploy en Railway.

**Patrón:** monolito modular por dominio. Cada módulo tiene `models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`. El motor de workflow es una **máquina de estados explícita** — sin Temporal, sin motor externo.

```
┌─────────────────────────────────────────────────┐
│  Cliente (browser, curl, Postman)               │
└─────────────────────┬───────────────────────────┘
                      │ HTTPS
┌─────────────────────▼───────────────────────────┐
│  FastAPI app (main.py)                          │
│   ├─ middleware CORS                            │
│   ├─ exception handler (SGPError → JSON)        │
│   ├─ /api/v1/* (routers de módulos)             │
│   ├─ /api/docs, /api/openapi.json               │
│   ├─ /health                                    │
│   └─ /  (StaticFiles → frontend/)               │
└─────────────────────┬───────────────────────────┘
                      │ async SQLAlchemy
┌─────────────────────▼───────────────────────────┐
│  Postgres 16 (Railway service)                  │
│   ├─ tablas de dominio                          │
│   ├─ enum sc_status_enum                        │
│   └─ trigger PL/pgSQL (audit_log append-only)   │
└─────────────────────────────────────────────────┘

  Railway Volume montado en /data → adjuntos
```

---

## Módulos del backend

Cada módulo en `src/sgp/modules/<modulo>/` y sigue el mismo layout.

| Módulo | Responsabilidad | Estado |
|---|---|---|
| **`solicitudes/`** | ★ Núcleo: SC + state machine + servicio + repositorio | 🟢 Completo |
| **`adjuntos/`** | Documentos de respaldo, storage adapter | 🟢 Completo |
| **`catalogo/`** | Items maestros + familias jerárquicas, relacionados a CC | 🟢 Completo |
| **`empresas/`** | Empresas + centros de costo (lectura) | 🟡 Skeleton |
| **`usuarios/`** | Usuarios + roles + scope por empresa (lectura) | 🟡 Skeleton |
| **`auditoria/`** | Audit log inmutable (con trigger SQL) | 🟢 Completo |

**Eliminado en el refactor reciente:** `gastos/` (módulo de medición de gasto comprometido vs ejecutado). Sin info económica en el sistema, no aplica.

---

## Capas dentro de un módulo

```
router.py        ←  HTTP endpoints, validación de query/body, auth
   │
   ▼
service.py       ←  orquestación de negocio, transacciones, audit
   │
   ▼
repository.py    ←  queries SQL, sin lógica de negocio
   │
   ▼
models.py        ←  ORM (SQLAlchemy declarative, async)

schemas.py       ←  Pydantic, payloads y respuestas tipadas
```

**Reglas:**
- El **router** solo serializa/des-serializa y delega al service. No tiene lógica.
- El **service** es el corazón: combina varios repositorios, valida reglas de negocio, registra audit log. No habla con HTTP.
- El **repository** solo hace queries. No conoce reglas.
- Los **schemas** validan formato del payload. Las **reglas semánticas** (ej. RN-CAT-CC) viven en service.

---

## Capa core (`src/sgp/core/`)

Cosas compartidas entre módulos.

| Archivo | Qué hace |
|---|---|
| `config.py` | Settings (Pydantic) leídos desde env. Validator que normaliza `postgresql://` → `postgresql+asyncpg://`. |
| `database.py` | `Base` declarative, `AsyncSessionLocal`, dependency `get_db()` para FastAPI. |
| `auth.py` | `get_current_user` (mock vía `X-User-Id`); `require_role(*, admin_override=True)` dependency. Cuando se integre Clerk: reemplazar verificación. |
| `exceptions.py` | Jerarquía `SGPError` → mapeada a HTTP por exception handler (404/403/409/422/500). |
| `audit.py` | `AuditService.log()` para escribir entradas inmutables en `audit_log`. |
| `storage.py` | `AttachmentStorage` Protocol + `RailwayVolumeStorage` (filesystem). Pluggable: para Azure Blob, implementar la misma interfaz. |

---

## El workflow de SC (state machine)

> Spec canónica: [transiciones_sc.md](transiciones_sc.md).

**18 estados** (14 intermedios + 4 terminales) en 6 fases. La SC es **cualitativa** — no tiene info económica. Los montos viven en cotizaciones (sprint 2 pendiente).

Pieza central: `src/sgp/modules/solicitudes/state_machine.py`. Define:
- `SCStatus` enum (todos los estados)
- `SCAction` enum (todas las acciones)
- `ALLOWED_TRANSITIONS` (mapa estado → estados destino válidos)
- `TRANSITION_BY_ACTION` (mapa (estado, acción) → estado destino)
- `SLA_HOURS_BY_STATUS` (configurables, denormalizados en SC)
- `ASSIGNEE_ROLE_BY_STATUS` (rol que tiene "la pelota", denormalizado)
- `apply_action(status, action)` (valida y devuelve nuevo estado)
- `available_actions(status)` (lista las acciones legales)

**Camino feliz simplificado:**
```
DRAFT → PENDING_AREA_APPROVAL → PENDING_QUOTATION → QUOTATION_RECEIVED
      → PENDING_VALORIZATION → VALORIZATION_APPROVED → PENDING_PO_APPROVAL
      → PO_APPROVED → PO_SENT_TO_SUPPLIER → PENDING_RECEPTION
      → RECEPTION_CONFORM → PENDING_INVOICE → INVOICE_MATCHED → CLOSED ✓
```

Estados terminales: `CLOSED`, `REJECTED`, `NON_CONFORMING`, `CANCELLED`.

---

## Datos de dominio

```
Empresa ──┬─< CentroCosto ──< CatalogoItem (RN-CAT-CC: 1 item ↔ 1 CC)
          │                       │
          │                       │ FK item_id
          │                       │
          │                       │
          └─< SolicitudCompra ──< SolicitudCompraLinea
                  │
                  ├─< SolicitudAdjunto (storage adapter)
                  │
                  └─< AuditLog (entity_type='solicitud_compra')

Usuario ──┬─< usuarios_roles ──── Rol
          │   (scope opcional empresa_id)
          │
          └─< SolicitudCompra (solicitante_id, approved_by_area_id)
```

### Reglas estructurales

| ID | Regla | Implementación |
|---|---|---|
| RN5 | `audit_log` append-only | Trigger PL/pgSQL `prevent_audit_log_modification` en migración 0001 |
| RN-CAT-CC | Cada item pertenece a 1 CC; SKU `UNIQUE(sku, centro_costo_id)` | Constraint compuesto + validación `_validar_items_pertenecen_al_cc` |
| RN-SCOPE | Rol del actor vinculado a empresa de la SC | `usuarios_roles.empresa_id` + check en `_authorize_action` |

---

## Migraciones (Alembic)

| Revisión | Qué hace |
|---|---|
| `0001_initial` | Schema completo inicial: 10 tablas, 4 enums (sc_status, tipo_compra, urgencia, etc.), trigger RN5 |
| `0002_pending_mgmt_approval` | Agrega `pending_management_approval` al enum (eliminada en refactor 0006) |
| `0003_assignee_sla` | Agrega `current_assignee_role` y `expected_resolution_at` a SC (denormalizados) |
| `0004_solicitud_adjuntos` | Tabla `solicitud_adjuntos` con FK a SC y a usuarios |
| `0005_phase_status` | Agrega `phase_status` a adjuntos (snapshot del estado al subir) |
| `0006_simplify_workflow` | **Refactor**: drop monto, drop estados de monto, link items a CC con UNIQUE compuesto |

**Política de migraciones:** forward-only. Downgrade no se mantiene a propósito (la 0006 explícitamente lo deshabilita) — para revertir se restaura desde backup.

Ver [`alembic/versions/`](../alembic/versions/) para el detalle de cada una.

---

## Tests

Dos capas, ambas en CI:

| Capa | Cómo corre | Cobertura |
|---|---|---|
| **Unit** (SQLite memoria) | `pytest -m "not postgres"` | state machine, service, schemas, repository, adjuntos, fixtures con catálogo+CC |
| **Integration** (Postgres real) | `pytest -m postgres` | enum nativo de PG, trigger RN5, JSON column, type casts |

CI: `.github/workflows/tests.yml` — dos jobs en paralelo, integration usa `postgres:16-alpine` como service container.

---

## Frontend

> Detalle: [frontend.md](frontend.md).

Prototipo SPA en HTML + JSX + Babel CDN, **sin build step**. Vive en `frontend/`, FastAPI lo sirve en `/` vía `StaticFiles`. Cliente HTTP en `frontend/api.js`. Componentes funcionales, estado vía hooks, panel de "tweaks" para alternar mock vs API real.

Origen: bundle de Claude Design (carpeta `solicitudes-de-pedido/` queda como referencia histórica).

---

## Deploy

> Detalle: [deploy.md](deploy.md).

- **Local:** `docker compose up` (Postgres + API + frontend en un solo dominio)
- **Producción:** Railway con auto-deploy desde `main` de GitHub
- **Storage de adjuntos:** Railway volume montado en `/data`
- **Migraciones:** se ejecutan en cada arranque vía `scripts/start.sh`
- **Seed:** condicional con `SEED_ON_STARTUP` env var

URL pública: https://sgpv2-production.up.railway.app
