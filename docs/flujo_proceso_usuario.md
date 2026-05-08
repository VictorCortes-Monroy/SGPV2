# Flujo de Proceso — SGPV2 (Sistema de Gestión de Compras)

> Documento que describe el flujo completo de una Solicitud de Compra (SC) desde la perspectiva de cada usuario/rol involucrado.

---

## Resumen del Ciclo de Vida

```
┌──────────┐    ┌───────────┐    ┌──────────────┐    ┌───────────┐    ┌──────────┐    ┌──────────┐
│ Solicitud│───▶│ Aprobación│───▶│  Cotización   │───▶│  Orden de │───▶│Recepción │───▶│ Cierre   │
│ & Envío  │    │  de Área  │    │ & Valorización│    │  Compra   │    │ en Bodega│    │ Factura  │
└──────────┘    └───────────┘    └──────────────┘    └───────────┘    └──────────┘    └──────────┘
  Solicitante    Jefe de Área     Abastecimiento      Gerencia        Bodega/         Finanzas
                                  + Jefe de Área      + Abastecim.    Solicitante
```

---

## Fase 1 — Creación y Envío de la Solicitud

**Actor:** Solicitante

### Pasos:

1. **Ingresar al sistema** y seleccionar el rol "Solicitante".
2. **Crear nueva solicitud** desde el dashboard → botón "Nueva Solicitud".
3. **Completar formulario:**
   - Seleccionar **Empresa** y **Centro de Costo** al que pertenece el requerimiento.
   - Indicar **Tipo** de solicitud: Bien o Servicio.
   - Seleccionar **Urgencia**: Normal, Urgente o Crítica.
   - Escribir una **descripción** del requerimiento y su **justificación**.
   - Indicar la **fecha requerida** de entrega.
4. **Agregar ítems** (líneas de la solicitud):
   - Buscar ítems del catálogo mediante el buscador predictivo (filtrado por centro de costo).
   - Si el ítem no existe en el catálogo, crear uno nuevo con el modal "Nuevo Ítem".
   - Indicar **cantidad** y **especificación técnica** por cada línea.
5. **Adjuntar documentos** de respaldo (opcional): cotizaciones previas, fichas técnicas, fotos, etc.
6. **Enviar la solicitud** (acción `SUBMIT`).
   - El estado cambia de `BORRADOR` → `PENDIENTE APROBACIÓN ÁREA`.
   - Se registra en el audit log quién envió y cuándo.

### Resultado:
La solicitud queda en la bandeja del Jefe de Área correspondiente.

---

## Fase 2 — Aprobación del Área

**Actor:** Jefe de Área

### Pasos:

1. **Revisar bandeja de entrada** — ver solicitudes pendientes de aprobación.
2. **Abrir detalle** de la solicitud: revisar descripción, justificación, ítems, adjuntos.
3. **Tomar decisión:**

| Acción | Estado resultante | Requisito |
|--------|------------------|-----------|
| **Aprobar** | `PENDIENTE COTIZACIÓN` | — |
| **Rechazar** | `RECHAZADA` | Comentario obligatorio con motivo |

### Resultado:
- **Si aprueba:** la solicitud pasa a Abastecimiento para gestión de cotizaciones.
- **Si rechaza:** el solicitante ve el rechazo con el motivo en su tracking. Fin del flujo.

---

## Fase 3 — Cotización

**Actor:** Abastecimiento

### Pasos:

1. **Revisar solicitudes** con estado "Pendiente Cotización".
2. **Gestionar cotizaciones** con proveedores externos (fuera del sistema en MVP).
3. **Registrar cotizaciones** recibidas (acción `REGISTER_QUOTATIONS`).
   - Estado cambia a `COTIZACIÓN RECIBIDA`.
4. **Enviar valorización** al Jefe de Área (acción `SEND_VALORIZATION`).
   - Estado cambia a `PENDIENTE VALORIZACIÓN`.

### Resultado:
La solicitud vuelve al Jefe de Área para evaluar las opciones cotizadas.

> **Nota MVP:** El módulo de Cotizaciones con detalle económico (proveedor, precios unitarios, condiciones) está planificado para Sprint 2. Actualmente la transición es cualitativa.

---

## Fase 4 — Valorización y Aprobación de Cotización

**Actor:** Jefe de Área

### Pasos:

1. **Revisar la valorización** presentada por Abastecimiento.
2. **Tomar decisión:**

| Acción | Estado resultante | Requisito |
|--------|------------------|-----------|
| **Aprobar valorización** | `VALORIZACIÓN APROBADA` | — |
| **Solicitar re-cotización** | `PENDIENTE COTIZACIÓN` | Máx. 2 ciclos (regla RN8) |
| **Rechazar valorización** | `RECHAZADA` | Comentario obligatorio |

### Ciclo de re-cotización:
- Si las cotizaciones no son satisfactorias, el Jefe de Área puede pedir que Abastecimiento busque nuevas opciones.
- Se permite un **máximo de 2 re-cotizaciones** por solicitud.
- Tras 2 ciclos, solo puede aprobar o rechazar.

### Resultado:
- **Si aprueba:** la solicitud avanza a generación de Orden de Compra.
- **Si rechaza:** fin del flujo, el solicitante ve el motivo.

---

## Fase 5 — Orden de Compra (OC)

**Actores:** Abastecimiento → Gerencia → Abastecimiento

### Pasos:

1. **Abastecimiento** emite la Orden de Compra (acción `EMIT_PO`).
   - Estado: `PENDIENTE APROBACIÓN OC`.
2. **Gerencia** revisa y decide:

| Acción | Estado resultante | Requisito |
|--------|------------------|-----------|
| **Aprobar OC** | `OC APROBADA` | — |
| **Rechazar OC** | `RECHAZADA` | Comentario obligatorio |

3. **Abastecimiento** envía la OC al proveedor (acción `SEND_PO_TO_SUPPLIER`).
   - Estado: `OC ENVIADA AL PROVEEDOR`.

### Resultado:
El proveedor recibe la orden y se espera la entrega del bien o servicio.

---

## Fase 6 — Recepción en Bodega

**Actor:** Bodega (o Solicitante)

### Pasos:

1. **Recibir** el bien o servicio del proveedor.
2. **Verificar conformidad** contra la OC: cantidades, especificaciones, estado.
3. **Registrar resultado:**

| Acción | Estado resultante | Requisito |
|--------|------------------|-----------|
| **Recepción conforme** | `RECEPCIÓN CONFORME` | — |
| **Recepción no conforme** | `NO CONFORME` | Comentario obligatorio (detalle del problema) |

### Resultado:
- **Conforme:** el flujo continúa a facturación.
- **No conforme:** estado terminal. Se debe gestionar con el proveedor fuera del sistema (devolución, reposición, etc.).

---

## Fase 7 — Facturación y Cierre

**Actor:** Finanzas (con apoyo de Abastecimiento)

### Pasos:

1. **Recibir factura** del proveedor (acción `RECEIVE_INVOICE`).
   - Estado: `PENDIENTE FACTURA` → `FACTURA RECIBIDA`.
2. **Realizar matching** de la factura contra la OC y la recepción:

| Acción | Estado resultante | Requisito |
|--------|------------------|-----------|
| **Matching OK** | `FACTURA CONCILIADA` | — |

3. **Cerrar** la solicitud (acción `CLOSE`).
   - Estado final: `CERRADA`.

### Resultado:
La solicitud queda completamente cerrada con trazabilidad de punta a punta.

---

## Acciones Transversales

### Cancelación
- **Quién:** Solicitante (de su propia SC) o Jefe de Área.
- **Cuándo:** Disponible en la mayoría de estados no terminales.
- **Estado resultante:** `CANCELADA` (terminal).
- **Nota:** No requiere comentario obligatorio.

### Duplicar Solicitud
- **Quién:** Solicitante.
- **Para qué:** Crear una nueva SC basada en una anterior (útil para pedidos recurrentes).
- **Resultado:** Nueva SC en estado `BORRADOR` con los mismos datos.

---

## Estados Terminales

| Estado | Significado | Cómo se llegó |
|--------|-------------|---------------|
| `CERRADA` | Proceso completado exitosamente | Flujo completo hasta matching + cierre |
| `RECHAZADA` | Solicitud rechazada en alguna aprobación | Rechazo en área, valorización u OC |
| `NO CONFORME` | Recepción no conforme | Bodega detectó problemas en la entrega |
| `CANCELADA` | Cancelación voluntaria | Solicitante o Jefe de Área canceló |

---

## Diagrama de Estados Completo

```
                         ┌──────────┐
                         │  DRAFT   │
                         └────┬─────┘
                              │ SUBMIT (solicitante)
                              ▼
                    ┌─────────────────────┐
                    │ PENDING_AREA_APPROVAL│
                    └────┬───────────┬────┘
           APPROVE_AREA  │           │  REJECT_AREA
           (jefe_area)   │           │  (jefe_area)
                         ▼           ▼
              ┌──────────────┐   ┌──────────┐
              │PENDING_      │   │ REJECTED │
              │QUOTATION     │   └──────────┘
              └──────┬───────┘        ▲
                     │                │ (rechazos en cualquier fase)
    REGISTER_        │                │
    QUOTATIONS       ▼                │
   (abastecim.) ┌──────────────┐     │
                │QUOTATION_    │     │
                │RECEIVED      │     │
                └──────┬───────┘     │
                       │              │
    SEND_VALORIZATION  │              │
    (abastecimiento)   ▼              │
              ┌──────────────────┐    │
              │PENDING_          │    │
              │VALORIZATION      │────┘ REJECT_VALORIZATION
              └──┬──────────┬───┘
   APPROVE_      │          │ REQUEST_RECOTIZATION
   VALORIZATION  │          │ (máx. 2 ciclos → vuelve a
   (jefe_area)   ▼          │  PENDING_QUOTATION)
         ┌───────────────┐  │
         │VALORIZATION_  │◄─┘
         │APPROVED       │
         └───────┬───────┘
                 │ EMIT_PO (abastecimiento)
                 ▼
        ┌────────────────┐
        │PENDING_PO_     │
        │APPROVAL        │──── REJECT_PO ──▶ REJECTED
        └────────┬───────┘     (gerencia)
                 │ APPROVE_PO (gerencia)
                 ▼
          ┌────────────┐
          │ PO_APPROVED│
          └──────┬─────┘
                 │ SEND_PO_TO_SUPPLIER (abastecimiento)
                 ▼
       ┌──────────────────┐
       │PO_SENT_TO_       │
       │SUPPLIER          │
       └────────┬─────────┘
                │ (recepción)
                ▼
       ┌────────────────┐
       │PENDING_        │
       │RECEPTION       │
       └───┬────────┬───┘
           │        │
  CONFORM  │        │  NON_CONFORM
  (bodega) ▼        ▼  (bodega)
  ┌────────────┐ ┌──────────────┐
  │RECEPTION_  │ │NON_CONFORMING│
  │CONFORM     │ └──────────────┘
  └──────┬─────┘
         │ RECEIVE_INVOICE (finanzas)
         ▼
  ┌──────────────┐
  │PENDING_      │
  │INVOICE       │
  └──────┬───────┘
         │ MATCH_INVOICE_OK (finanzas)
         ▼
  ┌──────────────┐
  │INVOICE_      │
  │MATCHED       │
  └──────┬───────┘
         │ CLOSE (finanzas/abastecimiento)
         ▼
    ┌──────────┐
    │  CLOSED  │
    └──────────┘
```

---

## Trazabilidad y Auditoría

A lo largo de todo el flujo:

- **Cada transición** queda registrada en el **audit log** inmutable con:
  - Quién ejecutó la acción (actor + rol).
  - Cuándo (timestamp).
  - Estado anterior y posterior (snapshots JSON).
  - Comentario (si aplica).
- El audit log está protegido a nivel de base de datos con un trigger PL/pgSQL que **impide modificar o eliminar** registros.
- El solicitante puede ver el **historial completo** de su solicitud en la vista de tracking.
- Cada estado tiene un **SLA esperado**, y el sistema muestra la fecha límite de resolución.

---

## Roles Involucrados (Resumen)

| Rol | Responsabilidad principal | Fases donde actúa |
|-----|--------------------------|-------------------|
| **Solicitante** | Crear, enviar, cancelar solicitudes; confirmar recepción | 1, 6 |
| **Jefe de Área** | Aprobar/rechazar solicitud y valorización | 2, 4 |
| **Abastecimiento** | Gestionar cotizaciones, emitir OC, enviar al proveedor | 3, 5 |
| **Gerencia** | Aprobar/rechazar Orden de Compra | 5 |
| **Bodega** | Registrar recepción conforme o no conforme | 6 |
| **Finanzas** | Recibir factura, conciliar, cerrar solicitud | 7 |
| **Auditor** | Consultar audit log (solo lectura) | Transversal |
| **Admin** | Acceso total, puede ejecutar cualquier acción | Todas |
