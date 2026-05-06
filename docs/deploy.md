# Deploy y operación

Playbook de cómo correr el sistema localmente y en Railway, troubleshooting de fallas conocidas.

---

## Local (desarrollo)

### Stack en un solo comando

```bash
docker compose up
```

Levanta:
- **Postgres 16** (puerto 5432, healthcheck con `pg_isready`)
- **API** (puerto 8000, build de `Dockerfile`)

El servicio API corre `bash scripts/start.sh`:
1. `alembic upgrade head` (aplica todas las migraciones)
2. Si `SEED_ON_STARTUP=true`: `python scripts/seed.py` (idempotente)
3. `uvicorn sgp.main:app --host 0.0.0.0 --port $PORT`

### URLs locales

| URL | Qué |
|---|---|
| http://localhost:8000/ | Frontend del prototipo |
| http://localhost:8000/health | Healthcheck `{"status":"ok"}` |
| http://localhost:8000/api/docs | Swagger UI |
| http://localhost:8000/api/v1/usuarios/me | Endpoint con `X-User-Id: user_victor` |

### Workflow típico

```bash
# 1. Levantar
docker compose up -d

# 2. Aplicar migraciones (si hay nuevas)
docker compose exec api alembic upgrade head

# 3. Seed idempotente
docker compose exec api python scripts/seed.py

# 4. Correr tests
docker compose exec api pytest -v               # todos
docker compose exec api pytest -m "not postgres" # solo unit
docker compose exec api pytest -m postgres -v   # solo integration

# 5. Logs en vivo
docker compose logs -f api

# 6. Reset total (borra volumes incluidos los adjuntos)
docker compose down -v
```

### Volumes en docker-compose

| Volume | Para qué |
|---|---|
| `sgp_pg_data` | Datos de Postgres (sobrevive `docker compose down`) |
| `sgp_adjuntos_data` | Adjuntos subidos (mount en `/data` del container API) |
| `./src:/app/src` (bind) | Cambios en código sin rebuild |
| `./alembic:/app/alembic` (bind) | Migraciones nuevas sin rebuild |
| `./scripts:/app/scripts` | Seed sin rebuild |
| `./tests:/app/tests` | Tests sin rebuild |
| `./frontend:/app/frontend` | Frontend sin rebuild |

---

## Railway (producción)

### Setup inicial

Documentado paso a paso en [README.md § Despliegue en Railway](../README.md#despliegue-en-railway). Resumen:

1. **New Project** → **Deploy from GitHub repo** → `SGPV2`
2. **+ New** → **Database** → **PostgreSQL**
3. En el servicio API: agregar volume **mount path `/data`**, size 1 GB
4. Variables (ver tabla abajo)
5. **Settings → Networking → Generate Domain** (target port `8080` — Railway inyecta `$PORT=8080`)

### Variables de entorno

| Variable | Valor | Notas |
|---|---|---|
| `DATABASE_URL` | Reference → `Postgres.DATABASE_URL` | Validator en `config.py` convierte `postgresql://` → `postgresql+asyncpg://` |
| `APP_ENV` | `production` | |
| `APP_DEBUG` | `false` | |
| `AUTH_MODE` | `mock` | Reemplazar por `clerk` cuando se integre |
| `LOG_LEVEL` | `INFO` | |
| `LOG_FORMAT` | `json` | Logs estructurados en producción |
| `CORS_ORIGINS` | `*` (testing) o lista explícita (prod) | Auto-flip de `credentials` según wildcard (ADR-013) |
| `STORAGE_PATH` | `/data/sgp/adjuntos` | Dentro del Railway volume |
| `SEED_ON_STARTUP` | `true` solo primera vez | Idempotente, después poner `false` |

**Variables que no van** (Railway las maneja o son innecesarias):
- `PORT` — Railway lo inyecta automáticamente
- `APP_PORT` — no la usa nadie
- `DATABASE_PUBLIC_URL` — solo para conectar desde fuera de Railway con un cliente

### Auto-deploy

Railway detecta push a `main` y auto-deploya. El script `start.sh` corre las migraciones automáticamente al arrancar — no hay paso manual.

### Healthcheck

`railway.json` declara `/health` con timeout 30s. Si la API no responde 200 en `/health`, Railway reinicia.

---

## Troubleshooting

### 502 Bad Gateway en el dominio público

**Causa:** mismatch entre el puerto del dominio y el puerto donde escucha la app.

**Diagnóstico:**
```bash
# Ver logs del último deploy en Railway → Deployments → Deploy Logs
# Buscar la línea: "Uvicorn running on http://0.0.0.0:XXXX"
```

**Fix:** ir al dominio en Railway → Settings → Networking → editar el dominio → cambiar **Target Port** al que muestra el log (típicamente `8080`).

### Migración falla con `DatatypeMismatchError: default for column "..." cannot be cast`

**Causa:** Postgres no puede castear automáticamente el server_default cuando se cambia el tipo de columna (ej. recrear un enum).

**Fix:** drop el default ANTES del `ALTER COLUMN TYPE`, re-aplicarlo después con el tipo nuevo. Ver migración 0006 como ejemplo:
```sql
ALTER TABLE solicitudes_compra ALTER COLUMN status DROP DEFAULT;
ALTER TABLE solicitudes_compra ALTER COLUMN status TYPE sc_status_enum_v2 USING ...;
ALTER TABLE solicitudes_compra ALTER COLUMN status SET DEFAULT 'draft'::sc_status_enum_v2;
```

### `invalid input value for enum sc_status_enum: "DRAFT"`

**Causa:** SQLAlchemy serializa enums por `.name` (mayúsculas) pero el enum nativo de Postgres se creó con `.value` (minúsculas).

**Fix:** ya aplicado en `solicitudes/models.py` — el `Enum` usa `values_callable=lambda enum_cls: [e.value for e in enum_cls]`. Si aparece este error en otra columna, replicar el patrón.

### CORS: "Failed to fetch" en el browser

**Causa:** el browser dispara preflight OPTIONS por headers no-simples (`X-User-Id`, `Content-Type: application/json`). Si el server no responde con headers CORS apropiados, falla **antes** de la request real, sin error visible en el cliente.

**Diagnóstico:**
```bash
curl -X OPTIONS https://<dominio>/api/v1/usuarios/me \
  -H "Origin: https://<origen-cliente>" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: x-user-id" \
  -i | head -15
```

Esperado: ver `access-control-allow-origin`, `access-control-allow-headers`, `access-control-allow-methods`.

**Fix:**
- Si quieres un origen específico: `CORS_ORIGINS=https://tu-frontend.app`
- Si quieres testing abierto: `CORS_ORIGINS=*` (auto-flip a `credentials=False` por ADR-013)
- Combinar: `CORS_ORIGINS=https://prod.app,https://staging.app`

### Adjuntos se pierden tras redeploy

**Causa:** el Railway volume no está montado correctamente, o `STORAGE_PATH` apunta fuera del mount.

**Fix:**
1. Settings → Volumes → confirmar mount path = `/data`
2. Variables → confirmar `STORAGE_PATH=/data/sgp/adjuntos` (dentro del mount)
3. Redeploy

### App arranca pero `/api/v1/*` da 401 en todos los requests

**Causa:** falta el header `X-User-Id` (modo `AUTH_MODE=mock`).

**Fix:** mientras `AUTH_MODE=mock`, todos los endpoints requieren `X-User-Id: <clerk_user_id>` que exista en `usuarios`. Sin ese header → 401.

### Columna nueva en migración pero `seed.py` falla con `column does not exist`

**Causa:** se agregó la columna en el modelo pero la migración no se ejecutó (o falló silenciosamente).

**Fix:**
```bash
docker compose exec api alembic current  # ver versión actual
docker compose exec api alembic upgrade head  # forzar ejecución
docker compose exec api python scripts/seed.py
```

---

## Costos

Estimación Railway (plan Hobby):

| Servicio | Costo/mes |
|---|---|
| API (compute) | ~USD 5 |
| Postgres | ~USD 5 |
| Volume 1 GB | incluido |
| **Total MVP** | **~USD 10** |

Cuando crezca:
- Volume > 1 GB: ~USD 0.25/GB extra
- Plan Pro: USD 20/mes con más recursos garantizados
- Migrar storage a S3/Azure Blob cuando los adjuntos pasen de GB

---

## Backup y restore

Hoy: nada automatizado. Postgres en Railway tiene snapshots automáticos en plan Pro pero no en Hobby.

**Manual** (mientras se decide algo automatizado):
```bash
# Backup desde tu máquina (necesita DATABASE_PUBLIC_URL)
pg_dump "postgresql://user:pass@host:port/railway" > backup-$(date +%F).sql

# Restore (cuidado: drop existing primero o usa pg_dump --clean)
psql "postgresql://user:pass@host:port/railway" < backup.sql
```

**Recomendación pendiente:** scheduled job en Railway que haga `pg_dump` a S3 diariamente. Sprint dedicado.

---

## Logs y observabilidad

Hoy: logs estructurados en JSON (`LOG_FORMAT=json`), accesibles vía Railway → Deployments → Deploy Logs.

**Pendiente:**
- Métricas (latencia, error rate) — sin Prometheus/Datadog hoy
- Distributed tracing — sin OpenTelemetry hoy
- Alertas — sin PagerDuty/Slack integration hoy

Aceptable para MVP. Antes de escalar a usuarios reales, abordar.
