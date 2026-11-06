import PropTypes from 'prop-types'

/**
 * Compact single-choice filter (e.g. invoice status). Buttons with
 * aria-pressed, so it works with Tab + Enter/Space out of the box.
 */
export default function SegmentedControl({ options, value, onChange, label }) {
  return (
    <div role="group" aria-label={label} className="inline-flex flex-wrap rounded-control bg-ink-100 p-0.5">
      {options.map((opt) => {
        const active = opt.value === value
        return (
          <button
            key={opt.value || 'all'}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(opt.value)}
            className={`inline-flex items-center gap-1.5 rounded-[6px] px-3 h-7 text-small font-medium transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
              ${active ? 'bg-white text-ink-900 shadow-xs' : 'text-ink-600 hover:text-ink-900'}`}
          >
            {opt.label}
            {opt.count !== undefined && (
              <span className={`tabular-nums text-caption ${active ? 'text-ink-500' : 'text-ink-400'}`}>{opt.count}</span>
            )}
          </button>
        )
      })}
    </div>
  )
}

SegmentedControl.propTypes = {
  options: PropTypes.arrayOf(PropTypes.shape({
    value: PropTypes.string.isRequired,
    label: PropTypes.node.isRequired,
    count: PropTypes.number,
  })).isRequired,
  value: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
  label: PropTypes.string.isRequired,
}
