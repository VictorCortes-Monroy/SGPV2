// data-source.jsx — Hook que abstrae mock vs API real

const useDataSource = ({ source, userId, baseUrl }) => {
  const [solicitudes, setSolicitudes] = React.useState(SOLICITUDES_MOCK);
  const [empresas, setEmpresas] = React.useState(EMPRESAS);
  const [centros, setCentros] = React.useState(CENTROS_COSTO);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [conn, setConn] = React.useState({ status: 'mock', detail: 'Datos locales' });

  // empresas/cc maps para el adapter
  const empresasMapRef = React.useRef({});
  const ccMapRef = React.useRef({});

  const loadFromApi = React.useCallback(async () => {
    setLoading(true); setError(null);
    try {
      // 1) empresas y CC en paralelo
      const empresasApi = await Api.empresas();
      const empresasMap = {};
      empresasApi.forEach((e) => { empresasMap[e.id] = e; });
      empresasMapRef.current = empresasMap;

      const ccByEmp = {};
      const ccMap = {};
      await Promise.all(empresasApi.map(async (e) => {
        const ccs = await Api.centrosCosto(e.id);
        ccs.forEach((c) => { ccMap[c.id] = c; });
        ccByEmp[e.nombre_corto.toLowerCase()] = ccs.map((c) => ({
          id: `cc-${c.id}`, codigo: c.codigo, nombre: c.nombre, proyecto: c.descripcion || '',
          presupuestoAnual: parseFloat(c.presupuesto_anual) || 0,
          gastoYtd: parseFloat(c.gasto_ytd) || 0,
          backendId: c.id,
        }));
      }));
      ccMapRef.current = ccMap;

      // 2) solicitudes
      const list = await Api.listSolicitudes({ limit: 50 });
      const items = Array.isArray(list) ? list : (list.items || list.results || []);
      const adapted = items.map((sc) => adaptSolicitud(sc, empresasMap, ccMap));

      setEmpresas(empresasApi.map((e) => ({
        id: e.nombre_corto.toLowerCase(), nombre: e.razon_social, rut: e.rut,
        rubro: e.giro || '', abrev: e.nombre_corto, backendId: e.id,
      })));
      setCentros(ccByEmp);
      setSolicitudes(adapted);
      setConn({ status: 'connected', detail: `${adapted.length} solicitudes cargadas` });
    } catch (e) {
      setError(e);
      setConn({ status: 'error', detail: e.message || 'Error desconocido' });
    } finally { setLoading(false); }
  }, []);

  React.useEffect(() => {
    if (source === 'api') {
      const ok = initApi({ baseUrl, userId, enabled: true });
      ApiClient.enabled = true;
      ApiClient.userId = userId;
      if (baseUrl) ApiClient.baseUrl = baseUrl;
      setConn({ status: 'loading', detail: 'Conectando…' });
      loadFromApi();
    } else {
      ApiClient.enabled = false;
      setSolicitudes(SOLICITUDES_MOCK);
      setEmpresas(EMPRESAS);
      setCentros(CENTROS_COSTO);
      setConn({ status: 'mock', detail: 'Datos locales' });
      setError(null);
    }
  }, [source, userId, baseUrl, loadFromApi]);

  // Mutaciones unificadas
  const refresh = () => source === 'api' ? loadFromApi() : null;

  const aprobar = async (solicitud, comentario) => {
    if (source === 'api' && solicitud.backendId) {
      try {
        await Api.approveArea(solicitud.backendId, comentario);
        await loadFromApi();
        return { ok: true };
      } catch (e) { return { ok: false, error: e }; }
    }
    setSolicitudes((prev) => prev.map((s) => s.id === solicitud.id ? {
      ...s, estadoActual: 'aprobada',
      eventos: [...s.eventos, { id: `e${Date.now()}`, estado: 'aprobada', fecha: new Date().toISOString().slice(0, 16).replace('T', ' '),
        actor: USUARIOS.aprobador.nombre, actorRol: 'Jefe directo', tipo: 'estado', mensaje: comentario || undefined }]
    } : s));
    return { ok: true };
  };

  const rechazar = async (solicitud, comentario) => {
    if (source === 'api' && solicitud.backendId) {
      try {
        await Api.rejectArea(solicitud.backendId, comentario);
        await loadFromApi();
        return { ok: true };
      } catch (e) { return { ok: false, error: e }; }
    }
    setSolicitudes((prev) => prev.map((s) => s.id === solicitud.id ? {
      ...s, estadoActual: 'rechazada',
      eventos: [...s.eventos, { id: `e${Date.now()}`, estado: 'rechazada', fecha: new Date().toISOString().slice(0, 16).replace('T', ' '),
        actor: USUARIOS.aprobador.nombre, actorRol: 'Jefe directo', tipo: 'estado', mensaje: comentario }]
    } : s));
    return { ok: true };
  };

  const solicitarCambios = async (solicitud, comentario) => {
    setSolicitudes((prev) => prev.map((s) => s.id === solicitud.id ? {
      ...s, eventos: [...s.eventos, { id: `e${Date.now()}`, fecha: new Date().toISOString().slice(0, 16).replace('T', ' '),
        actor: USUARIOS.aprobador.nombre, actorRol: 'Jefe directo', tipo: 'comentario', mensaje: comentario }]
    } : s));
    return { ok: true };
  };

  const crearSolicitud = async (form) => {
    if (source === 'api') {
      try {
        // Resolver string ids del frontend → numeric ids del backend.
        const empresaObj = empresas.find((e) => e.id === form.empresa);
        const ccs = centros[form.empresa] || [];
        const ccObj = ccs.find((c) => c.id === form.centroCosto);

        if (!empresaObj?.backendId) {
          return { ok: false, error: { message: `Empresa "${form.empresa}" no resuelta a backend ID.` } };
        }
        if (!ccObj?.backendId) {
          return { ok: false, error: { message: `Centro de costo "${form.centroCosto}" no resuelto.` } };
        }

        // Items: el form ya viene con `itemId` real (del picker del catálogo).
        // Si alguno no tiene itemId (no fue seleccionado del catálogo ni creado
        // como nuevo), rebota con error claro.
        const items = (form.items || []).filter((it) => it.itemId);
        const sinItemId = (form.items || []).filter((it) => !it.itemId);
        if (sinItemId.length > 0) {
          return {
            ok: false,
            error: { message: `Hay ${sinItemId.length} item(s) sin seleccionar del catálogo. Usá el buscador o creá un item nuevo.` },
          };
        }
        if (items.length === 0) {
          return { ok: false, error: { message: 'Agregá al menos un item desde el catálogo.' } };
        }

        const lineas = items.map((it) => ({
          item_id: it.itemId,
          cantidad: it.cantidad || 1,
          especificacion: (it.especificacion || '').trim() || null,
        }));

        const payload = {
          empresa_id: empresaObj.backendId,
          centro_costo_id: ccObj.backendId,
          tipo: form.tipo === 'servicios' ? 'SERVICIO' : 'BIEN',
          urgencia: URGENCIA_FRONTEND[form.urgencia] || 'NORMAL',
          descripcion: form.descripcion,
          justificacion: form.justificacion || null,
          fecha_requerida: form.fechaRequerida,
          lineas,
        };

        const created = await Api.createSolicitud(payload);
        await Api.submit(created.id, 'Enviada desde Acquira');
        await loadFromApi();
        return { ok: true, id: created.numero };
      } catch (e) { return { ok: false, error: e }; }
    }
    const id = `SOL-2026-${String(170 + solicitudes.length).padStart(4, '0')}`;
    const nueva = {
      id, ...form,
      estadoActual: 'revision',
      fechaSolicitud: new Date().toISOString().slice(0, 10),
      urgencia: form.urgencia || 'media',
      fechaRequerida: form.fechaRequerida || '2026-05-15',
      solicitante: USUARIOS.solicitante,
      eventos: [
        { id: 'e1', estado: 'solicitada', fecha: new Date().toISOString().slice(0, 16).replace('T', ' '), actor: USUARIOS.solicitante.nombre, actorRol: 'Solicitante', tipo: 'estado' },
        { id: 'e2', estado: 'revision', fecha: new Date().toISOString().slice(0, 16).replace('T', ' '), actor: 'Sistema', actorRol: 'Sistema', tipo: 'estado' },
      ],
    };
    setSolicitudes([nueva, ...solicitudes]);
    return { ok: true, id };
  };

  return {
    solicitudes, empresas, centros, loading, error, conn,
    refresh, aprobar, rechazar, solicitarCambios, crearSolicitud,
  };
};

window.useDataSource = useDataSource;
