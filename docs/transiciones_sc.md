# Reglas y condiciones de transición — Solicitudes de Compra (SC)

Documento de referencia que captura, para cada acción del workflow, **qué la dispara, quién puede ejecutarla, qué precondiciones se exigen, qué efectos produce y qué estado quedó implementado en código**.

> El **grafo de estados** vive en [src/sgp/modules/solicitudes/state_machine.py](../src/sgp/modules/solicitudes/state_machine.py).
> Las **autorizaciones por rol** y reglas de negocio en runtime, en [src/sgp/modules/solicitudes/service.py](../src/sgp/modules/solicitudes/service.py).
> Este doc es la **especificación canónica**: si código y doc divergen, el doc gana y hay que abrir un fix.

> **Nota de alcance (MVP actual):** se eliminó toda información económica del módulo. No hay `monto_estimado`, ni `precio_referencia`, ni matriz de aprobación por monto, ni módulo gastos. La SC es cualitativa. Los montos viven en el módulo de **Cotizaciones** (sprint 2). La fase de **valorización** se mantiene como punto de control cualitativo.

---

## Convenciones

| Marca | Significado |
|---|---|
| 🟢 | **IMPLEMENTADO** — la regla está en código y cubierta por tests |
| 🟡 | **PARCIAL** — parte está, parte falta |
| 🔴 | **PENDIENTE** — acordada con negocio, pendiente de codificar |

---

## Reglas globales (aplican a TODAS las transiciones)

| ID | Regla | Estado |
|---|---|---|
| RN5 | `audit_log` es append-only; trigger PL/pgSQL bloquea UPDATE/DELETE a nivel BD | 🟢 |
| RN8 | Máximo 2 ciclos de recotización por SC; el 3er ciclo lanza `BusinessRuleViolation` | 🟢 |
| RN-OWN | Solo el solicitante original puede ejecutar `SUBMIT` y `CANCEL` sobre su SC | 🟢 |
| RN-ADM | El rol `admin` puede ejecutar cualquier acción (override) | 🟢 |
| RN-AUDIT | Toda acción registra antes/después de la SC en `audit_log` con actor, rol y comment opcional | 🟢 |
| RN-COMMENT | `REJECT_AREA`, `REJECT_VALORIZATION`, `REJECT_PO` y `REGISTER_RECEPTION_NON_CONFORM` exigen `comment` no vacío | 🟢 |
| RN-SCOPE | El rol que autoriza al actor debe estar vinculado a la empresa de la SC (o ser global) | 🟢 |
| **RN-CAT-CC** | Cada item del catálogo pertenece a un único CC. Las líneas de la SC solo pueden referenciar items del mismo CC. Mismo SKU en CCs distintos = items con IDs distintos | 🟢 |

---

## Reglas de datos sobre la SC

| ID | Regla | Aplica en | Estado |
|---|---|---|---|
| RN-DAT-1 | `justificacion` opcional para SUBMIT | crear / `SUBMIT` | 🟢 |
| RN-DAT-2 | ≥ 1 línea con `item_id` válido | crear | 🟢 |
| RN-DAT-3 | `fecha_requerida` ≥ hoy | crear | 🟢 |
| RN-COT-1 | ≥ 1 cotización registrada antes de `QUOTATION_RECEIVED` | `REGISTER_QUOTATIONS` | 🔴 (sprint 2 cotizaciones) |
| RN-VAL-1 | Cotización ganadora con `proveedor.rut` y `proveedor.nombre` antes de `SEND_VALORIZATION` | `SEND_VALORIZATION` | 🔴 |

---

## Flujo del workflow (sin info económica)

```
DRAFT → PENDING_AREA_APPROVAL → PENDING_QUOTATION → QUOTATION_RECEIVED
      → PENDING_VALORIZATION → VALORIZATION_APPROVED → PENDING_PO_APPROVAL
      → PO_APPROVED → PO_SENT_TO_SUPPLIER → PENDING_RECEPTION
      → RECEPTION_CONFORM → PENDING_INVOICE → INVOICE_MATCHED → CLOSED ✓
```

**Bifurcaciones** (rechazos / cancelación):
- En `PENDING_AREA_APPROVAL`, `PENDING_VALORIZATION`, `PENDING_PO_APPROVAL` → `REJECTED` (terminal)
- En cualquier estado no terminal hasta `PENDING_PO_APPROVAL` → `CANCELLED` (terminal)
- En `PENDING_RECEPTION` → `NON_CONFORMING` (terminal)
- En `PENDING_VALORIZATION` → `PENDING_QUOTATION` (recotización, máx 2)

**18 estados totales** (14 intermedios + 4 terminales). **22 acciones**.

---

## Transiciones por fase

### Fase 1 — Solicitud y aprobación inicial

#### `SUBMIT` — DRAFT → PENDING_AREA_APPROVAL  🟢
- **Quién:** `solicitante` (dueño de la SC)
- **Pre:** RN-DAT-2 (≥ 1 línea válida)
- **Efecto:** audit_log "SUBMIT"

#### `APPROVE_AREA` — PENDING_AREA_APPROVAL → PENDING_QUOTATION  🟢
- **Quién:** `jefe_area`
- **Pre:** ninguna
- **Efecto:** `sc.approved_by_area_id = actor.id`; audit_log "APPROVE_AREA"

#### `REJECT_AREA` — PENDING_AREA_APPROVAL → REJECTED  🟢
- **Quién:** `jefe_area`
- **Pre:** **RN-COMMENT** — `comment` no vacío
- **Efecto:** SC terminal; audit_log

### Fase 2 — Cotización

#### `REGISTER_QUOTATIONS` — PENDING_QUOTATION → QUOTATION_RECEIVED  🟡
- **Quién:** `abastecimiento`
- **Pre:** **RN-COT-1** — ≥ 1 cotización registrada (🔴 hoy no se valida)
- **Efecto:** audit_log

### Fase 3 — Valorización (cualitativa)

#### `SEND_VALORIZATION` — QUOTATION_RECEIVED → PENDING_VALORIZATION  🟡
- **Quién:** `abastecimiento`
- **Pre:** **RN-VAL-1** — proveedor con RUT+nombre (🔴 hoy no se valida)
- **Efecto:** audit_log

#### `APPROVE_VALORIZATION` — PENDING_VALORIZATION → VALORIZATION_APPROVED  🟢
- **Quién:** `jefe_area`
- **Pre:** ninguna
- **Efecto:** audit_log

#### `REQUEST_RECOTIZATION` — PENDING_VALORIZATION → PENDING_QUOTATION  🟢
- **Quién:** `jefe_area`
- **Pre:** **RN8** — `sc.recotization_cycles < 2`
- **Efecto:** `sc.recotization_cycles += 1`; audit_log

#### `REJECT_VALORIZATION` — PENDING_VALORIZATION → REJECTED  🟢
- **Quién:** `jefe_area`
- **Pre:** **RN-COMMENT** — `comment` no vacío
- **Efecto:** SC terminal

### Fase 4 — Orden de Compra

#### `EMIT_PO` — VALORIZATION_APPROVED → PENDING_PO_APPROVAL  🟡
- **Quién:** `abastecimiento`
- **Pre:** ninguna en código (cuando exista módulo OC, crea registro)
- **Efecto:** audit_log

#### `APPROVE_PO` — PENDING_PO_APPROVAL → PO_APPROVED  🟢
- **Quién:** `gerencia`
- **Pre:** ninguna
- **Efecto:** audit_log

#### `REJECT_PO` — PENDING_PO_APPROVAL → REJECTED  🟢
- **Quién:** `gerencia`
- **Pre:** **RN-COMMENT** — `comment` no vacío
- **Efecto:** SC terminal

#### `SEND_PO_TO_SUPPLIER` — PO_APPROVED → PO_SENT_TO_SUPPLIER  🟢
- **Quién:** `abastecimiento`
- **Pre:** ninguna
- **Efecto:** audit_log

### Fase 5 — Recepción

#### `REGISTER_RECEPTION_CONFORM` — PO_SENT_TO_SUPPLIER → PENDING_RECEPTION  🟢
- **Quién:** `bodega`, `solicitante`

#### `REGISTER_RECEPTION_CONFORM` — PENDING_RECEPTION → RECEPTION_CONFORM  🟢
- **Quién:** `bodega`, `solicitante`

#### `REGISTER_RECEPTION_NON_CONFORM` — PENDING_RECEPTION → NON_CONFORMING  🟢
- **Quién:** `bodega`, `solicitante`
- **Pre:** **RN-COMMENT** — `comment` no vacío con motivo
- **Efecto:** SC terminal

### Fase 6 — Factura y CxP

#### `RECEIVE_INVOICE` — RECEPTION_CONFORM → PENDING_INVOICE  🟢
#### `MATCH_INVOICE_OK` — PENDING_INVOICE → INVOICE_MATCHED  🟢
#### `MATCH_INVOICE_FAIL` — PENDING_INVOICE → PENDING_INVOICE  🟡
#### `CLOSE` — INVOICE_MATCHED → CLOSED  🟢

### Cualquier fase no terminal

#### `CANCEL` — DRAFT/PENDING_*/VALORIZATION_APPROVED/PENDING_PO_APPROVAL → CANCELLED  🟢
- **Quién:** `solicitante` (dueño), `jefe_area`
- **Pre:** SC no está en un estado terminal

---

## Estados terminales

| Estado | Significado |
|---|---|
| CLOSED | Flujo completo exitoso |
| REJECTED | Rechazo en aprobación (área, valorización u OC) |
| NON_CONFORMING | Recepción no conforme |
| CANCELLED | Cancelación voluntaria |

---

## Apéndice: trazabilidad código ↔ doc

| Concepto | Archivo |
|---|---|
| Definición de estados y acciones | [state_machine.py](../src/sgp/modules/solicitudes/state_machine.py) |
| Grafo `ALLOWED_TRANSITIONS` y `TRANSITION_BY_ACTION` | idem |
| `SLA_HOURS_BY_STATUS`, `ASSIGNEE_ROLE_BY_STATUS` | idem |
| Mapeo acción → roles | [service.py](../src/sgp/modules/solicitudes/service.py) `REQUIRED_ROLES_BY_ACTION` |
| Comments obligatorios | service.py `ACTIONS_REQUIRING_COMMENT` |
| Ownership y admin override | service.py `_authorize_action` |
| RN8 (recotización) | service.py `_apply_business_rules` |
| **RN-CAT-CC** (item ↔ CC) | service.py `_validar_items_pertenecen_al_cc`; [catalogo/models.py](../src/sgp/modules/catalogo/models.py) |
| Trigger RN5 (audit_log) | [alembic/0001_initial_schema.py](../alembic/versions/0001_initial_schema.py) |

---

## Pendientes resumidos

| Sprint | Cambio |
|---|---|
| 2 (Cotizaciones) | RN-COT-1: validar ≥ 1 cotización antes de `REGISTER_QUOTATIONS` |
| 2 (Cotizaciones) | RN-VAL-1: validar proveedor.rut + proveedor.nombre antes de `SEND_VALORIZATION` |
| 4 (OC) | Side-effects de `EMIT_PO` (crear registro OC) |
| 5 (Recepción) | Adjuntos obligatorios en `REGISTER_RECEPTION_NON_CONFORM` |
| 6 (Factura) | Matching 3-vías real en `MATCH_INVOICE_OK` |
| Notificaciones | Ver [notificaciones_pendiente.md](notificaciones_pendiente.md) |
