// Datos mock del sistema de solicitudes de pedido

const EMPRESAS = [
  { id: 'tcl', nombre: 'Transportes Cordillera Ltda.', rut: '76.432.198-K', rubro: 'Transporte de material para minería', abrev: 'TCL' },
  { id: 'spm', nombre: 'Servicios Portuarios Mejillones S.A.', rut: '99.123.456-2', rubro: 'Servicios de amarra y desamarra', abrev: 'SPM' },
];

const TIPOS_COMPRA = [
  { id: 'insumos', label: 'Insumos', desc: 'Repuestos, consumibles, materiales' },
  { id: 'activos', label: 'Activos fijos', desc: 'Equipos, maquinaria, mobiliario' },
  { id: 'mant_correctiva', label: 'Mantención correctiva', desc: 'Reparación por falla' },
  { id: 'mant_preventiva', label: 'Mantención preventiva', desc: 'Mantenimiento programado' },
  { id: 'servicios', label: 'Otros servicios', desc: 'Asesorías, externalizaciones' },
];

// Centros de costo con presupuesto y monto YTD (en CLP)
const CENTROS_COSTO = {
  tcl: [
    { id: 'cc-tcl-ant', codigo: 'CC-101', nombre: 'Antucoya', proyecto: 'Operación minera', presupuestoAnual: 480000000, gastoYtd: 168400000 },
    { id: 'cc-tcl-cen', codigo: 'CC-102', nombre: 'Centinela', proyecto: 'Operación minera', presupuestoAnual: 520000000, gastoYtd: 220300000 },
    { id: 'cc-tcl-tgn', codigo: 'CC-103', nombre: 'TGN', proyecto: 'Terminal Graneles del Norte', presupuestoAnual: 290000000, gastoYtd: 142100000 },
    { id: 'cc-tcl-ops', codigo: 'CC-001', nombre: 'Operaciones', proyecto: 'Administración central', presupuestoAnual: 120000000, gastoYtd: 38500000 },
    { id: 'cc-tcl-rrhh', codigo: 'CC-002', nombre: 'RRHH', proyecto: 'Administración central', presupuestoAnual: 60000000, gastoYtd: 14200000 },
  ],
  spm: [
    { id: 'cc-spm-mej', codigo: 'CC-201', nombre: 'Mejillones', proyecto: 'Puerto principal', presupuestoAnual: 360000000, gastoYtd: 198700000 },
    { id: 'cc-spm-oxi', codigo: 'CC-202', nombre: 'OXIQUIM', proyecto: 'Terminal químico', presupuestoAnual: 240000000, gastoYtd: 89400000 },
    { id: 'cc-spm-ops', codigo: 'CC-001', nombre: 'Operaciones', proyecto: 'Administración central', presupuestoAnual: 90000000, gastoYtd: 22100000 },
    { id: 'cc-spm-rrhh', codigo: 'CC-002', nombre: 'RRHH', proyecto: 'Administración central', presupuestoAnual: 48000000, gastoYtd: 11000000 },
  ],
};

const ESTADOS = [
  { id: 'borrador', label: 'Borrador', icon: 'edit', desc: 'Solicitud en edición' },
  { id: 'solicitada', label: 'Solicitada', icon: 'send', desc: 'Enviada para revisión' },
  { id: 'revision', label: 'En revisión', icon: 'eye', desc: 'Validación por jefe directo' },
  { id: 'aprobada', label: 'Aprobada', icon: 'check', desc: 'Aprobada por gerencia' },
  { id: 'cotizada', label: 'Cotizada', icon: 'tag', desc: 'Cotizaciones recibidas' },
  { id: 'oc', label: 'OC Generada', icon: 'doc', desc: 'Orden de compra emitida' },
  { id: 'transito', label: 'En tránsito', icon: 'truck', desc: 'En camino' },
  { id: 'recibida', label: 'Recibida', icon: 'package', desc: 'Recepción conforme' },
  { id: 'facturada', label: 'Facturada', icon: 'invoice', desc: 'Factura emitida' },
  { id: 'rechazada', label: 'Rechazada', icon: 'x', desc: 'Rechazada por aprobador' },
];

// Roles del sistema
const ROLES = [
  { id: 'solicitante', label: 'Solicitante', desc: 'Crea solicitudes y hace seguimiento', icon: 'edit' },
  { id: 'aprobador', label: 'Jefe directo', desc: 'Aprueba o rechaza solicitudes del equipo', icon: 'check' },
];

// Usuarios mock
const USUARIOS = {
  solicitante: { nombre: 'Carolina Pérez', cargo: 'Jefa de Operaciones', avatar: 'CP', email: 'cperez@holding-norte.cl' },
  aprobador: { nombre: 'Marco Riquelme', cargo: 'Gerente de Área — Operaciones', avatar: 'MR', email: 'mriquelme@holding-norte.cl' },
};

// Urgencia: alta / media / baja
// Solicitudes mock
const SOLICITUDES_MOCK = [
  {
    id: 'SOL-2026-0142',
    titulo: 'Repuestos de frenos para camión Kenworth T800',
    empresa: 'tcl', tipo: 'mant_correctiva', centroCosto: 'cc-tcl-ant',
    descripcion: 'Se detectó desgaste anormal en el sistema de frenos del camión TLD-2398 durante inspección de ruta. Requiere reemplazo urgente para mantener disponibilidad en faena Antucoya.',
    items: [
      { id: 1, descripcion: 'Pastillas de freno delanteras Kenworth T800', cantidad: 4, unidad: 'unidad', precioUnit: 185000 },
      { id: 2, descripcion: 'Discos de freno traseros', cantidad: 2, unidad: 'unidad', precioUnit: 320000 },
      { id: 3, descripcion: 'Líquido de frenos DOT 4', cantidad: 5, unidad: 'litros', precioUnit: 12000 },
    ],
    adjuntos: [
      { nombre: 'Inspeccion_TLD2398.pdf', tipo: 'pdf', tamano: '2.4 MB' },
      { nombre: 'Foto_pastillas.jpg', tipo: 'img', tamano: '1.1 MB' },
    ],
    estadoActual: 'transito',
    fechaSolicitud: '2026-04-18',
    fechaRequerida: '2026-04-25',
    urgencia: 'alta',
    montoEstimado: 1440000,
    solicitante: { nombre: 'Carolina Pérez', cargo: 'Jefa de Operaciones', avatar: 'CP' },
    eventos: [
      { id: 'e1', estado: 'solicitada', fecha: '2026-04-18 09:42', actor: 'Carolina Pérez', actorRol: 'Solicitante', tipo: 'estado' },
      { id: 'e2', estado: 'revision', fecha: '2026-04-18 11:15', actor: 'Marco Riquelme', actorRol: 'Jefe directo', tipo: 'estado' },
      { id: 'e3', fecha: '2026-04-18 14:02', actor: 'Marco Riquelme', actorRol: 'Jefe directo', tipo: 'comentario', mensaje: '¿Tienes confirmación de que el TLD-2398 está fuera de servicio? Necesito el reporte del taller para aprobar.' },
      { id: 'e4', fecha: '2026-04-18 14:38', actor: 'Carolina Pérez', actorRol: 'Solicitante', tipo: 'comentario', mensaje: 'Sí, adjunté el informe de inspección. El camión está detenido desde ayer en faena.' },
      { id: 'e5', estado: 'aprobada', fecha: '2026-04-19 08:30', actor: 'Marco Riquelme', actorRol: 'Jefe directo', tipo: 'estado', mensaje: 'Aprobado. Priorizar despacho.' },
      { id: 'e6', estado: 'cotizada', fecha: '2026-04-21 16:20', actor: 'Daniel Soto', actorRol: 'Comprador', tipo: 'estado' },
      { id: 'e7', estado: 'oc', fecha: '2026-04-22 10:05', actor: 'Daniel Soto', actorRol: 'Comprador', tipo: 'estado', mensaje: 'OC-2026-0891 emitida a proveedor Repuestos del Norte SpA.' },
      { id: 'e8', estado: 'transito', fecha: '2026-04-24 09:15', actor: 'Daniel Soto', actorRol: 'Comprador', tipo: 'estado', mensaje: 'Despacho confirmado. Llegada estimada 26-04.' },
    ],
  },
  {
    id: 'SOL-2026-0151',
    titulo: 'Notebook Dell Latitude para nuevo coordinador',
    empresa: 'tcl', tipo: 'activos', centroCosto: 'cc-tcl-ops',
    descripcion: 'Equipamiento para nuevo coordinador de flota que ingresa el 02-05.',
    items: [
      { id: 1, descripcion: 'Notebook Dell Latitude 5450 i7 16GB', cantidad: 1, unidad: 'unidad', precioUnit: 1290000 },
      { id: 2, descripcion: 'Mouse inalámbrico Logitech', cantidad: 1, unidad: 'unidad', precioUnit: 35000 },
    ],
    adjuntos: [],
    estadoActual: 'revision',
    fechaSolicitud: '2026-04-23',
    fechaRequerida: '2026-05-02',
    urgencia: 'media',
    montoEstimado: 1325000,
    solicitante: { nombre: 'Carolina Pérez', cargo: 'Jefa de Operaciones', avatar: 'CP' },
    eventos: [
      { id: 'e1', estado: 'solicitada', fecha: '2026-04-23 16:45', actor: 'Carolina Pérez', actorRol: 'Solicitante', tipo: 'estado' },
      { id: 'e2', estado: 'revision', fecha: '2026-04-24 09:30', actor: 'Marco Riquelme', actorRol: 'Jefe directo', tipo: 'estado' },
      { id: 'e3', fecha: '2026-04-24 11:15', actor: 'Marco Riquelme', actorRol: 'Jefe directo', tipo: 'comentario', mensaje: '¿Esta persona ya está formalmente contratada? Necesito copia del contrato antes de pasarlo a finanzas.' },
    ],
  },
  // ── PENDIENTES DE APROBACIÓN (bandeja del jefe directo) ──
  {
    id: 'SOL-2026-0163',
    titulo: 'Reemplazo neumáticos camión TLD-1820 — urgente',
    empresa: 'tcl', tipo: 'mant_correctiva', centroCosto: 'cc-tcl-cen',
    descripcion: 'Camión TLD-1820 detenido en ruta Centinela por desgaste extremo de neumáticos traseros. Requiere reemplazo inmediato para volver a operación. La detención afecta cumplimiento de viajes programados.',
    items: [
      { id: 1, descripcion: 'Neumático Michelin XDA2 315/80R22.5', cantidad: 4, unidad: 'unidad', precioUnit: 720000 },
      { id: 2, descripcion: 'Servicio de montaje y balanceo', cantidad: 1, unidad: 'servicio', precioUnit: 180000 },
    ],
    adjuntos: [
      { nombre: 'Foto_neumaticos.jpg', tipo: 'img', tamano: '2.1 MB' },
      { nombre: 'Reporte_inspeccion.pdf', tipo: 'pdf', tamano: '780 KB' },
    ],
    estadoActual: 'revision',
    fechaSolicitud: '2026-04-26',
    fechaRequerida: '2026-04-28',
    urgencia: 'alta',
    montoEstimado: 3060000,
    solicitante: { nombre: 'Carolina Pérez', cargo: 'Jefa de Operaciones', avatar: 'CP' },
    eventos: [
      { id: 'e1', estado: 'solicitada', fecha: '2026-04-26 08:15', actor: 'Carolina Pérez', actorRol: 'Solicitante', tipo: 'estado' },
      { id: 'e2', estado: 'revision', fecha: '2026-04-26 09:00', actor: 'Sistema', actorRol: 'Sistema', tipo: 'estado', mensaje: 'Asignada a Marco Riquelme para revisión.' },
    ],
  },
  {
    id: 'SOL-2026-0164',
    titulo: 'EPP trimestral cuadrilla Mejillones',
    empresa: 'spm', tipo: 'insumos', centroCosto: 'cc-spm-mej',
    descripcion: 'Reposición trimestral de elementos de protección personal para cuadrilla de amarradores Mejillones. Stock de cascos y guantes al mínimo.',
    items: [
      { id: 1, descripcion: 'Casco de seguridad clase E con barboquejo', cantidad: 24, unidad: 'unidad', precioUnit: 28000 },
      { id: 2, descripcion: 'Guantes nitrilo de alta resistencia', cantidad: 60, unidad: 'unidad', precioUnit: 8500 },
      { id: 3, descripcion: 'Lentes de seguridad antiempañantes', cantidad: 30, unidad: 'unidad', precioUnit: 6500 },
      { id: 4, descripcion: 'Chaleco reflectante clase 2', cantidad: 20, unidad: 'unidad', precioUnit: 14000 },
    ],
    adjuntos: [
      { nombre: 'Stock_EPP_actual.xlsx', tipo: 'xls', tamano: '210 KB' },
    ],
    estadoActual: 'revision',
    fechaSolicitud: '2026-04-25',
    fechaRequerida: '2026-05-10',
    urgencia: 'media',
    montoEstimado: 1657000,
    solicitante: { nombre: 'Carolina Pérez', cargo: 'Jefa de Operaciones', avatar: 'CP' },
    eventos: [
      { id: 'e1', estado: 'solicitada', fecha: '2026-04-25 14:20', actor: 'Carolina Pérez', actorRol: 'Solicitante', tipo: 'estado' },
      { id: 'e2', estado: 'revision', fecha: '2026-04-25 14:21', actor: 'Sistema', actorRol: 'Sistema', tipo: 'estado' },
    ],
  },
  {
    id: 'SOL-2026-0165',
    titulo: 'Capacitación operadores grúa horquilla',
    empresa: 'spm', tipo: 'servicios', centroCosto: 'cc-spm-rrhh',
    descripcion: 'Renovación de licencia interna de operadores de grúa horquilla. 8 personas requieren recertificación antes del 31-05.',
    items: [
      { id: 1, descripcion: 'Curso recertificación grúa horquilla — 8 personas', cantidad: 1, unidad: 'servicio', precioUnit: 1280000 },
    ],
    adjuntos: [
      { nombre: 'Cotizacion_OTEC_Norte.pdf', tipo: 'pdf', tamano: '450 KB' },
    ],
    estadoActual: 'revision',
    fechaSolicitud: '2026-04-24',
    fechaRequerida: '2026-05-25',
    urgencia: 'baja',
    montoEstimado: 1280000,
    solicitante: { nombre: 'Carolina Pérez', cargo: 'Jefa de Operaciones', avatar: 'CP' },
    eventos: [
      { id: 'e1', estado: 'solicitada', fecha: '2026-04-24 10:00', actor: 'Carolina Pérez', actorRol: 'Solicitante', tipo: 'estado' },
      { id: 'e2', estado: 'revision', fecha: '2026-04-24 10:01', actor: 'Sistema', actorRol: 'Sistema', tipo: 'estado' },
    ],
  },
  {
    id: 'SOL-2026-0166',
    titulo: 'Reparación motor de winche — Mejillones',
    empresa: 'spm', tipo: 'mant_correctiva', centroCosto: 'cc-spm-mej',
    descripcion: 'Falla en motor del winche hidráulico W-04. Diagnóstico de taller indica necesidad de cambio de bomba y sellos. Equipo crítico para operación de amarra.',
    items: [
      { id: 1, descripcion: 'Bomba hidráulica Parker P350', cantidad: 1, unidad: 'unidad', precioUnit: 4200000 },
      { id: 2, descripcion: 'Kit sellos hidráulicos', cantidad: 1, unidad: 'unidad', precioUnit: 380000 },
      { id: 3, descripcion: 'Mano de obra especialista', cantidad: 16, unidad: 'hora', precioUnit: 65000 },
    ],
    adjuntos: [
      { nombre: 'Diagnostico_winche.pdf', tipo: 'pdf', tamano: '1.8 MB' },
      { nombre: 'Cotizacion_servicio.pdf', tipo: 'pdf', tamano: '620 KB' },
    ],
    estadoActual: 'revision',
    fechaSolicitud: '2026-04-26',
    fechaRequerida: '2026-04-30',
    urgencia: 'alta',
    montoEstimado: 5620000,
    solicitante: { nombre: 'Roberto Lagos', cargo: 'Supervisor de Operaciones SPM', avatar: 'RL' },
    eventos: [
      { id: 'e1', estado: 'solicitada', fecha: '2026-04-26 11:30', actor: 'Roberto Lagos', actorRol: 'Solicitante', tipo: 'estado' },
      { id: 'e2', estado: 'revision', fecha: '2026-04-26 11:31', actor: 'Sistema', actorRol: 'Sistema', tipo: 'estado' },
    ],
  },
  {
    id: 'SOL-2026-0167',
    titulo: 'Combustible diésel — flota TGN abril',
    empresa: 'tcl', tipo: 'insumos', centroCosto: 'cc-tcl-tgn',
    descripcion: 'Reposición mensual de combustible para flota TGN. Consumo estimado según despachos programados última semana abril.',
    items: [
      { id: 1, descripcion: 'Diésel B5 — abastecimiento estanque TGN', cantidad: 8000, unidad: 'litros', precioUnit: 1180 },
    ],
    adjuntos: [
      { nombre: 'Cotizacion_Copec.pdf', tipo: 'pdf', tamano: '380 KB' },
    ],
    estadoActual: 'revision',
    fechaSolicitud: '2026-04-25',
    fechaRequerida: '2026-04-29',
    urgencia: 'media',
    montoEstimado: 9440000,
    solicitante: { nombre: 'Carolina Pérez', cargo: 'Jefa de Operaciones', avatar: 'CP' },
    eventos: [
      { id: 'e1', estado: 'solicitada', fecha: '2026-04-25 09:00', actor: 'Carolina Pérez', actorRol: 'Solicitante', tipo: 'estado' },
      { id: 'e2', estado: 'revision', fecha: '2026-04-25 09:01', actor: 'Sistema', actorRol: 'Sistema', tipo: 'estado' },
    ],
  },
  // ── PROCESADAS POR EL APROBADOR (histórico) ──
  {
    id: 'SOL-2026-0138',
    titulo: 'Cabos de amarra Ø 80mm — reposición Mejillones',
    empresa: 'spm', tipo: 'insumos', centroCosto: 'cc-spm-mej',
    descripcion: 'Reposición trimestral de cabos de amarra para faena Mejillones. Stock actual al 20%.',
    items: [
      { id: 1, descripcion: 'Cabo polipropileno Ø 80mm x 220m', cantidad: 6, unidad: 'unidad', precioUnit: 1850000 },
      { id: 2, descripcion: 'Defensas neumáticas Yokohama 2.0m', cantidad: 2, unidad: 'unidad', precioUnit: 3400000 },
    ],
    adjuntos: [{ nombre: 'Stock_actual_mejillones.xlsx', tipo: 'xls', tamano: '340 KB' }],
    estadoActual: 'aprobada',
    fechaSolicitud: '2026-04-15',
    fechaRequerida: '2026-05-01',
    urgencia: 'media',
    montoEstimado: 17900000,
    solicitante: { nombre: 'Carolina Pérez', cargo: 'Jefa de Operaciones', avatar: 'CP' },
    eventos: [
      { id: 'e1', estado: 'solicitada', fecha: '2026-04-15 10:20', actor: 'Carolina Pérez', actorRol: 'Solicitante', tipo: 'estado' },
      { id: 'e2', estado: 'revision', fecha: '2026-04-15 14:00', actor: 'Marco Riquelme', actorRol: 'Jefe directo', tipo: 'estado' },
      { id: 'e3', estado: 'aprobada', fecha: '2026-04-16 09:10', actor: 'Marco Riquelme', actorRol: 'Jefe directo', tipo: 'estado', mensaje: 'Aprobada. Stock está crítico.' },
    ],
  },
  {
    id: 'SOL-2026-0156',
    titulo: 'Compra de impresora multifuncional oficina TGN',
    empresa: 'tcl', tipo: 'activos', centroCosto: 'cc-tcl-tgn',
    descripcion: 'Reemplazo de impresora actual con falla recurrente.',
    items: [
      { id: 1, descripcion: 'Impresora multifuncional HP LaserJet Pro', cantidad: 1, unidad: 'unidad', precioUnit: 580000 },
    ],
    adjuntos: [],
    estadoActual: 'rechazada',
    fechaSolicitud: '2026-04-20',
    fechaRequerida: '2026-05-05',
    urgencia: 'baja',
    montoEstimado: 580000,
    solicitante: { nombre: 'Carolina Pérez', cargo: 'Jefa de Operaciones', avatar: 'CP' },
    eventos: [
      { id: 'e1', estado: 'solicitada', fecha: '2026-04-20 11:00', actor: 'Carolina Pérez', actorRol: 'Solicitante', tipo: 'estado' },
      { id: 'e2', estado: 'revision', fecha: '2026-04-20 11:01', actor: 'Sistema', actorRol: 'Sistema', tipo: 'estado' },
      { id: 'e3', estado: 'rechazada', fecha: '2026-04-21 15:30', actor: 'Marco Riquelme', actorRol: 'Jefe directo', tipo: 'estado', mensaje: 'La impresora actual aún tiene contrato de mantención vigente. Coordinar con TI revisión técnica antes de reemplazar.' },
    ],
  },
  {
    id: 'SOL-2026-0129',
    titulo: 'Aceite hidráulico Shell Tellus S2 — bodega TGN',
    empresa: 'tcl', tipo: 'insumos', centroCosto: 'cc-tcl-tgn',
    descripcion: 'Reposición de aceite hidráulico para flota de camiones tolva en TGN.',
    items: [{ id: 1, descripcion: 'Aceite hidráulico Shell Tellus S2 V46 — tambor 200L', cantidad: 4, unidad: 'tambor', precioUnit: 480000 }],
    adjuntos: [{ nombre: 'Cotizacion_shell.pdf', tipo: 'pdf', tamano: '1.2 MB' }],
    estadoActual: 'facturada',
    fechaSolicitud: '2026-03-28',
    fechaRequerida: '2026-04-10',
    urgencia: 'media',
    montoEstimado: 1920000,
    solicitante: { nombre: 'Carolina Pérez', cargo: 'Jefa de Operaciones', avatar: 'CP' },
    eventos: [
      { id: 'e1', estado: 'solicitada', fecha: '2026-03-28 11:00', actor: 'Carolina Pérez', actorRol: 'Solicitante', tipo: 'estado' },
      { id: 'e2', estado: 'revision', fecha: '2026-03-28 15:00', actor: 'Marco Riquelme', actorRol: 'Jefe directo', tipo: 'estado' },
      { id: 'e3', estado: 'aprobada', fecha: '2026-03-30 10:20', actor: 'Marco Riquelme', actorRol: 'Jefe directo', tipo: 'estado' },
      { id: 'e4', estado: 'cotizada', fecha: '2026-04-01 09:00', actor: 'Daniel Soto', actorRol: 'Comprador', tipo: 'estado' },
      { id: 'e5', estado: 'oc', fecha: '2026-04-02 14:30', actor: 'Daniel Soto', actorRol: 'Comprador', tipo: 'estado' },
      { id: 'e6', estado: 'transito', fecha: '2026-04-05 08:00', actor: 'Daniel Soto', actorRol: 'Comprador', tipo: 'estado' },
      { id: 'e7', estado: 'recibida', fecha: '2026-04-08 16:45', actor: 'Bodeguero TGN', actorRol: 'Bodega', tipo: 'estado', mensaje: 'Recepción conforme. 4 tambores en bodega.' },
      { id: 'e8', estado: 'facturada', fecha: '2026-04-12 11:20', actor: 'Sistema', actorRol: 'Facturación', tipo: 'estado', mensaje: 'Factura N° 458231 conciliada con OC-2026-0824.' },
    ],
  },
  {
    id: 'SOL-2026-0155',
    titulo: 'Mantención preventiva grúa horquilla Mejillones',
    empresa: 'spm', tipo: 'mant_preventiva', centroCosto: 'cc-spm-mej',
    descripcion: 'Mantención de las 2.000 horas para grúa horquilla Hyster H80FT.',
    items: [{ id: 1, descripcion: 'Servicio mantención preventiva 2.000h', cantidad: 1, unidad: 'servicio', precioUnit: 980000 }],
    adjuntos: [{ nombre: 'Pauta_mantencion.pdf', tipo: 'pdf', tamano: '890 KB' }],
    estadoActual: 'borrador',
    fechaSolicitud: '2026-04-25',
    fechaRequerida: '2026-05-15',
    urgencia: 'baja',
    montoEstimado: 980000,
    solicitante: { nombre: 'Carolina Pérez', cargo: 'Jefa de Operaciones', avatar: 'CP' },
    eventos: [],
  },
];

// Helpers
const formatCLP = (n) => new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(n);
const formatCLPCompact = (n) => {
  if (n >= 1000000) return `$${(n / 1000000).toFixed(1).replace('.0', '')}M`;
  if (n >= 1000) return `$${(n / 1000).toFixed(0)}K`;
  return `$${n}`;
};
const diasHasta = (fechaIso) => {
  const ms = new Date(fechaIso) - new Date('2026-04-27');
  return Math.ceil(ms / (1000 * 60 * 60 * 24));
};

Object.assign(window, {
  EMPRESAS, TIPOS_COMPRA, CENTROS_COSTO, ESTADOS, ROLES, USUARIOS, SOLICITUDES_MOCK,
  formatCLP, formatCLPCompact, diasHasta,
});
