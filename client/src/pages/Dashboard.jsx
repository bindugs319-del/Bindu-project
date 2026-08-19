import { useMemo, useEffect, useState } from 'react'
import QuickActions from '../components/dashboard/QuickActions'
import DashboardSummaryCards from '../components/dashboard/DashboardSummaryCards'
import StatLinkCard from '../components/dashboard/StatLinkCard'
import StatsChart from '../components/ui/StatsChart'
import { buildMonthlySeries } from '../utils/monthlySeries'
import { formatCurrency, formatDate, getExpiryDisplay } from '../utils/dashboardDisplay'
import { useAuth } from '../state/authContext'
import { purchaseOrders, invoices, defaulters, settlements, appointments, wallet, adminApi, subscriptions, legal, businessCheck } from '../services/api/apiClient'
import { Link } from 'react-router-dom'
import EditPOModal from '../components/po/EditPOModal'
import PurchaseOrders from './PurchaseOrders'
import RoleDashboard from './roles/RoleDashboard'
import { logActivity, ACTIONS } from '../utils/activityLogger'
import BusinessRequestModal from '../components/BusinessRequestModal'
import SupportRequestModal from '../components/SupportRequestModal'

export default function Dashboard() {
  const { user, subscription, loading } = useAuth()
  
  const role = String(user?.role || '').toUpperCase()

  // Internal roles are handled by WorkflowDashboard
  // if (role === 'OPERATIONS' || role === 'OPERATION' || role === 'FINANCIAL' || role === 'FINANCE' || role === 'LEGAL') { 
  //   return <RoleDashboard /> 
  // }
  
  const isCompanyAdmin = role === 'COMPANY_ADMIN'
  const isUser = role === 'USER'
  const isMasterAdmin = role === 'MASTER_ADMIN'
  const isFinancial = role === 'FINANCIAL' || role === 'FINANCE'
  const isOperations = role === 'OPERATION' || role === 'OPERATIONS'
  const isLegal = role === 'LEGAL'
  const isInternal = ['MASTER_ADMIN', 'OPERATION', 'OPERATIONS', 'FINANCIAL', 'FINANCE', 'LEGAL'].includes(role)

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

  const calculateDaysLeft = (dueDateStr, paymentWindowDays = 0) => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    
    const dueDate = new Date(dueDateStr)
    dueDate.setHours(0, 0, 0, 0)
    
    // Add payment window days to due date
    const effectiveDueDate = new Date(dueDate)
    effectiveDueDate.setDate(effectiveDueDate.getDate() + parseInt(paymentWindowDays || 0))
    
    const daysLeft = Math.floor((effectiveDueDate - today) / (1000 * 60 * 60 * 24))
    return daysLeft
  }

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

  const planLabel = useMemo(() => {    if (!subscription) return 'No Plan'
    // Check if subscription has plan, plan_id, or is the admin free plan
    if (subscription.plan) return String(subscription.plan).toUpperCase()
    if (subscription.plan_id) return String(subscription.plan_id).toUpperCase()
    const subObj = subscription.subscription
    if (subObj?.plan_id) return String(subObj.plan_id).toUpperCase()
    if (subObj?.plan) return String(subObj.plan).toUpperCase()
    return 'BASE'
  }, [subscription])

  const planStatus = useMemo(() => {
    if (user?.subscription_bypass || user?.full_access) return 'Active'
    if (!subscription) return 'Inactive'
    if (subscription.is_active) return 'Active'
    const subObj = subscription.subscription
    if (subObj?.status) return String(subObj.status).charAt(0).toUpperCase() + String(subObj.status).slice(1)
    return 'Inactive'
  }, [subscription, user])

  // formatCurrency, formatDate, getActivityIcon, and getExpiryDisplay
  // now live in utils/dashboardDisplay.js (see import above) — they were
  // previously defined identically here and in InvoiceDashboard.jsx.

  return (
    <section className="py-8 md:py-12">
      <div className="container-custom space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-xs text-gray-500">
              {loading ? 'Loading profile...' : `Welcome back, ${user?.company_name || user?.email || 'Member'}`}
            </p>
            <h1 className="text-2xl font-heading font-bold text-gray-900">Dashboard</h1>
          </div>
          
          {/* My Wallet - Slim Inline Strip */}
          <div className="flex items-center gap-3 px-4 py-2 bg-indigo-50/50 border border-indigo-100 rounded-full">
            <span className="text-xs font-medium text-indigo-700 flex items-center gap-1.5">
              💳 Wallet: <span className="font-bold">{stats.wallet}</span> pts
            </span>
            <Link to="/wallet" className="text-[11px] font-semibold text-indigo-600 hover:underline">
              Redeem →
            </Link>
          </div>
        </div>

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
        <div className="space-y-3">
          <h2 className="text-base font-bold text-[#0F172A] uppercase tracking-wide mb-3">Quick Actions</h2>
          <div className="flex flex-wrap gap-4">
            <QuickActions context="po" />
            <button
              onClick={() => setShowBizRequest(true)}
              className="flex items-center gap-3 px-5 py-4 rounded-[12px] border border-[#E2E8F0] bg-white hover:bg-[#EFF6FF] hover:border-[#3B82F6] transition-all duration-200 group"
            >
              <span className="text-2xl group-hover:text-[#3B82F6] transition-colors">🔍</span>
              <span className="text-base font-semibold text-[#0F172A] group-hover:text-[#1E3A8A]">Check Company Safety</span>
            </button>
            <button
              onClick={() => setShowSupportRequest(true)}
              className="flex items-center gap-3 px-5 py-4 rounded-[12px] border border-[#E2E8F0] bg-white hover:bg-[#EFF6FF] hover:border-[#3B82F6] transition-all duration-200 group"
            >
              <span className="text-2xl group-hover:text-[#3B82F6] transition-colors">📋</span>
              <span className="text-base font-semibold text-[#0F172A] group-hover:text-[#1E3A8A]">Support Request</span>
            </button>
          </div>
        </div>



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
            <div style={{background: 'linear-gradient(135deg, #0F172A 0%, #1E3A8A 60%, #3B82F6 100%)'}} className="rounded-[20px] p-6 text-white shadow-xl">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-lg font-bold text-white">Company Credibility Score</h3>
                  <p className="text-blue-200 text-xs">Based on your payment history and vendor reports</p>
                </div>
                <div className="bg-white/20 p-2 rounded-lg">📊</div>
              </div>
              <div className="flex items-center gap-6 mt-6">
                <div className="text-6xl font-black text-white">82</div>
                <div>
                  <div className="bg-[#F59E0B] text-[#0F172A] text-[11px] font-bold px-3 py-1 rounded-full uppercase tracking-wide">A Grade</div>
                  <div className="text-sm mt-2 text-blue-200">Risk Level: <span className="text-white font-bold">Low</span></div>
                </div>
              </div>
              <Link to="/credibility-index" className="mt-6 block text-center bg-white text-[#1E3A8A] hover:bg-[#EFF6FF] py-3 rounded-xl text-sm font-bold transition-all">
                View Full Analysis →
              </Link>
            </div>

            <div className="bg-white rounded-[20px] border border-[#E2E8F0] p-6 shadow-[0_4px_24px_rgba(30,58,138,0.08)]">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-lg font-bold text-[#0F172A]">Subscription Status</h3>
                  <p className="text-[#475569] text-xs">Your current platform plan</p>
                </div>
                <div className="bg-[#EFF6FF] p-2 rounded-lg">💎</div>
              </div>
              <div className="mt-6">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-[#475569] font-semibold">{planLabel}</span>
                  <span className={`px-3 py-1 rounded-full text-[11px] font-bold uppercase ${planStatus === 'Active' ? 'bg-[#DCFCE7] text-[#16A34A]' : 'bg-[#FEE2E2] text-[#DC2626]'}`}>
                    {planStatus}
                  </span>
                </div>
                {(() => {
                  const expiry = getExpiryDisplay(subscription)
                  return (
                    <>
                      <div className="w-full h-3 bg-[#F0F4FF] rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-[#1E3A8A] rounded-full transition-all duration-500" 
                          style={{ width: `${expiry.percent}%` }}
                        />
                      </div>
                      <p className={`text-[11px] mt-2 ${expiry.color}`}>
                        {expiry.text}
                      </p>
                    </>
                  )
                })()}
              </div>
              <Link to="/membership" className="mt-6 block text-center hover:opacity-90 py-3 rounded-[12px] text-[#0F172A] text-sm font-bold transition-all shadow-md" style={{background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)'}}>
                Upgrade Plan
              </Link>
            </div>
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
        {showBizRequest && (
          <BusinessRequestModal
            onClose={() => setShowBizRequest(false)}
            onSuccess={() => {
              setShowBizRequest(false)
            }}
          />
        )}
        {showSupportRequest && (
          <SupportRequestModal
            onClose={() => setShowSupportRequest(false)}
            onSuccess={() => {
              setShowSupportRequest(false)
            }}
          />
        )}
      </div>
    </section>
  )
}
