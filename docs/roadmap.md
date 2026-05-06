# Roadmap

Estado del proyecto, qué falta para el MVP completo y qué viene después.

> Última revisión: 2026-05-05 (post-refactor 0006).

---

## Estado actual

✅ **Backend Solicitudes de Compra** sólido y deployado en Railway:
- 18 estados, 22 acciones, state machine explícita y testeada
- Roles + scope por empresa (RN-SCOPE), comments obligatorios en rechazos (RN-COMMENT)
- Adjuntos con storage adapter (Railway volume hoy, Azure mañana)
- Auditoría inmutable con trigger PL/pgSQL (RN5)
- 5 migraciones aplicadas (0001 a 0006), seed idempotente
- Tests en dos capas (SQLite rápido + Postgres real en CI)

✅ **Frontend prototipo** funcional:
- Selector de roles, dashboard, formulario nueva SC, tracking, bandeja del aprobador, detalle
- Item picker contra catálogo filtrado por CC
- Modal de creación de items nuevos en el CC actual
- Adjuntos por SC

✅ **Producción**: https://sgpv2-production.up.railway.app

❌ **Sin información económica** (decisión de scope MVP — ADR-006). Los montos viven en cotizaciones (sprint 2 pendiente).

---

## Lo que falta para MVP completo

### Sprint 2 — Módulo Cotizaciones ★

Es el bloqueador más grande. Habilita:
- **Montos reales** (cotización ganadora con valor)
- **RN-COT-1**: ≥ 1 cotización registrada antes de `QUOTATION_RECEIVED`
- **RN-VAL-1**: cotización ganadora con `proveedor.rut` + `proveedor.nombre` antes de `SEND_VALORIZATION`

Diseño tentativo:
- Tabla `cotizaciones` (FK a SC) con: proveedor (RUT, nombre, contacto), fecha emisión/vencimiento, condiciones de pago, plazo entrega
- Tabla `cotizaciones_lineas` con monto unitario por línea de SC
- Endpoint para registrar cotizaciones, marcar ganadora, comparativo automático
- Hook en `REGISTER_QUOTATIONS` valida ≥1
- Hook en `SEND_VALORIZATION` valida proveedor completo en la ganadora

**Esfuerzo estimado:** 1.5-2 sprints (~10-15 días-persona).

### Sprint 3 — Valorización con datos reales

Una vez que existen cotizaciones, la fase de valorización deja de ser cualitativa:
- El aprobador ve montos reales (de la cotización ganadora)
- Decisión 3-vías: aprobar / recotizar (RN8 máx 2) / rechazar
- Update del frontend para mostrar el comparativo de cotizaciones

**Esfuerzo:** ~5 días-persona, asumiendo que sprint 2 dejó la data lista.

### Sprint 4 — Módulo Órdenes de Compra

Hoy `EMIT_PO` solo cambia el estado. Falta:
- Tabla `ordenes_compra` vinculada a SC + cotización ganadora
- Generación de número correlativo (formato OC-YYYY-NNNNNN)
- Aprobación gerencial real (no solo cambio de estado)
- (Sprint 4b) Integración con Softland para sincronizar

**Esfuerzo:** 1-1.5 sprints.

### Sprint 5 — Recepción

`REGISTER_RECEPTION_CONFORM` es transición de estado. Falta:
- Tabla `recepciones` con: fecha, cantidad recibida vs solicitada, fotos/documentos obligatorios
- Diferencia de bienes (Bodega) vs servicios (Solicitante)
- Gate bloqueante para factura: no se acepta DTE sin recepción conforme
- Adjuntos obligatorios en `REGISTER_RECEPTION_NON_CONFORM` (foto del problema)

**Esfuerzo:** ~1 sprint.

### Sprint 6 — Factura y matching 3-vías

Hoy `MATCH_INVOICE_OK` no valida nada. Falta:
- Tabla `facturas` con DTE recibido del SII
- Matching 3-vías real: OC ↔ recepción ↔ factura en monto, cantidad, RUT proveedor
- `MATCH_INVOICE_FAIL` dispara reclamo formal al proveedor (campo + plazo)
- Integración con SII para recibir DTEs automáticamente

**Esfuerzo:** 1-2 sprints (depende de la integración SII).

### Sprint 7 — Notificaciones por email

Spec ya documentada en [notificaciones_pendiente.md](notificaciones_pendiente.md). Resumen:
- Adapter `EmailSender` (Protocol) con impl `ResendEmailSender`
- Tabla `notificaciones_enviadas` con `idempotency_key`
- Hook en `service.apply_transition` que dispara emails según matriz
- Job de SLA breached (cron) que recordatorios y escala

**Esfuerzo:** ~5-7 días-persona.

---

## Después del MVP

### Auth real (Clerk JWT)

ADR-001 documenta la decisión del mock. Para producción:
- Setear `AUTH_MODE=clerk` + `CLERK_SECRET_KEY` + `CLERK_JWT_VERIFICATION_KEY`
- Implementar verificación JWT en `core/auth.py::get_current_user`
- Mantener interfaz idéntica para no tocar el resto

**Esfuerzo:** 2-3 días-persona.

### Frontend en Next.js + TypeScript

ADR-005 documenta la decisión del prototipo. Cuando crezca:
- Migrar `frontend/*.jsx` a Next.js con TS
- Mantener `frontend/api.js` como cliente HTTP (refactor mínimo)
- Build separado, deploy en Vercel/Railway frontend service

**Esfuerzo:** 2-4 semanas (depende de qué tanto se rediseñe).

### Storage Azure Blob (sustituir Railway volume)

ADR-004 deja la abstracción lista:
- Implementar `AzureBlobStorage` con la misma interfaz `AttachmentStorage`
- Cambiar el factory `get_storage()`
- Migrar archivos existentes (script one-shot)

**Esfuerzo:** 3-5 días-persona.

### Integración Softland

Sprint 4b. Sincroniza OC y CxP con el ERP. Requiere:
- Credenciales de Softland API
- Mapeo de códigos
- Reconciliación de errores
- Probable: scheduled job + retry queue

**Esfuerzo:** 2-3 sprints.

---

## Deuda técnica conocida

| Item | Impacto | Cuándo abordar |
|---|---|---|
| Volume de Railway con tamaño limitado | Limita adjuntos a ~1 GB total | Cuando se llene |
| `data.jsx` mock con TCL/SPM no usados | Confunde si alguien busca esas empresas | Junto con migración a Next.js |
| Frontend sin tests | Regresiones manuales hoy | Junto con Next.js |
| Sin observabilidad (métricas, tracing) | Sin visibilidad en producción | Antes de escalar usuarios reales |
| Sin rate limiting | Cualquier curl puede inundar la API | Antes de exponer públicamente con auth real |
| `bodega` rol no tiene usuarios scopeados | El seed los crea con `empresa_id=NULL` | Cuando haya panel admin |
| Sin endpoint para listar/admin items | Crear items se hace desde el form de SC; no hay panel | Si se necesita gestión masiva |

---

## Funcionalidades exploradas pero no priorizadas

Decisiones que el negocio descartó (por ahora) y queda registrado:

### Escalación manual
Que un jefe pudiera escalar manualmente al nivel siguiente aunque el flujo no lo exija. **Descartado** (ver respuesta en análisis del aprobador) — la escalación automática por monto cubre los casos.

### Módulo de presupuestos
Endpoint `/gastos/resumen` con presupuesto por CC y % consumido. **Eliminado en refactor 0006** — fuera de alcance MVP.

### Inbox del aprobador
Endpoint `/solicitudes/inbox` que filtra automáticamente por `current_assignee_role`. Decidido **no implementar** porque los filtros existentes (`?status=...&empresa_id=...`) lo cubren combinándolos.

### Anti-duplicidad activa
Detección al crear: "ya hay 3 SCs similares creadas en últimos 30 días". **Diferido** — los filtros de búsqueda + el endpoint de duplicar SC dan el 80% del valor.

---

## Cumplimiento de objetivos por rol (snapshot post-refactor)

### Solicitante (5 objetivos del PRD)

| # | Objetivo | Estado |
|---|---|---|
| 1 | Registrar SC con formulario estandarizado | 🟢 95% |
| 2 | Consultar estado en tiempo real | 🟢 85% (assignee + ETA) |
| 3 | Recibir notificaciones de cambios | 🔴 0% (spec lista, sprint 7) |
| 4 | Adjuntar documentos de respaldo | 🟢 90% |
| 5 | Historial + evitar duplicidades | 🟢 85% |

**Promedio:** ~71%.

### Aprobador (objetivo compuesto)

| Sub-capacidad | Estado |
|---|---|
| Visualizar | 🟢 95% |
| Filtrar | 🟢 90% |
| Gestionar (workflow) | 🟢 100% |
| Escalar (automática) | 🟡 N/A (sin matriz de monto) |
| Con evidencia (adjuntos) | 🟢 95% |
| Monto real vs presupuesto | ❌ fuera de alcance MVP |

---

## Próxima decisión

**Sprint 2 (Cotizaciones)** es el siguiente sprint natural. Desbloquea:
- RN-COT-1, RN-VAL-1 (validaciones pendientes)
- Información económica (montos reales en cotización ganadora)
- La fase de valorización deja de ser cualitativa

Alternativas razonables (no excluyentes):
- **Notificaciones por email** — alto impacto en UX del solicitante, sprint corto
- **Auth real con Clerk** — antes de exponer al público
- **Conversión a Next.js** — si vamos a tener usuarios reales, vale la pena
