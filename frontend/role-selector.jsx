// Pantalla de selección de rol — entrada al prototipo

const RoleSelector = ({ onSelect }) => {
  return (
    <div className="role-screen">
      <div className="role-bg" />
      <div className="role-content">
        <div className="role-brand">
          <div className="role-brand-mark">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
              <path d="M3 17l9-14 9 14H3z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
              <path d="M8 17l4-6 4 6" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
            </svg>
          </div>
          <div>
            <div className="role-brand-name">Acquira</div>
            <div className="role-brand-sub">Holding Norte · Sistema de adquisiciones</div>
          </div>
        </div>
        <h1 className="role-title">¿Con qué rol quieres entrar?</h1>
        <p className="role-sub">Este prototipo te permite probar la experiencia desde dos puntos de vista del proceso.</p>

        <div className="role-grid">
          <button className="role-card" onClick={() => onSelect('solicitante')}>
            <div className="role-card-icon role-icon-solicitante">
              <Icon name="edit" size={22} />
            </div>
            <div className="role-card-name">Solicitante</div>
            <div className="role-card-cargo">Jefa de Operaciones</div>
            <div className="role-card-desc">Genera solicitudes de pedido y hace seguimiento al estado de cada una hasta el cierre.</div>
            <div className="role-card-user">
              <Avatar initials="CP" size={26} />
              <div>
                <div className="role-user-name">Carolina Pérez</div>
                <div className="role-user-mail">cperez@holding-norte.cl</div>
              </div>
            </div>
            <div className="role-card-cta">
              Entrar como solicitante <Icon name="chevronRight" size={14} />
            </div>
          </button>

          <button className="role-card role-card-featured" onClick={() => onSelect('aprobador')}>
            <div className="role-card-badge">Nuevo</div>
            <div className="role-card-icon role-icon-aprobador">
              <Icon name="check" size={22} />
            </div>
            <div className="role-card-name">Jefe directo</div>
            <div className="role-card-cargo">Gerente de Área — Operaciones</div>
            <div className="role-card-desc">Recibe solicitudes de su equipo, valida y decide si aprueba, rechaza o solicita cambios.</div>
            <div className="role-card-user">
              <Avatar initials="MR" size={26} color="#1d4ed8" />
              <div>
                <div className="role-user-name">Marco Riquelme</div>
                <div className="role-user-mail">mriquelme@holding-norte.cl</div>
              </div>
            </div>
            <div className="role-card-cta">
              Entrar como aprobador <Icon name="chevronRight" size={14} />
            </div>
          </button>
        </div>

        <div className="role-foot">
          <Icon name="info" size={13} />
          <span>Puedes cambiar de rol en cualquier momento desde el menú de usuario.</span>
        </div>
      </div>
    </div>
  );
};

window.RoleSelector = RoleSelector;
