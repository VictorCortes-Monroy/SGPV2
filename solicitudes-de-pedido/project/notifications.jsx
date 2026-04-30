// Centro de notificaciones expandido — panel desplegable

const NOTIFICACIONES = [
  { id: 'n1', tipo: 'pendiente', titulo: 'Nueva solicitud para aprobar', detalle: 'Roberto Lagos · SOL-2026-0166 · Reparación motor de winche', monto: 5620000, urgencia: 'alta', tiempo: 'hace 2h', noLeida: true },
  { id: 'n2', tipo: 'pendiente', titulo: 'Nueva solicitud para aprobar', detalle: 'Carolina Pérez · SOL-2026-0163 · Reemplazo neumáticos camión TLD-1820', monto: 3060000, urgencia: 'alta', tiempo: 'hace 5h', noLeida: true },
  { id: 'n3', tipo: 'sla', titulo: 'Solicitud cerca del plazo', detalle: 'SOL-2026-0151 · Notebook coordinador — fecha requerida en 5 días', tiempo: 'hace 1d', noLeida: true },
  { id: 'n4', tipo: 'comentario', titulo: 'Carolina respondió tu comentario', detalle: 'SOL-2026-0151 · "Sí, ya está formalmente contratado..."', tiempo: 'hace 1d', noLeida: false },
  { id: 'n5', tipo: 'sistema', titulo: 'Solicitud avanzó de etapa', detalle: 'SOL-2026-0142 · Repuestos de frenos — ahora en tránsito', tiempo: 'hace 3d', noLeida: false },
];

const NotificationCenter = ({ open, onClose }) => {
  const [tab, setTab] = React.useState('todas');
  const noLeidas = NOTIFICACIONES.filter((n) => n.noLeida);
  const lista = tab === 'noleidas' ? noLeidas : NOTIFICACIONES;

  if (!open) return null;
  return (
    <>
      <div className="notif-backdrop" onClick={onClose} />
      <div className="notif-panel">
        <div className="notif-head">
          <h3>Notificaciones</h3>
          <button className="modal-close" onClick={onClose}><Icon name="x" size={16} /></button>
        </div>
        <div className="notif-tabs">
          <button className={`notif-tab${tab === 'todas' ? ' notif-tab-active' : ''}`} onClick={() => setTab('todas')}>
            Todas <span className="notif-tab-count">{NOTIFICACIONES.length}</span>
          </button>
          <button className={`notif-tab${tab === 'noleidas' ? ' notif-tab-active' : ''}`} onClick={() => setTab('noleidas')}>
            No leídas <span className="notif-tab-count">{noLeidas.length}</span>
          </button>
        </div>
        <div className="notif-list">
          {lista.map((n) => {
            const icon = { pendiente: 'check', sla: 'clock', comentario: 'message', sistema: 'info' }[n.tipo] || 'bell';
            const colorClass = { pendiente: 'amber', sla: 'red', comentario: 'blue', sistema: 'neutral' }[n.tipo];
            return (
              <div key={n.id} className={`notif-item${n.noLeida ? ' notif-item-unread' : ''}`}>
                <div className={`notif-icon notif-icon-${colorClass}`}><Icon name={icon} size={14} /></div>
                <div className="notif-content">
                  <div className="notif-title">{n.titulo}</div>
                  <div className="notif-detail">{n.detalle}</div>
                  <div className="notif-foot">
                    {n.urgencia && <UrgenciaBadge urgencia={n.urgencia} />}
                    {n.monto && <span className="notif-monto">{formatCLP(n.monto)}</span>}
                    <span className="notif-time">{n.tiempo}</span>
                  </div>
                </div>
                {n.noLeida && <span className="notif-dot" />}
              </div>
            );
          })}
        </div>
        <div className="notif-foot-actions">
          <button className="notif-mark">Marcar todas como leídas</button>
        </div>
      </div>
    </>
  );
};

window.NotificationCenter = NotificationCenter;
