import { useEffect, useState } from 'react'
import { purchaseOrders, salesInvoices } from '../services/api/apiClient'

/**
 * Loads the user's real POs or Invoices when arriving with a `context`
 * query param ('po' or 'invoice'), so a picker can offer them and a
 * case list can be filtered to only entries referencing a real
 * PO/Invoice number. Identical logic was duplicated in Defaulters.jsx
 * and ReportDefaulter.jsx.
 *
 * Returns { contextOptions, contextNumbers, contextLoading }.
 * contextNumbers stays `null` until the lookup resolves (or immediately
 * if there's no context), so callers can distinguish "still loading"
 * from "loaded, but empty" when filtering a list against it.
 */
export function useDefaulterContext(context) {
  const [contextOptions, setContextOptions] = useState([])
  const [contextLoading, setContextLoading] = useState(false)
  const [contextNumbers, setContextNumbers] = useState(null)

  useEffect(() => {
    if (!context) { setContextNumbers(null); return }
    setContextLoading(true)
    async function loadContextOptions() {
      if (context === 'po') {
        const res = await purchaseOrders.list(1, 100, false)
        const items = res.ok ? (Array.isArray(res.data) ? res.data : (res.data?.items || [])) : []
        setContextOptions(items.map(po => ({
          id: po.id,
          label: `${po.po_number} — ${po.vendor_name || po.vendor} — ₹${po.amount}`,
          business_name: po.vendor_name || po.vendor,
          business_gstin: po.gstin || '',
          invoice_number: po.po_number,
          amount: po.amount,
          due_date: po.due_date ? String(po.due_date).slice(0, 10) : '',
        })))
        setContextNumbers(new Set(items.map(po => po.po_number)))
      } else if (context === 'invoice') {
        const res = await salesInvoices.list({ limit: 100 })
        const items = res.ok ? (res.data?.invoices || []) : []
        setContextOptions(items.map(inv => ({
          id: inv.id,
          label: `${inv.invoice_number} — ${inv.counterparty_name} — ₹${inv.total}`,
          business_name: inv.counterparty_name,
          business_gstin: inv.counterparty_gstin || '',
          invoice_number: inv.invoice_number,
          amount: inv.total,
          due_date: inv.payment_due_date ? String(inv.payment_due_date).slice(0, 10) : '',
        })))
        setContextNumbers(new Set(items.map(inv => inv.invoice_number)))
      }
      setContextLoading(false)
    }
    loadContextOptions()
  }, [context])

  return { contextOptions, contextNumbers, contextLoading }
}
