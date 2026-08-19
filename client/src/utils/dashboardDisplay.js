/**
 * Shared formatting/display helpers used by both Dashboard.jsx and
 * InvoiceDashboard.jsx (previously copy-pasted identically in each file).
 */

/** Format a number as INR currency, e.g. "₹12,000". */
export function formatCurrency(amount) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
  }).format(amount)
}

/** Format a date string as "12 Jan 2026", or "N/A" if missing. */
export function formatDate(dateString) {
  if (!dateString) return 'N/A'
  return new Date(dateString).toLocaleDateString('en-IN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/** Icon for a recent-activity feed entry, by activity type. */
export function getActivityIcon(type) {
  switch (type) {
    case 'purchase_order':
      return '📋'
    case 'invoice':
      return '💰'
    case 'defaulter':
      return '⚠️'
    case 'credit_report':
      return '📊'
    case 'settlement':
      return '✅'
    default:
      return '📄'
  }
}

// Plan durations in days, used by getExpiryDisplay.
const PLAN_DURATIONS = {
  BASE: 30, // 1 month in days
  ROYAL: 180, // 6 months
  GROUPS: 365, // 1 year
  ENTERPRISE: 365, // 1 year
  ADMIN_FREE: 30, // Default to 30 days for admin free
  LIFETIME: 36500, // 100 years for lifetime (shows as Never expires)
}

/**
 * Compute the display text/color/progress-percent for a subscription's
 * expiry, given whatever shape of subscription object the API returns.
 */
export function getExpiryDisplay(subscription) {
  const planName =
    subscription?.plan_name ||
    subscription?.subscription_plan ||
    subscription?.plan ||
    'BASE'

  // If truly lifetime — show Never expires, else calculate days
  if (planName === 'LIFETIME') {
    return { text: 'Never expires', color: 'text-green-500', percent: 100 }
  }

  // Use end date from DB if available
  const endDateRaw =
    subscription?.subscription_end_date ||
    subscription?.expires_at ||
    subscription?.valid_until ||
    subscription?.subscription_expires_at ||
    subscription?.expiry_date

  // Get start date
  const startRaw =
    subscription?.subscription_start_date ||
    subscription?.plan_activated_at ||
    subscription?.created_at ||
    subscription?.start_date

  if (!startRaw) {
    return { text: 'No expiry info', color: 'text-gray-400', percent: 50 }
  }

  const start = new Date(startRaw)
  let end = null
  let durationDays = PLAN_DURATIONS[planName] || 30

  if (endDateRaw) {
    end = new Date(endDateRaw)
    const calculatedDuration = Math.ceil((end - start) / (1000 * 60 * 60 * 24))
    durationDays = calculatedDuration > 0 ? calculatedDuration : durationDays
  } else {
    end = new Date(start)
    end.setDate(end.getDate() + durationDays)
  }

  const today = new Date()
  const daysLeft = Math.ceil((end - today) / (1000 * 60 * 60 * 24))
  const totalDays = durationDays
  const usedDays = Math.ceil((today - start) / (1000 * 60 * 60 * 24))
  const percent = Math.min(100, Math.max(0, Math.round((usedDays / totalDays) * 100)))

  if (daysLeft <= 0) {
    return { text: `Expired ${Math.abs(daysLeft)} days ago`, color: 'text-red-500', percent: 100 }
  }

  const months = Math.floor(daysLeft / 30)
  const days = daysLeft % 30
  const text =
    months > 0
      ? `Expires in ${months} month${months > 1 ? 's' : ''} ${days} days`
      : `Expires in ${days} days`

  return { text, color: daysLeft < 7 ? 'text-red-500' : 'text-gray-500', percent }
}
