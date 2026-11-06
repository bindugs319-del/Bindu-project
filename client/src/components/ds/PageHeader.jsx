import PropTypes from 'prop-types'

/** The one page-header pattern for every logged-in page. */
export default function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        {eyebrow && <p className="text-overline uppercase text-ink-500">{eyebrow}</p>}
        <h1 className="text-title text-ink-900 mt-1">{title}</h1>
        {description && <p className="text-body text-ink-600 mt-1">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

PageHeader.propTypes = {
  eyebrow: PropTypes.node,
  title: PropTypes.node.isRequired,
  description: PropTypes.node,
  actions: PropTypes.node,
}
