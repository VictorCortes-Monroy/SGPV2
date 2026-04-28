# Notificaciones — pendiente de implementar

Estado: 🔴 **NO IMPLEMENTADO**. Este documento es la **especificación funcional**
acordada con negocio y debería convertirse en sprint cuando se priorice.

> Razón por la que está pendiente: el resto del flujo (creación, workflow,
> adjuntos, búsqueda) cubre la operación mínima. Notificaciones es funcionalidad
> nueva, no refinamiento, y suma ~1 sprint completo.

---

## Objetivo de negocio

> *"El solicitante debe recibir notificaciones sobre cambios en el estado de
> la solicitud para estar informado."* — objetivo del solicitante.

Hoy el solicitante tiene que entrar a la app y mirar la SC para enterarse de
si fue aprobada/rechazada/cotizada/etc. Queremos push (email para empezar,
SMS y WhatsApp como follow-ups).

## Eventos a notificar

Por cada transición de estado, qué actor recibe email:

| Acción | Solicitante | Aprobador siguiente | Otros |
|---|:---:|:---:|---|
| `SUBMIT` | confirmación enviada | jefe_area "tienes SC pendiente" | — |
| `APPROVE_AREA` | "tu SC fue aprobada por jefe" | finanzas / abastecimiento | — |
| `REJECT_AREA` | "tu SC fue rechazada" + comment | — | — |
| `RELEASE_BUDGET` | "presupuesto liberado" | abast / gerencia | — |
| `FREEZE_BUDGET` | "tu SC quedó congelada" | gerencia | — |
| `AUTHORIZE_FROZEN` | "presupuesto autorizado" | abast | — |
| `APPROVE_MANAGEMENT` | "aprobada por gerencia" | abast | — |
| `REJECT_MANAGEMENT` | "rechazada por gerencia" + comment | — | — |
| `REGISTER_QUOTATIONS` | "cotizaciones recibidas" | jefe_area | — |
| `APPROVE_VALORIZATION` | "valorización aprobada" | abast | — |
| `REQUEST_RECOTIZATION` | "se pidió recotización" | abast | — |
| `REJECT_VALORIZATION` | "valorización rechazada" + comment | — | — |
| `EMIT_PO` | "OC emitida" | gerencia | — |
| `APPROVE_PO` | "OC aprobada" | abast | — |
| `REJECT_PO` | "OC rechazada" + comment | — | — |
| `SEND_PO_TO_SUPPLIER` | "OC enviada al proveedor" | bodega | — |
| `REGISTER_RECEPTION_CONFORM` | "recepción registrada conforme" | finanzas | — |
| `REGISTER_RECEPTION_NON_CONFORM` | "recepción no conforme" + comment | — | — |
| `RECEIVE_INVOICE` | — | finanzas | — |
| `MATCH_INVOICE_OK` | "factura aceptada, esperando cierre" | — | — |
| `CLOSE` | "tu compra está cerrada exitosamente" | — | — |

Adicionalmente, **alertas por SLA** (cron):
- A las X horas de excedido `expected_resolution_at`, recordatorio al
  `current_assignee_role`.
- Escalación al rol superior tras Y horas adicionales.

## Diseño técnico propuesto

### 1. Adapter de email (extensible)

Mismo patrón que `AttachmentStorage`: Protocol + impl.

```python
# core/notifications.py
class EmailSender(Protocol):
    async def send(self, *, to: str, subject: str, body_html: str, body_text: str) -> str: ...

class ResendEmailSender:
    """Implementación con Resend (recomendado para MVP)."""
    ...

class ConsoleEmailSender:
    """Para dev: imprime en stdout en vez de enviar."""
    ...
```

Recomendación de proveedor: **Resend** (DX simple, free tier 100/día,
$20/mes los 50k).

### 2. Tabla `notificaciones_enviadas`

Idempotencia + tracking. Evita re-enviar si una transición se reintenta o si
el job de SLA corre dos veces.

```sql
CREATE TABLE notificaciones_enviadas (
    id SERIAL PRIMARY KEY,
    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
        -- ej: "sc:42:transition:approve_area:to:user_123"
    destinatario_id INTEGER REFERENCES usuarios(id),
    destinatario_email VARCHAR(255) NOT NULL,
    template VARCHAR(100) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    enviado_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    provider_message_id VARCHAR(255),
    status VARCHAR(20) DEFAULT 'sent',   -- sent | failed | bounced
    error_detail TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

### 3. Hook en `service.apply_transition`

Tras el `audit.log()`, encolar notificaciones:

```python
notifications.notify_transition(
    sc=sc,
    action=request.action,
    actor=actor,
)
```

Donde `notify_transition` resuelve la matriz arriba y llama `email_sender.send`
para cada destinatario, persistiendo en `notificaciones_enviadas` con su
`idempotency_key`. Si la key ya existe → no-op.

### 4. Plantillas

Jinja2 con un layout base + 1 template por evento (o 1 generic con if/else).
Localización en español por defecto.

### 5. Preferencias del usuario

Campo opcional `usuarios.notification_preferences: JSON` con shape:

```json
{
  "email": {
    "enabled": true,
    "events": ["approve_area", "reject_area", "close", "..."]
  }
}
```

Si no está configurado → enviar todos por email. Como la mayoría querrá
recibir todo, default-on es razonable.

### 6. Configuración

Variables de entorno nuevas:
```
NOTIFICATIONS_BACKEND=resend          # resend | console (dev)
RESEND_API_KEY=re_xxx
RESEND_FROM_EMAIL=sgp@empresa.cl
RESEND_FROM_NAME="SGP — Compras"
```

### 7. Job de SLA breached

Tarea cron (Railway cron job o agent externo) que cada X minutos:
1. Busca SCs con `expected_resolution_at < now()` y status no terminal.
2. Si hace > Y horas que venció → envía recordatorio (idempotency key
   `sc:{id}:sla_warn:{day}`).
3. Si hace > Z horas → escala al rol superior.

## Qué NO hacer en este sprint

- ❌ SMS / WhatsApp — agrega complejidad (proveedor, costos, opt-in)
- ❌ Push notifications mobile — requiere app
- ❌ Web push browser — incremental, después
- ❌ Mensajería interna en la app (inbox) — duplicaría el feed que da el
  audit_log

## Costo estimado

- Resend: 100 emails/día gratis; ~USD 20/mes para 50k. SGP en producción real
  hablamos de cientos de SCs/mes con ~10 transiciones cada una → ~5k–10k
  emails/mes → free tier alcanza.
- Tiempo de implementación: 1 sprint corto (5–7 días-persona).

## Cuando se implemente, actualizar

- `docs/transiciones_sc.md`: marcar como 🟢 las acciones cuya notificación
  esté operativa.
- Sección de objetivos del solicitante en el README/análisis: pasar el
  punto 3 de 0% a 🟢.
- README.md "Reglas implementadas": agregar RN-NOTIF.
