import { Link } from 'react-router-dom'

// The welcome-text + wallet-strip header shared by Dashboard.jsx and
// InvoiceDashboard.jsx, which previously had identical copies of this
// markup apart from the page title.
export default function DashboardHeader({ title, loading, userLabel, walletBalance }) {
  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div className="flex flex-col gap-1">
        <p className="text-xs text-gray-500">
          {loading ? 'Loading profile...' : `Welcome back, ${userLabel || 'Member'}`}
        </p>
        <h1 className="text-2xl font-heading font-bold text-gray-900">{title}</h1>
      </div>

      {/* My Wallet - Slim Inline Strip */}
      <div className="flex items-center gap-3 px-4 py-2 bg-indigo-50/50 border border-indigo-100 rounded-full">
        <span className="text-xs font-medium text-indigo-700 flex items-center gap-1.5">
          💳 Wallet: <span className="font-bold">{walletBalance}</span> pts
        </span>
        <Link to="/wallet" className="text-[11px] font-semibold text-indigo-600 hover:underline">
          Redeem →
        </Link>
      </div>
    </div>
  )
}
