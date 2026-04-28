# Reglas y condiciones de transición — Solicitudes de Compra (SC)

Documento de referencia que captura, para cada acción del workflow, **qué la dispara, quién puede ejecutarla, qué precondiciones se exigen, qué efectos produce y qué estado quedó implementado en código**.

> El **grafo de estados** vive en [src/sgp/modules/solicitudes/state_machine.py](../src/sgp/modules/solicitudes/state_machine.py).
> Las **autorizaciones por rol** y reglas de negocio en runtime, en [src/sgp/modules/solicitudes/service.py](../src/sgp/modules/solicitudes/service.py).
> Este doc es la **especificación canónica**: si código y doc divergen, el doc gana y hay que abrir un fix.

---

## Convenciones

| Marca | Significado |
|---|---|
| 🟢 | **IMPLEMENTADO** — la regla está en código y cubierta por tests |
| 🟡 | **PARCIAL** — parte está, parte falta |
| 🔴 | **PENDIENTE** — acordada con negocio, pendiente de codificar |
| 🟠 | **PROPUESTA** — interpretación del autor del doc, requiere validación de negocio antes de codificar |

---

## Reglas globales (aplican a TODAS las transiciones)

| ID | Regla | Estado |
|---|---|---|
| RN5 | `audit_log` es append-only; trigger PL/pgSQL bloquea UPDATE/DELETE a nivel BD | 🟢 |
| RN8 | Máximo 2 ciclos de recotización por SC; el 3er ciclo lanza `BusinessRuleViolation` | 🟢 |
| RN-OWN | Solo el solicitante original puede ejecutar `SUBMIT` y `CANCEL` sobre su SC | 🟢 |
| RN-ADM | El rol `admin` puede ejecutar cualquier acción (override) | 🟢 |
| RN-AUDIT | Toda acción registra antes/después de la SC en `audit_log` con actor, rol y comment opcional | 🟢 |

---

## Reglas de datos sobre la SC

Condiciones que la SC debe cumplir para crearse o avanzar de estado.

| ID | Regla | Aplica en | Estado |
|---|---|---|---|
| RN-DAT-1 | La SC NO requiere `justificacion` para ser enviada (campo opcional) | crear / `SUBMIT` | 🟢 |
| RN-DAT-2 | La SC debe tener ≥ 1 línea con `item_id` y `cantidad > 0` al crearse | crear | 🟢 — `SolicitudCompraCreate.lineas: Field(..., min_length=1)` + `cantidad: Field(..., gt=0)` |
| RN-COT-1 | Debe haber ≥ 1 cotización registrada para pasar a `QUOTATION_RECEIVED` | `REGISTER_QUOTATIONS` | 🔴 |
| RN-VAL-1 | La cotización ganadora debe tener `proveedor.rut` y `proveedor.nombre` antes de `SEND_VALORIZATION` | `SEND_VALORIZATION` | 🔴 |

> Las RN-COT-1 y RN-VAL-1 dependen del **módulo Cotizaciones** (sprint 2). Hoy las acciones `REGISTER_QUOTATIONS` y `SEND_VALORIZATION` cambian el estado sin verificar nada de cotizaciones — son placeholders.

---

## RN-MONTO — Matriz de aprobación por monto 🔴

Aprobaciones requeridas según `monto_estimado` de la SC (CLP):

| Tramo | jefe_area | finanzas | gerencia |
|---|:---:|:---:|:---:|
| **≤ 1.000.000** | ✅ | — | — |
| **> 1.000.000 y ≤ 5.000.000** | ✅ | ✅ | — |
| **> 5.000.000** | ✅ | ✅ | ✅ |

Hoy el código exige **siempre** la aprobación de finanzas (estado `PENDING_BUDGET`) sin importar el monto, y gerencia solo aparece al final en `APPROVE_PO`. Hay que agregar la lógica condicional.

### Decisiones tomadas

| ID | Decisión | Estado |
|---|---|---|
| RN-MONTO-1 | Tramo ≤ 1M **salta** `PENDING_BUDGET`. `APPROVE_AREA` rutea directo a `PENDING_QUOTATION` | 🟢 |
| RN-MONTO-2 | Tramo > 5M agrega un estado nuevo `PENDING_MANAGEMENT_APPROVAL` (tras finanzas, antes de cotizar) y una acción `APPROVE_MANAGEMENT` | 🟢 |
| RN-MONTO-3 | Las aprobaciones son **secuenciales**: jefe_area → finanzas (si aplica) → gerencia (si aplica) → cotización | 🟢 |
| RN-MONTO-4 | `APPROVE_PO` al final se **mantiene siempre** como aprobación formal de la OC, independiente del monto | 🟢 |
| RN-MONTO-5 | El `monto_estimado` rutea las aprobaciones tempranas. El `monto_cotizado` real (cotización ganadora) re-valida la matriz antes de `EMIT_PO`; si cae en un tramo superior, la SC se bloquea y requiere las aprobaciones faltantes (escalación) | 🔴 — pendiente módulo Cotizaciones |

### Flujo resultante por tramo

```
≤ 1M   :  DRAFT → SUBMIT → PENDING_AREA_APPROVAL → APPROVE_AREA
                → PENDING_QUOTATION → … (resto del flujo)

1M-5M  :  DRAFT → SUBMIT → PENDING_AREA_APPROVAL → APPROVE_AREA
                → PENDING_BUDGET → RELEASE_BUDGET
                → PENDING_QUOTATION → … (resto del flujo)

> 5M   :  DRAFT → SUBMIT → PENDING_AREA_APPROVAL → APPROVE_AREA
                → PENDING_BUDGET → RELEASE_BUDGET
                → PENDING_MANAGEMENT_APPROVAL → APPROVE_MANAGEMENT
                → PENDING_QUOTATION → … (resto del flujo)
```

### Cambios al state machine que requiere RN-MONTO

**Estados nuevos (🔴 a agregar):**
- `PENDING_MANAGEMENT_APPROVAL` — esperando OK de gerencia (tramo > 5M, fase temprana)

**Acciones nuevas (🔴 a agregar):**
- `APPROVE_MANAGEMENT` — gerencia aprueba el gasto temprano (PENDING_MANAGEMENT_APPROVAL → PENDING_QUOTATION)
- `REJECT_MANAGEMENT` — gerencia rechaza el gasto (PENDING_MANAGEMENT_APPROVAL → REJECTED)

**Transiciones modificadas:**
- `APPROVE_AREA`: hoy va siempre a `PENDING_BUDGET`. Pasa a rutear según `monto_estimado`:
  - ≤ 1M → `PENDING_QUOTATION`
  - > 1M → `PENDING_BUDGET`
- `RELEASE_BUDGET`: hoy va siempre a `PENDING_QUOTATION`. Pasa a rutear según `monto_estimado`:
  - ≤ 5M → `PENDING_QUOTATION`
  - > 5M → `PENDING_MANAGEMENT_APPROVAL`

**Validación nueva pre-`EMIT_PO`:** comparar `monto_cotizado` (cotización ganadora) contra el tramo originalmente aprobado. Si subió de tramo, lanzar `BusinessRuleViolation` con la lista de aprobaciones que faltan, para que el frontend gatille la escalación.

---

## Transiciones por fase

Para cada acción: `nombre — estado_origen → estado_destino  ESTADO_IMPL`
- **Quién:** roles autorizados (los listados son OR; admin siempre puede)
- **Pre:** precondiciones que se validan antes de aplicar
- **Efecto:** side-effects sobre la SC y otros módulos
- **Notas:** advertencias, decisiones, links a issues

---

### Fase 1 — Solicitud y aprobación inicial

#### `SUBMIT` — DRAFT → PENDING_AREA_APPROVAL  🟢
- **Quién:** `solicitante` (dueño de la SC)
- **Pre:** RN-DAT-2 (≥ 1 línea válida)
- **Efecto:** audit_log entry "SUBMIT"

#### `APPROVE_AREA` — PENDING_AREA_APPROVAL → {PENDING_BUDGET | PENDING_QUOTATION}  🟡
- **Quién:** `jefe_area`
- **Pre:** ninguna
- **Efecto:** `sc.approved_by_area_id = actor.id`; audit_log "APPROVE_AREA"
- **Ruteo (RN-MONTO-1):**
  - `monto_estimado` ≤ 1M → `PENDING_QUOTATION` (salta finanzas) 🔴
  - `monto_estimado` > 1M → `PENDING_BUDGET` 🟢

#### `REJECT_AREA` — PENDING_AREA_APPROVAL → REJECTED  🟢
- **Quién:** `jefe_area`
- **Pre:** ninguna
- **Efecto:** SC queda en estado terminal; audit_log "REJECT_AREA"
- **Notas:** se recomienda exigir `comment` no vacío (🔴 falta validación).

#### `RELEASE_BUDGET` — PENDING_BUDGET → {PENDING_QUOTATION | PENDING_MANAGEMENT_APPROVAL}  🟡
- **Quién:** `finanzas`
- **Pre:** ninguna en código
- **Efecto:** audit_log "RELEASE_BUDGET"
- **Ruteo (RN-MONTO-2):**
  - `monto_estimado` ≤ 5M → `PENDING_QUOTATION` 🟢
  - `monto_estimado` > 5M → `PENDING_MANAGEMENT_APPROVAL` 🔴

#### `APPROVE_MANAGEMENT` — PENDING_MANAGEMENT_APPROVAL → PENDING_QUOTATION  🔴
- **Quién:** `gerencia`
- **Pre:** `monto_estimado` > 5M (la SC solo entra a este estado si lo cumple)
- **Efecto:** audit_log "APPROVE_MANAGEMENT"; opcional `sc.approved_by_management_id = actor.id` (campo nuevo)
- **Notas:** aprobación gerencial **temprana**, antes de gastar tiempo cotizando. Distinta de `APPROVE_PO` (que sigue al final como aprobación formal de la OC).

#### `REJECT_MANAGEMENT` — PENDING_MANAGEMENT_APPROVAL → REJECTED  🔴
- **Quién:** `gerencia`
- **Pre:** ninguna
- **Efecto:** SC terminal; audit_log "REJECT_MANAGEMENT"
- **Notas:** debería exigir `comment` no vacío.

#### `FREEZE_BUDGET` — PENDING_BUDGET → BUDGET_FROZEN  🟢
- **Quién:** `finanzas`
- **Pre:** ninguna
- **Efecto:** audit_log "FREEZE_BUDGET"
- **Notas:** uso típico — falta presupuesto del CC en el periodo, queda esperando autorización superior.

#### `AUTHORIZE_FROZEN` — BUDGET_FROZEN → PENDING_QUOTATION  🟢
- **Quién:** `gerencia`, `finanzas`
- **Pre:** ninguna
- **Efecto:** audit_log "AUTHORIZE_FROZEN"

---

### Fase 2 — Cotización

#### `REGISTER_QUOTATIONS` — PENDING_QUOTATION → QUOTATION_RECEIVED  🟡
- **Quién:** `abastecimiento`
- **Pre:** **RN-COT-1** — ≥ 1 cotización registrada (🔴 no validado hoy)
- **Efecto:** audit_log "REGISTER_QUOTATIONS". Cuando exista módulo Cotizaciones, persiste los registros.
- **Notas:** la state machine permite la transición sin tocar nada — la regla de "tener cotización" es invisible al código actual.

---

### Fase 3 — Valorización

#### `SEND_VALORIZATION` — QUOTATION_RECEIVED → PENDING_VALORIZATION  🟡
- **Quién:** `abastecimiento`
- **Pre:** **RN-VAL-1** — la cotización marcada como ganadora tiene `proveedor.rut` y `proveedor.nombre` (🔴 no validado hoy)
- **Efecto:** audit_log "SEND_VALORIZATION". Cuando exista el módulo, dispara notificación a jefe_area.

#### `APPROVE_VALORIZATION` — PENDING_VALORIZATION → VALORIZATION_APPROVED  🟢
- **Quién:** `jefe_area`
- **Pre:** ninguna
- **Efecto:** audit_log "APPROVE_VALORIZATION"
- **Notas:** la re-evaluación de la matriz por monto cotizado se difiere a `EMIT_PO` (ver RN-MONTO-5), no acá.

#### `REQUEST_RECOTIZATION` — PENDING_VALORIZATION → PENDING_QUOTATION  🟢
- **Quién:** `jefe_area`
- **Pre:** **RN8** — `sc.recotization_cycles < 2` (al ejecutarse incrementa en 1)
- **Efecto:** `sc.recotization_cycles += 1`; audit_log "REQUEST_RECOTIZATION"
- **Notas:** el 3er request lanza `BusinessRuleViolation`.

#### `REJECT_VALORIZATION` — PENDING_VALORIZATION → REJECTED  🟢
- **Quién:** `jefe_area`
- **Pre:** ninguna
- **Efecto:** SC terminal; audit_log "REJECT_VALORIZATION"

---

### Fase 4 — Orden de Compra

#### `EMIT_PO` — VALORIZATION_APPROVED → PENDING_PO_APPROVAL  🟡
- **Quién:** `abastecimiento`
- **Pre (RN-MONTO-5):** 🔴 re-evaluar la matriz contra `monto_cotizado` real (cotización ganadora).
  - Si el monto cotizado cae en un tramo superior al `monto_estimado` originalmente aprobado, lanzar `BusinessRuleViolation` con la lista de aprobaciones que faltan.
  - Ej: SC con `monto_estimado` = 800.000 saltó finanzas, pero cotización ganadora vino en 1.200.000 → bloquear y exigir `RELEASE_BUDGET` antes.
- **Efecto:** audit_log "EMIT_PO". Cuando exista módulo OC, crea registro de orden de compra vinculado a SC y cotización ganadora.

#### `APPROVE_PO` — PENDING_PO_APPROVAL → PO_APPROVED  🟢
- **Quién:** `gerencia`
- **Pre:** ninguna
- **Efecto:** audit_log "APPROVE_PO"
- **Notas:** discusión pendiente sobre si esta es la única aprobación gerencial o si para >5M hay un step previo (decisión 2).

#### `REJECT_PO` — PENDING_PO_APPROVAL → REJECTED  🟢
- **Quién:** `gerencia`
- **Pre:** ninguna
- **Efecto:** SC terminal; audit_log "REJECT_PO"

#### `SEND_PO_TO_SUPPLIER` — PO_APPROVED → PO_SENT_TO_SUPPLIER  🟢
- **Quién:** `abastecimiento`
- **Pre:** ninguna
- **Efecto:** audit_log "SEND_PO_TO_SUPPLIER". Cuando exista integración Softland, sincroniza la OC.

---

### Fase 5 — Recepción

#### `REGISTER_RECEPTION_CONFORM` — PO_SENT_TO_SUPPLIER → PENDING_RECEPTION  🟢
- **Quién:** `bodega`, `solicitante`
- **Pre:** ninguna
- **Efecto:** audit_log "REGISTER_RECEPTION_CONFORM"
- **Notas:** *misma acción* aplicada en `PENDING_RECEPTION` produce `RECEPTION_CONFORM` (ver siguiente). El nombre coincide pero la transición depende del estado origen.

#### `REGISTER_RECEPTION_CONFORM` — PENDING_RECEPTION → RECEPTION_CONFORM  🟢
- **Quién:** `bodega`, `solicitante` (típicamente solicitante para SERVICIO; bodega para BIEN)
- **Pre:** ninguna en código
- **Efecto:** audit_log "REGISTER_RECEPTION_CONFORM"
- **Notas:** 🔴 sería razonable exigir `comment` describiendo lo recibido y opcionalmente fotos/documento.

#### `REGISTER_RECEPTION_NON_CONFORM` — PENDING_RECEPTION → NON_CONFORMING  🟢
- **Quién:** `bodega`, `solicitante`
- **Pre:** ninguna
- **Efecto:** SC terminal (no-conforme); audit_log
- **Notas:** 🔴 debería exigir `comment` con motivo. Estado actual NON_CONFORMING es terminal sin reapertura — confirmar con negocio si debería poder reabrirse para reclamo.

---

### Fase 6 — Factura y CxP

#### `RECEIVE_INVOICE` — RECEPTION_CONFORM → PENDING_INVOICE  🟢
- **Quién:** `finanzas`, `abastecimiento`
- **Pre:** ninguna en código
- **Efecto:** audit_log "RECEIVE_INVOICE". Cuando exista integración SII, ingresa el DTE recibido.

#### `MATCH_INVOICE_OK` — PENDING_INVOICE → INVOICE_MATCHED  🟢
- **Quién:** `finanzas`
- **Pre:** ninguna en código
- **Efecto:** audit_log "MATCH_INVOICE_OK"
- **Notas:** 🔴 cuando exista módulo Factura, debe validar matching 3-vías (OC ↔ recepción ↔ factura) en monto, cantidad y RUT proveedor.

#### `MATCH_INVOICE_FAIL` — PENDING_INVOICE → PENDING_INVOICE  🟡
- **Quién:** `finanzas`
- **Pre:** ninguna
- **Efecto:** audit_log "MATCH_INVOICE_FAIL"
- **Notas:** mantiene la SC esperando reemisión de factura. 🔴 cuando exista módulo, debe gatillar reclamo formal al proveedor.

#### `CLOSE` — INVOICE_MATCHED → CLOSED  🟢
- **Quién:** `finanzas`, `abastecimiento`
- **Pre:** ninguna
- **Efecto:** SC terminal exitosa; audit_log "CLOSE"

---

### Cualquier fase no terminal

#### `CANCEL` — DRAFT/PENDING_*/VALORIZATION_APPROVED/PENDING_PO_APPROVAL → CANCELLED  🟢
- **Quién:** `solicitante` (dueño de la SC), `jefe_area`
- **Pre:** SC no está en un estado terminal (CLOSED, REJECTED, NON_CONFORMING, CANCELLED)
- **Efecto:** SC terminal; audit_log "CANCEL"
- **Notas:** después de `PO_APPROVED` la cancelación NO está habilitada en código — confirmar con negocio si debería ser posible (con autorización extra).

---

## Estados terminales

| Estado | Significado | ¿Reapertura? |
|---|---|---|
| CLOSED | Flujo completo exitoso | No |
| REJECTED | Rechazo en aprobación (área, valorización u OC) | No |
| NON_CONFORMING | Recepción no conforme | 🔴 confirmar política |
| CANCELLED | Cancelación voluntaria | No |

---

## Apéndice: trazabilidad código ↔ doc

| Concepto | Archivo / línea |
|---|---|
| Definición de estados | [state_machine.py:23-61](../src/sgp/modules/solicitudes/state_machine.py#L23-L61) |
| Definición de acciones | [state_machine.py:64-103](../src/sgp/modules/solicitudes/state_machine.py#L64-L103) |
| Grafo `ALLOWED_TRANSITIONS` | [state_machine.py:107-183](../src/sgp/modules/solicitudes/state_machine.py#L107-L183) |
| Mapeo `(estado, acción) → estado` | [state_machine.py:187-229](../src/sgp/modules/solicitudes/state_machine.py#L187-L229) |
| Mapeo acción → roles | [service.py:130-153](../src/sgp/modules/solicitudes/service.py#L130-L153) |
| Ownership y admin override | [service.py:155-171](../src/sgp/modules/solicitudes/service.py#L155-L171) |
| RN8 (recotización) | [service.py:186-195](../src/sgp/modules/solicitudes/service.py#L186-L195) |
| `approved_by_area_id` | [service.py:197-198](../src/sgp/modules/solicitudes/service.py#L197-L198) |
| Trigger RN5 (audit_log) | [alembic/0001_initial_schema.py:286-302](../alembic/versions/0001_initial_schema.py#L286-L302) |

---

## Cambios pendientes resumidos

Lista de implementación prioritaria que sale de este doc:

| Sprint | Cambio |
|---|---|
| ~~Próximo~~ | ~~RN-DAT-2~~: 🟢 ya estaba (Pydantic `min_length=1`) |
| ~~Próximo~~ | ~~RN-MONTO-1~~: 🟢 ruteo en `APPROVE_AREA` según `monto_estimado` |
| ~~Próximo~~ | ~~RN-MONTO-2~~: 🟢 nuevos estado/acciones + ruteo en `RELEASE_BUDGET` |
| 2 | RN-COT-1: validar ≥ 1 cotización antes de `REGISTER_QUOTATIONS` |
| 2 | RN-VAL-1: validar proveedor.rut + proveedor.nombre antes de `SEND_VALORIZATION` |
| 4 | RN-MONTO-5: re-evaluación de matriz pre-`EMIT_PO` con `monto_cotizado` real |
| 4 | Side-effects de `EMIT_PO` (crear registro OC) |
| 5 | Validación de `comment` obligatorio en rechazos y `REGISTER_RECEPTION_NON_CONFORM` |
| 6 | Matching 3-vías real en `MATCH_INVOICE_OK` |
