import { useMemo, useEffect, useState, useCallback } from 'react'
import QuickActionsRow from '../components/dashboard/QuickActionsRow'
import SubscriptionStatusCard from '../components/dashboard/SubscriptionStatusCard'
import CredibilityScoreCard from '../components/dashboard/CredibilityScoreCard'
import DashboardSummaryCards from '../components/dashboard/DashboardSummaryCards'
import StatLinkCard from '../components/dashboard/StatLinkCard'
import StatsChart from '../components/ui/StatsChart'
import { buildMonthlySeries } from '../utils/monthlySeries'
import { formatCurrency, formatDate } from '../utils/dashboardDisplay'
import { useAuth } from '../state/authContext'
import { invoices, defaulters, settlements, appointments, wallet, adminApi, subscriptions, legal, businessCheck, salesInvoices } from '../services/api/apiClient'
import { Link } from 'react-router-dom'
import Invoices from './Invoices'
import RoleDashboard from './roles/RoleDashboard'
import { logActivity, ACTIONS } from '../utils/activityLogger'
import DashboardHeader from '../components/dashboard/DashboardHeader'
import DashboardRequestModals from '../components/dashboard/DashboardRequestModals'
import { useRoleFlags } from '../hooks/useRoleFlags'
import { usePlanInfo } from '../hooks/usePlanInfo'

export default function InvoiceDashboard() {
  const { user, subscription, loading } = useAuth()

  // Internal roles are handled by WorkflowDashboard
  // if (role === 'OPERATIONS' || role === 'OPERATION' || role === 'FINANCIAL' || role === 'FINANCE' || role === 'LEGAL') { 
  //   return <RoleDashboard /> 
  // }

  const { isCompanyAdmin, isUser, isMasterAdmin, isFinancial, isOperations, isLegal, isInternal } = useRoleFlags(user)

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

  // Formats an amount in its OWN currency (e.g. "$775.80" for a USD
  // invoice) rather than always as INR — used for the Recent Invoices
  // table below, where each row should show what the invoice actually
  // says, not a forced-INR misreading of a foreign-currency amount.
  // (Aggregate figures like invoiceMonthlySeries below are a separate
  // case — those correctly convert via exchange_rate before summing.)
  const money = (value, currency = 'INR') => {
    try {
      return new Intl.NumberFormat('en-IN', { style: 'currency', currency: currency || 'INR', minimumFractionDigits: 2 }).format(Number(value) || 0)
    } catch {
      return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(Number(value) || 0)
    }
  }

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

  // formatCurrency, formatDate, getActivityIcon, and getExpiryDisplay
  // now live in utils/dashboardDisplay.js (see import above) — they were
  // previously defined identically here and in Dashboard.jsx.

  return (
    <section className="py-8 md:py-12">
      <div className="container-custom space-y-6">
        <DashboardHeader
          title="Invoice Dashboard"
          loading={loading}
          userLabel={user?.company_name || user?.email}
          walletBalance={stats.wallet}
        />

        <div className="flex flex-wrap gap-4">
          {/* All users see Invoices */}
          <>
          <StatLinkCard
              to="/invoices"
              label="Invoices"
              accentColor="#16A34A"
              subtitle="View all →"
              icon="💰"
              iconBg="#DCFCE7"
              value={stats.invoices}
              loading={loadingData}
            />
          <StatLinkCard
              to="/invoices"
              label="Pending Invoices"
              accentColor="#D97706"
              subtitle={loadingData ? 'Loading...' : `${formatCurrency(pendingInvoices.total_due)} outstanding`}
              icon="⏳"
              iconBg="#FEF3C7"
              value={pendingInvoices.count}
              loading={loadingData}
            />
          </>

          {/* All users see Defaulters */}
          <StatLinkCard
            to="/defaulters?context=invoice"
            label="Defaulters"
            accentColor="#D97706"
            subtitle="View all →"
            icon="⚠️"
            iconBg="#FEF3C7"
            value={invoiceDefaultersCount}
            loading={loadingData}
          />

          {/* Additional stats for admins */}
          <StatLinkCard
            to="/settlement"
            label="Settlements"
            accentColor="#1E3A8A"
            subtitle="View all →"
            icon="✅"
            iconBg="#EFF6FF"
            value={stats.settlements}
            loading={loadingData}
          />
        </div>

        {/* Quick Actions */}
        <QuickActionsRow
          context="invoice"
          onCheckSafety={() => setShowBizRequest(true)}
          onSupportRequest={() => setShowSupportRequest(true)}
        />



        {/* Stats Chart */}
        <div>
          <StatsChart
            data={invoiceMonthlySeries}
            title="Monthly Invoice Overview"
            countLabel="Invoices Raised"
            amountLabel="Invoice Value (₹)"
          />
        </div>



        {/* COMPANY ADMIN SPECIFIC SECTIONS */}
        {isCompanyAdmin && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
            <CredibilityScoreCard
              to="/inv-credibility-index"
              subtitle="Based on your invoice payment history and customer reports"
            />
            <SubscriptionStatusCard
              planLabel={planLabel}
              planStatus={planStatus}
              subscription={subscription}
            />
          </div>
        )}

        {/* Invoice Management Table for Company Admin & Master Admin */}
        {(isCompanyAdmin || isMasterAdmin) && (
          <div className="space-y-3 mt-8">
            <div className="flex justify-between items-center">
              <h2 className="text-base font-bold text-[#0F172A] uppercase tracking-wide">Recent Invoices</h2>
              <Link to="/invoices" className="text-xs text-[#3B82F6] font-bold hover:underline">View All Invoices →</Link>
            </div>
            <div className="bg-white rounded-[16px] shadow-[0_4px_24px_rgba(30,58,138,0.08)] overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead className="bg-[#F8FAFF] text-[#0F172A] font-bold uppercase text-[11px] tracking-wide">
                  <tr>
                    <th className="px-6 py-4">Invoice#</th>
                    <th className="px-6 py-4">Customer</th>
                    <th className="px-6 py-4">Amount</th>
                    <th className="px-6 py-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {invoiceRows.slice(0, 5).map((inv, index) => (
                    <tr key={inv.id} className="hover:bg-[#F0F4FF] transition-colors duration-150" style={{backgroundColor: index % 2 === 0 ? 'white' : '#FAFBFF'}}>
                      <td className="px-6 py-4 font-semibold text-[#1E3A8A] hover:underline cursor-pointer">{inv.invoice_number}</td>
                      <td className="px-6 py-4 text-[#475569]">{inv.counterparty_name}</td>
                      <td className="px-6 py-4 font-semibold text-[#0F172A]">{money(inv.total, inv.currency)}</td>
                      <td className="px-6 py-4">
                        <span className={`px-3 py-1 rounded-full text-[11px] font-bold ${inv.status === 'Paid' ? 'bg-[#DCFCE7] text-[#16A34A]' : 'bg-[#DBEAFE] text-[#1D4ED8]'}`}>
                          {inv.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {invoiceRows.length === 0 && (
                    <tr>
                      <td colSpan="4" className="px-6 py-8 text-center text-[#475569] italic">No invoices found. Create your first invoice to see it here.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Smaller Dashboard Cards */}
        <DashboardSummaryCards
          loadingData={loadingData}
          recentActivity={recentActivity}
          dueReminders={dueReminders}
          planLabel={planLabel}
          planStatus={planStatus}
          subscription={subscription}
        />

        <div>
          <Invoices onDataChange={loadInvoiceHistory} />
        </div>

        <DashboardRequestModals
          showBizRequest={showBizRequest} setShowBizRequest={setShowBizRequest}
          showSupportRequest={showSupportRequest} setShowSupportRequest={setShowSupportRequest}
        />
      </div>
    </section>
  )
}