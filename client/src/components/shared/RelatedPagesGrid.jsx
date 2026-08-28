import { Link } from 'react-router-dom'
import PropTypes from 'prop-types'

/**
 * Small "explore the other pages in this group" link grid, shown near
 * the top of each Services/Solutions sub-page so visitors can jump
 * between sibling pages (e.g. from Report Overdue Payer straight to
 * Credit Management) without going back to the parent /services or
 * /solutions page first.
 */
export default function RelatedPagesGrid({ title, items }) {
  return (
    <div>
      <h3 className="text-sm font-bold uppercase tracking-wide text-gray-400 mb-3">{title}</h3>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {items.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="card flex items-center justify-between gap-2 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 text-primary-700 font-semibold"
          >
            <span>{item.title}</span>
            <span aria-hidden="true" className="flex-shrink-0">→</span>
          </Link>
        ))}
      </div>
    </div>
  )
}

RelatedPagesGrid.propTypes = {
  title: PropTypes.string.isRequired,
  items: PropTypes.arrayOf(
    PropTypes.shape({
      title: PropTypes.string.isRequired,
      to: PropTypes.string.isRequired,
    })
  ).isRequired,
}
