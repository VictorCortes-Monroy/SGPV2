# Decisiones de diseño (ADRs)

Registro de las decisiones de arquitectura/producto importantes y el **por qué** detrás. Sirve para que un nuevo dev (humano o agente) entienda no solo *qué* está hecho sino *por qué* se hizo así, evitando rehacer discusiones ya cerradas.

Convención: cada decisión tiene **contexto**, **decisión**, **consecuencias**.

---

## ADR-001 — Mock auth con header `X-User-Id`

**Contexto:** integrar Clerk al inicio era riesgoso (config + dominio + verificación JWT) y la prioridad era validar el dominio.

**Decisión:** auth en modo mock controlado por env var `AUTH_MODE=mock`. Header `X-User-Id` mapea a `clerk_user_id` en `usuarios`. La interfaz `get_current_user()` se mantiene idéntica para cuando integremos Clerk.

**Consecuencias:**
- ✅ Cero fricción para desarrollar y demostrar el sistema.
- ✅ El día que se integre Clerk solo cambia la implementación interna del dependency.
- ⚠️ **Inseguro para producción real**: cualquier curl con `X-User-Id: user_admin` se hace pasar por admin. Hay que integrar Clerk antes de exponer al público.

---

## ADR-002 — State machine explícita (sin Temporal/Camunda)

**Contexto:** el workflow tiene 6 fases y ~22 acciones. Tentación de usar un motor de workflow tipo Temporal o Camunda.

**Decisión:** state machine en código Python, dos dicts (`ALLOWED_TRANSITIONS`, `TRANSITION_BY_ACTION`) + funciones puras. Vive en `solicitudes/state_machine.py`.

**Consecuencias:**
- ✅ Cero dependencias externas. Razonable para 18 estados y un dominio bounded.
- ✅ Tests rápidos y comprensivos (test_state_machine.py).
- ✅ El grafo es legible — se ve y se modifica en un solo archivo.
- ⚠️ Si alguna vez se necesitan workflows con espera (ej. esperar 5 días por una respuesta y escalar), Temporal sería mejor. Hoy no se necesita.

---

## ADR-003 — Audit log con trigger PL/pgSQL append-only

**Contexto:** auditoría tiene requerimientos legales (RN5). El código de Python podría hacer UPDATE/DELETE accidentalmente (bug, o un dev malicioso).

**Decisión:** trigger PL/pgSQL `prevent_audit_log_modification` que bloquea UPDATE/DELETE a nivel BD, antes de que SQLAlchemy llegue. Definido en migración 0001.

**Consecuencias:**
- ✅ Garantía hard de inmutabilidad — no depende de la disciplina del código.
- ✅ Si alguien intenta modificar audit_log desde una migración o psql, también revota.
- ⚠️ El trigger es Postgres-específico. Tests unitarios usan SQLite, donde no se aplica. Por eso hay un test de integración dedicado contra Postgres real.

---

## ADR-004 — Adjuntos: storage adapter con Railway volume hoy, Azure mañana

**Contexto:** los adjuntos tienen que persistir entre redeploys. Hay 3 opciones: filesystem (Railway volume), S3, Azure Blob.

**Decisión:** Protocol `AttachmentStorage` con métodos `save / read / delete`. Implementación inicial `RailwayVolumeStorage` (filesystem en `/data/sgp/adjuntos`). Cuando migremos a Azure: implementar `AzureBlobStorage` con la misma interfaz, cambiar el factory `get_storage()`.

**Consecuencias:**
- ✅ MVP listo en horas, sin proveedor externo.
- ✅ Migrar a cloud blob storage es localizado: una clase nueva, un cambio en factory.
- ⚠️ Railway volumes tienen tamaño limitado (1 GB plan Hobby). Para escalar de verdad hay que pasar a S3/Azure pronto.

---

## ADR-005 — Frontend prototipo HTML+JSX+Babel CDN (sin build)

**Contexto:** Claude Design entregó un bundle HTML+JSX. Las opciones eran: (a) servirlo como está, (b) convertir a Next.js, (c) reescribir desde cero.

**Decisión:** servir el prototipo tal cual desde FastAPI con `StaticFiles`. React + ReactDOM + Babel desde unpkg. Sin build step, sin Node, sin npm install.

**Consecuencias:**
- ✅ Cero infraestructura nueva. El mismo deploy de Railway sirve front y API.
- ✅ Iteración rápida: editar `.jsx` → recargar browser.
- ⚠️ No hay tipado, no hay tree-shaking, no hay optimización. Para producción real con miles de usuarios hay que migrar a Next.js + TypeScript.
- ⚠️ Babel en runtime es lento en el primer paint (mejorable con SSR o build).

**Path de evolución:** cuando crezca, convertir a Next.js manteniendo `frontend/api.js` casi tal cual (el cliente HTTP es agnóstico al framework).

---

## ADR-006 — Sin información económica en SC (refactor 0006)

**Contexto:** el sistema arrancó con `monto_estimado` en la SC, `precio_referencia` en items, una matriz `RN-MONTO` que ruteaba el workflow según el monto, y un módulo `gastos/` con endpoint de medición. Negocio decidió que eso es **fuera de alcance del MVP** — los costos viven en cotizaciones (sprint 2).

**Decisión:** drop completo de info económica del módulo de Solicitudes:
- Drop columnas `monto_estimado` y `precio_referencia`
- Drop estados `PENDING_BUDGET`, `BUDGET_FROZEN`, `PENDING_MANAGEMENT_APPROVAL`
- Drop acciones `RELEASE_BUDGET`, `FREEZE_BUDGET`, `AUTHORIZE_FROZEN`, `APPROVE_MANAGEMENT`, `REJECT_MANAGEMENT`
- Drop módulo `gastos/` entero
- Mantener fase de **valorización** (`PENDING_VALORIZATION` → `VALORIZATION_APPROVED`) como punto de control cualitativo

**Consecuencias:**
- ✅ Workflow más simple: 18 estados (vs 21), sin bifurcaciones por monto.
- ✅ La SC describe necesidad pura. Cuando lleguen cotizaciones (sprint 2), ahí van los montos.
- ⚠️ La fase de valorización queda "vacía de números" hasta sprint 2. Funcionalmente es un punto de aprobación cualitativa del jefe de área sobre las cotizaciones recibidas.
- ⚠️ El refactor borró código existente y testeado. Migración 0006 es destructiva (`downgrade()` deshabilitado).

---

## ADR-007 — CatalogoItem ↔ Centro de Costo (RN-CAT-CC)

**Contexto:** el catálogo era global (cualquier item podía usarse en cualquier CC). En la práctica, cada CC tiene su propio inventario operativo — los repuestos de mantención no se piden desde administración.

**Decisión:** cada `CatalogoItem` pertenece a **un único** `CentroCosto` (FK `centro_costo_id NOT NULL`). El mismo SKU en CCs distintos = items separados con IDs distintos. SKU `UNIQUE(sku, centro_costo_id)`.

**Validación en service:** `_validar_items_pertenecen_al_cc` rebota con `BusinessRuleViolation` si una línea de SC referencia un item de otro CC.

**Consecuencias:**
- ✅ Cada CC tiene su propio "catálogo operativo". Limpia confusiones.
- ✅ El item picker del frontend filtra por `centro_costo_id` automáticamente — el solicitante solo ve lo que aplica.
- ⚠️ Para tener "Aceite SAE 15W40" en CC-001 Mantención y CC-002 Operaciones, hay que crear 2 items distintos. Aceptable: en la práctica un mismo producto puede tener especificaciones distintas según el CC.
- ⚠️ La búsqueda predictiva del catálogo es por CC. Si se quisiera buscar "qué items hay con esta familia en TODA la empresa", habría que omitir el filtro de CC — lo soporta el endpoint pero no se usa hoy.

---

## ADR-008 — Items existentes preservados en migración 0006 (sin delete)

**Contexto:** al borrar `precio_referencia` y agregar `centro_costo_id NOT NULL`, había que decidir qué hacer con los items existentes en producción.

**Decisión:** la columna se agrega con `DEFAULT 1` (CC-001 Mantención del seed). Los items existentes quedan asignados a CC-001 automáticamente. Después se remueve el default. El nuevo seed es idempotente: agrega items en CCs 2/3/4 sin duplicar los del CC-001.

**Consecuencias:**
- ✅ Las SCs pre-existentes no se rompen — sus líneas siguen apuntando a items válidos.
- ⚠️ Todos los items del seed viejo terminaron en CC-001 aunque algunos tienen sentido en otros CCs (ej. el notebook va más en TI). Hay que crear los items "correctos" en sus CCs nuevos cuando se ejecute el seed.

---

## ADR-009 — Comments obligatorios en rechazos (RN-COMMENT)

**Contexto:** los rechazos sin justificación frustran al solicitante, que no sabe qué corregir.

**Decisión:** las acciones `REJECT_AREA`, `REJECT_VALORIZATION`, `REJECT_PO`, `REGISTER_RECEPTION_NON_CONFORM` exigen `comment` no vacío. `BusinessRuleViolation` (HTTP 422) si falta. Lista en `ACTIONS_REQUIRING_COMMENT`.

**Consecuencias:**
- ✅ Auditoría más útil — se puede ver el motivo en el audit log.
- ✅ El solicitante sabe qué pasó.
- ⚠️ Si el aprobador escribe basura ("xx") igual pasa. Por ahora aceptable; el control queda en el equipo, no en el sistema.

---

## ADR-010 — Scope por empresa en autorización (RN-SCOPE)

**Contexto:** el sistema soporta multi-empresa. Sin scope, un `jefe_area` de Empresa A podría aprobar SCs de Empresa B.

**Decisión:** la tabla intermedia `usuarios_roles` ya tiene `empresa_id` (nullable). Validación en `_authorize_action`: el rol que justifica la acción debe estar vinculado a la empresa de la SC, o ser global (`empresa_id IS NULL`).

**Consecuencias:**
- ✅ Aislamiento entre empresas.
- ✅ Roles globales (admin, super-aprobadores) siguen funcionando.
- ⚠️ Hoy no hay UI para administrar el scope — se setea por SQL/seed. Cuando haya panel admin, exponerlo.

---

## ADR-011 — Notificaciones diferidas a sprint dedicado

**Contexto:** uno de los objetivos del solicitante es "recibir notificaciones de cambios de estado".

**Decisión:** documentar el diseño completo en [`notificaciones_pendiente.md`](notificaciones_pendiente.md) pero no implementar todavía. Sprint dedicado de ~5-7 días-persona cuando se priorice.

**Consecuencias:**
- ✅ Spec lista cuando llegue el momento.
- ⚠️ Hoy el solicitante tiene que entrar a la app y refrescar para ver cambios.

---

## ADR-012 — Frontend del prototipo en mismo dominio que la API

**Contexto:** opciones eran (a) frontend en Vercel/Cloudflare separado, (b) frontend como servicio Railway separado, (c) servido por la misma FastAPI.

**Decisión:** opción (c). FastAPI monta `StaticFiles` en `/`; Swagger UI se mueve a `/api/docs`; OpenAPI a `/api/openapi.json`.

**Consecuencias:**
- ✅ Sin CORS para producción (mismo origen).
- ✅ Un solo deploy, un solo dominio, una sola URL para compartir.
- ✅ El prototipo aprovecha la sesión de la API.
- ⚠️ Cuando el frontend crezca y tenga su propio build + CDN, separar tiene sentido. Por ahora overkill.

---

## ADR-013 — CORS auto-flip credentials según wildcard

**Contexto:** durante testing necesitábamos `CORS_ORIGINS=*` (varios orígenes de prototipos). Pero la spec CORS prohibe `allow_credentials=True` con `allow_origins=["*"]` — el browser rechaza la respuesta silenciosamente.

**Decisión:** lógica en `main.py` que detecta `*` en la lista y auto-aplica `credentials=False`. Si la lista es explícita, mantiene `credentials=True` (preparado para Clerk con cookies).

**Consecuencias:**
- ✅ Una sola env var (`CORS_ORIGINS`) controla todo, sin trampas silenciosas.
- ✅ Producción puede ir con orígenes explícitos sin tocar código.
