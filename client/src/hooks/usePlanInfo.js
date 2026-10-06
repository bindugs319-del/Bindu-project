import { useMemo } from 'react'

// Derives the subscription plan label and status shown on the dashboard
// cards. Previously defined identically in both Dashboard.jsx and
// InvoiceDashboard.jsx.
export function usePlanInfo(subscription, user) {
  const planLabel = useMemo(() => {
    if (!subscription) return 'No Plan'
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

  return { planLabel, planStatus }
}
