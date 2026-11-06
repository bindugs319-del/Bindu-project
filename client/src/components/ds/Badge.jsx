import PropTypes from 'prop-types'

const TONES = {
  neutral: 'bg-ink-100 text-ink-700 ring-ink-200',
  info: 'bg-brand-50 text-brand-700 ring-brand-100',
  success: 'bg-success-50 text-success-700 ring-success-200',
  warning: 'bg-warning-50 text-warning-700 ring-warning-200',
  danger: 'bg-danger-50 text-danger-700 ring-danger-200',
}

const DOTS = {
  neutral: 'bg-ink-400',
  info: 'bg-brand-500',
  success: 'bg-success-500',
  warning: 'bg-warning-500',
  danger: 'bg-danger-500',
}

/** Status pill. Colour is never the only signal — the label always says it. */
export default function Badge({ tone = 'neutral', dot = true, children, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-caption font-medium ring-1 ring-inset ${TONES[tone]} ${className}`}>
      {dot && <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${DOTS[tone]}`} />}
      {children}
    </span>
  )
}

Badge.propTypes = {
  tone: PropTypes.oneOf(['neutral', 'info', 'success', 'warning', 'danger']),
  dot: PropTypes.bool,
  children: PropTypes.node,
  className: PropTypes.string,
}
