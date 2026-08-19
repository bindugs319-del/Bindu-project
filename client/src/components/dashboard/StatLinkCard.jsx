import { Link } from 'react-router-dom'

/**
 * The colored, icon + count "stat" card used across Dashboard.jsx and
 * InvoiceDashboard.jsx (Purchase Orders / Invoices / Pending POs /
 * Pending Invoices / etc). Each usage only differed by link target,
 * accent color, icon, label text, and the value shown — extracted here
 * to remove that duplication.
 */
export default function StatLinkCard({
  to,
  label,
  accentColor,
  subtitle,
  icon,
  iconBg,
  value,
  loading,
}) {
  return (
    <Link
      to={to}
      className="flex items-center justify-between px-6 py-5 rounded-[16px] shadow-[0_4px_24px_rgba(30,58,138,0.08)] bg-white border-l-[4px] hover:shadow-[0_8px_32px_rgba(30,58,138,0.12)] transition-all group w-full sm:w-auto"
      style={{ borderLeftColor: accentColor }}
    >
      <div className="flex flex-col">
        <p className="text-xs text-[#475569]">{label}</p>
        <span className="text-xs group-hover:underline inline-block" style={{ color: accentColor }}>
          {subtitle}
        </span>
      </div>
      <div className="flex items-center gap-3">
        {loading ? (
          <div className="w-10 h-10 rounded-full skeleton-shimmer" />
        ) : (
          <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: iconBg }}>
            <span className="text-lg" style={{ color: accentColor }}>{icon}</span>
          </div>
        )}
        {loading ? (
          <div className="w-12 h-8 rounded skeleton-shimmer" />
        ) : (
          <p className="text-2xl font-bold text-[#0F172A]">{value}</p>
        )}
      </div>
    </Link>
  )
}
