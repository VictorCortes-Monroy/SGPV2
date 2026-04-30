// Vista de tracking de solicitud — timeline horizontal tipo Mercado Libre + comentarios

const TimelineHorizontal = ({ estadoActual }) => {
  const idxActual = ESTADOS.findIndex((e) => e.id === estadoActual);
  return (
    <div className="hl-timeline-wrap">
      <div className="hl-timeline">
        {ESTADOS.map((e, i) => {
          const done = i < idxActual;
          const current = i === idxActual;
          const pending = i > idxActual;
          return (
            <React.Fragment key={e.id}>
              <div className={`hl-step${done ? ' hl-done' : ''}${current ? ' hl-current' : ''}${pending ? ' hl-pending' : ''}`}>
                <div className="hl-circle">
                  {done ? <Icon name="check" size={16} /> : <Icon name={e.icon} size={16} />}
                  {current && <div className="hl-pulse" />}
                </div>
                <div className="hl-label">{e.label}</div>
              </div>
              {i < ESTADOS.length - 1 && (
                <div className={`hl-line${i < idxActual ? ' hl-line-done' : ''}`}>
                  <div className="hl-line-fill" />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};

const TrackingView = ({ solicitud, onBack }) => {
  // Priorizar info embebida del API; fallback al mock para compatibilidad off-line.
  const empresa = solicitud.empresaInfo
    ? { abrev: solicitud.empresaInfo.nombre_corto, nombre: solicitud.empresaInfo.razon_social }
    : EMPRESAS.find((e) => e.id === solicitud.empresa) || { abrev: solicitud.empresa || '—', nombre: solicitud.empresa || '—' };
  const cc = solicitud.centroCostoInfo
    ? { codigo: solicitud.centroCostoInfo.codigo, nombre: solicitud.centroCostoInfo.nombre, presupuestoAnual: 0, gastoYtd: 0 }
    : (CENTROS_COSTO[solicitud.empresa] || []).find((c) => c.id === solicitud.centroCosto) || { codigo: '—', nombre: '—' };
  const tipo = TIPOS_COMPRA.find((t) => t.id === solicitud.tipo);
  const idxActual = ESTADOS.findIndex((e) => e.id === solicitud.estadoActual);
  const estadoActual = ESTADOS[idxActual];
  const [nuevoComentario, setNuevoComentario] = React.useState('');
  const [eventos, setEventos] = React.useState(solicitud.eventos);

  const enviar = () => {
    if (!nuevoComentario.trim()) return;
    const e = {
      id: `local-${Date.now()}`,
      fecha: new Date().toISOString().slice(0, 16).replace('T', ' '),
      actor: 'Carolina Pérez',
      actorRol: 'Solicitante',
      tipo: 'comentario',
      mensaje: nuevoComentario.trim(),
    };
    setEventos([...eventos, e]);
    setNuevoComentario('');
  };

  // Próximo estado / siguiente paso
  const siguienteEstado = ESTADOS[idxActual + 1];
  const tieneNovedad = eventos.some((e) => e.tipo === 'comentario' && e.actorRol !== 'Solicitante');

  return (
    <div className="tracking">
      <button className="back-link" onClick={onBack}>
        <Icon name="arrowLeft" size={14} /> Volver a mis solicitudes
      </button>

      {/* Header con folio + estado actual destacado */}
      <div className="tracking-hero">
        <div className="tracking-hero-left">
          <div className="tracking-folio">{solicitud.id}</div>
          <h1 className="tracking-title">{solicitud.titulo}</h1>
          <div className="tracking-meta-row">
            <span className="empresa-pill">{empresa.abrev}</span>
            <span className="meta-dot" />
            <span>{cc?.nombre} · {cc?.codigo}</span>
            <span className="meta-dot" />
            <span>{tipo?.label}</span>
            <span className="meta-dot" />
            <span>Solicitada el {formatFecha(solicitud.fechaSolicitud)}</span>
          </div>
        </div>
        <div className="tracking-hero-right">
          <div className={`hero-status hero-status-${solicitud.estadoActual}`}>
            <div className="hero-status-icon">
              <Icon name={estadoActual.icon} size={22} />
            </div>
            <div>
              <div className="hero-status-label">Estado actual</div>
              <div className="hero-status-value">{estadoActual.label}</div>
            </div>
          </div>
          {siguienteEstado && solicitud.estadoActual !== 'borrador' && (
            <div className="hero-next">
              Siguiente: <strong>{siguienteEstado.label}</strong>
            </div>
          )}
        </div>
      </div>

      {/* Timeline horizontal */}
      <Card className="tracking-timeline-card">
        <TimelineHorizontal estadoActual={solicitud.estadoActual} />
      </Card>

      {tieneNovedad && (
        <div className="alert alert-amber">
          <Icon name="alert" size={16} />
          <div>
            <strong>Tienes novedades</strong>
            <span> — un aprobador dejó un comentario que requiere tu respuesta. Revisa la actividad más abajo.</span>
          </div>
        </div>
      )}

      <div className="tracking-grid">
        {/* Columna izquierda: actividad */}
        <div className="tracking-main">
          <Card>
            <div className="card-head">
              <h3>Actividad y comentarios</h3>
              <span className="card-head-count">{eventos.length}</span>
            </div>
            <div className="activity">
              {eventos.length === 0 && (
                <div className="empty-mini">Aún no hay actividad. La solicitud está en borrador.</div>
              )}
              {eventos.map((ev, i) => {
                const estadoEv = ev.estado ? ESTADOS.find((e) => e.id === ev.estado) : null;
                return (
                  <div key={ev.id} className={`activity-item activity-${ev.tipo}`}>
                    <div className="activity-marker">
                      {ev.tipo === 'estado' ? (
                        <div className="activity-marker-estado">
                          <Icon name={estadoEv?.icon || 'check'} size={12} />
                        </div>
                      ) : (
                        <Avatar initials={ev.actor.split(' ').map((s) => s[0]).slice(0, 2).join('')} size={26}
                                color={ev.actorRol === 'Solicitante' ? '#1e6f5c' : '#475569'} />
                      )}
                      {i < eventos.length - 1 && <div className="activity-line" />}
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
            <div className="comment-box">
              <Avatar initials="CP" size={32} />
              <div className="comment-box-input">
                <Textarea
                  rows={2}
                  placeholder="Escribe un comentario o responde a una novedad…"
                  value={nuevoComentario}
                  onChange={(e) => setNuevoComentario(e.target.value)}
                />
                <div className="comment-box-actions">
                  <button className="comment-attach" aria-label="Adjuntar">
                    <Icon name="paperclip" size={14} /> Adjuntar
                  </button>
                  <Button variant="primary" size="sm" icon="send" onClick={enviar} disabled={!nuevoComentario.trim()}>
                    Enviar
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Columna derecha: detalles */}
        <div className="tracking-side">
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
            <div className="card-head"><h3>Descripción</h3></div>
            <p className="desc-text">{solicitud.descripcion}</p>
          </Card>

          <Card>
            <div className="card-head"><h3>Items solicitados</h3><span className="card-head-count">{solicitud.items.length}</span></div>
            <ul className="items-list">
              {solicitud.items.map((it) => (
                <li key={it.id} className="items-list-item">
                  <div className="items-list-desc">{it.descripcion}</div>
                  <div className="items-list-cant">{it.cantidad} {it.unidad}</div>
                </li>
              ))}
            </ul>
          </Card>

          {solicitud.adjuntos.length > 0 && (
            <Card>
              <div className="card-head"><h3>Respaldos</h3><span className="card-head-count">{solicitud.adjuntos.length}</span></div>
              <div className="adjuntos-list adjuntos-list-side">
                {solicitud.adjuntos.map((a, i) => (
                  <div key={i} className="adjunto-item">
                    <div className={`adjunto-icon adjunto-icon-${a.tipo}`}>
                      <Icon name={iconAdjunto(a.tipo)} size={16} />
                    </div>
                    <div className="adjunto-text">
                      <div className="adjunto-nombre">{a.nombre}</div>
                      <div className="adjunto-meta">{a.tamano}</div>
                    </div>
                    <button className="adjunto-download" aria-label="Descargar">
                      <Icon name="download" size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <Card>
            <div className="card-head"><h3>Aprobaciones</h3></div>
            <div className="aprobaciones-list">
              {[
                { rol: 'Jefe directo', nombre: 'Marco Riquelme', estado: idxActual >= 2 ? 'ok' : (idxActual === 1 ? 'wait' : 'pending') },
                { rol: 'Finanzas', nombre: 'Patricia Núñez', estado: idxActual >= 3 ? 'ok' : (idxActual === 2 ? 'wait' : 'pending') },
                { rol: 'Gerencia', nombre: 'Sofía Gallardo', estado: idxActual >= 3 ? 'ok' : 'pending' },
              ].map((a, i) => (
                <div key={i} className="aprob-row">
                  <Avatar initials={a.nombre.split(' ').map((s) => s[0]).slice(0, 2).join('')} size={28} color="#475569" />
                  <div className="aprob-text">
                    <div className="aprob-rol">{a.rol}</div>
                    <div className="aprob-nombre">{a.nombre}</div>
                  </div>
                  <div className={`aprob-estado aprob-${a.estado}`}>
                    {a.estado === 'ok' && <Icon name="check" size={14} />}
                    {a.estado === 'wait' && <Icon name="clock" size={14} />}
                    {a.estado === 'pending' && <span className="aprob-dot" />}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

window.TrackingView = TrackingView;
