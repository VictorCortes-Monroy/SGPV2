# Frontend — arquitectura del prototipo

El frontend actual es un **prototipo** entregado por Claude Design (carpeta `solicitudes-de-pedido/`), implementado en HTML + JSX + Babel CDN sin build step. Vive en `frontend/` y FastAPI lo sirve en `/`.

> Para evolucionar a producción → migrar a Next.js + TypeScript (ver [decisiones.md ADR-005](decisiones.md#adr-005--frontend-prototipo-htmljsxbabel-cdn-sin-build)).

---

## Layout de archivos

```
frontend/
├── index.html              # Entry — servida por FastAPI en /
│   ├─ <link> a CSS (styles.css, styles-aprobador.css)
│   ├─ <script> CDN: react, react-dom, @babel/standalone
│   ├─ <script src="api.js">  ← cliente HTTP (no JSX)
│   └─ <script type="text/babel"> componente raíz <App />
│
├── api.js                  # Cliente HTTP del backend (Api.*, adapters)
│
├── data.jsx                # Mock data para preview off-line
├── icons.jsx               # Catálogo de iconos SVG
├── ui.jsx                  # Primitivos: Card, Input, Select, Button, Field, Avatar, etc.
├── layout.jsx              # Sidebar, TopBar
│
├── role-selector.jsx       # Pantalla "elige tu rol"
├── data-source.jsx         # Hook useDataSource (mock vs API real)
├── tweaks-panel.jsx        # Panel flotante de tweaks (cambiar baseUrl, userId, etc.)
│
├── dashboard.jsx           # Vista solicitante: lista de mis SCs
├── form.jsx                # Vista solicitante: nueva SC + ItemPicker + NuevoItemModal
├── tracking.jsx            # Vista solicitante: detalle de su SC
│
├── aprobador-bandeja.jsx   # Vista aprobador: bandeja (3 layouts: tabla/lista/cards)
├── aprobador-detalle.jsx   # Vista aprobador: detalle + acciones
│
├── notifications.jsx       # Centro de notificaciones (placeholder)
│
├── styles.css              # Estilos globales
└── styles-aprobador.css    # Estilos específicos del aprobador
```

---

## Cómo se carga

`index.html` declara los scripts en orden. Babel transpila en runtime los `<script type="text/babel">`:

```html
<script src="https://unpkg.com/react@18.3.1/.../react.development.js"></script>
<script src="https://unpkg.com/react-dom@18.3.1/.../react-dom.development.js"></script>
<script src="https://unpkg.com/@babel/standalone@7.29.0/.../babel.min.js"></script>
<script src="api.js"></script>     ← cliente HTTP, plain JS

<script type="text/babel" src="data.jsx"></script>      ← mock data
<script type="text/babel" src="icons.jsx"></script>     ← shared
<script type="text/babel" src="ui.jsx"></script>        ← shared
<script type="text/babel" src="layout.jsx"></script>
<script type="text/babel" src="dashboard.jsx"></script>
<script type="text/babel" src="form.jsx"></script>
... etc

<script type="text/babel">
  function App() { ... }
  ReactDOM.createRoot(document.getElementById('root')).render(<App />);
</script>
```

**Cada `.jsx`** termina con `window.NombreComponente = NombreComponente;` para exportar al scope global. No hay módulos ES6 — todo vive en `window`.

---

## Estado de la app (App component)

```js
function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [role, setRole] = React.useState(null);          // 'solicitante' | 'aprobador' | null
  const [view, setView] = React.useState('dashboard');   // 'dashboard' | 'nueva' | 'tracking' | 'bandeja' | 'aprob-detalle'
  const [activeId, setActiveId] = React.useState(null);  // SC seleccionada actualmente
  const [toast, setToast] = React.useState(null);

  const ds = useDataSource({ source: t.dataSource, userId: t.apiUserId, baseUrl: t.apiBaseUrl });
  const { solicitudes, conn, empresas, centros } = ds;
  ...
}
```

`useDataSource` es el hook clave: abstrae **mock** vs **API real**. Cuando `source === 'api'`, fetcha empresas/CCs/SCs del backend, los adapta al shape del frontend, y maneja mutaciones.

---

## Cliente HTTP (`api.js`)

No es JSX. Plain JavaScript con `fetch`. Estructura:

```js
const ApiClient = { baseUrl, userId, enabled, lastError };

const Api = {
  health, me,
  empresas, centrosCosto, familias,
  searchItems(q, centro_costo_id, limit),
  getItem, createItem,
  listSolicitudes, getSolicitud, createSolicitud, duplicateSolicitud,
  applyTransition,
  // shortcuts: submit, approveArea, rejectArea, cancel
  listAdjuntos, uploadAdjunto, deleteAdjunto, downloadAdjuntoUrl,
  auditLogs,
};

const initApi = ({ baseUrl, userId, enabled }) => {...};

const adaptSolicitud = (sc, empresasMap, ccMap) => {
  // Convierte SolicitudCompraRead del backend al shape del frontend
};

window.Api = Api;
window.adaptSolicitud = adaptSolicitud;
```

Manejo de errores: clases `APIError(status, body, url)` y `APIDisabled`.

---

## Adapters backend ↔ frontend

El frontend usa shapes ligeramente distintos al backend. Convertimos en `adaptSolicitud`:

```js
{
  // identificación
  id: sc.numero || `SC-${sc.id}`,    // ← frontend usa el numero como id principal
  backendId: sc.id,                  // ← preservamos el id numérico
  backendStatus: sc.status,
  statusLabel: STATUS_LABELS[sc.status],
  availableActions: sc.available_actions,

  // empresa / cc — embebido para evitar lookups
  empresaInfo: empresa,              // <- objeto completo, usado por dashboard/tracking
  centroCostoInfo: cc,

  // tipo / urgencia / fechas (sin info económica)
  tipo: 'insumos' | 'servicios',
  urgencia: 'baja' | 'media' | 'alta',
  fechaSolicitud, fechaRequerida,

  // workflow
  estadoActual: STATUS_TO_PHASE[sc.status],   // mapeo a 9 fases visuales
  currentAssigneeRole, expectedResolutionAt,

  // items embebidos
  items: [{ id, itemId, sku, descripcion, cantidad }],
  adjuntos: [{ id, nombre, tipo, tamano }],

  // solicitante (placeholder — backend solo devuelve solicitante_id)
  solicitante: { nombre, cargo, avatar },

  // raw para escape hatch
  _raw: sc,
}
```

---

## Item picker (formulario nueva SC)

Componente clave del refactor reciente. En `form.jsx::SectionItems`:

```
┌──────────────────────────────┬─────────┬──────────────┬──────┐
│ <ItemPicker row={it} ... />  │ cantidad│ especificación│  ✕   │
└──────────────────────────────┴─────────┴──────────────┴──────┘
        ↓ dropdown predictivo cuando typing
        ┌──────────────────────────────────┐
        │ ITM-LUB-15W40 — Aceite hidráulico│
        │ ITM-FIL-A102  — Filtro aire ...  │
        │ ─────────────────────────────────│
        │ + Crear nuevo item en este CC    │
        └──────────────────────────────────┘
```

**ItemPicker:**
- Si `row.itemId` existe → modo "seleccionado": muestra SKU + nombre + ✕
- Si no → input de búsqueda. `onChange` con debounce de 250ms llama `Api.searchItems(q, ccBackendId, 10)`
- Dropdown lista resultados; click en uno setea `itemId, sku, nombre`
- Botón "+ Crear nuevo item" abre `<NuevoItemModal>`

**NuevoItemModal:**
- Form con `sku, nombre, familia_id, unidad_medida, criticidad, especificacion_tecnica`
- `centro_costo_id` viene auto-asignado del CC actual de la SC (readonly)
- Llama `Api.createItem({...})` → 201 → cierra modal e inserta en la fila

---

## Panel de tweaks

Botón flotante abajo a la derecha. Permite cambiar en runtime:

| Tweak | Valores |
|---|---|
| `dataSource` | `mock` / `api` |
| `apiBaseUrl` | URL del backend (default: producción Railway) |
| `apiUserId` | header `X-User-Id` (default: `user_victor`) |
| `formLayout` | `twocol` / `single` / `wizard` |
| `bandejaLayout` | `tabla` / `lista` / `cards` |

Estado se persiste en `localStorage`. Útil para:
- Probar con distintos roles sin cambiar de browser
- Apuntar a un backend local mientras el front está deployado
- Comparar layouts del aprobador

---

## Limitaciones conocidas

| Item | Detalle |
|---|---|
| Sin tipos | Cualquier shape mismatch crashea en runtime. Mitigado con tests E2E manuales. |
| Sin tree-shaking | Todo el bundle se carga siempre. ~50KB de `data.jsx` mock se serve aunque no se use. |
| Babel runtime | El primer paint tarda más. Aceptable para prototipo, no para prod. |
| `window.X = X` | No hay encapsulamiento. Conflictos potenciales si dos archivos exportan el mismo nombre. |
| No hay router | URLs no reflejan la vista (`view` es state interno). El back/forward del browser no funciona. |
| Mock data en `data.jsx` | Algunos componentes (Dashboard's empresa filter) usan `EMPRESAS` del mock. Pueden quedar desincronizados con el API. |

---

## Testing del frontend

Hoy: **manual**. Smoke tests que se hacen apenas se deploya:

1. Abrir https://sgpv2-production.up.railway.app/
2. Hard refresh (`Ctrl+Shift+R`)
3. Selecciona rol Solicitante → Dashboard debe listar SCs reales
4. Click en una SC → tracking sin errores
5. Nueva solicitud → seleccionar empresa+CC → buscar item → crear SC → debería redirect al tracking
6. Cambiar a rol Aprobador → bandeja → click en una pendiente → ver detalle, aprobar/rechazar
7. Tweaks → cambiar `dataSource` a `mock` → todo funciona offline
8. DevTools → Console → no debe haber errores rojos

Para tests automáticos, hace falta migrar a Next.js (Playwright/Cypress).

---

## Path de evolución a Next.js

Cuando se priorice convertir el prototipo a producción:

1. **Crear app Next.js** en `frontend-next/` (no tocar `frontend/` hasta migrar todo).
2. Reusar **`api.js`** casi tal cual — ya es plain JS y agnóstico al framework. Mover a `lib/api.ts` con tipos.
3. Convertir cada `.jsx` a componente Next.js. La lógica funcional (hooks, fetch) se preserva, los imports cambian.
4. Reemplazar `window.X = X` por exports ES6.
5. Reemplazar `EMPRESAS`, `CENTROS_COSTO`, `TIPOS_COMPRA` mock por consultas API reales (los componentes ya tienen los hooks `empresasInfo`/`centroCostoInfo` para fallback).
6. Routing con Next.js App Router. Cada vista (dashboard, tracking, bandeja, etc.) es una página.
7. Tipos de los responses del backend: generar desde OpenAPI con `openapi-typescript` o `swagger-typescript-api`.
8. Tests con Playwright para los flujos E2E críticos.

**Esfuerzo estimado:** 2-4 semanas, dependiendo de cuánto se rediseñe la UX.
