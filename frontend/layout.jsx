// Layout principal — sidebar + header + contenido (multi-rol)

const NAV_ITEMS = {
  solicitante: [
    { id: 'dashboard', label: 'Mis solicitudes', icon: 'home' },
    { id: 'nueva', label: 'Nueva solicitud', icon: 'plus' },
  ],
  aprobador: [
    { id: 'bandeja', label: 'Bandeja de aprobación', icon: 'check' },
    { id: 'historico', label: 'Histórico', icon: 'list' },
  ],
};

const Sidebar = ({ role, currentView, onNavigate, mobileOpen, onMobileClose, pendientesCount = 0, onSwitchRole }) => {
  const items = NAV_ITEMS[role] || [];
  const user = USUARIOS[role];
  return (
    <>
      {mobileOpen && <div className="sidebar-backdrop" onClick={onMobileClose} />}
      <aside className={`sidebar${mobileOpen ? ' sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-mark">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path d="M3 17l9-14 9 14H3z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
              <path d="M8 17l4-6 4 6" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
            </svg>
          </div>
          <div className="brand-text">
            <div className="brand-name">Acquira</div>
            <div className="brand-sub">Holding Norte</div>
          </div>
        </div>
        <nav className="sidebar-nav">
          {items.map((it) => (
            <button
              key={it.id}
              className={`nav-item${currentView === it.id ? ' nav-item-active' : ''}`}
              onClick={() => { onNavigate(it.id); onMobileClose && onMobileClose(); }}
            >
              <Icon name={it.icon} size={16} />
              <span>{it.label}</span>
              {it.id === 'bandeja' && pendientesCount > 0 && (
                <span className="nav-badge">{pendientesCount}</span>
              )}
            </button>
          ))}
          <div className="nav-section">Pronto</div>
          {role === 'solicitante' ? (
            <>
              <button className="nav-item nav-item-disabled" disabled>
                <Icon name="doc" size={16} /><span>Órdenes de compra</span><span className="nav-soon">soon</span>
              </button>
              <button className="nav-item nav-item-disabled" disabled>
                <Icon name="invoice" size={16} /><span>Facturas</span><span className="nav-soon">soon</span>
              </button>
            </>
          ) : (
            <>
              <button className="nav-item nav-item-disabled" disabled>
                <Icon name="folder" size={16} /><span>Reportes de gasto</span><span className="nav-soon">soon</span>
              </button>
              <button className="nav-item nav-item-disabled" disabled>
                <Icon name="settings" size={16} /><span>Reglas de aprobación</span><span className="nav-soon">soon</span>
              </button>
            </>
          )}
        </nav>
        <div className="sidebar-foot">
          <button className="user-chip user-chip-btn" onClick={onSwitchRole}>
            <Avatar initials={user.avatar} size={32} color={role === 'aprobador' ? '#1d4ed8' : '#1e6f5c'} />
            <div className="user-chip-text">
              <div className="user-name">{user.nombre}</div>
              <div className="user-role">{user.cargo}</div>
            </div>
            <Icon name="chevronRight" size={14} className="user-switch-icon" />
          </button>
        </div>
      </aside>
    </>
  );
};

const TopBar = ({ title, subtitle, actions, onMobileMenu, breadcrumb, onNotifClick, notifCount = 0 }) => (
  <header className="topbar">
    <div className="topbar-left">
      <button className="mobile-menu" onClick={onMobileMenu} aria-label="Menu">
        <Icon name="menu" size={20} />
      </button>
      <div>
        {breadcrumb && <div className="breadcrumb">{breadcrumb}</div>}
        <h1 className="topbar-title">{title}</h1>
        {subtitle && <div className="topbar-sub">{subtitle}</div>}
      </div>
    </div>
    <div className="topbar-actions">
      {actions}
      <button className="icon-btn" aria-label="Notificaciones" onClick={onNotifClick}>
        <Icon name="bell" size={18} />
        {notifCount > 0 && <span className="icon-btn-badge">{notifCount}</span>}
      </button>
    </div>
  </header>
);

window.Sidebar = Sidebar;
window.TopBar = TopBar;
