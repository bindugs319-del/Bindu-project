import { Link } from 'react-router-dom'
import NotificationsPanel from './NotificationsPanel'
import { formatCurrency, formatDate, getActivityIcon, getExpiryDisplay } from '../../utils/dashboardDisplay'

/**
 * The row of 4 small summary cards (Recent Activity, Due Reminders,
 * Notifications, Subscription) shown at the bottom of both Dashboard.jsx
 * and InvoiceDashboard.jsx. Extracted because it was identical,
 * copy-pasted markup in both pages.
 */
export default function DashboardSummaryCards({
  loadingData,
  recentActivity,
  dueReminders,
  planLabel,
  planStatus,
  subscription,
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
      {/* Recent Activity */}
      <div className="flex items-center gap-4 px-6 py-5 rounded-[16px] shadow-[0_4px_24px_rgba(30,58,138,0.08)] bg-white border-l-[4px] border-l-[#3B82F6] hover:shadow-[0_8px_32px_rgba(30,58,138,0.12)] transition-shadow">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm">🕐</span>
            <h2 className="text-xs text-[#475569] uppercase font-semibold">Recent Activity</h2>
          </div>
          {loadingData && (
            <p className="text-xs text-[#475569]">Loading activity...</p>
          )}
          {!loadingData && recentActivity.length === 0 && (
            <p className="text-xs text-[#475569] py-1">No recent activity</p>
          )}
          {!loadingData && recentActivity.length > 0 && (
            <div className="space-y-1 overflow-y-auto max-h-24 pr-1">
              {recentActivity.slice(0, 3).map((activity) => (
                <Link
                  key={`${activity.type}-${activity.title}`}
                  to={activity.link}
                  className="flex items-start gap-2 p-1 rounded hover:bg-[#F0F4FF] transition-colors"
                >
                  <span className="text-sm">{getActivityIcon(activity.type)}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] font-semibold text-[#0F172A] truncate">{activity.title}</p>
                    <p className="text-[9px] text-[#475569] truncate">{activity.description}</p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Due Reminders */}
      <div className="flex items-center gap-4 px-6 py-5 rounded-[16px] shadow-[0_4px_24px_rgba(30,58,138,0.08)] bg-white border-l-[4px] border-l-[#D97706] hover:shadow-[0_8px_32px_rgba(30,58,138,0.12)] transition-shadow">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm">🔔</span>
            <h2 className="text-xs text-[#475569] uppercase font-semibold">Due Reminders</h2>
          </div>
          {loadingData && (
            <p className="text-xs text-[#475569]">Loading...</p>
          )}
          {!loadingData && dueReminders.length === 0 && (
            <p className="text-xs text-[#475569] py-1">No reminders due</p>
          )}
          {!loadingData && dueReminders.length > 0 && (
            <div className="space-y-1 overflow-y-auto max-h-24 pr-1">
              {dueReminders.slice(0, 2).map((invoice) => (
                <div key={invoice.id} className="p-1 bg-[#FEF3C7]/50 border border-[#F59E0B]/30 rounded">
                  <p className="text-[10px] font-semibold text-[#0F172A] truncate">{invoice.invoice_number}</p>
                  <div className="flex justify-between items-center mt-0.5">
                    <p className="text-[9px] font-bold text-[#D97706]">
                      {formatCurrency(invoice.amount)}
                    </p>
                    <p className="text-[8px] text-[#475569]">Due: {formatDate(invoice.due_date)}</p>
                  </div>
                </div>
              ))}
              <Link
                to="/invoices"
                className="text-[9px] text-[#3B82F6] hover:underline inline-block"
              >
                View all →
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Notifications */}
      <NotificationsPanel dueReminders={dueReminders} />

      {/* Plan Info */}
      <div className="flex items-center gap-4 px-6 py-5 rounded-[16px] shadow-[0_4px_24px_rgba(30,58,138,0.08)] bg-white border-l-[4px] border-l-[#1E3A8A] hover:shadow-[0_8px_32px_rgba(30,58,138,0.12)] transition-shadow">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm">💳</span>
            <h2 className="text-xs text-[#475569] uppercase font-semibold">Subscription</h2>
          </div>
          <div className="flex flex-col gap-2">
            <div className="flex justify-between items-center">
              <span className="text-xs font-medium text-[#0F172A]">{planLabel}</span>
              <span className={`px-3 py-1 rounded-full text-[11px] font-bold uppercase ${planStatus === 'Active' ? 'bg-[#DCFCE7] text-[#16A34A]' : 'bg-[#FEE2E2] text-[#DC2626]'}`}>
                {planStatus}
              </span>
            </div>
            {(() => {
              const expiry = getExpiryDisplay(subscription)
              return (
                <p className={`text-[9px] ${expiry.color}`}>
                  {expiry.text}
                </p>
              )
            })()}
            <Link to="/membership" className="inline-flex items-center justify-center bg-[#F0F4FF] border border-[#E2E8F0] text-[#1E3A8A] py-2 rounded text-[10px] font-semibold hover:bg-[#EFF6FF] transition-colors">
              Manage Plan
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
