import { Routes, Route, createBrowserRouter, RouterProvider, Navigate, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import MainLayout from '../components/layout/MainLayout'
import Home from '../pages/Home'
import About from '../pages/About'
import Services from '../pages/Services'
import Solutions from '../pages/Solutions'
import Offerings from '../pages/Offerings'
import Contact from '../pages/Contact'
import Appointment from '../pages/Appointment'
import NotFound from '../pages/NotFound'

import ReportOverdue from '../pages/services/ReportOverdue'
import CreditManagement from '../pages/services/CreditManagement'
import PartnersReport from '../pages/services/PartnersReport'
import Finalization from '../pages/services/Finalization'

import B2B from '../pages/solutions/B2B'
import MSME from '../pages/solutions/MSME'
import BusinessCredit from '../pages/solutions/BusinessCredit'
import BusinessDebt from '../pages/solutions/BusinessDebt'

import AuthLanding from '../pages/auth/AuthLanding'
import Login from '../pages/auth/Login'
import Register from '../pages/auth/Register'
import ForgotPassword from '../pages/auth/ForgotPassword'
import AcceptInvite from '../pages/auth/AcceptInvite'
import Dashboard from '../pages/Dashboard'
import Membership from '../pages/Membership'
import Wallet from '../pages/Wallet'
import PurchaseOrders from '../pages/PurchaseOrders'
import Invoices from '../pages/Invoices'
import CompanyProfile from '../pages/CompanyProfile'
import Defaulters from '../pages/Defaulters'
import ReportDefaulter from '../pages/ReportDefaulter'
import CreditReports from '../pages/CreditReports'
import Settlement from '../pages/Settlement'
import Privacy from '../pages/Privacy'
import Terms from '../pages/Terms'
import Account from '../pages/account/Account'
import TeamManagement from '../pages/admin/TeamManagement'
import POReminderConfig from '../pages/admin/POReminderConfig'
import AdminSettings from '../pages/AdminSettings';
import RoleDashboard from '../pages/roles/RoleDashboard'
import RoleRoute from '../components/RoleRoute'
import { useAuth } from '../state/authContext'
import CredibilityIndex from '../pages/CredibilityIndex'
import CredibilityDetail from '../pages/CredibilityDetail'
import InvCredibilityIndex from '../pages/InvCredibilityIndex'
import InvCredibilityDetail from '../pages/InvCredibilityDetail'
import InvoiceDashboard from '../pages/InvoiceDashboard'
import POApprovals from '../pages/admin/POApprovals'
import DefaulterApprovals from '../pages/admin/DefaulterApprovals'
import ActivityLogs from '../pages/admin/ActivityLogs'
import Payments from '../pages/admin/Payments'
import UserProfile from '../pages/UserProfile'

function DashboardRedirect() {
  const { user, isAuthenticated, loading } = useAuth()
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!isAuthenticated || !user) return <Navigate to="/auth/login" replace />
  
  const role = String(user.role || '').toUpperCase()
  
  if (role === 'MASTER_ADMIN') {
    return <Navigate to="/dashboard/admin" replace />
  } else if (role === 'FINANCIAL' || role === 'FINANCE') {
    return <Navigate to="/dashboard/financial" replace />
  } else if (role === 'OPERATION' || role === 'OPERATIONS') {
    return <Navigate to="/dashboard/operation" replace />
  } else if (role === 'LEGAL') {
    return <Navigate to="/dashboard/legal" replace />
  } else {
    return <Navigate to="/dashboard/user" replace />
  }
}

export default function AppRoutes() {
  const location = useLocation()

  // Reset scroll position to the top on every route change. Without
  // this, React Router preserves the browser's current scroll offset
  // across navigations (it's an SPA, not a real page load), so
  // clicking a link like "Book Appointment" from partway down a long
  // page — e.g. the CTASection at the bottom of Home — would land on
  // the new page still scrolled down, instead of at its top.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [location.pathname])

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.3 }}
      >
        <Routes location={location}>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<Home />} />
            <Route path="about" element={<About />} />
            <Route path="services" element={<Services />} />
            <Route path="services/report-overdue" element={<ReportOverdue />} />
            <Route path="services/credit-management" element={<CreditManagement />} />
            <Route path="services/partners-report" element={<PartnersReport />} />
            <Route path="services/finalization" element={<Finalization />} />

            <Route path="solutions" element={<Solutions />} />
            <Route path="solutions/b2b" element={<B2B />} />
            <Route path="solutions/msme" element={<MSME />} />
            <Route path="solutions/business-credit" element={<BusinessCredit />} />
            <Route path="solutions/business-debt" element={<BusinessDebt />} />

            <Route path="offerings" element={<Offerings />} />
            <Route path="contact" element={<Contact />} />
            <Route path="appointment" element={<Appointment />} />
            <Route
              path="account"
              element={(
                <RoleRoute>
                  <Account />
                </RoleRoute>
              )}
            />
            <Route
              path="dashboard"
              element={(
                <RoleRoute>
                  <DashboardRedirect />
                </RoleRoute>
              )}
            />
            <Route
              path="dashboard/admin"
              element={(
                <RoleRoute allowedRoles={['MASTER_ADMIN']}>
                  <RoleDashboard />
                </RoleRoute>
              )}
            />
            <Route
              path="dashboard/financial"
              element={(
                <RoleRoute allowedRoles={['FINANCIAL', 'FINANCE']}>
                  <RoleDashboard />
                </RoleRoute>
              )}
            />
            <Route
              path="dashboard/operation"
              element={(
                <RoleRoute allowedRoles={['OPERATION', 'OPERATIONS']}>
                  <RoleDashboard />
                </RoleRoute>
              )}
            />
            <Route
              path="dashboard/legal"
              element={(
                <RoleRoute allowedRoles={['LEGAL']}>
                  <RoleDashboard />
                </RoleRoute>
              )}
            />
            <Route
              path="dashboard/user"
              element={(
                <RoleRoute allowedRoles={['USER', 'COMPANY_ADMIN']} requiredFeature="PO_MANAGEMENT">
                  <Dashboard />
                </RoleRoute>
              )}
            />
            <Route
              path="invoice-dashboard"
              element={(
                <RoleRoute requiredFeature="CREDIT_MANAGEMENT">
                  <InvoiceDashboard />
                </RoleRoute>
              )}
            />
            <Route
              path="membership"
              element={(
                <RoleRoute>
                  <Membership />
                </RoleRoute>
              )}
            />
            <Route
              path="wallet"
              element={(
                <RoleRoute>
                  <Wallet />
                </RoleRoute>
              )}
            />
            <Route
              path="/admin/team"
              element={(
                <RoleRoute allowedRoles={['MASTER_ADMIN', 'COMPANY_ADMIN', 'OPERATION', 'OPERATIONS', 'FINANCIAL', 'FINANCE', 'LEGAL']}>
                  <TeamManagement />
                </RoleRoute>
              )}
            />
            <Route
              path="/admin/reminders"
              element={(
                <RoleRoute allowedRoles={['MASTER_ADMIN', 'COMPANY_ADMIN']}>
                  <POReminderConfig />
                </RoleRoute>
              )}
            />

              <Route
                path="/admin/settings"
                element={(
                  <RoleRoute allowedRoles={['MASTER_ADMIN']}>
                    <AdminSettings />
                  </RoleRoute>
                )}
              />

              <Route
                path="/admin/po-approvals"
                element={(
                  <RoleRoute allowedRoles={['MASTER_ADMIN', 'FINANCIAL']}>
                    <POApprovals />
                  </RoleRoute>
                )}
              />

              <Route
                path="/admin/defaulter-approvals"
                element={(
                  <RoleRoute allowedRoles={['MASTER_ADMIN', 'COMPANY_ADMIN', 'OPERATION', 'LEGAL', 'FINANCIAL']}>
                    <DefaulterApprovals />
                  </RoleRoute>
                )}
              />

              <Route
                path="/admin/activity"
                element={(
                  <RoleRoute allowedRoles={['MASTER_ADMIN', 'COMPANY_ADMIN', 'OPERATION', 'OPERATIONS', 'FINANCIAL', 'FINANCE', 'LEGAL']}>
                    <ActivityLogs />
                  </RoleRoute>
                )}
              />

              <Route
                path="/admin/payments"
                element={(
                  <RoleRoute allowedRoles={['MASTER_ADMIN', 'OPERATIONS', 'FINANCIAL']}>
                    <Payments />
                  </RoleRoute>
                )}
              />
              <Route
                path="/admin/users/:userId"
                element={(
                  <RoleRoute allowedRoles={['MASTER_ADMIN', 'OPERATION', 'OPERATIONS', 'LEGAL', 'FINANCIAL', 'FINANCE']}>
                    <UserProfile />
                  </RoleRoute>
                )}
              />

            <Route
              path="credibility-index"
              element={(
                <RoleRoute requiredFeature="CREDIBILITY_VIEW">
                  <CredibilityIndex />
                </RoleRoute>
              )}
            />
            <Route
              path="credibility-index/:companyId"
              element={<CredibilityDetail />}
            />
            <Route
              path="inv-credibility-index"
              element={(
                <RoleRoute requiredFeature="CREDIBILITY_VIEW">
                  <InvCredibilityIndex />
                </RoleRoute>
              )}
            />
            <Route
              path="inv-credibility-index/:companyId"
              element={<InvCredibilityDetail />}
            />
            <Route
              path="purchase-orders"
              element={(
                <RoleRoute requiredFeature="PO_MANAGEMENT">
                  <PurchaseOrders />
                </RoleRoute>
              )}
            />
            <Route
              path="invoices"
              element={(
                <RoleRoute requiredFeature="CREDIT_MANAGEMENT">
                  <Invoices />
                </RoleRoute>
              )}
            />
            <Route path="company-profile" element={<CompanyProfile />} />
            <Route path="defaulters" element={<Defaulters />} />
            <Route
              path="defaulters/report"
              element={(
                <RoleRoute requiredFeature="REPORT_OVERDUE">
                  <ReportDefaulter />
                </RoleRoute>
              )}
            />
            <Route
              path="credit-reports"
              element={(
                <RoleRoute requiredFeature="CREDIT_REPORTS">
                  <CreditReports />
                </RoleRoute>
              )}
            />
            <Route
              path="settlement"
              element={(
                <RoleRoute requiredFeature="SETTLEMENT">
                  <Settlement />
                </RoleRoute>
              )}
            />
            <Route path="privacy" element={<Privacy />} />
            <Route path="terms" element={<Terms />} />

            <Route path="auth" element={<AuthLanding />} />
            <Route path="auth/login" element={<Login />} />
            <Route path="auth/register" element={<Register />} />
            <Route path="auth/forgot-password" element={<ForgotPassword />} />
            <Route path="accept-invite" element={<AcceptInvite />} />

            <Route path="*" element={<NotFound />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  )
}
