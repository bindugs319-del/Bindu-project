/**
 * Number/date formatting for the design system. Indian digit grouping
 * (12,34,567) everywhere; compact amounts use lakh (L) / crore (Cr).
 */

const INR_FULL = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
const INR_PAISE = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2 })
const COUNT = new Intl.NumberFormat('en-IN')

/** ₹12,34,567 (no paise). Pass { paise: true } for ₹12,34,567.00. */
export function formatINR(value, { paise = false } = {}) {
  const n = Number(value) || 0
  return (paise ? INR_PAISE : INR_FULL).format(n)
}

/** ₹4,500 · ₹1.25 L · ₹3.40 Cr — for KPI tiles and chart axes. */
export function formatINRCompact(value) {
  const n = Number(value) || 0
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 1e7) return `${sign}₹${trim(abs / 1e7)} Cr`
  if (abs >= 1e5) return `${sign}₹${trim(abs / 1e5)} L`
  return INR_FULL.format(n)
}

function trim(x) {
  return x.toFixed(2).replace(/\.?0+$/, '')
}

/** Money in an invoice's own currency (falls back to INR). */
export function formatMoney(value, currency = 'INR') {
  try {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: currency || 'INR', minimumFractionDigits: 2 }).format(Number(value) || 0)
  } catch {
    return INR_PAISE.format(Number(value) || 0)
  }
}

/** 1,23,456 */
export function formatCount(value) {
  return COUNT.format(Number(value) || 0)
}

/** 12 Jan 2026 (or an em dash). */
export function formatDateShort(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}
