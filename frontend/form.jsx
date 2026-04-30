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
const SectionEmpresa = ({ form, set, errors }) => (
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
        {EMPRESAS.map((e) => (
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

// Sección: Detalle (descripción + centro de costo)
const SectionDetalle = ({ form, set, errors }) => {
  const ccDisponibles = form.empresa ? CENTROS_COSTO[form.empresa] : [];
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
      <Field label="Descripción" required error={errors.descripcion} hint="Indica el contexto, urgencia y justificación de la compra">
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
    </div>
  );
};

// Sección: Items
const SectionItems = ({ form, set, errors }) => {
  const updateItem = (id, patch) => {
    set({ items: form.items.map((it) => (it.id === id ? { ...it, ...patch } : it)) });
  };
  const addItem = () => {
    const nextId = Math.max(0, ...form.items.map((i) => i.id)) + 1;
    set({ items: [...form.items, { id: nextId, descripcion: '', cantidad: 1, unidad: 'unidad' }] });
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
          <p className="section-sub">Agrega cada item con su cantidad. Puedes agregar todos los necesarios.</p>
        </div>
      </div>
      <div className="items-table">
        <div className="items-head">
          <div>Descripción del item</div>
          <div>Cantidad</div>
          <div>Unidad</div>
          <div></div>
        </div>
        {form.items.map((it, idx) => (
          <div key={it.id} className="items-row">
            <div className="items-cell">
              <Input
                placeholder={`Item ${idx + 1} — Ej: Pastillas de freno delanteras`}
                value={it.descripcion}
                onChange={(e) => updateItem(it.id, { descripcion: e.target.value })}
              />
            </div>
            <div className="items-cell">
              <Input
                type="number"
                min="1"
                value={it.cantidad}
                onChange={(e) => updateItem(it.id, { cantidad: Number(e.target.value) })}
              />
            </div>
            <div className="items-cell">
              <Select value={it.unidad} onChange={(e) => updateItem(it.id, { unidad: e.target.value })}>
                <option value="unidad">unidad</option>
                <option value="caja">caja</option>
                <option value="litros">litros</option>
                <option value="kg">kg</option>
                <option value="metros">metros</option>
                <option value="servicio">servicio</option>
                <option value="hora">hora</option>
                <option value="tambor">tambor</option>
              </Select>
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
const ResumenLateral = ({ form }) => {
  const empresa = EMPRESAS.find((e) => e.id === form.empresa);
  const cc = form.empresa ? CENTROS_COSTO[form.empresa].find((c) => c.id === form.centroCosto) : null;
  const tipo = TIPOS_COMPRA.find((t) => t.id === form.tipo);
  const completitud = (() => {
    let n = 0, total = 5;
    if (form.empresa) n++;
    if (form.tipo) n++;
    if (form.titulo && form.descripcion) n++;
    if (form.centroCosto) n++;
    if (form.items.some((i) => i.descripcion)) n++;
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
          <dd>{form.items.filter((i) => i.descripcion).length || <span className="resumen-empty">—</span>}</dd>
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

const NuevaSolicitud = ({ layout = 'twocol', onSubmit, onCancel }) => {
  const [form, setForm] = React.useState({
    empresa: '', tipo: '', titulo: '', descripcion: '', centroCosto: '',
    items: [{ id: 1, descripcion: '', cantidad: 1, unidad: 'unidad' }],
    adjuntos: [],
  });
  const [errors, setErrors] = React.useState({});
  const [step, setStep] = React.useState(0);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const validate = () => {
    const e = {};
    if (!form.empresa) e.empresa = 'Selecciona una empresa';
    if (!form.tipo) e.tipo = 'Selecciona el tipo de compra';
    if (!form.titulo.trim()) e.titulo = 'Agrega un título';
    if (!form.descripcion.trim()) e.descripcion = 'Agrega una descripción';
    if (!form.centroCosto) e.centroCosto = 'Selecciona un centro de costo';
    if (!form.items.some((i) => i.descripcion.trim())) e.items = 'Agrega al menos un item con descripción';
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
        <SectionEmpresa form={form} set={set} errors={errors} />
        <SectionDetalle form={form} set={set} errors={errors} />
        <SectionItems form={form} set={set} errors={errors} />
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
          <SectionEmpresa form={form} set={set} errors={errors} />
          <SectionDetalle form={form} set={set} errors={errors} />
          <SectionItems form={form} set={set} errors={errors} />
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
          <ResumenLateral form={form} />
        </aside>
      </div>
    );
  }

  // ── Wizard (stepper)
  const steps = [
    { label: 'Empresa', component: <SectionEmpresa form={form} set={set} errors={errors} /> },
    { label: 'Detalle', component: <SectionDetalle form={form} set={set} errors={errors} /> },
    { label: 'Items', component: <SectionItems form={form} set={set} errors={errors} /> },
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
