import PropTypes from 'prop-types'

/** Centered empty / error message with an optional action. */
export default function EmptyState({ icon: Icon, title, description, action, compact = false }) {
  return (
    <div className={`flex flex-col items-center justify-center text-center ${compact ? 'py-6 px-4' : 'py-12 px-6'}`}>
      {Icon && (
        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-ink-100">
          <Icon aria-hidden="true" className="h-5 w-5 text-ink-500" strokeWidth={2} />
        </div>
      )}
      <p className="text-body font-medium text-ink-900">{title}</p>
      {description && <p className="mt-1 max-w-sm text-small text-ink-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

EmptyState.propTypes = {
  icon: PropTypes.elementType,
  title: PropTypes.node.isRequired,
  description: PropTypes.node,
  action: PropTypes.node,
  compact: PropTypes.bool,
}
