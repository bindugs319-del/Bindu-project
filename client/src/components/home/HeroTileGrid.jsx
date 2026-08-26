import { Link } from 'react-router-dom'

/**
 * The translucent "quick link" tile grid used in the homepage hero
 * (Partners Credit Overdue Report / Payment Follow-ups / etc). Extracted
 * out of HeroSection.jsx so it can be reused inside other dark-gradient
 * hero sections (Services, Solutions) with their own tile lists.
 *
 * Only meant to sit on the same dark blue gradient background as the
 * homepage hero — the glass effect (bg-white/10 + backdrop-blur) needs
 * a dark background behind it to read correctly.
 */
export default function HeroTileGrid({ tiles, columns = 'grid-cols-2 md:grid-cols-3' }) {
  return (
    <div
      className={`grid ${columns} gap-4 items-stretch`}
      style={{ filter: 'drop-shadow(0 0 40px rgba(59,130,246,0.3))' }}
    >
      {tiles.map((tile) => (
        <div key={tile.title} className="group h-full">
          <Link to={tile.to} className="block h-full">
            <div className="card h-full flex flex-col justify-between bg-white/10 border border-white/20 text-white backdrop-blur-md hover:bg-white/15">
              <div className="flex items-start justify-between gap-3">
                <p className="font-semibold leading-snug text-base">{tile.title}</p>
                <span className="text-sm text-white/80 flex-shrink-0 group-hover:rotate-45 group-hover:translate-x-1 transition-all duration-300">
                  →
                </span>
              </div>
              <div className="mt-3 h-1.5 w-12 rounded-full bg-gradient-to-r from-[#1E3A8A] to-[#3B82F6] group-hover:w-full transition-all duration-300" />
            </div>
          </Link>
        </div>
      ))}
    </div>
  )
}
