// Bandeja del aprobador — soporta 3 layouts: tabla, lista, cards

const urgenciaLabel = { alta: 'Alta', media: 'Media', baja: 'Baja' };

const UrgenciaBadge = ({ urgencia }) => {
  const cls = `urg urg-${urgencia}`;
  return (
    <span className={cls}>
      <span className="urg-dot" />
      {urgenciaLabel[urgencia]}
    </span>
  );
};

const FechaRequerida = ({ fecha }) => {
  const dias = diasHasta(fecha);
  let cls = 'fecha-req';
  let label = '';
  if (dias < 0) { cls += ' fecha-vencida'; label = `Vencida hace ${Math.abs(dias)}d`; }
  else if (dias === 0) { cls += ' fecha-hoy'; label = 'Hoy'; }
  else if (dias <= 3) { cls += ' fecha-proxima'; label = `En ${dias}d`; }
  else { label = `En ${dias}d`; }
  return (
    <span className={cls}>
      <Icon name="clock" size={11} />
      {label}
    </span>
  );
};

// ── Vista TABLA ──
const BandejaTabla = ({ solicitudes, onOpen }) => (
  <Card className="list-card">
    <table className="solicitud-table aprob-table">
      <thead>
        <tr>
          <th>Folio</th>
          <th>Solicitud</th>
          <th>Solicitante</th>
          <th>Centro de costo</th>
          <th>Urgencia</th>
          <th>Requerida</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {solicitudes.map((s) => {
          const empresa = s.empresaInfo
            ? { abrev: s.empresaInfo.nombre_corto }
            : EMPRESAS.find((e) => e.id === s.empresa) || { abrev: s.empresa || '—' };
          const cc = s.centroCostoInfo
            ? { codigo: s.centroCostoInfo.codigo, nombre: s.centroCostoInfo.nombre }
            : (CENTROS_COSTO[s.empresa] || []).find((c) => c.id === s.centroCosto) || { codigo: '—', nombre: '—' };
          return (
            <tr key={s.id} onClick={() => onOpen(s.id)} className="row-click">
              <td className="cell-folio">{s.id}</td>
              <td>
                <div className="cell-titulo">{s.titulo}</div>
                <div className="cell-sub">
                  <span className="empresa-pill empresa-pill-sm">{empresa.abrev}</span>
                  {' · '}{TIPOS_COMPRA.find((t) => t.id === s.tipo)?.label}
                </div>
              </td>
              <td>
                <div className="solicitante-mini">
                  <Avatar initials={s.solicitante.avatar} size={24} />
                  <span>{s.solicitante.nombre.split(' ')[0]}</span>
                </div>
              </td>
              <td>
                <div className="cell-cc">{cc?.nombre}</div>
                <div className="cell-sub">{cc?.codigo}</div>
              </td>
              <td><UrgenciaBadge urgencia={s.urgencia} /></td>
              <td><FechaRequerida fecha={s.fechaRequerida} /></td>
              <td><Icon name="chevronRight" size={16} className="row-chevron" /></td>
            </tr>
          );
        })}
      </tbody>
    </table>
    {solicitudes.length === 0 && <div className="empty"><Icon name="check" size={32} /><div>No hay solicitudes pendientes — todo al día</div></div>}
  </Card>
);

// ── Vista LISTA (filas densas) ──
const BandejaLista = ({ solicitudes, onOpen }) => (
  <Card className="list-card">
    <div className="lista-bandeja">
      {solicitudes.map((s) => {
        const empresa = s.empresaInfo
          ? { abrev: s.empresaInfo.nombre_corto }
          : EMPRESAS.find((e) => e.id === s.empresa) || { abrev: s.empresa || '—' };
        const cc = s.centroCostoInfo
          ? { codigo: s.centroCostoInfo.codigo, nombre: s.centroCostoInfo.nombre }
          : (CENTROS_COSTO[s.empresa] || []).find((c) => c.id === s.centroCosto) || { codigo: '—', nombre: '—' };
        return (
          <div key={s.id} className="lista-row" onClick={() => onOpen(s.id)}>
            <div className={`lista-urg-bar lista-urg-${s.urgencia}`} />
            <div className="lista-row-main">
              <div className="lista-row-top">
                <span className="cell-folio">{s.id}</span>
                <span className="empresa-pill empresa-pill-sm">{empresa.abrev}</span>
                <UrgenciaBadge urgencia={s.urgencia} />
                <FechaRequerida fecha={s.fechaRequerida} />
              </div>
              <div className="lista-titulo">{s.titulo}</div>
              <div className="lista-meta">
                <span><Icon name="user" size={12} /> {s.solicitante.nombre}</span>
                <span className="meta-dot" />
                <span><Icon name="folder" size={12} /> {cc?.nombre} ({cc?.codigo})</span>
                <span className="meta-dot" />
                <span><Icon name="tag" size={12} /> {TIPOS_COMPRA.find((t) => t.id === s.tipo)?.label}</span>
              </div>
            </div>
            <Icon name="chevronRight" size={16} className="row-chevron" />
          </div>
        );
      })}
    </div>
    {solicitudes.length === 0 && <div className="empty"><Icon name="check" size={32} /><div>No hay solicitudes pendientes — todo al día</div></div>}
  </Card>
);

// ── Vista CARDS (grid) ──
const BandejaCards = ({ solicitudes, onOpen }) => (
  <div className="bandeja-cards">
    {solicitudes.map((s) => {
      const empresa = s.empresaInfo
        ? { abrev: s.empresaInfo.nombre_corto }
        : EMPRESAS.find((e) => e.id === s.empresa) || { abrev: s.empresa || '—' };
      const cc = s.centroCostoInfo
        ? { codigo: s.centroCostoInfo.codigo, nombre: s.centroCostoInfo.nombre }
        : (CENTROS_COSTO[s.empresa] || []).find((c) => c.id === s.centroCosto) || { codigo: '—', nombre: '—' };
      return (
        <Card key={s.id} hover className="bandeja-card" onClick={() => onOpen(s.id)}>
          <div className="bandeja-card-head">
            <span className="cell-folio">{s.id}</span>
            <UrgenciaBadge urgencia={s.urgencia} />
          </div>
          <h3 className="bandeja-card-title">{s.titulo}</h3>
          <div className="bandeja-card-meta">
            <span className="empresa-pill empresa-pill-sm">{empresa.abrev}</span>
            <span>{TIPOS_COMPRA.find((t) => t.id === s.tipo)?.label}</span>
          </div>
          <dl className="bandeja-card-grid">
            <div><dt>Solicitante</dt><dd>{s.solicitante.nombre}</dd></div>
            <div><dt>Centro de costo</dt><dd>{cc?.nombre}</dd></div>
            <div><dt>Items</dt><dd>{s.items.length}</dd></div>
            <div><dt>Requerida</dt><dd><FechaRequerida fecha={s.fechaRequerida} /></dd></div>
          </dl>
          <div className="bandeja-card-foot">
            <span>{s.items.length} item{s.items.length > 1 ? 's' : ''}</span>
            {s.adjuntos.length > 0 && <span><Icon name="paperclip" size={11} /> {s.adjuntos.length}</span>}
            <Icon name="chevronRight" size={14} className="row-chevron" />
          </div>
        </Card>
      );
    })}
    {solicitudes.length === 0 && (
      <Card className="empty-card"><div className="empty"><Icon name="check" size={32} /><div>No hay solicitudes pendientes — todo al día</div></div></Card>
    )}
  </div>
);

const BandejaAprobador = ({ solicitudes, onOpen, layout = 'tabla' }) => {
  const [tab, setTab] = React.useState('pendientes');
  const [orden, setOrden] = React.useState('urgencia');
  const [search, setSearch] = React.useState('');

  const pendientes = solicitudes.filter((s) => s.estadoActual === 'revision');
  const procesadas = solicitudes.filter((s) => ['aprobada', 'rechazada', 'cotizada', 'oc', 'transito', 'recibida', 'facturada'].includes(s.estadoActual));

  const lista = (tab === 'pendientes' ? pendientes : procesadas)
    .filter((s) => !search || `${s.titulo} ${s.id} ${s.solicitante.nombre}`.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (orden === 'urgencia') {
        const ord = { alta: 0, media: 1, baja: 2 };
        return ord[a.urgencia] - ord[b.urgencia];
      }
      if (orden === 'fecha') return new Date(a.fechaRequerida) - new Date(b.fechaRequerida);
      return 0;
    });

  const urgentes = pendientes.filter((s) => s.urgencia === 'alta').length;
  const vencidas = pendientes.filter((s) => diasHasta(s.fechaRequerida) <= 0).length;

  return (
    <div className="dashboard">
      <div className="stats-grid">
        <Card className={pendientes.length > 0 ? 'stat-card stat-highlight' : 'stat-card'}>
          <div className="stat-label">Pendientes de aprobación</div>
          <div className="stat-value">{pendientes.length}</div>
          <div className="stat-hint">esperando tu decisión</div>
        </Card>
        <Card className="stat-card">
          <div className="stat-label">Urgentes</div>
          <div className="stat-value" style={{ color: 'var(--accent-red)' }}>{urgentes}</div>
          <div className="stat-hint">prioridad alta</div>
        </Card>
        <Card className="stat-card">
          <div className="stat-label">Plazo vencido o de hoy</div>
          <div className="stat-value">{vencidas}</div>
          <div className="stat-hint">requieren acción inmediata</div>
        </Card>
        <Card className="stat-card">
          <div className="stat-label">Total pendientes</div>
          <div className="stat-value">{pendientes.length}</div>
          <div className="stat-hint">solicitudes en cola</div>
        </Card>
      </div>

      <div className="list-toolbar">
        <div className="filter-tabs">
          <button className={`tab${tab === 'pendientes' ? ' tab-active' : ''}`} onClick={() => setTab('pendientes')}>
            Pendientes
            {pendientes.length > 0 && <span className="tab-count">{pendientes.length}</span>}
          </button>
          <button className={`tab${tab === 'historico' ? ' tab-active' : ''}`} onClick={() => setTab('historico')}>
            Histórico
          </button>
        </div>
        <div className="search-box">
          <Icon name="search" size={16} />
          <input placeholder="Buscar por título, folio o solicitante…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <Select value={orden} onChange={(e) => setOrden(e.target.value)}>
          <option value="urgencia">Por urgencia</option>
          <option value="fecha">Por fecha requerida</option>
        </Select>
      </div>

      {layout === 'tabla' && <BandejaTabla solicitudes={lista} onOpen={onOpen} />}
      {layout === 'lista' && <BandejaLista solicitudes={lista} onOpen={onOpen} />}
      {layout === 'cards' && <BandejaCards solicitudes={lista} onOpen={onOpen} />}
    </div>
  );
};

window.BandejaAprobador = BandejaAprobador;
window.UrgenciaBadge = UrgenciaBadge;
window.FechaRequerida = FechaRequerida;
