import PropTypes from 'prop-types'

/** Base surface: white, 1px border, 12px radius. `padded={false}` for tables. */
export default function Card({ as: Tag = 'section', padded = true, className = '', children, ...rest }) {
  return (
    <Tag className={`bg-surface-card border border-ink-200 rounded-card shadow-xs ${padded ? 'p-5' : ''} ${className}`} {...rest}>
      {children}
    </Tag>
  )
}

Card.propTypes = {
  as: PropTypes.elementType,
  padded: PropTypes.bool,
  className: PropTypes.string,
  children: PropTypes.node,
}

/** Card title row: title + optional description on the left, actions on the right. */
export function CardHeader({ title, description, actions, className = '', id }) {
  return (
    <div className={`flex flex-wrap items-start justify-between gap-3 ${className}`}>
      <div className="min-w-0">
        <h2 id={id} className="text-heading text-ink-900">{title}</h2>
        {description && <p className="text-small text-ink-500 mt-0.5">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

CardHeader.propTypes = {
  title: PropTypes.node.isRequired,
  description: PropTypes.node,
  actions: PropTypes.node,
  className: PropTypes.string,
  id: PropTypes.string,
}
