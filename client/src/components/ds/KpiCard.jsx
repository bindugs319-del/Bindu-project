import PropTypes from 'prop-types'
import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'

const ACCENTS = {
  neutral: 'text-ink-500',
  warning: 'text-warning-600',
  danger: 'text-danger-500',
  success: 'text-success-600',
}

/**
 * KPI tile: label, big tabular number, one line of context. The whole tile
 * is a link when `to` is set. No coloured borders or icon bubbles — tone
 * only tints the context line when it signals something (e.g. overdue).
 */
export default function KpiCard({ label, value, context, tone = 'neutral', icon: Icon, to, loading }) {
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <p className="text-caption font-medium text-ink-600">{label}</p>
        {Icon && <Icon aria-hidden="true" className="h-4 w-4 text-ink-400" strokeWidth={2} />}
      </div>
      {loading ? (
        <div className="mt-3 space-y-2" aria-hidden="true">
          <div className="h-8 w-16 rounded skeleton-shimmer" />
          <div className="h-3 w-28 rounded skeleton-shimmer" />
        </div>
      ) : (
        <>
          <p className="mt-2 text-display text-ink-900 tabular-nums">{value}</p>
          {context && <p className={`mt-1 text-caption ${ACCENTS[tone]}`}>{context}</p>}
        </>
      )}
      {to && (
        <ArrowUpRight
          aria-hidden="true"
          className="absolute right-4 bottom-4 h-4 w-4 text-ink-300 transition-colors group-hover:text-brand-600"
        />
      )}
    </>
  )

  const cls = 'group relative block bg-surface-card border border-ink-200 rounded-card shadow-xs p-5'
  if (to) {
    return (
      <Link
        to={to}
        aria-label={`${label}: ${loading ? 'loading' : value}${context ? `, ${context}` : ''}`}
        className={`${cls} transition-colors hover:border-brand-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2`}
      >
        {body}
      </Link>
    )
  }
  return <div className={cls}>{body}</div>
}

KpiCard.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.node,
  context: PropTypes.node,
  tone: PropTypes.oneOf(['neutral', 'warning', 'danger', 'success']),
  icon: PropTypes.elementType,
  to: PropTypes.string,
  loading: PropTypes.bool,
}
