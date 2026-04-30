// Componentes UI base — botones, inputs, badges

const Button = ({ variant = 'primary', size = 'md', icon, children, onClick, type = 'button', disabled = false, fullWidth = false, ...rest }) => {
  const cls = `btn btn-${variant} btn-${size}${fullWidth ? ' btn-full' : ''}`;
  return (
    <button type={type} className={cls} onClick={onClick} disabled={disabled} {...rest}>
      {icon && <Icon name={icon} size={size === 'sm' ? 14 : 16} />}
      {children && <span>{children}</span>}
    </button>
  );
};

const Field = ({ label, required, error, hint, children }) => (
  <div className="field">
    {label && (
      <label className="field-label">
        {label}
        {required && <span className="field-req">*</span>}
      </label>
    )}
    {children}
    {hint && !error && <div className="field-hint">{hint}</div>}
    {error && <div className="field-error">{error}</div>}
  </div>
);

const Input = React.forwardRef(({ error, ...props }, ref) => (
  <input ref={ref} className={`input${error ? ' input-error' : ''}`} {...props} />
));

const Textarea = ({ error, rows = 4, ...props }) => (
  <textarea className={`textarea${error ? ' input-error' : ''}`} rows={rows} {...props} />
);

const Select = ({ error, children, ...props }) => (
  <div className={`select-wrap${error ? ' input-error' : ''}`}>
    <select className="select" {...props}>{children}</select>
    <Icon name="chevronDown" size={16} className="select-chevron" />
  </div>
);

const Badge = ({ variant = 'neutral', icon, children, size = 'md' }) => (
  <span className={`badge badge-${variant} badge-${size}`}>
    {icon && <Icon name={icon} size={size === 'sm' ? 11 : 12} />}
    {children}
  </span>
);

const StatusBadge = ({ estadoId }) => {
  const estado = ESTADOS.find((e) => e.id === estadoId);
  if (!estado) return null;
  const variantMap = {
    borrador: 'neutral', solicitada: 'blue', revision: 'amber',
    aprobada: 'emerald', cotizada: 'violet', oc: 'violet',
    transito: 'blue', recibida: 'emerald', facturada: 'emerald',
  };
  return (
    <Badge variant={variantMap[estadoId] || 'neutral'} icon={estado.icon}>
      {estado.label}
    </Badge>
  );
};

const Avatar = ({ initials, size = 28, color = '#1e6f5c' }) => (
  <div className="avatar" style={{ width: size, height: size, fontSize: size * 0.4, background: color }}>
    {initials}
  </div>
);

const Card = ({ children, className = '', onClick, hover = false }) => (
  <div className={`card${hover ? ' card-hover' : ''} ${className}`} onClick={onClick}>
    {children}
  </div>
);

Object.assign(window, {
  Button, Field, Input, Textarea, Select, Badge, StatusBadge, Avatar, Card,
});
