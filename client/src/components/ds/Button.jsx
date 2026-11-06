import PropTypes from 'prop-types'
import { Link } from 'react-router-dom'

const BASE =
  'inline-flex items-center justify-center gap-2 font-medium rounded-control whitespace-nowrap transition-colors ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 ' +
  'disabled:opacity-50 disabled:cursor-not-allowed'

const VARIANTS = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700 shadow-xs',
  secondary: 'bg-white text-ink-900 border border-ink-200 hover:bg-ink-50 hover:border-ink-300 shadow-xs',
  ghost: 'text-ink-700 hover:bg-ink-100 hover:text-ink-900',
  danger: 'bg-danger-500 text-white hover:bg-danger-600 shadow-xs',
}

const SIZES = {
  sm: 'h-8 px-3 text-small',
  md: 'h-9 px-4 text-body',
}

/**
 * Design-system button. Renders a <Link> when `to` is given, otherwise a
 * <button>. `icon` is a lucide-react component.
 */
export default function Button({
  variant = 'secondary', size = 'md', icon: Icon, to, className = '', children, type = 'button', ...rest
}) {
  const cls = `${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${className}`
  const content = (
    <>
      {Icon && <Icon aria-hidden="true" className={size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'} strokeWidth={2} />}
      {children}
    </>
  )
  if (to) {
    return <Link to={to} className={cls} {...rest}>{content}</Link>
  }
  return <button type={type} className={cls} {...rest}>{content}</button>
}

Button.propTypes = {
  variant: PropTypes.oneOf(['primary', 'secondary', 'ghost', 'danger']),
  size: PropTypes.oneOf(['sm', 'md']),
  icon: PropTypes.elementType,
  to: PropTypes.string,
  className: PropTypes.string,
  children: PropTypes.node,
  type: PropTypes.string,
}

const ICON_TONES = {
  neutral: 'text-ink-600 hover:bg-ink-100 hover:text-ink-900',
  brand: 'text-brand-600 hover:bg-brand-50',
  success: 'text-success-600 hover:bg-success-50',
  warning: 'text-warning-600 hover:bg-warning-50',
  danger: 'text-danger-500 hover:bg-danger-50',
}

/** Square icon-only button. `label` is required: it becomes aria-label + tooltip. */
export function IconButton({ icon: Icon, label, tone = 'neutral', className = '', children, ...rest }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-control transition-colors
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1
        disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent ${ICON_TONES[tone]} ${className}`}
      {...rest}
    >
      {children || <Icon aria-hidden="true" className="h-4 w-4" strokeWidth={2} />}
    </button>
  )
}

IconButton.propTypes = {
  icon: PropTypes.elementType,
  label: PropTypes.string.isRequired,
  tone: PropTypes.oneOf(['neutral', 'brand', 'success', 'warning', 'danger']),
  className: PropTypes.string,
  children: PropTypes.node,
}
