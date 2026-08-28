import PropTypes from 'prop-types'
import HeroTileGrid from '../home/HeroTileGrid'

/**
 * The dark-gradient hero banner (icon, title, orange underline, subtitle,
 * and an optional "explore other pages" tile row) shared by all 8
 * Services/Solutions sub-pages. Extracted because copy-pasting this same
 * ~15-line block into each of the 8 pages (rather than parameterizing a
 * shared component) reintroduced the exact kind of duplication that had
 * already been cleaned up elsewhere in this codebase.
 */
export default function PageHero({ icon, title, subtitle, exploreLabel, tiles }) {
  return (
    <section
      className="py-20 px-4 text-white text-center"
      style={{ background: 'linear-gradient(135deg, #0F172A 0%, #1E3A8A 60%, #1D4ED8 100%)' }}
    >
      <div className="max-w-5xl mx-auto">
        <div className="text-4xl mb-3">{icon}</div>
        <h1 className="text-4xl md:text-5xl font-bold mb-4">{title}</h1>
        <div className="mx-auto mb-4" style={{ width: '48px', height: '3px', backgroundColor: '#F59E0B' }}></div>
        <p className="text-[#93C5FD] text-lg max-w-3xl mx-auto">{subtitle}</p>

        {tiles && tiles.length > 0 && (
          <div className="mt-10 text-left">
            <p className="text-white/70 text-xs uppercase tracking-wide font-bold mb-3 text-center sm:text-left">
              {exploreLabel}
            </p>
            <HeroTileGrid columns="grid-cols-1 sm:grid-cols-3" tiles={tiles} />
          </div>
        )}
      </div>
    </section>
  )
}

PageHero.propTypes = {
  icon: PropTypes.node.isRequired,
  title: PropTypes.string.isRequired,
  subtitle: PropTypes.string.isRequired,
  exploreLabel: PropTypes.string,
  tiles: PropTypes.arrayOf(
    PropTypes.shape({
      title: PropTypes.string.isRequired,
      to: PropTypes.string.isRequired,
    })
  ),
}
