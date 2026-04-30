// Dashboard — lista de solicitudes del solicitante

const Dashboard = ({ solicitudes, onOpen, onNueva }) => {
  const [filtro, setFiltro] = React.useState('todas');
  const [empresaFiltro, setEmpresaFiltro] = React.useState('todas');
  const [search, setSearch] = React.useState('');

  const filtradas = solicitudes.filter((s) => {
    if (filtro === 'activas' && (s.estadoActual === 'facturada' || s.estadoActual === 'borrador')) return false;
    if (filtro === 'borradores' && s.estadoActual !== 'borrador') return false;
    if (filtro === 'completadas' && s.estadoActual !== 'facturada') return false;
    if (empresaFiltro !== 'todas' && s.empresa !== empresaFiltro) return false;
    if (search && !`${s.titulo} ${s.id}`.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const stats = [
    { label: 'En curso', value: solicitudes.filter((s) => !['borrador', 'facturada'].includes(s.estadoActual)).length, hint: 'esperando una acción' },
    { label: 'Borradores', value: solicitudes.filter((s) => s.estadoActual === 'borrador').length, hint: 'sin enviar' },
    { label: 'Completadas', value: solicitudes.filter((s) => s.estadoActual === 'facturada').length, hint: 'este mes' },
    { label: 'Con novedades', value: 2, hint: 'requieren tu respuesta', highlight: true },
  ];

  return (
    <div className="dashboard">
      <div className="stats-grid">
        {stats.map((s, i) => (
          <Card key={i} className={s.highlight ? 'stat-card stat-highlight' : 'stat-card'}>
            <div className="stat-label">{s.label}</div>
            <div className="stat-value">{s.value}</div>
            <div className="stat-hint">{s.hint}</div>
          </Card>
        ))}
      </div>

      <div className="list-toolbar">
        <div className="search-box">
          <Icon name="search" size={16} />
          <input placeholder="Buscar por título o folio…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className="filter-tabs">
          {[
            { id: 'todas', label: 'Todas' },
            { id: 'activas', label: 'Activas' },
            { id: 'borradores', label: 'Borradores' },
            { id: 'completadas', label: 'Completadas' },
          ].map((t) => (
            <button key={t.id} className={`tab${filtro === t.id ? ' tab-active' : ''}`} onClick={() => setFiltro(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
        <Select value={empresaFiltro} onChange={(e) => setEmpresaFiltro(e.target.value)}>
          <option value="todas">Todas las empresas</option>
          {EMPRESAS.map((e) => <option key={e.id} value={e.id}>{e.abrev}</option>)}
        </Select>
        <Button variant="primary" icon="plus" onClick={onNueva}>Nueva solicitud</Button>
      </div>

      <Card className="list-card">
        <table className="solicitud-table">
          <thead>
            <tr>
              <th>Folio</th>
              <th>Solicitud</th>
              <th>Empresa</th>
              <th>Centro de costo</th>
              <th>Estado</th>
              <th>Fecha</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtradas.map((s) => {
              const empresa = EMPRESAS.find((e) => e.id === s.empresa);
              const cc = CENTROS_COSTO[s.empresa].find((c) => c.id === s.centroCosto);
              const estadoIdx = ESTADOS.findIndex((e) => e.id === s.estadoActual);
              const progreso = s.estadoActual === 'borrador' ? 0 : ((estadoIdx) / (ESTADOS.length - 1)) * 100;
              return (
                <tr key={s.id} onClick={() => onOpen(s.id)} className="row-click">
                  <td className="cell-folio">{s.id}</td>
                  <td>
                    <div className="cell-titulo">{s.titulo}</div>
                    <div className="cell-sub">{TIPOS_COMPRA.find((t) => t.id === s.tipo)?.label}</div>
                  </td>
                  <td><span className="empresa-pill">{empresa.abrev}</span></td>
                  <td>
                    <div className="cell-cc">{cc?.nombre}</div>
                    <div className="cell-sub">{cc?.codigo}</div>
                  </td>
                  <td>
                    <StatusBadge estadoId={s.estadoActual} />
                    {s.estadoActual !== 'borrador' && (
                      <div className="row-progress">
                        <div className="row-progress-fill" style={{ width: `${progreso}%` }} />
                      </div>
                    )}
                  </td>
                  <td className="cell-fecha">{formatFecha(s.fechaSolicitud)}</td>
                  <td><Icon name="chevronRight" size={16} className="row-chevron" /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtradas.length === 0 && (
          <div className="empty">
            <Icon name="folder" size={32} />
            <div>No hay solicitudes que coincidan</div>
          </div>
        )}
      </Card>

      {/* Mobile cards */}
      <div className="mobile-list">
        {filtradas.map((s) => {
          const empresa = EMPRESAS.find((e) => e.id === s.empresa);
          const cc = CENTROS_COSTO[s.empresa].find((c) => c.id === s.centroCosto);
          return (
            <Card key={s.id} hover onClick={() => onOpen(s.id)} className="mobile-row">
              <div className="mobile-row-top">
                <span className="cell-folio">{s.id}</span>
                <StatusBadge estadoId={s.estadoActual} />
              </div>
              <div className="cell-titulo">{s.titulo}</div>
              <div className="mobile-row-meta">
                <span className="empresa-pill">{empresa.abrev}</span>
                <span>·</span>
                <span>{cc?.nombre}</span>
                <span>·</span>
                <span>{formatFecha(s.fechaSolicitud)}</span>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
};

function formatFecha(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });
}

window.Dashboard = Dashboard;
window.formatFecha = formatFecha;
