// Formulario de nueva solicitud — soporta layouts: stepper, single, two-column

const tiposAdjunto = (nombre) => {
  const ext = nombre.split('.').pop().toLowerCase();
  if (['pdf'].includes(ext)) return 'pdf';
  if (['png', 'jpg', 'jpeg', 'webp'].includes(ext)) return 'img';
  if (['xls', 'xlsx', 'csv'].includes(ext)) return 'xls';
  return 'file';
};

const iconAdjunto = (tipo) => ({ pdf: 'file', img: 'image', xls: 'sheet', file: 'file' })[tipo] || 'file';

// Sección: Empresa + Tipo
const SectionEmpresa = ({ form, set, errors, empresas }) => (
  <div className="form-section">
    <div className="section-head">
      <div className="section-num">1</div>
      <div>
        <h3 className="section-title">Empresa y tipo de compra</h3>
        <p className="section-sub">Indica para qué empresa del holding es la solicitud</p>
      </div>
    </div>
    <Field label="Empresa" required error={errors.empresa}>
      <div className="empresa-cards">
        {empresas.map((e) => (
          <button
            key={e.id}
            type="button"
            className={`empresa-card${form.empresa === e.id ? ' empresa-card-active' : ''}`}
            onClick={() => set({ empresa: e.id, centroCosto: '' })}
          >
            <div className="empresa-card-mark">
              <Icon name="building" size={20} />
            </div>
            <div className="empresa-card-text">
              <div className="empresa-card-name">{e.nombre}</div>
              <div className="empresa-card-meta">{e.rubro} · {e.rut}</div>
            </div>
            <div className="empresa-card-radio">
              {form.empresa === e.id && <div className="empresa-card-radio-dot" />}
            </div>
          </button>
        ))}
      </div>
    </Field>

    <Field label="Tipo de compra" required error={errors.tipo}>
      <div className="tipo-grid">
        {TIPOS_COMPRA.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`tipo-chip${form.tipo === t.id ? ' tipo-chip-active' : ''}`}
            onClick={() => set({ tipo: t.id })}
          >
            <div className="tipo-chip-label">{t.label}</div>
            <div className="tipo-chip-desc">{t.desc}</div>
          </button>
        ))}
      </div>
    </Field>
  </div>
);

const URGENCIA_OPCIONES = [
  { id: 'NORMAL',   label: 'Normal',   desc: 'Se procesa por orden de llegada' },
  { id: 'URGENTE',  label: 'Urgente',  desc: 'Se prioriza sobre solicitudes normales' },
  { id: 'CRITICA',  label: 'Crítica',  desc: 'Bloquea operación — atención inmediata' },
];

// Sección: Detalle (descripción + centro de costo + urgencia)
const SectionDetalle = ({ form, set, errors, centros }) => {
  const ccDisponibles = form.empresa ? (centros[form.empresa] || []) : [];
  return (
    <div className="form-section">
      <div className="section-head">
        <div className="section-num">2</div>
        <div>
          <h3 className="section-title">Detalle de la solicitud</h3>
          <p className="section-sub">Describe la necesidad y asigna el centro de costo</p>
        </div>
      </div>
      <Field label="Título de la solicitud" required error={errors.titulo}>
        <Input
          placeholder="Ej: Repuestos de frenos para camión Kenworth"
          value={form.titulo}
          onChange={(e) => set({ titulo: e.target.value })}
        />
      </Field>
      <Field label="Descripción" required error={errors.descripcion} hint="Indica el contexto y la justificación de la compra">
        <Textarea
          rows={5}
          placeholder="Describe la necesidad, el motivo y cualquier información relevante para la aprobación…"
          value={form.descripcion}
          onChange={(e) => set({ descripcion: e.target.value })}
        />
      </Field>
      <Field label="Centro de costo" required error={errors.centroCosto} hint={!form.empresa ? 'Selecciona primero la empresa' : null}>
        <Select
          value={form.centroCosto}
          onChange={(e) => set({ centroCosto: e.target.value })}
          disabled={!form.empresa}
        >
          <option value="">Seleccionar centro de costo…</option>
          {ccDisponibles.map((c) => (
            <option key={c.id} value={c.id}>{c.codigo} · {c.nombre} — {c.proyecto}</option>
          ))}
        </Select>
      </Field>
      <Field label="Fecha requerida" required error={errors.fechaRequerida} hint="¿Para cuándo se necesita la compra? (mínimo, hoy)">
        <Input
          type="date"
          value={form.fechaRequerida}
          min={new Date().toISOString().slice(0, 10)}
          onChange={(e) => set({ fechaRequerida: e.target.value })}
        />
      </Field>
      <Field label="Urgencia" required hint="Define la prioridad del flujo de aprobación">
        <div className="tipo-grid">
          {URGENCIA_OPCIONES.map((u) => (
            <button
              key={u.id}
              type="button"
              className={`tipo-chip${form.urgenciaBackend === u.id ? ' tipo-chip-active' : ''}`}
              onClick={() => set({ urgenciaBackend: u.id })}
            >
              <div className="tipo-chip-label">{u.label}</div>
              <div className="tipo-chip-desc">{u.desc}</div>
            </button>
          ))}
        </div>
      </Field>
    </div>
  );
};

// Picker inline: input de búsqueda → dropdown con resultados del catálogo
// (filtrados por CC) + opción "+ Crear nuevo item" que dispara el modal.
const ItemPicker = ({ row, ccBackendId, onSelect, onCreateNew }) => {
  const [q, setQ] = React.useState('');
  const [results, setResults] = React.useState([]);
  const [open, setOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const debounceRef = React.useRef(null);

  // Si ya está seleccionado, mostrar el "chip" con SKU + nombre y un ✕.
  if (row.itemId) {
    return (
      <div className="item-selected">
        <span className="item-selected-sku">{row.sku}</span>
        <span className="item-selected-nombre">— {row.nombre}</span>
        <button
          type="button"
          className="item-selected-clear"
          onClick={() => onSelect({ itemId: null, sku: '', nombre: '' })}
          aria-label="Cambiar item"
        >
          <Icon name="x" size={12} />
        </button>
      </div>
    );
  }

  const search = (text) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      if (!text || text.length < 2 || !ccBackendId) {
        setResults([]); return;
      }
      setLoading(true);
      try {
        const items = await Api.searchItems(text, ccBackendId, 10);
        setResults(items || []);
      } catch (_e) {
        setResults([]);
      } finally { setLoading(false); }
    }, 250);
  };

  const tieneQuery = q.trim().length >= 2;
  const sinResultados = tieneQuery && !loading && results.length === 0;

  return (
    <div className="item-picker" onBlur={(e) => {
      // Cerrar el dropdown cuando el foco sale del componente entero
      if (!e.currentTarget.contains(e.relatedTarget)) setTimeout(() => setOpen(false), 150);
    }}>
      <div className="item-picker-input">
        <Icon name="search" size={14} className="item-picker-input-icon" />
        <Input
          placeholder={ccBackendId ? 'Buscar por SKU o nombre…' : 'Selecciona empresa y CC primero'}
          value={q}
          disabled={!ccBackendId}
          onFocus={() => setOpen(true)}
          onChange={(e) => { setQ(e.target.value); search(e.target.value); setOpen(true); }}
        />
      </div>
      {open && ccBackendId && (
        <div className="item-picker-dropdown">
          {!tieneQuery && (
            <div className="item-picker-empty">Escribí al menos 2 caracteres para buscar en el catálogo del CC.</div>
          )}
          {tieneQuery && loading && (
            <div className="item-picker-empty">Buscando…</div>
          )}
          {sinResultados && (
            <div className="item-picker-empty">No hay items que coincidan con “{q}”.</div>
          )}
          {!loading && results.map((it) => (
            <button
              key={it.id}
              type="button"
              className="item-picker-option"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onSelect({ itemId: it.id, sku: it.sku, nombre: it.nombre });
                setOpen(false); setQ('');
              }}
            >
              <span className="item-picker-sku">{it.sku}</span>
              <span className="item-picker-nombre">{it.nombre}</span>
              {it.familia_nombre && <span className="item-picker-fam">{it.familia_nombre}</span>}
            </button>
          ))}
          {tieneQuery && (
            <button
              type="button"
              className="item-picker-create"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => { onCreateNew(q); setOpen(false); }}
            >
              <Icon name="plus" size={14} /> Crear “{q}” como item nuevo en este CC
            </button>
          )}
        </div>
      )}
    </div>
  );
};

// Modal de creación de un nuevo CatalogoItem vinculado al CC actual.
const NuevoItemModal = ({ ccBackendId, ccLabel, initialName, onCreated, onCancel }) => {
  const [familias, setFamilias] = React.useState([]);
  const [form, setForm] = React.useState({
    sku: '',
    nombre: initialName || '',
    familia_id: '',
    unidad_medida: 'UN',
    criticidad: 'ESTANDAR',
    especificacion_tecnica: '',
  });
  const [error, setError] = React.useState(null);
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    Api.familias().then(setFamilias).catch(() => setFamilias([]));
  }, []);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const submit = async () => {
    setError(null);
    if (form.sku.length < 3) return setError('SKU mínimo 3 caracteres.');
    if (form.nombre.length < 3) return setError('Nombre mínimo 3 caracteres.');
    if (!form.familia_id) return setError('Selecciona una familia.');
    setSubmitting(true);
    try {
      const created = await Api.createItem({
        sku: form.sku.trim(),
        nombre: form.nombre.trim(),
        familia_id: parseInt(form.familia_id, 10),
        centro_costo_id: ccBackendId,
        unidad_medida: form.unidad_medida,
        criticidad: form.criticidad,
        especificacion_tecnica: form.especificacion_tecnica.trim() || null,
      });
      onCreated({ itemId: created.id, sku: created.sku, nombre: created.nombre });
    } catch (e) {
      setError(e?.body?.error?.message || e?.message || 'No se pudo crear el item.');
    } finally { setSubmitting(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>Nuevo item del catálogo</h3>
          <button className="modal-close" onClick={onCancel}><Icon name="x" size={16} /></button>
        </div>
        <div className="modal-body">
          <Field label="Centro de costo" hint="Asignación automática">
            <Input value={ccLabel || `CC #${ccBackendId}`} disabled />
          </Field>
          <Field label="SKU" required>
            <Input value={form.sku} placeholder="ITM-..." onChange={(e) => set({ sku: e.target.value })} />
          </Field>
          <Field label="Nombre" required>
            <Input value={form.nombre} onChange={(e) => set({ nombre: e.target.value })} />
          </Field>
          <Field label="Familia" required>
            <Select value={form.familia_id} onChange={(e) => set({ familia_id: e.target.value })}>
              <option value="">Selecciona…</option>
              {familias.map((f) => (
                <option key={f.id} value={f.id}>{'— '.repeat(f.nivel - 1)}{f.nombre}</option>
              ))}
            </Select>
          </Field>
          <Field label="Unidad de medida">
            <Select value={form.unidad_medida} onChange={(e) => set({ unidad_medida: e.target.value })}>
              <option value="UN">UN — Unidad</option>
              <option value="KG">KG — Kilogramo</option>
              <option value="LT">LT — Litro</option>
              <option value="M">M — Metro</option>
              <option value="M2">M2 — Metro cuadrado</option>
              <option value="M3">M3 — Metro cúbico</option>
              <option value="HR">HR — Hora</option>
              <option value="SVC">SVC — Servicio</option>
            </Select>
          </Field>
          <Field label="Criticidad">
            <Select value={form.criticidad} onChange={(e) => set({ criticidad: e.target.value })}>
              <option value="GENERICO">Genérico</option>
              <option value="ESTANDAR">Estándar</option>
              <option value="CRITICO">Crítico</option>
            </Select>
          </Field>
          <Field label="Especificación técnica" hint="Opcional">
            <Textarea
              rows={3}
              value={form.especificacion_tecnica}
              onChange={(e) => set({ especificacion_tecnica: e.target.value })}
            />
          </Field>
          {error && <div className="field-error">{error}</div>}
        </div>
        <div className="modal-actions">
          <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
          <Button variant="primary" onClick={submit} disabled={submitting}>
            {submitting ? 'Creando…' : 'Crear item'}
          </Button>
        </div>
      </div>
    </div>
  );
};

// Sección: Items (con picker inline contra el catálogo del CC actual).
const SectionItems = ({ form, set, errors, ccBackendId, ccLabel }) => {
  const [pickerForRow, setPickerForRow] = React.useState(null); // { rowId, initialName }

  const updateItem = (id, patch) => {
    set({ items: form.items.map((it) => (it.id === id ? { ...it, ...patch } : it)) });
  };
  const addItem = () => {
    const nextId = Math.max(0, ...form.items.map((i) => i.id)) + 1;
    set({
      items: [
        ...form.items,
        { id: nextId, itemId: null, sku: '', nombre: '', cantidad: 1, especificacion: '' },
      ],
    });
  };
  const removeItem = (id) => {
    set({ items: form.items.filter((it) => it.id !== id) });
  };

  return (
    <div className="form-section">
      <div className="section-head">
        <div className="section-num">3</div>
        <div>
          <h3 className="section-title">Items solicitados</h3>
          <p className="section-sub">
            Buscá y selecciona items del catálogo de este CC. Si el item no existe, podés crearlo
            sobre la marcha — quedará vinculado a este CC.
          </p>
        </div>
      </div>
      <div className="items-table">
        <div className="items-head">
          <div>Item del catálogo</div>
          <div>Cantidad</div>
          <div>Especificación</div>
          <div></div>
        </div>
        {form.items.map((it) => (
          <div key={it.id} className="items-row">
            <div className="items-cell">
              <ItemPicker
                row={it}
                ccBackendId={ccBackendId}
                onSelect={(patch) => updateItem(it.id, patch)}
                onCreateNew={(initialName) => setPickerForRow({ rowId: it.id, initialName })}
              />
            </div>
            <div className="items-cell">
              <Input
                type="number"
                min="0.0001"
                step="any"
                value={it.cantidad}
                onChange={(e) => updateItem(it.id, { cantidad: Number(e.target.value) })}
              />
            </div>
            <div className="items-cell">
              <Input
                placeholder="Detalle adicional (opcional)"
                value={it.especificacion}
                onChange={(e) => updateItem(it.id, { especificacion: e.target.value })}
              />
            </div>
            <div className="items-cell items-cell-actions">
              {form.items.length > 1 && (
                <button className="items-remove" onClick={() => removeItem(it.id)} aria-label="Eliminar">
                  <Icon name="trash" size={14} />
                </button>
              )}
            </div>
          </div>
        ))}
        {errors.items && <div className="field-error">{errors.items}</div>}
      </div>
      <button type="button" className="add-item-btn" onClick={addItem}>
        <Icon name="plus" size={14} /> Agregar otro item
      </button>

      {pickerForRow && (
        <NuevoItemModal
          ccBackendId={ccBackendId}
          ccLabel={ccLabel}
          initialName={pickerForRow.initialName}
          onCancel={() => setPickerForRow(null)}
          onCreated={(patch) => {
            updateItem(pickerForRow.rowId, patch);
            setPickerForRow(null);
          }}
        />
      )}
    </div>
  );
};

// Sección: Adjuntos
const SectionAdjuntos = ({ form, set }) => {
  const inputRef = React.useRef(null);
  const [drag, setDrag] = React.useState(false);

  const handleFiles = (files) => {
    const nuevos = Array.from(files).map((f) => ({
      nombre: f.name,
      tipo: tiposAdjunto(f.name),
      tamano: `${(f.size / 1024 / 1024).toFixed(1)} MB`,
      file: f,
    }));
    set({ adjuntos: [...form.adjuntos, ...nuevos] });
  };

  return (
    <div className="form-section">
      <div className="section-head">
        <div className="section-num">4</div>
        <div>
          <h3 className="section-title">Respaldos</h3>
          <p className="section-sub">Adjunta cotizaciones, fotos, fichas técnicas o cualquier documento de respaldo</p>
        </div>
      </div>
      <div
        className={`dropzone${drag ? ' dropzone-active' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); handleFiles(e.dataTransfer.files); }}
        onClick={() => inputRef.current?.click()}
      >
        <Icon name="upload" size={28} />
        <div className="dropzone-title">Arrastra archivos aquí o haz clic para seleccionar</div>
        <div className="dropzone-sub">PDF, imágenes, Excel · hasta 10 MB por archivo</div>
        <input
          ref={inputRef}
          type="file"
          multiple
          style={{ display: 'none' }}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {form.adjuntos.length > 0 && (
        <div className="adjuntos-list">
          {form.adjuntos.map((a, i) => (
            <div key={i} className="adjunto-item">
              <div className={`adjunto-icon adjunto-icon-${a.tipo}`}>
                <Icon name={iconAdjunto(a.tipo)} size={18} />
              </div>
              <div className="adjunto-text">
                <div className="adjunto-nombre">{a.nombre}</div>
                <div className="adjunto-meta">{a.tamano}</div>
              </div>
              <button
                className="adjunto-remove"
                onClick={() => set({ adjuntos: form.adjuntos.filter((_, j) => j !== i) })}
                aria-label="Eliminar"
              >
                <Icon name="x" size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Resumen lateral
const ResumenLateral = ({ form, empresas, centros }) => {
  const empresa = empresas.find((e) => e.id === form.empresa);
  const cc = form.empresa ? (centros[form.empresa] || []).find((c) => c.id === form.centroCosto) : null;
  const tipo = TIPOS_COMPRA.find((t) => t.id === form.tipo);
  const completitud = (() => {
    let n = 0, total = 5;
    if (form.empresa) n++;
    if (form.tipo) n++;
    if (form.titulo && form.descripcion) n++;
    if (form.centroCosto) n++;
    if (form.items.some((i) => i.itemId)) n++;
    return Math.round((n / total) * 100);
  })();

  return (
    <div className="resumen">
      <div className="resumen-head">
        <span>Resumen</span>
        <span className="resumen-pct">{completitud}%</span>
      </div>
      <div className="resumen-bar">
        <div className="resumen-bar-fill" style={{ width: `${completitud}%` }} />
      </div>
      <dl className="resumen-list">
        <div className="resumen-item">
          <dt>Empresa</dt>
          <dd>{empresa ? empresa.abrev : <span className="resumen-empty">—</span>}</dd>
        </div>
        <div className="resumen-item">
          <dt>Tipo</dt>
          <dd>{tipo ? tipo.label : <span className="resumen-empty">—</span>}</dd>
        </div>
        <div className="resumen-item">
          <dt>Centro costo</dt>
          <dd>{cc ? cc.nombre : <span className="resumen-empty">—</span>}</dd>
        </div>
        <div className="resumen-item">
          <dt>Items</dt>
          <dd>{form.items.filter((i) => i.itemId).length || <span className="resumen-empty">—</span>}</dd>
        </div>
        <div className="resumen-item">
          <dt>Adjuntos</dt>
          <dd>{form.adjuntos.length || <span className="resumen-empty">—</span>}</dd>
        </div>
      </dl>
      <div className="resumen-footer">
        <Icon name="info" size={14} />
        <span>Tu solicitud pasará por 3 niveles de aprobación: jefe directo, finanzas y gerencia.</span>
      </div>
    </div>
  );
};

const NuevaSolicitud = ({ layout = 'twocol', onSubmit, onCancel, empresas: empresasProp, centros: centrosProp }) => {
  // Si data-source nos pasó empresas/centros del API, usamos esos.
  // Caso contrario fallback al mock para que el preview off-line siga funcionando.
  const empresas = (empresasProp && empresasProp.length) ? empresasProp : EMPRESAS;
  const centros = (centrosProp && Object.keys(centrosProp).length) ? centrosProp : CENTROS_COSTO;

  const [form, setForm] = React.useState({
    empresa: '', tipo: '', titulo: '', descripcion: '', centroCosto: '',
    fechaRequerida: '',
    urgenciaBackend: 'NORMAL',
    // items: cada uno tiene `itemId` (backend id, asignado por el picker) o
    // null mientras no se haya seleccionado/creado.
    items: [{ id: 1, itemId: null, sku: '', nombre: '', cantidad: 1, especificacion: '' }],
    adjuntos: [],
  });

  // Resolución del CC actual a sus datos de backend, para pasar al SectionItems.
  const ccsDelEmpresa = form.empresa ? (centros[form.empresa] || []) : [];
  const ccObj = ccsDelEmpresa.find((c) => c.id === form.centroCosto);
  const ccBackendId = ccObj?.backendId;
  const ccLabel = ccObj ? `${ccObj.codigo} · ${ccObj.nombre}` : null;
  const [errors, setErrors] = React.useState({});
  const [step, setStep] = React.useState(0);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const validate = () => {
    const e = {};
    if (!form.empresa) e.empresa = 'Selecciona una empresa';
    if (!form.tipo) e.tipo = 'Selecciona el tipo de compra';
    if (!form.titulo.trim()) e.titulo = 'Agrega un título';
    if (!form.descripcion.trim()) e.descripcion = 'Agrega una descripción';
    else if (form.descripcion.trim().length < 10) e.descripcion = 'La descripción debe tener al menos 10 caracteres';
    if (!form.centroCosto) e.centroCosto = 'Selecciona un centro de costo';
    if (!form.fechaRequerida) e.fechaRequerida = 'Indica para cuándo se necesita';
    else if (form.fechaRequerida < new Date().toISOString().slice(0, 10)) {
      e.fechaRequerida = 'La fecha no puede ser anterior a hoy';
    }
    const itemsValidos = form.items.filter((i) => i.itemId);
    if (itemsValidos.length === 0) {
      e.items = 'Agrega al menos un item del catálogo (o creá uno nuevo)';
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const submit = () => {
    if (validate()) onSubmit(form);
  };

  // ── Single-page layout
  if (layout === 'single') {
    return (
      <div className="form-container form-single">
        <SectionEmpresa form={form} set={set} errors={errors} empresas={empresas} />
        <SectionDetalle form={form} set={set} errors={errors} centros={centros} />
        <SectionItems form={form} set={set} errors={errors} ccBackendId={ccBackendId} ccLabel={ccLabel} />
        <SectionAdjuntos form={form} set={set} />
        <div className="form-actions">
          <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
          <div className="form-actions-right">
            <Button variant="secondary">Guardar borrador</Button>
            <Button variant="primary" icon="send" onClick={submit}>Enviar solicitud</Button>
          </div>
        </div>
      </div>
    );
  }

  // ── Two-column layout
  if (layout === 'twocol') {
    return (
      <div className="form-container form-twocol">
        <div className="form-twocol-main">
          <SectionEmpresa form={form} set={set} errors={errors} empresas={empresas} />
          <SectionDetalle form={form} set={set} errors={errors} centros={centros} />
          <SectionItems form={form} set={set} errors={errors} ccBackendId={ccBackendId} ccLabel={ccLabel} />
          <SectionAdjuntos form={form} set={set} />
          <div className="form-actions">
            <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
            <div className="form-actions-right">
              <Button variant="secondary">Guardar borrador</Button>
              <Button variant="primary" icon="send" onClick={submit}>Enviar solicitud</Button>
            </div>
          </div>
        </div>
        <aside className="form-twocol-side">
          <ResumenLateral form={form} empresas={empresas} centros={centros} />
        </aside>
      </div>
    );
  }

  // ── Wizard (stepper)
  const steps = [
    { label: 'Empresa', component: <SectionEmpresa form={form} set={set} errors={errors} empresas={empresas} /> },
    { label: 'Detalle', component: <SectionDetalle form={form} set={set} errors={errors} centros={centros} /> },
    { label: 'Items', component: <SectionItems form={form} set={set} errors={errors} ccBackendId={ccBackendId} ccLabel={ccLabel} /> },
    { label: 'Respaldos', component: <SectionAdjuntos form={form} set={set} /> },
  ];

  return (
    <div className="form-container form-wizard">
      <div className="wizard-stepper">
        {steps.map((s, i) => (
          <div key={i} className={`wizard-step${i === step ? ' wizard-step-active' : ''}${i < step ? ' wizard-step-done' : ''}`}>
            <div className="wizard-step-num">{i < step ? <Icon name="check" size={14} /> : i + 1}</div>
            <div className="wizard-step-label">{s.label}</div>
            {i < steps.length - 1 && <div className="wizard-step-line" />}
          </div>
        ))}
      </div>
      <div className="wizard-content">
        {steps[step].component}
      </div>
      <div className="form-actions">
        <Button variant="ghost" onClick={step === 0 ? onCancel : () => setStep(step - 1)}>
          {step === 0 ? 'Cancelar' : '← Anterior'}
        </Button>
        <div className="form-actions-right">
          {step < steps.length - 1 ? (
            <Button variant="primary" onClick={() => setStep(step + 1)}>Siguiente →</Button>
          ) : (
            <>
              <Button variant="secondary">Guardar borrador</Button>
              <Button variant="primary" icon="send" onClick={submit}>Enviar solicitud</Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

window.NuevaSolicitud = NuevaSolicitud;
