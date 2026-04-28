# SGP — Sistema de Gestión de Compras

API del Sistema de Gestión de Compras (SGP). Stack: **FastAPI + SQLAlchemy 2.0 async + PostgreSQL + Alembic**.

> Implementación basada en el diseño técnico v2.0 (`docs/SGP_DISENO_TECNICO_v2.md`) y el PRD v2.0.

---

## Tabla de contenidos

- [Quick start](#quick-start)
- [Stack y arquitectura](#stack-y-arquitectura)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Estados del workflow (state machine)](#estados-del-workflow-state-machine)
- [Endpoints disponibles](#endpoints-disponibles)
- [Autenticación (modo mock)](#autenticación-modo-mock)
- [Datos demo](#datos-demo)
- [Demo end-to-end con curl](#demo-end-to-end-con-curl)
- [Testing](#testing)
- [Despliegue en Railway](#despliegue-en-railway)
- [Próximos pasos](#próximos-pasos)

---

## Quick start

### Opción 1: Docker Compose (recomendado)

Levanta API + Postgres + ejecuta migraciones + carga datos demo automáticamente:

```bash
git clone <tu-repo>
cd sgp-api
cp .env.example .env
docker compose up
```

Listo. La API queda en **http://localhost:8000**.

- Healthcheck: `curl http://localhost:8000/health`
- OpenAPI / Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Opción 2: Desarrollo local sin Docker

Requiere Python 3.12+ y PostgreSQL 14+ (o SQLite para tests).

```bash
# 1. Instalar dependencias
pip install -e ".[dev]"

# 2. Configurar .env con la URL de tu Postgres local
cp .env.example .env

# 3. Migrar
alembic upgrade head

# 4. Cargar datos demo
python scripts/seed.py

# 5. Levantar la API
uvicorn sgp.main:app --reload
```

---

## Stack y arquitectura

| Capa | Tecnología |
|---|---|
| Backend | FastAPI 0.115+ |
| ORM | SQLAlchemy 2.0 (async) |
| Validación | Pydantic v2 |
| Migraciones | Alembic |
| Base de datos | PostgreSQL 16 (SQLite en tests) |
| Autenticación | Mock (header `X-User-Id`) — preparado para Clerk |
| Tests | pytest + pytest-asyncio |
| Despliegue | Docker + Railway |

**Patrón arquitectónico:** monolito modular por dominio. Cada módulo tiene `models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`. El motor de workflow es una **máquina de estados explícita** en `modules/solicitudes/state_machine.py` (sin Temporal ni motor externo).

Ver `docs/SGP_DISENO_TECNICO_v2.md` para el diseño completo.

---

## Estructura del proyecto

```
sgp-api/
├── src/sgp/
│   ├── core/                       # Configuración, DB, auth, audit, excepciones
│   ├── api/v1.py                   # Agrega todos los routers
│   ├── modules/
│   │   ├── usuarios/               # Usuarios y roles
│   │   ├── empresas/               # Empresas y centros de costo
│   │   ├── catalogo/               # Catálogo maestro de items + taxonomía
│   │   ├── solicitudes/            # ★ Núcleo: SC + state machine
│   │   │   └── state_machine.py    # ← El corazón del proceso
│   │   └── auditoria/              # Audit log inmutable
│   └── main.py                     # FastAPI app
├── alembic/                        # Migraciones (Alembic con async)
├── tests/                          # 33 tests (state machine + service)
├── scripts/seed.py                 # Datos demo
├── docker-compose.yml              # Stack local: API + Postgres
├── Dockerfile
├── railway.json                    # Despliegue en Railway
├── pyproject.toml
└── README.md
```

---

## Estados del workflow (state machine)

El ciclo de vida de una SC tiene **20 estados** organizados en 6 fases del PRD:

```
                                   ┌── REJECTED (terminal)
                                   │
DRAFT ─[submit]→ PENDING_AREA_APPROVAL
                                   │
                          [approve_area]
                                   ↓
                          PENDING_BUDGET ─[freeze_budget]→ BUDGET_FROZEN
                                   │
                         [release_budget]
                                   ↓
                         PENDING_QUOTATION ◄──┐
                                   │          │ [request_recotization] (RN8: máx 2)
                       [register_quotations]  │
                                   ↓          │
                         QUOTATION_RECEIVED   │
                                   │          │
                          [send_valorization] │
                                   ↓          │
                         PENDING_VALORIZATION ┘
                                   │
                         [approve_valorization]
                                   ↓
                       VALORIZATION_APPROVED
                                   │
                              [emit_po]
                                   ↓
                         PENDING_PO_APPROVAL ─[reject_po]→ REJECTED
                                   │
                            [approve_po]
                                   ↓
                         PO_APPROVED
                                   │
                       [send_po_to_supplier]
                                   ↓
                         PO_SENT_TO_SUPPLIER
                                   │
                  [register_reception_conform]
                                   ↓
                          PENDING_RECEPTION ─[non_conform]→ NON_CONFORMING
                                   │
                  [register_reception_conform]
                                   ↓
                         RECEPTION_CONFORM
                                   │
                          [receive_invoice]
                                   ↓
                         PENDING_INVOICE
                                   │
                       [match_invoice_ok]
                                   ↓
                         INVOICE_MATCHED
                                   │
                              [close]
                                   ↓
                            CLOSED ✓
```

El módulo `state_machine.py` define:
- `SCStatus` enum (todos los estados)
- `SCAction` enum (todas las acciones del usuario)
- `ALLOWED_TRANSITIONS` — qué transiciones permite cada estado
- `TRANSITION_BY_ACTION` — qué nuevo estado produce cada acción
- `apply_action(status, action)` — valida y devuelve el nuevo estado
- `available_actions(status)` — útil para que el frontend muestre solo los botones válidos

**Reglas de negocio implementadas:**
- **RN5 (Auditoría inmutable):** trigger PL/pgSQL en migración bloquea UPDATE/DELETE en `audit_log`
- **RN8 (Recotización máxima):** 2 ciclos antes de exigir aprobación gerencial extra

---

## Endpoints disponibles

Todos los endpoints están bajo `/api/v1` y requieren header `X-User-Id` (modo mock).

### Usuarios
- `GET /usuarios/me` — usuario autenticado actual con sus roles

### Empresas
- `GET /empresas` — lista de empresas activas
- `GET /empresas/{id}/centros-costo` — CCs de la empresa

### Catálogo maestro
- `GET /catalogo/familias` — taxonomía jerárquica
- `GET /catalogo/items/search?q=<query>` — búsqueda predictiva (SKU o nombre)
- `GET /catalogo/items/{id}` — detalle del SKU
- `POST /catalogo/items` — crear SKU (requiere rol admin/abastecimiento)

### Solicitudes de Compra
- `POST /solicitudes` — crear SC en estado DRAFT
- `GET /solicitudes` — listar (filtros: `?status=`, `?mias=true`)
- `GET /solicitudes/{id}` — detalle de la SC con líneas y `available_actions`
- `POST /solicitudes/{id}/transitions` — aplicar acción al workflow

### Auditoría
- `GET /auditoria/` — log inmutable filtrable por entity, actor, etc.

Documentación completa con ejemplos: **http://localhost:8000/docs**.

---

## Autenticación (modo mock)

Para el MVP, la autenticación funciona vía header HTTP `X-User-Id`. Cuando se integre Clerk, este header será reemplazado por verificación JWT y la interfaz `get_current_user` se mantendrá idéntica.

```bash
curl -H "X-User-Id: user_victor" http://localhost:8000/api/v1/usuarios/me
```

---

## Datos demo

`scripts/seed.py` carga datos mínimos para arrancar:

**Usuarios** (use cualquiera como `X-User-Id`):

| clerk_user_id | nombre | roles |
|---|---|---|
| `user_admin` | Admin Demo | admin |
| `user_victor` | Victor Cortés-Monroy | admin, solicitante |
| `user_jefe` | Jefe de Área Demo | jefe_area |
| `user_finanzas` | Finanzas Demo | finanzas |
| `user_abast` | Abastecimiento Demo | abastecimiento |
| `user_gerente` | Gerente Demo | gerencia |
| `user_bodega` | Bodega Demo | bodega |

**Empresa:** Empresa Demo S.A. (`DEMO`)
**Centros de costo:** CC-001 (Mantención), CC-002 (Operaciones), CC-003 (Administración), CC-004 (TI)
**Items del catálogo:** 5 SKUs de ejemplo (lubricantes, repuestos, servicios, hardware)

---

## Demo end-to-end con curl

Después de levantar la API con `docker compose up`:

```bash
API=http://localhost:8000

# 1. Verificar usuario
curl -s -H "X-User-Id: user_victor" $API/api/v1/usuarios/me | jq

# 2. Buscar item del catálogo
curl -s -H "X-User-Id: user_victor" "$API/api/v1/catalogo/items/search?q=15W40" | jq

# 3. Crear una SC
curl -s -X POST -H "X-User-Id: user_victor" -H "Content-Type: application/json" \
  $API/api/v1/solicitudes \
  -d '{
    "empresa_id": 1,
    "centro_costo_id": 1,
    "tipo": "BIEN",
    "urgencia": "NORMAL",
    "descripcion": "Compra de aceite para mantención CAT 320",
    "monto_estimado": 1350000,
    "fecha_requerida": "2026-06-15",
    "lineas": [{"item_id": 1, "cantidad": 3}]
  }' | jq

# 4. Submit a aprobación (ID 1 asumiendo es la primera)
curl -s -X POST -H "X-User-Id: user_victor" -H "Content-Type: application/json" \
  $API/api/v1/solicitudes/1/transitions \
  -d '{"action": "submit"}' | jq

# 5. Jefe aprueba
curl -s -X POST -H "X-User-Id: user_jefe" -H "Content-Type: application/json" \
  $API/api/v1/solicitudes/1/transitions \
  -d '{"action": "approve_area", "comment": "Aprobado"}' | jq

# 6. Finanzas libera presupuesto
curl -s -X POST -H "X-User-Id: user_finanzas" -H "Content-Type: application/json" \
  $API/api/v1/solicitudes/1/transitions \
  -d '{"action": "release_budget"}' | jq

# 7. Ver el audit log de la SC
curl -s -H "X-User-Id: user_victor" \
  "$API/api/v1/auditoria/?entity_type=solicitud_compra&entity_id=1" | jq
```

**Casos de prueba interesantes:**
- Intentar `approve_area` como `user_solpuro` (un solicitante puro) → 403 con mensaje claro de roles requeridos
- Intentar `close` desde un estado no terminal → 409 con la lista de acciones válidas
- Pedir `request_recotization` 3 veces seguidas → 422 por RN8 (máximo 2 ciclos)

---

## Testing

La suite tiene dos capas:

### Capa 1: Tests unitarios (SQLite, rápidos)

```bash
# Default: corre solo los unitarios (33 tests, ~1 segundo)
pytest -m "not postgres"

# Solo state machine
pytest tests/test_state_machine.py -v

# Solo flujo end-to-end del service
pytest tests/test_solicitudes_service.py -v

# Con cobertura
pytest -m "not postgres" --cov=src/sgp --cov-report=html
```

Usan **SQLite en memoria** vía `aiosqlite`. Cubren state machine (transiciones,
estados terminales, coherencia del mapa) y service (creación, permisos por rol,
RN8 recotización, audit log).

### Capa 2: Smoke tests contra Postgres (integración)

```bash
# Con docker compose ya corriendo:
docker compose exec api pytest -m postgres -v

# O standalone, exportando DATABASE_URL:
export DATABASE_URL=postgresql+asyncpg://sgp:sgp_dev_password@localhost:5432/sgp_dev
pytest -m postgres -v
```

Los smoke tests (`tests/integration/`) atrapan bugs específicos del dialecto que
SQLite no detecta:

- Mismatch entre el enum nativo de Postgres y los enums de Python (un bug real
  ocurrido: SQLAlchemy serializa por `.name` mayúsculas pero el enum de la BD
  tiene los `.value` minúsculas).
- Trigger PL/pgSQL `prevent_audit_log_modification` (RN5: `audit_log` append-only).

Si `DATABASE_URL` no apunta a Postgres, los smoke tests se saltan automáticamente.

### CI

`.github/workflows/tests.yml` corre ambas capas en cada push/PR:

- **Job `unit`**: SQLite, sin servicios, ~10 s.
- **Job `integration`**: levanta `postgres:16-alpine` como service, aplica
  migraciones, carga seed, y corre `-m postgres`.

### Correr todo localmente

```bash
docker compose exec api pytest -v   # 39 tests (33 unit + 6 integration)
```

---

## Despliegue en Railway

El proyecto incluye `railway.json` configurado para deployment directo desde GitHub.

### Pasos:

1. **Conectar el repo de GitHub a Railway**
2. **Agregar servicio de Postgres** desde el panel de Railway (Add Service → Database → PostgreSQL)
3. **Variables de entorno:** Railway inyecta `DATABASE_URL` automáticamente. Solo agregar:
   ```
   APP_ENV=production
   AUTH_MODE=mock
   LOG_LEVEL=INFO
   CORS_ORIGINS=https://tu-frontend.railway.app
   ```
4. **El servicio se despliega solo** — Railway detecta el `Dockerfile` y `railway.json`. El `startCommand` corre las migraciones automáticamente antes de iniciar uvicorn.

**Importante:** la variable `DATABASE_URL` que inyecta Railway viene en formato `postgresql://...`. SQLAlchemy async necesita `postgresql+asyncpg://...`. Para resolver esto, agregar en `core/config.py` un validator que reemplace el prefijo, o configurar manualmente la `DATABASE_URL` con `postgresql+asyncpg://...`.

### Costo estimado en Railway

- API service: ~USD 5/mes (use Hobby plan o pay-as-you-go)
- Postgres: ~USD 5–10/mes
- **Total: USD 10–20/mes** para el MVP.

---

## Próximos pasos

El scaffolding entrega los **3 primeros estados del proceso** (Fase 1, 2, 3 del PRD parcialmente). Lo que falta para llegar al MVP completo:

| Sprint | Entregable |
|---|---|
| 2 | **Módulo Cotizaciones:** RFQ, registro de cotizaciones, comparativo automático, marcado de ganadora |
| 3 | **Valorización:** generación automática + decisión 3-vías (aprobar / recotizar / rechazar) |
| 4 | **Módulo Órdenes de Compra:** emisión vinculada a SC + cotización ganadora, matriz dual de aprobación |
| 5 | **Módulo Recepción:** bienes (Bodega) y servicios (Solicitante), gate bloqueante para factura |
| 6 | **Frontend Next.js:** dashboard, formularios de SC, aprobaciones móviles, audit log explorable |

Después del MVP:
- Integración real con Softland (sync OC + CxP)
- Integración con SII (DTE + ventana 8 días + matching 3-way)
- Migración del header `X-User-Id` a Clerk JWT
- Notificaciones por email (Resend) y SMS
- Reportes y dashboard de gasto

---

## Licencia

Propiedad de la empresa. Confidencial — Uso interno.

---

**Versión:** 0.1.0 · **Stack:** Python 3.12 · FastAPI · PostgreSQL 16 · **Mantenido por:** Excelencia Operacional
