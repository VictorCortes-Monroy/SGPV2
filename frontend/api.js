// api.js — Cliente HTTP para SGP — Sistema de Gestión de Compras
// Backend: https://sgpv2-production.up.railway.app
// Auth: header X-User-Id (clerk_user_id) — modo MVP

const API_BASE = 'https://sgpv2-production.up.railway.app';

// ── ESTADO GLOBAL DEL CLIENTE ────────────────────────────────────────
const ApiClient = {
  baseUrl: API_BASE,
  userId: null,        // X-User-Id header value (clerk id)
  enabled: false,      // si false, los métodos lanzan APIDisabled
  lastError: null,
};

class APIDisabled extends Error { constructor() { super('API deshabilitada — usando datos mock'); } }
class APIError extends Error {
  constructor(status, body, url) {
    super(`API ${status} en ${url}`);
    this.status = status; this.body = body; this.url = url;
  }
}

const buildHeaders = () => {
  const h = { 'Content-Type': 'application/json' };
  if (ApiClient.userId) h['X-User-Id'] = ApiClient.userId;
  return h;
};

const handleResponse = async (res, url) => {
  if (!res.ok) {
    let body = null;
    try { body = await res.json(); } catch { body = await res.text(); }
    const err = new APIError(res.status, body, url);
    ApiClient.lastError = err;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
};

const request = async (method, path, { body, query, isForm } = {}) => {
  if (!ApiClient.enabled) throw new APIDisabled();
  let url = ApiClient.baseUrl + path;
  if (query) {
    const qs = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') qs.append(k, v);
    });
    const s = qs.toString();
    if (s) url += '?' + s;
  }
  const opts = { method, headers: isForm ? (() => {
    const h = {};
    if (ApiClient.userId) h['X-User-Id'] = ApiClient.userId;
    return h;
  })() : buildHeaders() };
  if (body !== undefined) opts.body = isForm ? body : JSON.stringify(body);
  const res = await fetch(url, opts);
  return handleResponse(res, url);
};

// ── ENDPOINTS ────────────────────────────────────────────────────────
const Api = {
  // Health & current user
  health:        () => request('GET', '/health'),
  me:            () => request('GET', '/api/v1/usuarios/me'),

  // Catálogos
  empresas:      () => request('GET', '/api/v1/empresas'),
  centrosCosto:  (empresaId) => request('GET', `/api/v1/empresas/${empresaId}/centros-costo`),
  familias:      () => request('GET', '/api/v1/catalogo/familias'),
  // RN-CAT-CC: el catálogo está particionado por CC. Pasar `centro_costo_id`
  // para que solo aparezcan items del CC de la SC.
  searchItems:   (q, centro_costo_id = null, limit = 20) =>
    request('GET', '/api/v1/catalogo/items/search', {
      query: { q, centro_costo_id, limit },
    }),
  getItem:       (id) => request('GET', `/api/v1/catalogo/items/${id}`),
  createItem:    (payload) => request('POST', '/api/v1/catalogo/items', { body: payload }),

  // Solicitudes (SC)
  listSolicitudes: (filters = {}) => request('GET', '/api/v1/solicitudes', { query: filters }),
  getSolicitud:    (id) => request('GET', `/api/v1/solicitudes/${id}`),
  createSolicitud: (payload) => request('POST', '/api/v1/solicitudes', { body: payload }),
  duplicateSolicitud: (id, fecha_requerida) => request('POST', `/api/v1/solicitudes/${id}/duplicate`, { query: { fecha_requerida } }),

  // Workflow — transitions (devuelve available_actions actualizado)
  applyTransition: (id, action, comment) => request('POST', `/api/v1/solicitudes/${id}/transitions`, { body: { action, comment } }),

  // Atajos de workflow (mapean acciones de UI → SCAction del backend)
  submit:        (id, comment) => Api.applyTransition(id, 'submit', comment),
  approveArea:   (id, comment) => Api.applyTransition(id, 'approve_area', comment),
  rejectArea:    (id, comment) => Api.applyTransition(id, 'reject_area', comment),
  cancel:        (id, comment) => Api.applyTransition(id, 'cancel', comment),

  // Adjuntos
  listAdjuntos:    (scId) => request('GET', `/api/v1/solicitudes/${scId}/adjuntos`),
  uploadAdjunto:   (scId, file) => {
    const fd = new FormData();
    fd.append('file', file);
    return request('POST', `/api/v1/solicitudes/${scId}/adjuntos`, { body: fd, isForm: true });
  },
  deleteAdjunto:   (scId, adjId) => request('DELETE', `/api/v1/solicitudes/${scId}/adjuntos/${adjId}`),
  downloadAdjuntoUrl: (scId, adjId) => `${ApiClient.baseUrl}/api/v1/solicitudes/${scId}/adjuntos/${adjId}/download`,

  // Auditoría
  auditLogs: (filters = {}) => request('GET', '/api/v1/auditoria/', { query: filters }),
};

// ── ENUMS DEL BACKEND ────────────────────────────────────────────────
const BACKEND_STATUS = [
  'draft', 'pending_area_approval', 'pending_quotation', 'quotation_received',
  'pending_valorization', 'valorization_approved', 'pending_po_emission',
  'pending_po_approval', 'po_approved', 'po_sent_to_supplier',
  'pending_reception', 'reception_conform', 'pending_invoice',
  'invoice_matched', 'closed', 'rejected', 'non_conforming', 'cancelled',
];

const STATUS_LABELS = {
  draft: 'Borrador',
  pending_area_approval: 'Pendiente aprobación del área',
  pending_quotation: 'Pendiente cotización',
  quotation_received: 'Cotización recibida',
  pending_valorization: 'Pendiente valorización',
  valorization_approved: 'Valorización aprobada',
  pending_po_emission: 'Pendiente emisión OC',
  pending_po_approval: 'Pendiente aprobación OC',
  po_approved: 'OC aprobada',
  po_sent_to_supplier: 'OC enviada al proveedor',
  pending_reception: 'Pendiente recepción',
  reception_conform: 'Recepción conforme',
  pending_invoice: 'Pendiente factura',
  invoice_matched: 'Factura conciliada',
  closed: 'Cerrada',
  rejected: 'Rechazada',
  non_conforming: 'No conforme',
  cancelled: 'Cancelada',
};

// Mapeo simplificado para el timeline de 9 estados de la UI
const STATUS_TO_PHASE = {
  draft: 'borrador',
  pending_area_approval: 'revision',
  pending_quotation: 'aprobada',
  quotation_received: 'cotizada',
  pending_valorization: 'cotizada',
  valorization_approved: 'cotizada',
  pending_po_emission: 'cotizada',
  pending_po_approval: 'cotizada',
  po_approved: 'oc',
  po_sent_to_supplier: 'oc',
  pending_reception: 'transito',
  reception_conform: 'recibida',
  pending_invoice: 'recibida',
  invoice_matched: 'facturada',
  closed: 'facturada',
  rejected: 'rechazada',
  non_conforming: 'rechazada',
  cancelled: 'rechazada',
};

const ACTION_LABELS = {
  submit: 'Enviar a aprobación',
  approve_area: 'Aprobar (jefe de área)',
  reject_area: 'Rechazar',
  register_quotations: 'Registrar cotizaciones',
  send_valorization: 'Enviar a valorización',
  approve_valorization: 'Aprobar valorización',
  request_recotization: 'Solicitar re-cotización',
  reject_valorization: 'Rechazar valorización',
  emit_po: 'Emitir OC',
  approve_po: 'Aprobar OC',
  reject_po: 'Rechazar OC',
  send_po_to_supplier: 'Enviar OC al proveedor',
  register_reception_conform: 'Registrar recepción conforme',
  register_reception_non_conform: 'Registrar no-conformidad',
  receive_invoice: 'Recibir factura',
  match_invoice_ok: 'Conciliar factura',
  match_invoice_fail: 'Reportar discrepancia',
  close: 'Cerrar',
  cancel: 'Cancelar',
};

const URGENCIA_BACKEND = { NORMAL: 'media', URGENTE: 'alta', CRITICA: 'alta' };
const URGENCIA_FRONTEND = { baja: 'NORMAL', media: 'NORMAL', alta: 'URGENTE' };

// ── ADAPTERS — backend ↔ frontend ────────────────────────────────────
// Convierte SolicitudCompraRead del backend al shape del frontend
const adaptSolicitud = (sc, empresasMap, ccMap) => {
  const empresa = empresasMap?.[sc.empresa_id];
  const cc = ccMap?.[sc.centro_costo_id];
  const phase = STATUS_TO_PHASE[sc.status] || 'solicitada';
  const urgencia = URGENCIA_BACKEND[sc.urgencia] || 'media';
  return {
    // identificación
    id: sc.numero || `SC-${sc.id}`,
    backendId: sc.id,
    backendStatus: sc.status,
    statusLabel: STATUS_LABELS[sc.status],
    availableActions: sc.available_actions || [],
    // título: usa primeras palabras de la descripción
    titulo: sc.descripcion?.split('\n')[0]?.slice(0, 90) || `Solicitud ${sc.numero}`,
    descripcion: sc.descripcion,
    justificacion: sc.justificacion,
    // empresa / cc
    empresa: empresa?.nombre_corto?.toLowerCase() || `emp-${sc.empresa_id}`,
    empresaId: sc.empresa_id,
    empresaInfo: empresa,
    centroCosto: cc ? `cc-${cc.id}` : `cc-${sc.centro_costo_id}`,
    centroCostoId: sc.centro_costo_id,
    centroCostoInfo: cc,
    // tipo / urgencia / fechas (sin info económica — fuera de alcance MVP)
    tipo: sc.tipo === 'BIEN' ? 'insumos' : 'servicios',
    tipoBackend: sc.tipo,
    urgencia,
    urgenciaBackend: sc.urgencia,
    fechaSolicitud: sc.created_at?.slice(0, 10),
    fechaRequerida: sc.fecha_requerida,
    // workflow / phase
    estadoActual: phase,
    currentAssigneeRole: sc.current_assignee_role,
    expectedResolutionAt: sc.expected_resolution_at,
    // items / adjuntos
    items: (sc.lineas || []).map((l) => ({
      id: l.id,
      itemId: l.item_id,
      sku: l.item_sku,
      descripcion: l.item_nombre + (l.especificacion ? ` — ${l.especificacion}` : ''),
      cantidad: parseFloat(l.cantidad),
      unidad: '',
    })),
    adjuntos: (sc.adjuntos || []).map((a) => ({
      id: a.id,
      nombre: a.filename,
      tipo: a.content_type?.includes('pdf') ? 'pdf' :
            a.content_type?.startsWith('image/') ? 'img' :
            a.content_type?.includes('sheet') ? 'xls' : 'file',
      tamano: formatBytes(a.size_bytes),
    })),
    // solicitante (placeholder — el backend devuelve solo solicitante_id)
    solicitante: {
      nombre: `Usuario #${sc.solicitante_id}`,
      cargo: '',
      avatar: 'U' + sc.solicitante_id,
    },
    // eventos: backend no expone log inline; lo derivamos del status
    eventos: [
      { id: `e-create-${sc.id}`, fecha: sc.created_at?.slice(0, 16).replace('T', ' '),
        actor: `Usuario #${sc.solicitante_id}`, actorRol: 'Solicitante', tipo: 'estado', estado: 'solicitada' },
    ],
    _raw: sc,
  };
};

const formatBytes = (n) => {
  if (!n) return '—';
  if (n >= 1048576) return `${(n / 1048576).toFixed(1)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${n} B`;
};

// Convierte form del UI → SolicitudCompraCreate
const buildCreatePayload = (form) => {
  return {
    empresa_id: form.empresaId,
    centro_costo_id: form.centroCostoId,
    tipo: form.tipoBackend || (form.tipo === 'servicios' ? 'SERVICIO' : 'BIEN'),
    urgencia: form.urgenciaBackend || URGENCIA_FRONTEND[form.urgencia] || 'NORMAL',
    descripcion: form.descripcion,
    justificacion: form.justificacion || null,
    fecha_requerida: form.fechaRequerida,
    lineas: (form.items || []).map((it) => ({
      item_id: it.itemId,
      cantidad: it.cantidad,
      especificacion: it.especificacion || null,
    })),
  };
};

// ── INIT / TEST ──────────────────────────────────────────────────────
const initApi = async ({ baseUrl, userId, enabled = true } = {}) => {
  if (baseUrl) ApiClient.baseUrl = baseUrl;
  if (userId !== undefined) ApiClient.userId = userId;
  ApiClient.enabled = enabled;
  ApiClient.lastError = null;
  try {
    const h = await Api.health();
    return { ok: true, health: h };
  } catch (e) {
    return { ok: false, error: e };
  }
};

Object.assign(window, {
  Api, ApiClient, APIError, APIDisabled,
  initApi, adaptSolicitud, buildCreatePayload,
  STATUS_LABELS, STATUS_TO_PHASE, ACTION_LABELS,
  URGENCIA_BACKEND, URGENCIA_FRONTEND, BACKEND_STATUS,
});
