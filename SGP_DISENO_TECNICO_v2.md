# SGP — Diseño Técnico (v2.0, corregido)

**Código:** SGP-TECH-DESIGN-2026-002
**Fecha:** Marzo 2026
**Reemplaza a:** Diseño técnico Temporal-céntrico (versión descartada)
**Autor:** Excelencia Operacional
**Estado:** Decisión cerrada — listo para construir

---

## 1. Decisión arquitectónica

Construimos el SGP como una **aplicación web tradicional** (FastAPI + Postgres + Next.js) con una **máquina de estados explícita en código** que representa el ciclo de vida de la Solicitud de Compra.

Se descartó el uso de un motor de workflow (Temporal, Camunda) porque:

- El volumen objetivo (~500 SC/mes) no justifica la complejidad operacional.
- El equipo actual son 2 personas sin experiencia previa en motores de workflow.
- Las capacidades críticas (timers, eventos asincrónicos, retries, auditoría inmutable) se resuelven idiomáticamente con herramientas estándar.
- El BPMN se mantiene como **artefacto de gobernanza**, no como artefacto ejecutable.

Esta decisión es reversible: si el sistema escala más allá de lo previsto, migrar a Temporal en una fase posterior es viable porque la lógica de negocio se mantiene aislada del transporte.

---

## 2. Stack final

| Capa | Tecnología | Versión |
|---|---|---|
| Frontend | Next.js + Tailwind + shadcn/ui | 14+ |
| Backend | FastAPI + SQLAlchemy + Pydantic | Python 3.12 |
| Base de datos | PostgreSQL | 16 |
| Tareas asíncronas | Celery + Redis | 5.x / 7.x |
| Scheduler (cron) | APScheduler embebido en FastAPI | 3.x |
| Autenticación | Clerk (managed) | última |
| Almacenamiento de archivos | Cloudflare R2 (S3-compatible) | — |
| Email | Resend | — |
| Errores y logs | Sentry + Railway logs | — |
| Hosting | Railway | — |
| CI/CD | GitHub Actions + Railway auto-deploy | — |

**Costo de infraestructura estimado para MVP:** USD 25–40 / mes.

---

## 3. Modelo de capas

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND (Next.js)                                     │
│  • Pages: SC, OC, Aprobaciones, Catálogo, Dashboard     │
│  • API client tipado contra OpenAPI                     │
└─────────────────────────────────────────────────────────┘
                       ↕ HTTPS / JSON
┌─────────────────────────────────────────────────────────┐
│  API GATEWAY  (Clerk middleware → FastAPI)              │
│  • Auth, rate limiting, OpenAPI docs                    │
└─────────────────────────────────────────────────────────┘
                       ↕
┌─────────────────────────────────────────────────────────┐
│  APPLICATION (FastAPI)                                  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Routers (HTTP endpoints)                        │   │
│  └─────────────────────────────────────────────────┘   │
│                       ↕                                 │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Services (lógica de negocio)                    │   │
│  │ • SolicitudService     • CotizacionService      │   │
│  │ • OrdenCompraService   • RecepcionService       │   │
│  │ • FacturaService       • CatalogoService        │   │
│  └─────────────────────────────────────────────────┘   │
│       ↕                                ↕                │
│  ┌──────────────────┐         ┌──────────────────────┐ │
│  │ State Machine    │         │ Celery Tasks         │ │
│  │ (transiciones    │         │ • Notificaciones     │ │
│  │  válidas)        │         │ • Sync ERP           │ │
│  │                  │         │ • Sync SII           │ │
│  └──────────────────┘         │ • Matching 3-way     │ │
│       ↕                       └──────────────────────┘ │
│  ┌──────────────────┐         ┌──────────────────────┐ │
│  │ Repositories     │         │ Scheduler (APS)      │ │
│  │ (SQLAlchemy)     │         │ • Timer SII 8 días   │ │
│  └──────────────────┘         │ • SLAs aprobación    │ │
│       ↕                       │ • Health checks      │ │
│                               └──────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                       ↕
┌─────────────────────────────────────────────────────────┐
│  PERSISTENCE                                            │
│  • PostgreSQL (transaccional)                           │
│  • Redis (Celery broker + cache)                        │
│  • Cloudflare R2 (archivos adjuntos)                    │
└─────────────────────────────────────────────────────────┘
                       ↕
┌─────────────────────────────────────────────────────────┐
│  ADAPTERS (capa de integración aislada)                 │
│  • softland_adapter   • sii_adapter                     │
│  • email_adapter      • sharepoint_adapter (Fase 3)     │
└─────────────────────────────────────────────────────────┘
```

**Principio clave:** la lógica de negocio vive en `Services`, completamente desacoplada del transporte (HTTP, Celery, Scheduler). Esto permite testear con tests unitarios y permite migrar a otro motor de orquestación en el futuro sin reescribir reglas.

---

## 4. Cómo se implementa cada capacidad crítica

| Capacidad del PRD | Implementación concreta |
|---|---|
| **Estados del proceso** | Enum `SCStatus` + tabla `solicitudes.status` + módulo `state_machine.py` con `ALLOWED_TRANSITIONS` y validación obligatoria en cada cambio. |
| **Aprobaciones (humanas, asincrónicas)** | Endpoint REST que cambia el estado y registra en `audit_log`. Las "esperas" no existen como código bloqueante: son simplemente filas con `status='PENDING_APPROVAL'`. |
| **SLA de aprobación** | APScheduler corre cada hora una query `WHERE status LIKE '%PENDING%' AND updated_at < NOW() - sla_threshold` y dispara escalamiento + notificación. |
| **Ventana SII de 8 días hábiles** | APScheduler corre cada hora sobre `facturas WHERE received_at + 8_business_days < NOW() AND status='PENDING'`. Calcula días hábiles con librería `python-holidays` (feriados Chile). Alertas en día 5 y día 7. |
| **Recepción de DTE asincrónico** | Webhook endpoint `/api/sii/dte-received` (o polling cada 15min al buzón DTE). Crea registro en `facturas`, dispara Celery task de matching 3-way. |
| **Matching 3-way bloqueante** | Servicio puro: `MatchingService.execute(po, recepcion, factura) -> MatchResult`. Tres validaciones: existencia de OC, existencia de Recepción Conforme, coincidencia de monto con tolerancia. Idempotente. |
| **Reintento ante fallo de integración** | Celery con `autoretry_for=(IntegrationError,)`, `max_retries=5`, backoff exponencial. Si falla persistentemente → fila en `integration_failures` con alerta. |
| **Recotización (loop)** | Status vuelve a `PENDING_QUOTATION` con `recotization_cycles += 1`. Si supera el máximo configurado → requiere aprobación adicional (estado `PENDING_RECOTIZATION_APPROVAL`). |
| **Auditoría inmutable** | Tabla `audit_log` append-only. Permisos UPDATE/DELETE revocados a nivel DB para todos los roles excepto `archivist` (>7 años). Trigger BEFORE UPDATE/DELETE que dispara excepción. |
| **Configuración de matrices SC/OC** | Tabla `approval_matrices` con scope (empresa, CC, tipo, rango monto, rol aprobador, nivel). Editable vía UI por Administrador del Workflow. Sin redeploy. |
| **Visibilidad del proceso** | Dashboard que consulta `solicitudes` con agregaciones por status. Vista de timeline por SC mostrando transiciones desde `audit_log`. |

**Lo que se gana con este enfoque:** todo es código Python estándar, debuggeable con `pdb`, testeable con `pytest`, sin abstracciones nuevas. Lo que se pierde: no hay un "Temporal UI" gratis — el dashboard hay que construirlo (1-2 días de trabajo).

---

## 5. Estructura del repositorio

```
sgp/
├── apps/
│   ├── web/                          # Next.js frontend
│   │   ├── app/
│   │   │   ├── solicitudes/
│   │   │   ├── ordenes-compra/
│   │   │   ├── aprobaciones/
│   │   │   ├── catalogo/
│   │   │   └── dashboard/
│   │   └── lib/api-client.ts         # Generado desde OpenAPI
│   │
│   └── api/                          # FastAPI backend
│       ├── src/sgp/
│       │   ├── core/
│       │   │   ├── config.py
│       │   │   ├── database.py
│       │   │   ├── auth.py           # Clerk integration
│       │   │   └── audit.py          # Audit log helper
│       │   │
│       │   ├── modules/
│       │   │   ├── catalogo/
│       │   │   │   ├── models.py
│       │   │   │   ├── schemas.py    # Pydantic
│       │   │   │   ├── repository.py
│       │   │   │   ├── service.py
│       │   │   │   └── router.py
│       │   │   ├── solicitudes/
│       │   │   │   ├── models.py
│       │   │   │   ├── schemas.py
│       │   │   │   ├── repository.py
│       │   │   │   ├── service.py
│       │   │   │   ├── state_machine.py    # ← núcleo del proceso
│       │   │   │   └── router.py
│       │   │   ├── cotizaciones/
│       │   │   ├── ordenes_compra/
│       │   │   ├── recepciones/
│       │   │   ├── facturas/
│       │   │   ├── presupuesto/
│       │   │   ├── usuarios/
│       │   │   └── auditoria/
│       │   │
│       │   ├── adapters/
│       │   │   ├── softland.py
│       │   │   ├── sii.py
│       │   │   ├── email_resend.py
│       │   │   └── storage_r2.py
│       │   │
│       │   ├── tasks/                # Celery tasks
│       │   │   ├── notifications.py
│       │   │   ├── sync_softland.py
│       │   │   ├── sync_sii.py
│       │   │   └── matching.py
│       │   │
│       │   ├── scheduler/            # APScheduler jobs
│       │   │   ├── sla_checker.py
│       │   │   ├── sii_window.py
│       │   │   └── budget_refresh.py
│       │   │
│       │   ├── main.py               # FastAPI app
│       │   └── celery_app.py
│       │
│       ├── alembic/                  # Migraciones
│       ├── tests/
│       │   ├── unit/
│       │   ├── integration/
│       │   └── fixtures/
│       ├── pyproject.toml
│       └── Dockerfile
│
├── docker-compose.yml                # Para desarrollo local
├── railway.json                      # Config Railway
├── docs/
│   ├── ARCHITECTURE.md               # Este documento
│   ├── PRD_v2.docx
│   └── BPMN_PROCESO_COMPRAS.bpm
└── README.md
```

---

## 6. Modelo de datos (entidades núcleo)

Solo las tablas críticas para arrancar. El detalle completo de campos se desarrolla en sprint 1.

```
empresas (id, razon_social, rut, ...)
centros_costo (id, empresa_id, codigo, nombre, ...)
presupuestos (id, cc_id, periodo, monto_asignado, monto_consumido)

usuarios (id, clerk_user_id, email, nombre, ...)
roles (id, nombre)                                  # solicitante, jefe_area, finanzas, etc.
usuarios_roles (usuario_id, rol_id, empresa_id)     # multi-tenant ready

familias (id, parent_id, nombre, nivel)             # taxonomía jerárquica
catalogo_items (id, sku, nombre, familia_id, unidad_medida, precio_referencia, ...)
proveedores (id, rut, razon_social, ...)

solicitudes_compra (
  id, numero, status, empresa_id, cc_id, solicitante_id,
  tipo, urgencia, monto_estimado, fecha_requerida,
  recotization_cycles, created_at, updated_at,
  ...
)
solicitudes_compra_lineas (id, sc_id, item_id, cantidad, especificacion)

cotizaciones (
  id, sc_id, proveedor_id, ciclo,
  precio_unitario, plazo, condiciones_pago, validez,
  archivo_url, is_winner, status
)

ordenes_compra (
  id, numero, sc_id, cotizacion_id,                 # vínculo inmutable (RN1)
  proveedor_id, monto_total_neto, iva, status,
  approved_by, approved_at,
  softland_oc_id, softland_synced_at,
  ...
)

recepciones (
  id, oc_id, tipo,                                  # bien | servicio
  receptor_id, conformidad,                         # conforme | no_conforme
  fecha_recepcion, observaciones, fotos_urls,
  ...
)

facturas (
  id, oc_id, folio_dte, fecha_dte, fecha_recepcion_sii,
  monto_neto, monto_iva, monto_total,
  match_status, match_executed_at,
  sii_action, sii_action_at, sii_deadline,
  cxp_softland_id,
  ...
)

approval_matrices (
  id, matrix_type,                                  # SC | OC
  empresa_id, cc_id, tipo_compra,
  monto_min, monto_max,
  rol_aprobador, nivel_aprobacion,
  valid_from, valid_to
)

audit_log (
  id, entity_type, entity_id,
  action, actor_id, actor_role,
  before_state, after_state,                        # JSONB
  ip_address, timestamp
)
-- Append-only: REVOKE UPDATE, DELETE ON audit_log FROM PUBLIC;
```

---

## 7. Patrones de código clave

### 7.1 State machine

Núcleo del proceso. Valida transiciones; centraliza la auditoría.

```python
# modules/solicitudes/state_machine.py
from enum import Enum
from typing import Set

class SCStatus(str, Enum):
    DRAFT = "draft"
    PENDING_AREA_APPROVAL = "pending_area_approval"
    PENDING_BUDGET = "pending_budget"
    BUDGET_FROZEN = "budget_frozen"
    PENDING_QUOTATION = "pending_quotation"
    QUOTATION_RECEIVED = "quotation_received"
    PENDING_VALORIZATION = "pending_valorization"
    VALORIZATION_APPROVED = "valorization_approved"
    PENDING_PO_EMISSION = "pending_po_emission"
    PENDING_PO_APPROVAL = "pending_po_approval"
    PO_APPROVED = "po_approved"
    PENDING_RECEPTION = "pending_reception"
    RECEPTION_CONFORM = "reception_conform"
    PENDING_INVOICE = "pending_invoice"
    INVOICE_MATCHED = "invoice_matched"
    CLOSED = "closed"
    REJECTED = "rejected"

ALLOWED_TRANSITIONS: dict[SCStatus, Set[SCStatus]] = {
    SCStatus.DRAFT: {SCStatus.PENDING_AREA_APPROVAL},
    SCStatus.PENDING_AREA_APPROVAL: {SCStatus.PENDING_BUDGET, SCStatus.REJECTED},
    SCStatus.PENDING_BUDGET: {SCStatus.PENDING_QUOTATION, SCStatus.BUDGET_FROZEN, SCStatus.REJECTED},
    SCStatus.PENDING_QUOTATION: {SCStatus.QUOTATION_RECEIVED, SCStatus.REJECTED},
    SCStatus.QUOTATION_RECEIVED: {SCStatus.PENDING_VALORIZATION},
    SCStatus.PENDING_VALORIZATION: {
        SCStatus.VALORIZATION_APPROVED,
        SCStatus.PENDING_QUOTATION,                  # recotización
        SCStatus.REJECTED,
    },
    # ... resto de transiciones
}

class InvalidTransitionError(Exception): pass

def validate_transition(from_status: SCStatus, to_status: SCStatus) -> None:
    if to_status not in ALLOWED_TRANSITIONS.get(from_status, set()):
        raise InvalidTransitionError(f"{from_status} → {to_status} no permitida")
```

### 7.2 Service con auditoría obligatoria

```python
# modules/solicitudes/service.py
class SolicitudService:
    def __init__(self, repo, audit, notifier):
        self.repo = repo
        self.audit = audit
        self.notifier = notifier

    def approve_by_area(self, sc_id: int, user: User, comment: str | None) -> SolicitudCompra:
        sc = self.repo.get_or_404(sc_id)

        if not user.has_role("jefe_area", scope=sc.area_id):
            raise PermissionDenied()

        validate_transition(sc.status, SCStatus.PENDING_BUDGET)

        before = sc.snapshot()
        sc.status = SCStatus.PENDING_BUDGET
        sc.approved_by_area_id = user.id
        sc.approved_by_area_at = utcnow()

        self.repo.save(sc)
        self.audit.log(
            entity=sc, action="AREA_APPROVAL",
            actor=user, before=before, after=sc.snapshot(),
            comment=comment,
        )
        self.notifier.queue("budget_validation_required", sc)
        return sc
```

### 7.3 Cron job con APScheduler

```python
# scheduler/sii_window.py
from apscheduler.triggers.cron import CronTrigger

@scheduler.scheduled_job(CronTrigger(minute=0))  # cada hora
def check_sii_window():
    """Implementa RN4: ventana SII de 8 días hábiles."""
    pending = facturas_repo.find_pending_with_deadline_before(
        deadline=add_business_days(utcnow(), -1)  # día 7
    )
    for f in pending:
        days_left = business_days_until(f.sii_deadline)
        if days_left == 3:
            notifier.send("sii_alert_day_5", f)
        elif days_left == 1:
            notifier.send("sii_alert_day_7", f)
        elif days_left <= 0:
            escalate_to_cfo(f)
```

### 7.4 Celery task con retry

```python
# tasks/sync_softland.py
@celery_app.task(
    autoretry_for=(IntegrationError,),
    max_retries=5,
    retry_backoff=True,           # backoff exponencial
    retry_backoff_max=3600,
)
def sync_oc_to_softland(oc_id: int):
    oc = ordenes_compra_repo.get(oc_id)
    softland_id = softland_adapter.create_oc(oc)
    ordenes_compra_repo.update(oc_id, softland_oc_id=softland_id, softland_synced_at=utcnow())
```

---

## 8. Decisiones explícitamente diferidas

Para no sobrediseñar, las siguientes decisiones se toman cuando sea necesario, no antes:

| Decisión | Cuándo se toma |
|---|---|
| Estrategia de despliegue para producción real (K8s vs PaaS) | Cuando el MVP esté validado y se apruebe el proyecto completo |
| App móvil nativa vs PWA | F2 — primero validar qué tareas se hacen en bodega vs escritorio |
| Estrategia exacta de integración con Softland (API, SQL directo, archivo) | F0 — depende del PoC con TI |
| Estrategia exacta de integración con SII (API, buzón, terceros) | F0 — depende de acceso real |
| Cambio a Temporal o motor de workflow | Si el sistema escala >10K SC/mes o requiere integraciones más complejas |
| BI / Data Warehouse corporativo | F4 — cuando haya datos suficientes para reportería avanzada |
| Multi-tenant fuerte (varias empresas en una sola instancia) | F2 — el modelo de datos lo soporta, pero la UX se diseña después |

---

## 9. Riesgos técnicos identificados

| Riesgo | Mitigación |
|---|---|
| Cálculo de días hábiles chilenos para ventana SII | Usar librería `python-holidays['CL']`. Tests unitarios con feriados conocidos. |
| Auditoría inmutable a nivel DB | Trigger PL/pgSQL que rechaza UPDATE/DELETE. Cobertura en tests de integración. |
| Idempotencia en sync con Softland | UUID de operación + tabla `integration_operations` con estado. Reintentos no duplican. |
| Reglas dinámicas en `approval_matrices` con conflictos | Resolver por especificidad: empresa+cc+tipo > empresa+cc > empresa > default. Tests exhaustivos. |
| Volumen de `audit_log` | Particionado por mes. Política de archivado a frío >2 años. |
| Curva de aprendizaje Celery + APScheduler | Mínima si seguimos patrones documentados. Backup: cron de Railway directo si Celery se complica. |

---

## 10. Próximo paso concreto

Construir el **scaffolding del proyecto**:

1. Repo en GitHub con la estructura de carpetas de la sección 5.
2. `docker-compose.yml` para desarrollo local (Postgres + Redis + API + Worker Celery).
3. `railway.json` con servicios definidos (api, worker, db, redis).
4. FastAPI app inicial con health check, Clerk middleware, OpenAPI funcionando.
5. Primera migración Alembic con tablas `usuarios`, `roles`, `audit_log`.
6. Endpoint de prueba `POST /api/healthcheck` deployable a Railway.

**Definition of Done del scaffolding:** vos podés clonar el repo, hacer `docker-compose up`, deployarlo a Railway, y ver el endpoint de healthcheck respondiendo en una URL pública con HTTPS.

Tiempo estimado: 1 sesión de pair programming (~3 horas).

---

*Fin del documento — SGP Diseño Técnico v2.0*
