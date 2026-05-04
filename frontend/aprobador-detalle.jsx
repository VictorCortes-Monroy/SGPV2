// Vista de detalle del aprobador — con acciones aprobar/rechazar/solicitar cambios

const ApprovalActionModal = ({ tipo, solicitud, onClose, onConfirm }) => {
  const [motivo, setMotivo] = React.useState('');
  const [observaciones, setObservaciones] = React.useState('');

  const config = {
    aprobar: {
      titulo: 'Aprobar solicitud',
      sub: 'La solicitud avanzará a la siguiente etapa del proceso.',
      icon: 'check', color: 'emerald',
      label: 'Observaciones (opcional)',
      placeholder: 'Comentarios para el equipo de compras o el solicitante…',
      btn: 'Confirmar aprobación', btnVar: 'primary',
      requiere: false,
    },
    rechazar: {
      titulo: 'Rechazar solicitud',
      sub: 'La solicitud volverá al solicitante con el motivo del rechazo.',
      icon: 'x', color: 'red',
      label: 'Motivo del rechazo *',
      placeholder: 'Explica al solicitante por qué se rechaza la solicitud…',
      btn: 'Confirmar rechazo', btnVar: 'danger',
      requiere: true,
    },
    cambios: {
      titulo: 'Solicitar cambios',
      sub: 'La solicitud volverá al solicitante para que ajuste o complete información.',
      icon: 'edit', color: 'amber',
      label: '¿Qué necesitas que cambie o agregue? *',
      placeholder: 'Ej: Adjuntar cotización adicional, corregir centro de costo, aclarar urgencia…',
      btn: 'Enviar solicitud de cambios', btnVar: 'primary',
      requiere: true,
    },
  };
  const c = config[tipo];
  const valor = tipo === 'aprobar' ? observaciones : motivo;
  const setValor = tipo === 'aprobar' ? setObservaciones : setMotivo;
  const valido = !c.requiere || valor.trim().length >= 5;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className={`modal-head modal-head-${c.color}`}>
          <div className={`modal-icon modal-icon-${c.color}`}>
            <Icon name={c.icon} size={20} />
          </div>
          <div>
            <h3 className="modal-title">{c.titulo}</h3>
            <p className="modal-sub">{c.sub}</p>
          </div>
          <button className="modal-close" onClick={onClose}><Icon name="x" size={16} /></button>
        </div>
        <div className="modal-body">
          <div className="modal-summary">
            <div className="modal-summary-folio">{solicitud.id}</div>
            <div className="modal-summary-titulo">{solicitud.titulo}</div>
            <div className="modal-summary-meta">
              <span>{solicitud.solicitante.nombre}</span>
              <span className="meta-dot" />
              <span>{solicitud.items.length} item{solicitud.items.length !== 1 ? 's' : ''}</span>
            </div>
          </div>
          <Field label={c.label}>
            <Textarea rows={4} placeholder={c.placeholder} value={valor} onChange={(e) => setValor(e.target.value)} />
          </Field>
        </div>
        <div className="modal-foot">
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button variant={c.btnVar} disabled={!valido} onClick={() => onConfirm(valor)}>{c.btn}</Button>
        </div>
      </div>
    </div>
  );
};

const PresupuestoCC = ({ centroCosto, empresa, montoSolicitado }) => {
  // Si la empresa no está en el mock (ej. SC viene del API real), no mostramos
  // la card de presupuesto — los datos de presupuesto/YTD viven solo en mock.
  // TODO: cuando el backend exponga /presupuestos, reemplazar lookup por API.
  const cc = (CENTROS_COSTO[empresa] || []).find((c) => c.id === centroCosto);
  if (!cc) return null;
  const usado = cc.gastoYtd;
  const total = cc.presupuestoAnual;
  const conSolicitud = usado + montoSolicitado;
  const pctUsado = (usado / total) * 100;
  const pctConSolicitud = (conSolicitud / total) * 100;
  const disponible = total - usado;
  const alerta = pctConSolicitud > 90;

  return (
    <Card>
      <div className="card-head"><h3>Presupuesto del centro de costo</h3></div>
      <div className="presupuesto">
        <div className="presupuesto-row">
          <span>{cc.nombre}</span>
          <span className="presupuesto-codigo">{cc.codigo}</span>
        </div>
        <div className="presupuesto-bar-track">
          <div className="presupuesto-bar-used" style={{ width: `${Math.min(pctUsado, 100)}%` }} />
          <div className="presupuesto-bar-new" style={{ left: `${Math.min(pctUsado, 100)}%`, width: `${Math.min(pctConSolicitud - pctUsado, 100 - pctUsado)}%` }} />
        </div>
        <div className="presupuesto-legend">
          <span className="presupuesto-pct">{pctConSolicitud.toFixed(1)}% comprometido</span>
          <span>{formatCLP(disponible)} disponibles</span>
        </div>
        <dl className="presupuesto-detail">
          <div><dt>Presupuesto anual</dt><dd>{formatCLP(total)}</dd></div>
          <div><dt>Gastado YTD</dt><dd>{formatCLP(usado)}</dd></div>
          <div className="presupuesto-detail-new">
            <dt>Esta solicitud</dt><dd>+ {formatCLP(montoSolicitado)}</dd>
          </div>
          <div className="presupuesto-detail-total">
            <dt>Total comprometido</dt><dd>{formatCLP(conSolicitud)}</dd>
          </div>
        </dl>
        {alerta && (
          <div className="presupuesto-alert">
            <Icon name="alert" size={14} />
            <span>Este pedido deja el centro de costo sobre el 90% del presupuesto anual.</span>
          </div>
        )}
      </div>
    </Card>
  );
};

const AprobadorDetalle = ({ solicitud, onBack, onAction, readonly }) => {
  const empresa = solicitud.empresaInfo
    ? { abrev: solicitud.empresaInfo.nombre_corto, nombre: solicitud.empresaInfo.razon_social }
    : EMPRESAS.find((e) => e.id === solicitud.empresa) || { abrev: solicitud.empresa || '—', nombre: solicitud.empresa || '—' };
  const cc = solicitud.centroCostoInfo
    ? { codigo: solicitud.centroCostoInfo.codigo, nombre: solicitud.centroCostoInfo.nombre, presupuestoAnual: 0, gastoYtd: 0 }
    : (CENTROS_COSTO[solicitud.empresa] || []).find((c) => c.id === solicitud.centroCosto) || { codigo: '—', nombre: '—', presupuestoAnual: 0, gastoYtd: 0 };
  const tipo = TIPOS_COMPRA.find((t) => t.id === solicitud.tipo);
  const [modal, setModal] = React.useState(null);

  return (
    <div className="tracking">
      <button className="back-link" onClick={onBack}>
        <Icon name="arrowLeft" size={14} /> Volver a la bandeja
      </button>

      <div className="tracking-hero aprob-hero">
        <div className="tracking-hero-left">
          <div className="aprob-hero-row">
            <div className="tracking-folio">{solicitud.id}</div>
            <UrgenciaBadge urgencia={solicitud.urgencia} />
            <FechaRequerida fecha={solicitud.fechaRequerida} />
          </div>
          <h1 className="tracking-title">{solicitud.titulo}</h1>
          <div className="tracking-meta-row">
            <span className="empresa-pill">{empresa.abrev}</span>
            <span className="meta-dot" />
            <span>{cc?.nombre} · {cc?.codigo}</span>
            <span className="meta-dot" />
            <span>{tipo?.label}</span>
            <span className="meta-dot" />
            <span>Solicitada {formatFecha(solicitud.fechaSolicitud)}</span>
          </div>
        </div>
        <div className="aprob-hero-right">
          <UrgenciaBadge urgencia={solicitud.urgencia} />
        </div>
      </div>

      {!readonly && (
        <div className="aprob-actions-bar">
          <div className="aprob-actions-info">
            <Icon name="info" size={14} />
            <span>Esta solicitud espera tu decisión. Revisa el detalle y elige una acción.</span>
          </div>
          <div className="aprob-actions-btns">
            <Button variant="secondary" icon="edit" onClick={() => setModal('cambios')}>Solicitar cambios</Button>
            <Button variant="danger" icon="x" onClick={() => setModal('rechazar')}>Rechazar</Button>
            <Button variant="primary" icon="check" onClick={() => setModal('aprobar')}>Aprobar</Button>
          </div>
        </div>
      )}

      <div className="tracking-grid">
        <div className="tracking-main">
          <Card>
            <div className="card-head"><h3>Solicitante</h3></div>
            <div className="solicitante-block">
              <Avatar initials={solicitud.solicitante.avatar} size={40} />
              <div>
                <div className="solicitante-nombre">{solicitud.solicitante.nombre}</div>
                <div className="solicitante-rol">{solicitud.solicitante.cargo}</div>
              </div>
            </div>
          </Card>

          <Card>
            <div className="card-head"><h3>Descripción y justificación</h3></div>
            <p className="desc-text">{solicitud.descripcion}</p>
          </Card>

          <Card>
            <div className="card-head"><h3>Items solicitados</h3><span className="card-head-count">{solicitud.items.length}</span></div>
            <table className="items-detail">
              <thead>
                <tr><th>SKU</th><th>Descripción</th><th>Cant.</th></tr>
              </thead>
              <tbody>
                {solicitud.items.map((it) => (
                  <tr key={it.id}>
                    <td><code>{it.sku || '—'}</code></td>
                    <td>{it.descripcion}</td>
                    <td className="num">{it.cantidad}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          {solicitud.adjuntos.length > 0 && (
            <Card>
              <div className="card-head"><h3>Respaldos</h3><span className="card-head-count">{solicitud.adjuntos.length}</span></div>
              <div className="adjuntos-list">
                {solicitud.adjuntos.map((a, i) => (
                  <div key={i} className="adjunto-item">
                    <div className={`adjunto-icon adjunto-icon-${a.tipo}`}>
                      <Icon name={a.tipo === 'pdf' ? 'file' : a.tipo === 'img' ? 'image' : a.tipo === 'xls' ? 'sheet' : 'file'} size={16} />
                    </div>
                    <div className="adjunto-text">
                      <div className="adjunto-nombre">{a.nombre}</div>
                      <div className="adjunto-meta">{a.tamano}</div>
                    </div>
                    <button className="adjunto-download"><Icon name="download" size={14} /></button>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <Card>
            <div className="card-head"><h3>Actividad</h3></div>
            <div className="activity">
              {solicitud.eventos.map((ev, i) => {
                const estadoEv = ev.estado ? ESTADOS.find((e) => e.id === ev.estado) : null;
                return (
                  <div key={ev.id} className={`activity-item activity-${ev.tipo}`}>
                    <div className="activity-marker">
                      {ev.tipo === 'estado' ? (
                        <div className="activity-marker-estado"><Icon name={estadoEv?.icon || 'check'} size={12} /></div>
                      ) : (
                        <Avatar initials={ev.actor.split(' ').map((s) => s[0]).slice(0, 2).join('')} size={26} color="#475569" />
                      )}
                      {i < solicitud.eventos.length - 1 && <div className="activity-line" />}
                    </div>
                    <div className="activity-content">
                      <div className="activity-head">
                        <span className="activity-actor">{ev.actor}</span>
                        <span className="activity-rol">{ev.actorRol}</span>
                        <span className="activity-time">{ev.fecha}</span>
                      </div>
                      {ev.tipo === 'estado' ? (
                        <div className="activity-body">
                          <span>cambió el estado a </span>
                          <StatusBadge estadoId={ev.estado} />
                          {ev.mensaje && <div className="activity-msg activity-msg-inline">{ev.mensaje}</div>}
                        </div>
                      ) : (
                        <div className="activity-msg">{ev.mensaje}</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>

        <div className="tracking-side">
          <Card>
            <div className="card-head"><h3>Resumen rápido</h3></div>
            <dl className="resumen-list">
              <div className="resumen-item"><dt>Fecha requerida</dt><dd>{formatFecha(solicitud.fechaRequerida)}</dd></div>
              <div className="resumen-item"><dt>Días para entrega</dt><dd>{diasHasta(solicitud.fechaRequerida)} días</dd></div>
              <div className="resumen-item"><dt>Tipo</dt><dd>{tipo?.label}</dd></div>
              <div className="resumen-item"><dt>Items</dt><dd>{solicitud.items.length}</dd></div>
              <div className="resumen-item"><dt>Adjuntos</dt><dd>{solicitud.adjuntos.length}</dd></div>
            </dl>
          </Card>
        </div>
      </div>

      {modal && (
        <ApprovalActionModal
          tipo={modal}
          solicitud={solicitud}
          onClose={() => setModal(null)}
          onConfirm={(texto) => { onAction(modal, texto); setModal(null); }}
        />
      )}
    </div>
  );
};

window.AprobadorDetalle = AprobadorDetalle;
