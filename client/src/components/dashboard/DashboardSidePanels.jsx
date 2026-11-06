import PropTypes from 'prop-types'
import { Link } from 'react-router-dom'
import {
  Bell, CalendarClock, History, FileText, AlertTriangle, ClipboardList, BarChart3, CheckCircle2, CreditCard, ArrowRight,
} from 'lucide-react'
import Card, { CardHeader } from '../ds/Card'
import Badge from '../ds/Badge'
import EmptyState from '../ds/EmptyState'
import { useDashboardNotifications } from './NotificationsPanel'
import { getExpiryDisplay } from '../../utils/dashboardDisplay'
import { formatINR, formatDateShort } from '../../utils/format'

const ACTIVITY_ICONS = {
  purchase_order: ClipboardList,
  invoice: FileText,
  defaulter: AlertTriangle,
  credit_report: BarChart3,
  settlement: CheckCircle2,
}

function ListSkeleton() {
  return (
    <div className="mt-4 space-y-3" aria-hidden="true">
      {[0, 1, 2].map((i) => <div key={i} className="h-9 rounded-control skeleton-shimmer" />)}
    </div>
  )
}

export function DueRemindersCard({ loading, dueReminders }) {
  return (
    <Card>
      <CardHeader
        title="Payments due"
        actions={dueReminders.length > 0 && <Link to="/invoices" className="text-small font-medium text-brand-600 hover:underline">View all</Link>}
      />
      {loading && <ListSkeleton />}
      {!loading && dueReminders.length === 0 && <EmptyState compact icon={CalendarClock} title="No payments due" description="Invoices nearing their due date will show here." />}
      {!loading && dueReminders.length > 0 && (
        <ul className="mt-3 divide-y divide-ink-100">
          {dueReminders.slice(0, 4).map((inv) => (
            <li key={inv.id} className="flex items-center justify-between gap-3 py-2.5">
              <div className="min-w-0">
                <p className="truncate text-small font-medium text-ink-900">{inv.invoice_number}</p>
                <p className="text-caption text-ink-500">Due {formatDateShort(inv.due_date)}</p>
              </div>
              <span className="text-small font-semibold text-ink-900 tabular-nums">{formatINR(inv.amount)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

DueRemindersCard.propTypes = { loading: PropTypes.bool, dueReminders: PropTypes.array.isRequired }

export function RecentActivityCard({ loading, recentActivity }) {
  return (
    <Card>
      <CardHeader title="Recent activity" />
      {loading && <ListSkeleton />}
      {!loading && recentActivity.length === 0 && <EmptyState compact icon={History} title="No recent activity" />}
      {!loading && recentActivity.length > 0 && (
        <ul className="mt-3 space-y-1">
          {recentActivity.slice(0, 5).map((a) => {
            const Icon = ACTIVITY_ICONS[a.type] || FileText
            return (
              <li key={`${a.type}-${a.title}`}>
                <Link to={a.link} className="flex items-start gap-3 rounded-control p-2 -mx-2 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
                  <Icon aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" />
                  <span className="min-w-0">
                    <span className="block truncate text-small font-medium text-ink-900">{a.title}</span>
                    <span className="block truncate text-caption text-ink-500">{a.description}</span>
                  </span>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

RecentActivityCard.propTypes = { loading: PropTypes.bool, recentActivity: PropTypes.array.isRequired }

export function NotificationsCard({ dueReminders }) {
  const items = useDashboardNotifications(dueReminders)
  return (
    <Card>
      <CardHeader title="Notifications" actions={items.length > 0 && <Badge tone="info" dot={false}>{items.length} new</Badge>} />
      {items.length === 0 ? (
        <EmptyState compact icon={Bell} title="You’re all caught up" />
      ) : (
        <ul className="mt-3 space-y-2">
          {items.slice(0, 3).map((n) => (
            <li key={n.id} className="flex items-start gap-2 text-small text-ink-700">
              <span aria-hidden="true" className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${n.priority === 'high' ? 'bg-danger-500' : 'bg-warning-500'}`} />
              {n.text}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

NotificationsCard.propTypes = { dueReminders: PropTypes.array.isRequired }

export function PlanCard({ planLabel, planStatus, subscription }) {
  const expiry = getExpiryDisplay(subscription)
  const active = planStatus === 'Active'
  // getExpiryDisplay returns a placeholder 50% when it has no dates; don't draw a fake bar.
  const showProgress = typeof expiry.percent === 'number' && expiry.text !== 'No expiry info'
  return (
    <Card>
      <CardHeader
        title="Membership"
        actions={<Badge tone={active ? 'success' : 'danger'}>{planStatus}</Badge>}
      />
      <div className="mt-3 flex items-center gap-3">
        <CreditCard aria-hidden="true" className="h-4 w-4 text-ink-400" />
        <p className="text-body font-medium text-ink-900">{planLabel}</p>
      </div>
      {showProgress && (
        <progress
          value={Math.round(expiry.percent)}
          max={100}
          aria-label="Plan period used"
          className="mt-3 block h-1.5 w-full appearance-none overflow-hidden rounded-full bg-ink-100
            [&::-webkit-progress-bar]:bg-ink-100 [&::-webkit-progress-value]:rounded-full [&::-webkit-progress-value]:bg-brand-600
            [&::-moz-progress-bar]:rounded-full [&::-moz-progress-bar]:bg-brand-600"
        />
      )}
      <p className="mt-2 text-caption text-ink-500">{expiry.text}</p>
      <Link to="/membership" className="mt-3 inline-flex items-center gap-1 text-small font-medium text-brand-600 hover:underline">
        Manage plan <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
      </Link>
    </Card>
  )
}

PlanCard.propTypes = { planLabel: PropTypes.string, planStatus: PropTypes.string, subscription: PropTypes.object }
