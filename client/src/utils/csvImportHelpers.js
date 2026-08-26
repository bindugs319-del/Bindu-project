// Shared by CSVImportModal.jsx (PO) and InvoiceCSVImportModal.jsx —
// previously each file had its own near-identical copy of these.
// Note: the PO version used to have an extra "DD MMM YYYY" regex branch
// before falling back to `new Date(s)` — that branch did exactly what the
// fallback below it already does, so it was dead/redundant code, not a
// real behavior difference. This version keeps the same net behavior.

export const formatDateToISO = (dateStr) => {
  if (!dateStr) return null
  const s = String(dateStr).trim()

  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s

  const ddmmyyyy = s.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/)
  if (ddmmyyyy) {
    const [, d, m, y] = ddmmyyyy
    return `${y}-${m.padStart(2, '0')}-${d.padStart(2, '0')}`
  }

  const d = new Date(s)
  if (!isNaN(d.getTime())) return d.toISOString().split('T')[0]

  return null
}

export const parseAmount = (val) => {
  if (val === undefined || val === null) return 0
  const s = String(val).replace(/[₹Rs.,\s%]/g, '')
  const parsed = parseFloat(s)
  return isNaN(parsed) ? 0 : parsed
}

export const looksLikePercent = (val) => {
  if (val === undefined || val === null) return false
  return String(val).includes('%')
}
