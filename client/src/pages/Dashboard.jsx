import { useMemo, useEffect, useState } from 'react'
import QuickActionsRow from '../components/dashboard/QuickActionsRow'
import SubscriptionStatusCard from '../components/dashboard/SubscriptionStatusCard'
import CredibilityScoreCard from '../components/dashboard/CredibilityScoreCard'
import DashboardSummaryCards from '../components/dashboard/DashboardSummaryCards'
import StatLinkCard from '../components/dashboard/StatLinkCard'
import StatsChart from '../components/ui/StatsChart'
import { buildMonthlySeries } from '../utils/monthlySeries'
import { formatCurrency, formatDate } from '../utils/dashboardDisplay'
import { useAuth } from '../state/authContext'
import { purchaseOrders, invoices, defaulters, settlements, appointments, wallet, adminApi, subscriptions, legal, businessCheck } from '../services/api/apiClient'
import { Link } from 'react-router-dom'
import EditPOModal from '../components/po/EditPOModal'
import PurchaseOrders from './PurchaseOrders'
import RoleDashboard from './roles/RoleDashboard'
import { logActivity, ACTIONS } from '../utils/activityLogger'
import DashboardHeader from '../components/dashboard/DashboardHeader'
import DashboardRequestModals from '../components/dashboard/DashboardRequestModals'
import { useRoleFlags } from '../hooks/useRoleFlags'
import { usePlanInfo } from '../hooks/usePlanInfo'

export default function Dashboard() {
  const { user, subscription, loading } = useAuth()

  // Internal roles are handled by WorkflowDashboard
  // if (role === 'OPERATIONS' || role === 'OPERATION' || role === 'FINANCIAL' || role === 'FINANCE' || role === 'LEGAL') { 
  //   return <RoleDashboard /> 
  // }

  const { isCompanyAdmin, isUser, isMasterAdmin, isFinancial, isOperations, isLegal, isInternal } = useRoleFlags(user)

  const [stats, setStats] = useState({
    purchaseOrders: 0,
    settlements: 0,
    appointments: 0,
    wallet: 0,
  })
  const [recentActivity, setRecentActivity] = useState([])
  const [dueReminders, setDueReminders] = useState([])
  const [loadingData, setLoadingData] = useState(true)
  const [purchaseRows, setPurchaseRows] = useState([])
  const [allDefaulters, setAllDefaulters] = useState([])
  const [purchaseLoading, setPurchaseLoading] = useState(false)
  const [editingPO, setEditingPO] = useState(null)
  const [showBizRequest, setShowBizRequest] = useState(false)
  const [showSupportRequest, setShowSupportRequest] = useState(false)

  useEffect(() => {
    if (user) {
      logActivity(ACTIONS.VIEW_DASHBOARD) 
      fetchDashboardData()
      loadPurchaseHistory()
    }
  }, [user])

  const fetchDashboardData = async () => {
    setLoadingData(true)
    try {
      // Use longer timeouts for dashboard summary stats
      const opt = { timeout: 20000 }
      const [posRes, invoicesRes, defaultersRes, settlementsRes, appointmentsRes, remindersRes, walletRes] = await Promise.all([
        purchaseOrders.list(1, 10, false, opt),
        invoices.list({ limit: 10 }, opt),
        defaulters.list(1, 10, opt),
        settlements.list(1, 10, opt),
        appointments.list(null, opt),
        invoices.getDueReminders(opt),
        wallet.getBalance(opt),
      ])

      // Set stats
      setStats({
        purchaseOrders: posRes.ok ? (Array.isArray(posRes.data) ? posRes.data.length : (posRes.data?.items?.length || 0)) : 0,
        settlements: settlementsRes.ok ? (Array.isArray(settlementsRes.data) ? settlementsRes.data.length : (settlementsRes.data?.items?.length || 0)) : 0,
        appointments: appointmentsRes.ok ? (Array.isArray(appointmentsRes.data) ? appointmentsRes.data.length : 0) : 0,
        wallet: walletRes.ok ? (walletRes.data?.balance || 0) : 0,
      })
      setAllDefaulters(
        defaultersRes.ok
          ? (Array.isArray(defaultersRes.data) ? defaultersRes.data : (defaultersRes.data?.items || []))
          : []
      )

      // Build recent activity from all sources
      const activity = []

      if (posRes.ok && posRes.data?.items) {
        posRes.data.items.slice(0, 3).forEach(po => {
          activity.push({
            type: 'purchase_order',
            title: `PO: ${po.number}`,
            description: `${po.vendor_name} - ${new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(po.amount)}`,
            date: po.created_at,
            link: '/purchase-orders',
          })
        })
      }

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

  const loadPurchaseHistory = async () => {
    setPurchaseLoading(true)
    const res = await purchaseOrders.list(1, 100, true)
    if (res.ok && Array.isArray(res.data?.items)) {
      setPurchaseRows(res.data.items)
    } else if (res.ok && Array.isArray(res.data)) {
      setPurchaseRows(res.data)
    } else {
      setPurchaseRows([])
    }
    setPurchaseLoading(false)
  }

  const handleArchivePO = async (po) => {
    const res = await purchaseOrders.archive(po.id)
    if (res.ok) {
      setPurchaseRows((prev) => prev.map(r => r.id === po.id ? { ...r, is_archived: !r.is_archived } : r))
    }
  }

  const handleDeletePO = async (po) => {
    const res = await purchaseOrders.delete(po.id)
    if (res.ok) {
      setPurchaseRows((prev) => prev.filter(r => r.id !== po.id))
    }
  }

  const handleSaveEditPO = async (payload) => {
    if (!editingPO) return false
    const res = await purchaseOrders.update(editingPO.id, payload)
    if (res.ok) {
      setPurchaseRows((prev) => prev.map(r => r.id === editingPO.id ? { ...r, ...payload } : r))
      return true
    }
    return false
  }

  const poMonthlySeries = useMemo(() => buildMonthlySeries(purchaseRows, {
    getDate: (po) => po.created_at,
    getAmount: (po) => po.amount,
  }), [purchaseRows])

  // Pending PO card — derived from the already-loaded purchase order
  // history, so no extra API call. "Pending" = not yet closed/paid.
  const pendingPOs = useMemo(() => {
    const pending = purchaseRows.filter(po =>
      !po.payment_completed_at && po.status !== 'Closed' && po.status !== 'PAID'
    )
    return {
      count: pending.length,
      total_due: pending.reduce((sum, po) => sum + (Number(po.amount) || 0), 0),
    }
  }, [purchaseRows])

  // Defaulters count, scoped to cases that reference a real PO number —
  // matches the same filtering logic used on the Defaulters/Report
  // Overdue Payer pages when opened with ?context=po from this dashboard.
  const poDefaultersCount = useMemo(() => {
    const poNumbers = new Set(purchaseRows.map(po => po.po_number))
    return allDefaulters.filter(d => poNumbers.has(d.invoice_number)).length
  }, [purchaseRows, allDefaulters])

  const { planLabel, planStatus } = usePlanInfo(subscription, user)

  // formatCurrency, formatDate, getActivityIcon, and getExpiryDisplay
  // now live in utils/dashboardDisplay.js (see import above) — they were
  // previously defined identically here and in InvoiceDashboard.jsx.

  return (
    <section className="py-8 md:py-12">
      <div className="container-custom space-y-6">
        <DashboardHeader
          title="Dashboard"
          loading={loading}
          userLabel={user?.company_name || user?.email}
          walletBalance={stats.wallet}
        />

        <div className="flex flex-wrap gap-4">
          {/* All users see Purchase Orders and Invoices */}
          <>
          <StatLinkCard
              to="/purchase-orders"
              label="Purchase Orders"
              accentColor="#3B82F6"
              subtitle="View all →"
              icon="📋"
              iconBg="#EFF6FF"
              value={stats.purchaseOrders}
              loading={loadingData}
            />
          <StatLinkCard
              to="/purchase-orders"
              label="Pending PO"
              accentColor="#D97706"
              subtitle={loadingData ? 'Loading...' : `${formatCurrency(pendingPOs.total_due)} outstanding`}
              icon="⏳"
              iconBg="#FEF3C7"
              value={pendingPOs.count}
              loading={loadingData}
            />
          </>

          {/* All users see Defaulters */}
          <StatLinkCard
            to="/defaulters?context=po"
            label="Defaulters"
            accentColor="#D97706"
            subtitle="View all →"
            icon="⚠️"
            iconBg="#FEF3C7"
            value={poDefaultersCount}
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
          context="po"
          onCheckSafety={() => setShowBizRequest(true)}
          onSupportRequest={() => setShowSupportRequest(true)}
        />



        {/* Stats Chart */}
        <div>
          <StatsChart
            data={poMonthlySeries}
            title="Monthly Purchase Order Overview"
            countLabel="POs Raised"
            amountLabel="PO Value (₹)"
          />
        </div>



        {/* COMPANY ADMIN SPECIFIC SECTIONS */}
        {isCompanyAdmin && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
            <CredibilityScoreCard
              to="/credibility-index"
              subtitle="Based on your payment history and vendor reports"
            />
            <SubscriptionStatusCard
              planLabel={planLabel}
              planStatus={planStatus}
              subscription={subscription}
            />
          </div>
        )}

        {/* PO Management Table for Company Admin & Master Admin */}
        {(isCompanyAdmin || isMasterAdmin) && (
          <div className="space-y-3 mt-8">
            <div className="flex justify-between items-center">
              <h2 className="text-base font-bold text-[#0F172A] uppercase tracking-wide">Recent Purchase Orders</h2>
              <Link to="/purchase-orders" className="text-xs text-[#3B82F6] font-bold hover:underline">View All POs →</Link>
            </div>
            <div className="bg-white rounded-[16px] shadow-[0_4px_24px_rgba(30,58,138,0.08)] overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead className="bg-[#F8FAFF] text-[#0F172A] font-bold uppercase text-[11px] tracking-wide">
                  <tr>
                    <th className="px-6 py-4">PO#</th>
                    <th className="px-6 py-4">Vendor</th>
                    <th className="px-6 py-4">Amount</th>
                    <th className="px-6 py-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {purchaseRows.slice(0, 5).map((po, index) => (
                    <tr key={po.id} className="hover:bg-[#F0F4FF] transition-colors duration-150" style={{backgroundColor: index % 2 === 0 ? 'white' : '#FAFBFF'}}>
                      <td className="px-6 py-4 font-semibold text-[#1E3A8A] hover:underline cursor-pointer">{po.po_number}</td>
                      <td className="px-6 py-4 text-[#475569]">{po.vendor_name || po.vendor}</td>
                      <td className="px-6 py-4 font-semibold text-[#0F172A]">{formatCurrency(po.amount)}</td>
                      <td className="px-6 py-4">
                        <span className={`px-3 py-1 rounded-full text-[11px] font-bold ${po.status === 'Closed' ? 'bg-[#DCFCE7] text-[#16A34A]' : 'bg-[#DBEAFE] text-[#1D4ED8]'}`}>
                          {po.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {purchaseRows.length === 0 && (
                    <tr>
                      <td colSpan="4" className="px-6 py-8 text-center text-[#475569] italic">No purchase orders found. Create your first PO to see it here.</td>
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
          <PurchaseOrders />
        </div>

        {editingPO && (
          <EditPOModal
            po={editingPO}
            onClose={() => setEditingPO(null)}
            onSave={handleSaveEditPO}
          />
        )}
        <DashboardRequestModals
          showBizRequest={showBizRequest} setShowBizRequest={setShowBizRequest}
          showSupportRequest={showSupportRequest} setShowSupportRequest={setShowSupportRequest}
        />
      </div>
    </section>
  )
}
