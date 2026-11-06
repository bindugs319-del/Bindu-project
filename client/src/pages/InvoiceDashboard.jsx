import { useMemo, useEffect, useState, useCallback } from 'react'
import { FileText, Clock, AlertTriangle, Handshake, Wallet, Gauge } from 'lucide-react'
import { buildMonthlySeries } from '../utils/monthlySeries'
import { formatINR, formatCount } from '../utils/format'
import { useAuth } from '../state/authContext'
import { invoices, defaulters, settlements, appointments, wallet, salesInvoices } from '../services/api/apiClient'
import Invoices from './Invoices'
import { logActivity, ACTIONS } from '../utils/activityLogger'
import DashboardRequestModals from '../components/dashboard/DashboardRequestModals'
import QuickActionBar from '../components/dashboard/QuickActionBar'
import { DueRemindersCard, NotificationsCard, RecentActivityCard, PlanCard } from '../components/dashboard/DashboardSidePanels'
import PageHeader from '../components/ds/PageHeader'
import KpiCard from '../components/ds/KpiCard'
import Card from '../components/ds/Card'
import Button from '../components/ds/Button'
import MonthlyBarChart from '../components/ds/MonthlyBarChart'
import { useRoleFlags } from '../hooks/useRoleFlags'
import { usePlanInfo } from '../hooks/usePlanInfo'
import AuthorizedClientsPanel from '../components/admin-access/AuthorizedClientsPanel'

export default function InvoiceDashboard() {
  const { user, subscription, loading } = useAuth()

  // Internal roles are handled by WorkflowDashboard
  // if (role === 'OPERATIONS' || role === 'OPERATION' || role === 'FINANCIAL' || role === 'FINANCE' || role === 'LEGAL') { 
  //   return <RoleDashboard /> 
  // }

  const { isCompanyAdmin, isMasterAdmin, isOperations } = useRoleFlags(user)

  const [stats, setStats] = useState({
    invoices: 0,
    settlements: 0,
    appointments: 0,
    wallet: 0,
  })
  const [allDefaulters, setAllDefaulters] = useState([])
  const [pendingInvoices, setPendingInvoices] = useState({ count: 0, total_due: 0 })
  const [recentActivity, setRecentActivity] = useState([])
  const [dueReminders, setDueReminders] = useState([])
  const [loadingData, setLoadingData] = useState(true)
  const [invoiceRows, setInvoiceRows] = useState([])
  const [invoiceLoading, setInvoiceLoading] = useState(false)
  const [showBizRequest, setShowBizRequest] = useState(false)
  const [showSupportRequest, setShowSupportRequest] = useState(false)

  useEffect(() => {
    if (user) {
      logActivity(ACTIONS.VIEW_DASHBOARD) 
      void fetchDashboardData()
      void loadInvoiceHistory()
    }
  }, [user])

  const fetchDashboardData = async () => {
    setLoadingData(true)
    try {
      // Use longer timeouts for dashboard summary stats
      const opt = { timeout: 20000 }
      const [invoicesRes, defaultersRes, settlementsRes, appointmentsRes, remindersRes, walletRes, pendingRes] = await Promise.all([
        invoices.list({ limit: 10 }, opt),
        defaulters.list(1, 10, opt),
        settlements.list(1, 10, opt),
        appointments.list(null, opt),
        invoices.getDueReminders(opt),
        wallet.getBalance(opt),
        salesInvoices.pendingSummary(opt),
      ])

      // Set stats
      setStats({
        invoices: invoicesRes.ok ? (Array.isArray(invoicesRes.data) ? invoicesRes.data.length : (invoicesRes.data?.invoices?.length || 0)) : 0,
        settlements: settlementsRes.ok ? (Array.isArray(settlementsRes.data) ? settlementsRes.data.length : (settlementsRes.data?.items?.length || 0)) : 0,
        appointments: appointmentsRes.ok ? (Array.isArray(appointmentsRes.data) ? appointmentsRes.data.length : 0) : 0,
        wallet: walletRes.ok ? (walletRes.data?.balance || 0) : 0,
      })
      setAllDefaulters(
        defaultersRes.ok
          ? (Array.isArray(defaultersRes.data) ? defaultersRes.data : (defaultersRes.data?.items || []))
          : []
      )

      setPendingInvoices(
        pendingRes.ok
          ? { count: pendingRes.data?.count || 0, total_due: pendingRes.data?.total_due || 0 }
          : { count: 0, total_due: 0 }
      )

      // Build recent activity from all sources
      const activity = []

      if (invoicesRes.ok && invoicesRes.data?.invoices) {
        invoicesRes.data.invoices.slice(0, 3).forEach(inv => {
          activity.push({
            type: 'invoice',
            title: `Invoice: ${inv.invoice_number}`,
            description: `${inv.counterparty_name} - ${new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(inv.amount)}`,
            date: inv.created_at,
            link: '/invoices',
          })
        })
      }

      if (defaultersRes.ok && defaultersRes.data?.items) {
        defaultersRes.data.items.slice(0, 2).forEach(def => {
          activity.push({
            type: 'defaulter',
            title: `Defaulter Case: ${def.business_name}`,
            description: `GSTIN: ${def.business_gstin}`,
            date: def.created_at,
            link: '/defaulters',
          })
        })
      }

      // Sort by date and take top 8
      activity.sort((a, b) => new Date(b.date) - new Date(a.date))
      setRecentActivity(activity.slice(0, 8))

      // Set due reminders
      if (remindersRes.ok && remindersRes.data?.invoices) {
        setDueReminders(remindersRes.data.invoices.slice(0, 5))
      }
    } catch (error) {
      console.error('Error fetching dashboard data:', error)
    }
    setLoadingData(false)
  }

  const loadInvoiceHistory = useCallback(async () => {
    setInvoiceLoading(true)
    const res = await salesInvoices.list({ limit: 100, include_archived: true })
    if (res.ok && Array.isArray(res.data?.invoices)) {
      setInvoiceRows(res.data.invoices)
    } else {
      setInvoiceRows([])
    }
    setInvoiceLoading(false)
  }, [])

  const invoiceMonthlySeries = useMemo(() => buildMonthlySeries(invoiceRows, {
    getDate: (inv) => inv.created_at,
    // Converted to INR via exchange_rate — same reasoning as
    // invoiceTotal in Invoices.jsx (an unconverted sum would treat a
    // USD invoice's total as if it were already rupees).
    getAmount: (inv) => (Number(inv.total) || 0) * (Number(inv.exchange_rate) || 1),
  }), [invoiceRows])

  // Defaulters count, scoped to cases that reference a real invoice number
  // — matches the same filtering logic used on the Defaulters/Report
  // Overdue Payer pages when opened with ?context=invoice from this dashboard.
  const invoiceDefaultersCount = useMemo(() => {
    const invoiceNumbers = new Set(invoiceRows.map(inv => inv.invoice_number))
    return allDefaulters.filter(d => invoiceNumbers.has(d.invoice_number)).length
  }, [invoiceRows, allDefaulters])

  const { planLabel, planStatus } = usePlanInfo(subscription, user)

  const welcome = loading ? 'Loading profile…' : `Welcome back, ${user?.company_name || user?.email || 'Member'}`
  const hasOutstanding = (pendingInvoices.count || 0) > 0

  return (
    <section className="min-h-screen bg-surface-page py-8">
      <div className="container-custom space-y-6">
        <PageHeader
          eyebrow="Invoices"
          title="Customer invoices"
          description={welcome}
          actions={(
            <Button to="/wallet" variant="secondary" size="sm" icon={Wallet}>
              <span className="tabular-nums">{formatCount(stats.wallet)}</span> pts · Redeem
            </Button>
          )}
        />

        {/* KPIs */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard
            to="/invoices"
            label="Invoices"
            icon={FileText}
            value={formatCount(stats.invoices)}
            context="Recently raised"
            loading={loadingData}
          />
          <KpiCard
            to="/invoices"
            label="Pending invoices"
            icon={Clock}
            value={formatCount(pendingInvoices.count)}
            context={`${formatINR(pendingInvoices.total_due)} outstanding`}
            tone={hasOutstanding ? 'warning' : 'neutral'}
            loading={loadingData}
          />
          <KpiCard
            to="/defaulters?context=invoice"
            label="Defaulters"
            icon={AlertTriangle}
            value={formatCount(invoiceDefaultersCount)}
            context="Linked to your invoices"
            tone={invoiceDefaultersCount > 0 ? 'danger' : 'neutral'}
            loading={loadingData}
          />
          <KpiCard
            to="/settlement"
            label="Settlements"
            icon={Handshake}
            value={formatCount(stats.settlements)}
            context="Recorded settlements"
            loading={loadingData}
          />
        </div>

        <QuickActionBar
          context="invoice"
          onCheckSafety={() => setShowBizRequest(true)}
          onSupportRequest={() => setShowSupportRequest(true)}
        />

        {/* Trend + side panels */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-4">
            <MonthlyBarChart
              data={invoiceMonthlySeries}
              title="Invoices by month"
              description="Invoices you raised in the last 6 months"
              countLabel="Invoices raised"
              amountLabel="Invoice value"
              loading={invoiceLoading}
            />
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <RecentActivityCard loading={loadingData} recentActivity={recentActivity} />
              <PlanCard planLabel={planLabel} planStatus={planStatus} subscription={subscription} />
            </div>
          </div>
          <div className="space-y-4">
            <DueRemindersCard loading={loadingData} dueReminders={dueReminders} />
            <NotificationsCard dueReminders={dueReminders} />
            {isCompanyAdmin && (
              <Card>
                <div className="flex items-start gap-3">
                  <Gauge aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-brand-600" />
                  <div>
                    <h2 className="text-heading text-ink-900">Company credibility</h2>
                    <p className="text-small text-ink-500">Based on your invoice payment history and customer reports.</p>
                    <Button to="/inv-credibility-index" variant="secondary" size="sm" className="mt-3">View analysis</Button>
                  </div>
                </div>
              </Card>
            )}
          </div>
        </div>

        <Invoices onDataChange={loadInvoiceHistory} embedded />

        <DashboardRequestModals
          showBizRequest={showBizRequest} setShowBizRequest={setShowBizRequest}
          showSupportRequest={showSupportRequest} setShowSupportRequest={setShowSupportRequest}
        />

        {/* Clients who granted this admin read-only view access */}
        {(isMasterAdmin || isOperations) && <AuthorizedClientsPanel />}
      </div>
    </section>
  )
}