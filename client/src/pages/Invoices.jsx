import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { Link } from 'react-router-dom'
import { salesInvoices as invoicesApi, purchaseOrders as poApi, api, STATIC_BASE_URL } from '../services/api/apiClient'
import InvoiceCSVImportModal from '../components/invoices/InvoiceCSVImportModal'
import InvoicePDFImportModal from '../components/invoices/InvoicePDFImportModal'
import InfoTooltip from '../components/common/InfoTooltip'

/**
 * Label + optional "*" required marker + info tooltip, used above every
 * field in the Add Invoice form so the field's purpose stays visible even
 * once the placeholder text has been typed over.
 */
function FieldLabel({ text, tip, required }) {
  return (
    <label className="relative flex items-start min-h-[2rem] text-xs font-medium text-gray-600 mb-1">
      <span>{text}{required && <span className="text-red-500"> *</span>}</span>
      {tip && <InfoTooltip text={tip} />}
    </label>
  )
}

/**
 * Turn whatever shape an API error comes back as into a readable string.
 * FastAPI validation failures (422) return `detail` as an array of
 * { loc, msg, type } objects — String()'ing that array directly produces
 * "[object Object],[object Object]" since Array.toString() just calls
 * toString() on each element. This extracts the actual message(s).
 */
function formatError(error) {
  if (error === null || error === undefined) return ''
  if (typeof error === 'string') return error

  if (Array.isArray(error)) {
    return error
      .map((e) => {
        if (typeof e === 'string') return e
        if (e && typeof e === 'object') {
          const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : null
          const msg = e.msg || e.message || JSON.stringify(e)
          return field ? `${field}: ${msg}` : msg
        }
        return String(e)
      })
      .join('; ')
  }

  if (typeof error === 'object') {
    if (error.detail) return formatError(error.detail)
    if (error.message) return error.message
    try {
      return JSON.stringify(error)
    } catch {
      return String(error)
    }
  }

  return String(error)
}

export default function Invoices() {
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [showInvoiceImport, setShowInvoiceImport] = useState(false)
  const [showInvoicePdfImport, setShowInvoicePdfImport] = useState(false)
  const [uploadingDocForInvoiceId, setUploadingDocForInvoiceId] = useState(null)
  const [error, setError] = useState(null)
  const [showCreateModal, setShowCreateModal] = useState(true)
  const [selectedInvoice, setSelectedInvoice] = useState(null)
  const [editingInvoiceId, setEditingInvoiceId] = useState(null)

  // Matches the SalesInvoiceItem schema exactly: desc/hsn/qty/rate/amount.
  // No per-item tax field — tax is handled at the invoice level via
  // tax_breakdown (cgst/sgst/igst).
  const emptyItem = {
    desc: '',
    hsn: '',
    qty: 1,
    rate: '',
    amount: 0,
  }

  const emptyForm = {
    invoice_number: '',
    invoice_date: '',
    payment_due_date: '',
    payment_terms: '',

    po_number: '',
    po_date: '',
    expected_delivery_date: '',

    counterparty_name: '',
    counterparty_gstin: '',
    counterparty_pan: '',
    counterparty_email: '',
    counterparty_phone: '',
    document_url: '',

    // bill_to / ship_to are {name, address} objects, matching the spec.
    bill_to: { name: '', address: '' },
    ship_to: { name: '', address: '' },

    currency: 'INR',
    lut_arn: '',
    lut_filing_date: '',
    place_of_supply: '',
    is_sez_export: false,

    subtotal: 0,
    // tax_breakdown: {cgst, sgst, igst} — only one of cgst+sgst (intra-
    // state) or igst (inter-state) is normally non-zero at a time.
    tax_breakdown: { cgst: 0, sgst: 0, igst: 0 },
    tax_amount: 0,
    total: 0,
    balance_due: 0,

    status: 'Draft',
    notes: '',
    items: [emptyItem],
  }

  const [formData, setFormData] = useState(emptyForm)
  // Which GST split the user is entering: intra-state (CGST+SGST) or
  // inter-state (IGST). Only one is sent as non-zero.
  const [taxMode, setTaxMode] = useState('igst')
  const [taxRate, setTaxRate] = useState(0)

  // PO Number autocomplete: suggests real, existing PO numbers as the user
  // types, and offers to auto-fill vendor/GSTIN/date from that PO. This is
  // a soft reference only - po_number stays a plain string, invoices are
  // never linked to a PurchaseOrder by foreign key, and typing a number
  // that doesn't match anything is still allowed.
  const [poSuggestions, setPoSuggestions] = useState([])
  const [showPoSuggestions, setShowPoSuggestions] = useState(false)
  const [poSearchLoading, setPoSearchLoading] = useState(false)

  // Read-only display of the caller's own company details, auto-filled
  // from their saved BusinessProfile — not editable here, and not part
  // of the create payload (the backend snapshots it server-side).
  const [companyProfile, setCompanyProfile] = useState(null)

  // Status filter tabs + archive toggle, mirroring the Purchase Orders
  // page's "Open POs" list controls.
  const [statusFilter, setStatusFilter] = useState('')
  const [showArchived, setShowArchived] = useState(false)
  const [archivingId, setArchivingId] = useState(null)
  const [invoiceFile, setInvoiceFile] = useState(null)

  // Preview a file the user just selected, before it's uploaded/saved —
  // uses a local blob URL since the file only exists in-browser at this
  // point. Opens in a new tab; browsers natively render PDFs and images.
  const previewFile = (file) => {
    if (!file) return
    const url = URL.createObjectURL(file)
    window.open(url, '_blank', 'noopener,noreferrer')
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  }

  // Edit-approval fields, only shown/used when editing an existing
  // invoice, mirroring purchase_orders' EditPOModal exactly.
  const [editReason, setEditReason] = useState('')
  const [editEvidenceFile, setEditEvidenceFile] = useState(null)
  const [submitForApproval, setSubmitForApproval] = useState(false)
  const formPanelRef = useRef(null)

  const fetchInvoices = useCallback(async () => {
    setLoading(true)

    try {
      const response = await invoicesApi.list({ limit: 100, include_archived: showArchived })

      if (response.ok) {
        setInvoices(
          response.data?.invoices ||
          response.data ||
          []
        )
      } else {
        setError(response.error)
      }
    } catch (err) {
      setError(err.message)
    }

    setLoading(false)
  }, [showArchived])

  useEffect(() => {
    fetchInvoices()
  }, [fetchInvoices])

  const handleQuickInvoiceDocUpload = async (invoice, file) => {
    if (!file) return
    setUploadingDocForInvoiceId(invoice.id)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const uploadRes = await api.post('/upload/evidence', formData)
      if (!uploadRes.ok) {
        setError(uploadRes.error || 'Failed to upload document')
        setUploadingDocForInvoiceId(null)
        return
      }
      const documentUrl = uploadRes.data?.url
      const res = await invoicesApi.update(invoice.id, { document_url: documentUrl })
      if (res.ok) {
        setInvoices((prev) => prev.map(inv => inv.id === invoice.id ? { ...inv, document_url: documentUrl } : inv))
      } else {
        setError(res.error || 'Failed to attach document to invoice')
      }
    } catch (err) {
      setError(err.message || 'Failed to upload document')
    } finally {
      setUploadingDocForInvoiceId(null)
    }
  }


  // The Add Invoice panel is now always visible (mirroring the
  // Purchase Orders page's always-visible Add PO panel) instead of a
  // modal opened by a button, so prefill it once on mount.
  useEffect(() => {
    openCreateModal()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Active (non-archived) rows, then filtered by status tab, mirroring
  // the Purchase Orders page's activeRows/filteredRows/displayRows split.
  const activeRows = useMemo(() => invoices.filter(inv => !inv.archived), [invoices])
  const filteredRows = useMemo(() => {
    if (!statusFilter) return activeRows
    return activeRows.filter(inv => (inv.status || 'Draft') === statusFilter)
  }, [activeRows, statusFilter])
  const displayRows = showArchived ? invoices : filteredRows
  const archivedCount = useMemo(() => invoices.filter(inv => inv.archived).length, [invoices])
  const invoiceTotal = useMemo(() => displayRows.reduce((sum, inv) => sum + (Number(inv.total) || 0), 0), [displayRows])

  const invoiceStats = useMemo(() => {
    const totalCount = activeRows.length
    const completed = activeRows.filter(inv => inv.status === 'Paid').length
    const pending = activeRows.filter(inv => inv.status !== 'Paid' && inv.status !== 'Cancelled').length
    return { totalCount, completed, pending }
  }, [activeRows])

  const handleArchiveInvoice = async (invoice) => {
    setArchivingId(invoice.id)
    try {
      const res = await invoicesApi.archive(invoice.id)
      if (res.ok) {
        fetchInvoices()
      } else {
        alert(res.error || 'Failed to update archive status')
      }
    } catch (e) {
      alert('Network error while archiving invoice')
    }
    setArchivingId(null)
  }

  const downloadInvoiceTemplate = () => {
    const templateHeaders = [
      'Invoice #', 'Counterparty Name', 'Email', 'Phone', 'GSTIN',
      'Subtotal', 'Tax Rate (%)', 'Total', 'Invoice Date', 'Due Date', 'Status'
    ]
    const example = [
      'INV-2026-01', 'Test Customer', 'customer@email.com', '9876543210', '22AAAAA0000A1Z5',
      '45000', '18', '', '2026-04-01', '2026-04-30', 'Draft'
    ]
    const csv = [templateHeaders.join(','), example.join(',')].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'Invoice_Upload_Template.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadInvoicesAsCSV = () => {
    const headers = ['Invoice #', 'Customer', 'Email', 'Mobile', 'GSTIN', 'Total', 'Invoice Date', 'Due Date', 'Status', 'Document URL']
    const rows = displayRows.map(inv => [
      inv.invoice_number,
      inv.counterparty_name,
      inv.counterparty_email || '',
      inv.counterparty_phone || '',
      inv.counterparty_gstin || '',
      `₹${Number(inv.total || 0).toLocaleString('en-IN')}`,
      inv.invoice_date?.slice(0, 10) || inv.invoice_date || '',
      inv.payment_due_date?.slice(0, 10) || inv.payment_due_date || '',
      inv.status,
      inv.document_url || ''
    ])
    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'SalesInvoices.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  // Days-left calculation and status badge, mirroring the Purchase
  // Orders page exactly (no payment-window grace period for invoices,
  // since SalesInvoice has no equivalent field).
  const calculateDaysLeft = (dueDateStr) => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const dueDate = new Date(dueDateStr)
    dueDate.setHours(0, 0, 0, 0)
    return Math.floor((dueDate - today) / (1000 * 60 * 60 * 24))
  }

  const getDaysLeftBadge = (row) => {
    const isPaid = row.payment_completed_at || row.status === 'Paid'
    if (isPaid) return <span className="text-gray-400">—</span>
    const daysLeft = calculateDaysLeft(row.payment_due_date)
    if (daysLeft > 7) return <span className="text-emerald-600 font-medium">{daysLeft} days left</span>
    if (daysLeft >= 1 && daysLeft <= 7) return <span className="text-amber-600 font-medium">{daysLeft} days left ⚠️</span>
    if (daysLeft === 0) return <span className="text-red-600 font-bold">Due Today!</span>
    return <span className="text-red-600 font-bold">0 days</span>
  }

  const getStatusPill = (row) => {
    const isPaid = row.payment_completed_at || row.status === 'Paid'
    if (isPaid) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 border border-emerald-200">
          <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-emerald-500"></span>
          Paid
        </span>
      )
    }
    const daysLeft = calculateDaysLeft(row.payment_due_date)
    if (daysLeft < 0) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 border border-red-200">
          <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-red-500"></span>
          Overdue
        </span>
      )
    }
    if (daysLeft === 0) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200">
          <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-amber-500"></span>
          Due Today
        </span>
      )
    }
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
        <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-blue-500"></span>
        open
      </span>
    )
  }

  // Mark Paid / Send Reminder / Send to Legal Support, mirroring the
  // Purchase Orders page's action handlers and reason modal.
  const [reasonModal, setReasonModal] = useState({ open: false, action: '', invoice: null })
  const [reasonText, setReasonText] = useState('')
  const [paymentReceipt, setPaymentReceipt] = useState(null)
  const [reminderLoadingId, setReminderLoadingId] = useState(null)
  const [showLegalSupportConfirm, setShowLegalSupportConfirm] = useState(null)
  const [legalSupportReason, setLegalSupportReason] = useState('')
  const [legalSupportFile, setLegalSupportFile] = useState(null)

  const handleMarkPaid = (invoice) => {
    setReasonModal({ open: true, action: 'MARK_PAID', invoice })
  }

  const confirmMarkPaid = async () => {
    if (!reasonText.trim()) { alert('Please enter a reason'); return }
    const res = await invoicesApi.markPaid(reasonModal.invoice.id, reasonText, paymentReceipt)
    if (res.ok) {
      fetchInvoices()
    } else {
      alert(res.error || 'Failed to mark as paid')
    }
    setReasonModal({ open: false, action: '', invoice: null })
    setReasonText('')
    setPaymentReceipt(null)
  }

  const [reminderModalInvoice, setReminderModalInvoice] = useState(null)
  const [reminderSubject, setReminderSubject] = useState('')
  const [reminderBody, setReminderBody] = useState('')
  const [reminderScheduleType, setReminderScheduleType] = useState('now')
  const [reminderScheduledAt, setReminderScheduledAt] = useState('')
  const [reminderSending, setReminderSending] = useState(false)
  // "Attach Legal Notice as PDF" option, mirroring PO's ReminderModal.
  const [reminderIncludeLegalNotice, setReminderIncludeLegalNotice] = useState(false)
  const [reminderLegalNoticeContent, setReminderLegalNoticeContent] = useState('')
  const [showInvoiceLegalNoticeConfirm, setShowInvoiceLegalNoticeConfirm] = useState(null)

  const handleSendReminder = (invoice) => {
    const dueDateStr = invoice.payment_due_date?.slice(0, 10) || 'N/A'
    const amountStr = `₹${Number(invoice.total || 0).toLocaleString('en-IN')}`
    setReminderSubject(`Payment Reminder: Invoice ${invoice.invoice_number} due on ${dueDateStr}`)
    setReminderBody(
      `Dear ${invoice.counterparty_name || 'Customer'},\n\n` +
      `This is a reminder that Invoice ${invoice.invoice_number} for amount ${amountStr} ` +
      `is due on ${dueDateStr}. Please arrange payment at the earliest.\n\n` +
      `Regards,\n${invoice.company_name || 'Your Vendor'}`
    )
    setReminderScheduleType('now')
    setReminderScheduledAt('')
    setReminderIncludeLegalNotice(false)
    setReminderLegalNoticeContent(
      `To: ${invoice.counterparty_name || ''}\n` +
      `RE: Outstanding Payment - Invoice ${invoice.invoice_number || ''}\n\n` +
      `Dear ${invoice.counterparty_name || ''},\n\n` +
      `This is a formal legal notice that payment of ${amountStr} for Invoice ${invoice.invoice_number || ''} due on ${dueDateStr} remains unpaid/pending.\n\n` +
      `You are required to clear this payment within 7 days of receiving this notice, failing which legal proceedings will be initiated without further notice.\n\n` +
      `Issued by: ${invoice.company_name || ''}\n` +
      `Date: ${new Date().toLocaleDateString('en-IN')}`
    )
    setReminderModalInvoice(invoice)
  }

  const closeReminderModal = () => {
    setReminderModalInvoice(null)
    setReminderSubject('')
    setReminderBody('')
    setReminderScheduleType('now')
    setReminderScheduledAt('')
    setReminderIncludeLegalNotice(false)
    setReminderLegalNoticeContent('')
  }

  // Actually calls the API. Separated from handleConfirmReminder so the
  // "Send Legal Notice?" confirmation step (below) can call this same
  // function once the user confirms, mirroring PO's
  // handleConfirmReminder(payload) / showLegalConfirm flow.
  const sendReminderRequest = async (payload) => {
    setReminderSending(true)
    setReminderLoadingId(reminderModalInvoice.id)
    try {
      const res = await invoicesApi.sendReminder(reminderModalInvoice.id, payload)
      if (res.ok) {
        // Always surface the backend's actual message — it may say the
        // reminder was logged but NOT actually emailed (e.g. no email
        // provider configured on the server), which used to be reported
        // identically to a real success with zero visible feedback either way.
        alert(res.message || res.data?.message || 'Reminder processed.')
        closeReminderModal()
        setShowInvoiceLegalNoticeConfirm(null)
        fetchInvoices()
      } else {
        alert(res.error || 'Failed to send reminder')
      }
    } catch (e) {
      alert('Network error while sending reminder')
    } finally {
      setReminderSending(false)
      setReminderLoadingId(null)
    }
  }

  const handleConfirmReminder = async () => {
    const payload = {
      subject: reminderSubject,
      body: reminderBody,
      scheduled_at: reminderScheduleType === 'later' ? new Date(reminderScheduledAt).toISOString() : null,
      include_legal_notice: reminderIncludeLegalNotice,
      legal_notice_content: reminderIncludeLegalNotice ? reminderLegalNoticeContent : null,
    }
    // Sending now with a legal notice attached needs an explicit
    // confirmation step first, mirroring the Purchase Orders page.
    if (reminderIncludeLegalNotice && reminderScheduleType === 'now') {
      setShowInvoiceLegalNoticeConfirm({ invoice: reminderModalInvoice, payload })
      return
    }
    await sendReminderRequest(payload)
  }

  const handleSendToLegal = async (invoice) => {
    const res = await invoicesApi.sendToLegal(invoice.id, legalSupportReason, legalSupportFile)
    if (res.ok) {
      fetchInvoices()
    } else {
      alert(res.error || 'Failed to send to legal support')
    }
    setShowLegalSupportConfirm(null)
    setLegalSupportReason('')
    setLegalSupportFile(null)
  }

  // Debounced search: waits 300ms after typing stops before calling the
  // backend, so we're not firing a request on every keystroke.
  useEffect(() => {
    const q = formData.po_number
    if (!q || q.length < 2) {
      setPoSuggestions([])
      return
    }
    const timer = setTimeout(async () => {
      setPoSearchLoading(true)
      try {
        const res = await poApi.search(q, 8)
        if (res.ok && res.success) {
          setPoSuggestions(res.data || [])
        }
      } catch (e) {
        // Silent - autocomplete is a convenience, not a required feature.
        // A failed search just means no suggestions show; the user can
        // still type the PO number freely.
      }
      setPoSearchLoading(false)
    }, 300)
    return () => clearTimeout(timer)
  }, [formData.po_number])

  // When the user picks a suggestion, fill the PO Number/Date fields and
  // - only if they're currently empty - the vendor name/GSTIN too, so we
  // don't clobber something the user already typed themselves.
  const selectPoSuggestion = (po) => {
    setFormData(prev => ({
      ...prev,
      po_number: po.po_number || prev.po_number,
      po_date: po.po_date || prev.po_date,
      counterparty_name: prev.counterparty_name || po.vendor || '',
      counterparty_gstin: prev.counterparty_gstin || po.gstin || '',
    }))
    setShowPoSuggestions(false)
    setPoSuggestions([])
  }

  const updateItem = (index, field, value) => {
    const items = [...formData.items]
    items[index] = {
      ...items[index],
      [field]: value,
    }

    const qty = Number(items[index].qty) || 0
    const rate = Number(items[index].rate) || 0

    items[index].amount = qty * rate

    calculateTotals(items, taxMode, taxRate)
  }

  const addItem = () => {
    setFormData(prev => ({
      ...prev,
      items: [...prev.items, { ...emptyItem }],
    }))
  }

  const removeItem = (index) => {
    if (formData.items.length === 1) return

    const items = formData.items.filter((_, i) => i !== index)
    calculateTotals(items, taxMode, taxRate)
  }

  // Banner shown above the form after a PDF scan, so the person knows
  // which fields came from the file (and any OCR/ambiguity warnings)
  // before they hit "Create Invoice" themselves.
  const [pdfScanBanner, setPdfScanBanner] = useState(null)

  // Fills the main Add Invoice form directly from a scanned PDF's
  // fields/items — no separate "confirm & save" step. Only overwrites a
  // field when the scan actually found something for it, so anything
  // the person already typed manually before scanning is preserved.
  const handlePdfScanned = ({ fields, items, warnings, fileName }) => {
    const mappedItems = (items && items.length > 0)
      ? items.map(it => {
          const qty = Number(it.qty) || 1
          const rate = Number(it.rate) || 0
          return {
            desc: it.desc || '',
            hsn: it.hsn || '',
            qty,
            rate,
            amount: it.amount !== undefined && it.amount !== null ? Number(it.amount) : qty * rate,
          }
        })
      : null

    setFormData(prev => {
      const next = { ...prev }
      const setIfFound = (key, value) => {
        if (value !== undefined && value !== null && value !== '') next[key] = value
      }

      setIfFound('invoice_number', fields.invoice_number)
      setIfFound('invoice_date', fields.invoice_date)
      setIfFound('payment_due_date', fields.payment_due_date)
      setIfFound('payment_terms', fields.payment_terms)
      setIfFound('po_number', fields.po_number)
      setIfFound('po_date', fields.po_date)
      setIfFound('expected_delivery_date', fields.expected_delivery_date)
      setIfFound('counterparty_name', fields.counterparty_name)
      setIfFound('counterparty_gstin', fields.counterparty_gstin)
      setIfFound('counterparty_pan', fields.counterparty_pan)
      setIfFound('counterparty_email', fields.counterparty_email)
      setIfFound('counterparty_phone', fields.counterparty_phone)
      setIfFound('place_of_supply', fields.place_of_supply)
      setIfFound('currency', fields.currency)

      if (fields.counterparty_name || fields.bill_to_address) {
        next.bill_to = {
          name: fields.counterparty_name || prev.bill_to.name,
          address: fields.bill_to_address || prev.bill_to.address,
        }
      }

      if (fields.ship_to_name || fields.ship_to_address) {
        next.ship_to = {
          name: fields.ship_to_name || prev.ship_to.name,
          address: fields.ship_to_address || prev.ship_to.address,
        }
      }

      if (mappedItems) {
        // calculateTotals (below) recomputes subtotal/tax/total off these
        // items and writes them back into state — kept in sync here only
        // so the effect isn't briefly overwritten by this same update.
        next.items = mappedItems
      } else if (fields.subtotal !== undefined || fields.total !== undefined) {
        // No item table could be read from the PDF, so fall back to the
        // invoice-level totals the scan did find.
        next.subtotal = fields.subtotal ?? prev.subtotal
        next.tax_amount = fields.tax_amount ?? prev.tax_amount
        next.total = fields.total ?? prev.total
        next.balance_due = fields.total ?? prev.balance_due
      }

      return next
    })

    if (mappedItems) {
      calculateTotals(mappedItems, taxMode, taxRate)
    }

    setPdfScanBanner({
      fileName,
      itemsFound: (items || []).length,
      warnings: warnings || [],
    })
    formPanelRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }


  const calculateTotals = (items, mode = taxMode, rate = taxRate) => {
    const subtotal = items.reduce(
      (sum, item) => sum + (Number(item.amount) || 0),
      0
    )

    const pct = Number(rate) || 0
    const taxAmount = subtotal * pct / 100

    const breakdown = mode === 'cgst_sgst'
      ? { cgst: taxAmount / 2, sgst: taxAmount / 2, igst: 0 }
      : { cgst: 0, sgst: 0, igst: taxAmount }

    const total = subtotal + taxAmount

    setFormData(prev => ({
      ...prev,
      items,
      subtotal,
      tax_breakdown: breakdown,
      tax_amount: taxAmount,
      total,
      balance_due: total,
    }))
  }

  const handleTaxRateChange = (value) => {
    setTaxRate(value)
    calculateTotals(formData.items, taxMode, value)
  }

  const handleTaxModeChange = (mode) => {
    setTaxMode(mode)
    calculateTotals(formData.items, mode, taxRate)
  }

  const openCreateModal = async () => {
    setShowCreateModal(true)

    // Prefill invoice/PO number with the next auto-generated value so
    // the user can see (and override) it up front.
    try {
      const res = await invoicesApi.nextNumber()
      if (res.ok) {
        setFormData((prev) => ({
          ...prev,
          invoice_number: prev.invoice_number || res.data?.invoice_number || '',
          po_number: prev.po_number || res.data?.po_number || '',
        }))
      }
    } catch {
      // If this fails, the form just stays blank — the backend still
      // auto-generates a number on submit either way.
    }

    // Load the caller's own company details for read-only display —
    // these come from BusinessProfile, not from this form.
    try {
      const res = await fetch('/api/v1/account/profile', { credentials: 'include' })
      const data = await res.json()
      if (data?.data) {
        setCompanyProfile(data.data)
      }
    } catch {
      // Non-critical — the invoice still gets the company snapshot
      // server-side regardless of whether this preview loads.
    }
  }

  const openEditModal = async (invoice) => {
    setEditingInvoiceId(invoice.id)
    setEditReason('')
    setEditEvidenceFile(null)
    setSubmitForApproval(false)

    const breakdown = invoice.tax_breakdown || { cgst: 0, sgst: 0, igst: 0 }
    const mode = (breakdown.cgst || breakdown.sgst) ? 'cgst_sgst' : 'igst'
    const taxTotal = mode === 'cgst_sgst'
      ? (breakdown.cgst || 0) + (breakdown.sgst || 0)
      : (breakdown.igst || 0)
    const rate = invoice.subtotal ? (taxTotal / invoice.subtotal) * 100 : 0

    setTaxMode(mode)
    setTaxRate(rate)

    setFormData({
      invoice_number: invoice.invoice_number || '',
      invoice_date: invoice.invoice_date || '',
      payment_due_date: invoice.payment_due_date || '',
      payment_terms: invoice.payment_terms || '',

      po_number: invoice.po_number || '',
      po_date: invoice.po_date || '',
      expected_delivery_date: invoice.expected_delivery_date || '',

      counterparty_name: invoice.counterparty_name || '',
      counterparty_gstin: invoice.counterparty_gstin || '',
      counterparty_pan: invoice.counterparty_pan || '',
      counterparty_email: invoice.counterparty_email || '',
      counterparty_phone: invoice.counterparty_phone || '',
      document_url: invoice.document_url || '',

      bill_to: invoice.bill_to || { name: '', address: '' },
      ship_to: invoice.ship_to || { name: '', address: '' },

      currency: invoice.currency || 'INR',
      lut_arn: invoice.lut_arn || '',
      lut_filing_date: invoice.lut_filing_date || '',
      place_of_supply: invoice.place_of_supply || '',
      is_sez_export: !!invoice.is_sez_export,

      subtotal: invoice.subtotal || 0,
      tax_breakdown: breakdown,
      tax_amount: invoice.tax_amount || 0,
      total: invoice.total || 0,
      balance_due: invoice.balance_due || 0,

      status: invoice.status || 'Draft',
      notes: invoice.notes || '',
      items: (invoice.items && invoice.items.length > 0)
        ? invoice.items.map(item => ({
            desc: item.desc || '',
            hsn: item.hsn || '',
            qty: item.qty ?? 1,
            rate: item.rate ?? '',
            amount: item.amount || 0,
          }))
        : [{ ...emptyItem }],
    })

    setShowCreateModal(true)
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setError(null)

    const wantsApproval = submitForApproval || !!editEvidenceFile

    // Mirrors EditPOModal's validation: reason is always required when
    // editing an existing invoice, and evidence is required if the
    // approval-flow checkbox is on.
    if (editingInvoiceId) {
      if (!editReason.trim()) {
        setError('Please enter a reason for this update')
        return
      }
      if (wantsApproval && !editEvidenceFile) {
        setError('Please attach evidence for the approval flow')
        return
      }
    }

    try {
      const payload = {
        ...formData,

        bill_to: (formData.bill_to.name || formData.bill_to.address)
          ? formData.bill_to
          : null,
        ship_to: (formData.ship_to.name || formData.ship_to.address)
          ? formData.ship_to
          : null,

        subtotal: Number(formData.subtotal),
        tax_amount: Number(formData.tax_amount),
        total: Number(formData.total),
        balance_due: Number(formData.balance_due),

        items: formData.items.map(item => ({
          desc: item.desc,
          hsn: item.hsn,
          qty: Number(item.qty),
          rate: Number(item.rate),
          amount: Number(item.amount),
        })),
      }

      let response

      if (editingInvoiceId && wantsApproval) {
        // Two-step approval flow: upload evidence, then submit the
        // edit for Operations Truth Check -> Master Admin approval,
        // instead of applying it immediately.
        const uploadRes = await invoicesApi.uploadEvidence(editingInvoiceId, editEvidenceFile)
        if (!uploadRes.ok) {
          setError(uploadRes.error || 'Failed to upload evidence')
          return
        }
        response = await invoicesApi.requestApproval(
          editingInvoiceId,
          payload,
          uploadRes.data?.url,
          uploadRes.data?.filename,
          editReason
        )
      } else if (editingInvoiceId) {
        // Normal save, applies immediately.
        response = await invoicesApi.update(editingInvoiceId, payload)
      } else {
        response = await invoicesApi.create(payload)
      }

      if (response.ok) {
        const savedInvoiceId = editingInvoiceId || response.data?.id

        if (invoiceFile && savedInvoiceId) {
          const uploadRes = await invoicesApi.uploadDocument(savedInvoiceId, invoiceFile)
          if (!uploadRes.ok) {
            setError(uploadRes.error || 'Invoice saved, but the document upload failed')
          }
        }

        closeFormModal()
        fetchInvoices()
      } else {
        setError(response.error)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const formatDate = (date) => {
    if (!date) return 'N/A'

    return new Date(date).toLocaleDateString('en-IN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    })
  }

  const money = (value, currency = 'INR') => {
    try {
      return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: currency || 'INR',
        minimumFractionDigits: 2,
      }).format(Number(value) || 0)
    } catch {
      // Malformed/legacy currency code (shouldn't happen — backend
      // validates it — but Intl throws rather than ignoring a bad code,
      // and a crashed amount cell is worse than falling back to INR).
      return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 2,
      }).format(Number(value) || 0)
    }
  }

  const handleDownloadPdf = async (invoice) => {
    const res = await invoicesApi.downloadPdf(
      invoice.id,
      `${invoice.invoice_number || invoice.id}.pdf`
    )
    if (!res.ok) {
      setError(res.error)
    }
  }

  const handleDelete = async (invoice) => {
    if (!confirm(`Delete invoice ${invoice.invoice_number}? This can't be undone.`)) return

    const res = await invoicesApi.delete(invoice.id)
    if (res.ok) {
      fetchInvoices()
    } else {
      setError(res.error)
    }
  }

  const handleStatusChange = async (invoice, newStatus) => {
    const payload = { status: newStatus }
    if (newStatus === 'Paid') payload.balance_due = 0

    const res = await invoicesApi.update(invoice.id, payload)
    if (res.ok) {
      fetchInvoices()
    } else {
      setError(res.error)
    }
  }

  const approvalBadge = (invoice) => {
    const ws = invoice.workflow_status
    if (!ws || ws === 'Draft') return null
    const styles = {
      'Pending Operations Review': 'bg-amber-100 text-amber-700',
      'Pending Master Admin Approval': 'bg-blue-100 text-blue-700',
      'Approved': 'bg-green-100 text-green-700',
      'Rejected': 'bg-red-100 text-red-700',
    }
    const labels = {
      'Pending Operations Review': 'Edit: Operations review',
      'Pending Master Admin Approval': 'Edit: Master Admin review',
      'Approved': 'Edit approved',
      'Rejected': 'Edit rejected',
    }
    return (
      <span className={`px-2 py-1 rounded text-xs font-semibold ${styles[ws] || 'bg-gray-100 text-gray-600'}`}>
        {labels[ws] || ws}
      </span>
    )
  }

  const closeFormModal = () => {
    setEditingInvoiceId(null)
    setFormData(emptyForm)
    setTaxMode('igst')
    setTaxRate(0)
    setInvoiceFile(null)
    setEditReason('')
    setEditEvidenceFile(null)
    setSubmitForApproval(false)
    setPdfScanBanner(null)
  }

  const renderInvoiceFormBody = () => (
              <div className="p-6">

                <div className="flex justify-between mb-6">
                  <h2 className="text-2xl font-bold">
                    {editingInvoiceId ? 'Edit Tax Invoice' : 'Add Invoice'}
                  </h2>

                  {editingInvoiceId && (
                    <button
                      type="button"
                      onClick={closeFormModal}
                      className="text-sm text-gray-500 hover:text-gray-700 underline"
                    >
                      Cancel edit
                    </button>
                  )}
                </div>

                {!editingInvoiceId && (
                  <div className="flex flex-wrap gap-2 mb-6">
                    <button
                      type="button"
                      onClick={() => setShowInvoiceImport(true)}
                      className="flex-1 text-xs bg-primary-600 text-white px-3 py-1.5 rounded-lg hover:bg-primary-700 transition-colors font-medium flex items-center justify-center gap-1"
                    >
                      📥 Import Invoices
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowInvoicePdfImport(true)}
                      className="flex-1 text-xs text-primary-700 border border-primary-300 px-3 py-1.5 rounded-lg hover:bg-primary-50 transition-colors font-medium flex items-center justify-center gap-1"
                    >
                      📄 Import (.pdf)
                    </button>
                    <button
                      type="button"
                      onClick={downloadInvoiceTemplate}
                      className="flex-1 text-xs text-blue-600 border border-blue-600 px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors font-medium flex items-center justify-center gap-1"
                    >
                      📄 Template (CSV)
                    </button>
                  </div>
                )}

                {pdfScanBanner && (
                  <div className="mb-6 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium">
                          Filled from {pdfScanBanner.fileName} — review the fields below, fill in anything missed, then click Create Invoice.
                        </p>
                        {pdfScanBanner.itemsFound === 0 && (
                          <p className="mt-1 text-green-700">No item table could be read from this file — please add items manually.</p>
                        )}
                        {pdfScanBanner.warnings.length > 0 && (
                          <ul className="mt-2 list-disc list-inside text-amber-800">
                            {pdfScanBanner.warnings.map((w, i) => <li key={i}>{w}</li>)}
                          </ul>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => setPdfScanBanner(null)}
                        className="text-green-700 hover:text-green-900 font-bold leading-none"
                        aria-label="Dismiss"
                      >
                        ×
                      </button>
                    </div>
                  </div>
                )}

                {/* INVOICE INFORMATION */}

                <h3 className="font-bold text-lg mb-3">
                  Invoice Information
                </h3>

                <div className="grid md:grid-cols-3 gap-4 mb-6">

                  <div className="group">
                    <FieldLabel text="Invoice Number" required />
                    <input
                      required
                      placeholder="Invoice Number *"
                      value={formData.invoice_number}
                      onChange={e =>
                        setFormData({
                          ...formData,
                          invoice_number: e.target.value
                        })
                      }
                      className="border p-2 rounded w-full"
                    />
                  </div>

                  <div className="group">
                    <FieldLabel text="Invoice Date" required />
                    <input
                      required
                      type="date"
                      value={formData.invoice_date}
                      onChange={e =>
                        setFormData({
                          ...formData,
                          invoice_date: e.target.value
                        })
                      }
                      className="border p-2 rounded w-full"
                    />
                  </div>

                  <div className="group">
                    <FieldLabel text="Payment Due Date" required />
                    <input
                      required
                      type="date"
                      value={formData.payment_due_date}
                      onChange={e =>
                        setFormData({
                          ...formData,
                          payment_due_date: e.target.value
                        })
                      }
                      className="border p-2 rounded w-full"
                    />
                  </div>

                  <div className="group">
                    <FieldLabel text="Extra days" />
                    <input
                      value={formData.payment_terms}
                      onChange={e =>
                        setFormData({
                          ...formData,
                          payment_terms: e.target.value
                        })
                      }
                      className="border p-2 rounded w-full"
                    />
                  </div>

                  <div className="relative group">
                    <FieldLabel text="PO Number" />
                    <input
                      placeholder="PO Number"
                      value={formData.po_number}
                      onChange={e => {
                        setFormData({
                          ...formData,
                          po_number: e.target.value
                        })
                        setShowPoSuggestions(true)
                      }}
                      onFocus={() => setShowPoSuggestions(true)}
                      onBlur={() => setTimeout(() => setShowPoSuggestions(false), 150)}
                      className="border p-2 rounded w-full"
                      autoComplete="off"
                    />
                    {showPoSuggestions && (poSuggestions.length > 0 || poSearchLoading) && (
                      <div className="absolute z-10 mt-1 w-full bg-white border rounded shadow-lg max-h-56 overflow-y-auto">
                        {poSearchLoading && (
                          <div className="p-2 text-sm text-gray-400">Searching...</div>
                        )}
                        {!poSearchLoading && poSuggestions.map(po => (
                          <button
                            type="button"
                            key={po.po_number}
                            onMouseDown={() => selectPoSuggestion(po)}
                            className="block w-full text-left p-2 hover:bg-blue-50 border-b last:border-b-0"
                          >
                            <div className="font-medium text-sm">{po.po_number}</div>
                            <div className="text-xs text-gray-500">
                              {po.vendor}{po.gstin ? ` — ${po.gstin}` : ''}
                              {po.amount ? ` — ₹${po.amount}` : ''}
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="group">
                    <FieldLabel text="PO Date" />
                    <input
                      type="date"
                      value={formData.po_date}
                      onChange={e =>
                        setFormData({
                          ...formData,
                          po_date: e.target.value
                        })
                      }
                      className="border p-2 rounded w-full"
                      placeholder="PO Date"
                    />
                  </div>

                  <div className="group">
                    <FieldLabel text="Expected Delivery Date" />
                    <input
                      type="date"
                      value={formData.expected_delivery_date}
                      onChange={e =>
                        setFormData({
                          ...formData,
                          expected_delivery_date: e.target.value
                        })
                      }
                      className="border p-2 rounded w-full"
                      placeholder="Expected Delivery Date"
                    />
                  </div>

                </div>


                {/* ITEMS */}

                <div className="flex justify-between items-center mb-3">

                  <h3 className="font-bold text-lg">
                    Items
                  </h3>

                  <button
                    type="button"
                    onClick={addItem}
                    className="px-3 py-2 bg-blue-600 text-white rounded"
                  >
                    + Add Item
                  </button>

                </div>

                <div className="overflow-x-auto mb-4">

                  <table className="w-full border">

                    <thead className="bg-gray-100">
                      <tr>
                        <th className="p-2">Description</th>
                        <th className="p-2">HSN/SAC</th>
                        <th className="p-2">Qty</th>
                        <th className="p-2">Rate</th>
                        <th className="p-2">Amount</th>
                        <th></th>
                      </tr>
                    </thead>

                    <tbody>

                      {formData.items.map((item, index) => (

                        <tr key={index}>

                          <td className="p-2">
                            <input
                              required
                              value={item.desc}
                              onChange={e =>
                                updateItem(
                                  index,
                                  'desc',
                                  e.target.value
                                )
                              }
                              className="border p-2 rounded w-full"
                            />
                          </td>

                          <td className="p-2">
                            <input
                              value={item.hsn}
                              onChange={e =>
                                updateItem(
                                  index,
                                  'hsn',
                                  e.target.value
                                )
                              }
                              className="border p-2 rounded w-24"
                            />
                          </td>

                          <td className="p-2">
                            <input
                              type="number"
                              min="0"
                              value={item.qty}
                              onChange={e =>
                                updateItem(
                                  index,
                                  'qty',
                                  e.target.value
                                )
                              }
                              className="border p-2 rounded w-20"
                            />
                          </td>

                          <td className="p-2">
                            <input
                              type="number"
                              min="0"
                              value={item.rate}
                              onChange={e =>
                                updateItem(
                                  index,
                                  'rate',
                                  e.target.value
                                )
                              }
                              className="border p-2 rounded w-28"
                            />
                          </td>

                          <td className="p-2 font-semibold">
                            {money(item.amount, formData.currency)}
                          </td>

                          <td>
                            <button
                              type="button"
                              onClick={() => removeItem(index)}
                              className="text-red-600"
                            >
                              ×
                            </button>
                          </td>

                        </tr>

                      ))}

                    </tbody>

                  </table>

                </div>


                {/* TAX SPLIT */}

                <div className="flex items-center gap-4 mb-6 flex-wrap">
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      checked={taxMode === 'igst'}
                      onChange={() => handleTaxModeChange('igst')}
                    />
                    IGST (inter-state)
                  </label>

                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      checked={taxMode === 'cgst_sgst'}
                      onChange={() => handleTaxModeChange('cgst_sgst')}
                    />
                    CGST + SGST (intra-state)
                  </label>

                  <label className="flex items-center gap-2">
                    Tax %
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={taxRate}
                      onChange={e => handleTaxRateChange(e.target.value)}
                      className="border p-2 rounded w-24"
                    />
                  </label>
                </div>


                {/* TOTALS */}

                <div className="flex justify-end mb-6">

                  <div className="w-80 space-y-2">

                    <div className="flex justify-between">
                      <span>Sub Total</span>
                      <b>{money(formData.subtotal, formData.currency)}</b>
                    </div>

                    {taxMode === 'cgst_sgst' ? (
                      <>
                        <div className="flex justify-between">
                          <span>CGST</span>
                          <b>{money(formData.tax_breakdown.cgst, formData.currency)}</b>
                        </div>
                        <div className="flex justify-between">
                          <span>SGST</span>
                          <b>{money(formData.tax_breakdown.sgst, formData.currency)}</b>
                        </div>
                      </>
                    ) : (
                      <div className="flex justify-between">
                        <span>IGST</span>
                        <b>{money(formData.tax_breakdown.igst, formData.currency)}</b>
                      </div>
                    )}

                    <div className="flex justify-between text-lg border-t pt-2">
                      <span>Total</span>
                      <b>{money(formData.total, formData.currency)}</b>
                    </div>

                    <div className="flex justify-between">
                      <span>Balance Due</span>
                      <b>{money(formData.balance_due, formData.currency)}</b>
                    </div>

                  </div>

                </div>


                {/* BILL TO / SHIP TO */}

                <div className="grid md:grid-cols-2 gap-6 mb-6">

                  <div className="border rounded-lg p-4">

                    <h3 className="font-bold text-lg mb-3">
                      Bill To
                    </h3>

                    <div className="group mb-3">
                      <FieldLabel text="Customer Name" required />
                      <input
                        required
                        value={formData.counterparty_name}
                        onChange={e =>
                          setFormData({
                            ...formData,
                            counterparty_name: e.target.value,
                            bill_to: { ...formData.bill_to, name: e.target.value },
                          })
                        }
                        className="w-full border p-2 rounded"
                      />
                    </div>

                    <div className="group mb-3">
                      <FieldLabel text="Customer Address" />
                      <textarea
                        value={formData.bill_to.address}
                        onChange={e =>
                          setFormData({
                            ...formData,
                            bill_to: { ...formData.bill_to, address: e.target.value },
                          })
                        }
                        className="w-full border p-2 rounded"
                        rows="3"
                      />
                    </div>

                    <div className="group mb-3">
                      <FieldLabel text="GSTIN" />
                      <input
                        value={formData.counterparty_gstin}
                        onChange={e =>
                          setFormData({
                            ...formData,
                            counterparty_gstin: e.target.value
                          })
                        }
                        className="w-full border p-2 rounded"
                      />
                    </div>

                    <div className="group mb-3">
                      <FieldLabel text="PAN" />
                      <input
                        value={formData.counterparty_pan}
                        onChange={e =>
                          setFormData({
                            ...formData,
                            counterparty_pan: e.target.value
                          })
                        }
                        className="w-full border p-2 rounded"
                      />
                    </div>

                    <div className="group mb-3">
                      <FieldLabel text="Customer Email" />
                      <input
                        type="email"
                        value={formData.counterparty_email}
                        onChange={e =>
                          setFormData({
                            ...formData,
                            counterparty_email: e.target.value
                          })
                        }
                        className="w-full border p-2 rounded"
                      />
                    </div>

                    <div className="group">
                      <FieldLabel text="Customer Mobile" />
                      <input
                        type="tel"
                        value={formData.counterparty_phone}
                        onChange={e =>
                          setFormData({
                            ...formData,
                            counterparty_phone: e.target.value
                          })
                        }
                        className="w-full border p-2 rounded"
                      />
                    </div>

                  </div>


                  <div className="border rounded-lg p-4">

                    <h3 className="font-bold text-lg mb-3">
                      Ship To
                    </h3>

                    <div className="group mb-3">
                      <FieldLabel text="Ship To Name" />
                      <input
                        value={formData.ship_to.name}
                        onChange={e =>
                          setFormData({
                            ...formData,
                            ship_to: { ...formData.ship_to, name: e.target.value },
                          })
                        }
                        className="w-full border p-2 rounded"
                      />
                    </div>

                    <div className="group">
                      <FieldLabel text="Ship To Address" />
                      <textarea
                        value={formData.ship_to.address}
                        onChange={e =>
                          setFormData({
                            ...formData,
                            ship_to: { ...formData.ship_to, address: e.target.value },
                          })
                        }
                        className="w-full border p-2 rounded"
                        rows="5"
                      />
                    </div>

                  </div>

                </div>


                {/* SUPPORTING DOCUMENT */}

                <h3 className="font-bold text-lg mb-3">
                  Supporting Document
                </h3>

                <div className="mb-6 group">
                  <label className="relative block text-sm font-medium text-gray-700 mb-2">
                    Upload Document (optional)
                    <InfoTooltip text="Attach a supporting file." />
                  </label>
                  <input
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png"
                    onChange={(e) => setInvoiceFile(e.target.files?.[0] || null)}
                    className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                  />
                  {invoiceFile && (
                    <div className="mt-2 p-2 bg-green-50 rounded-lg text-sm text-green-700 flex items-center justify-between gap-3">
                      <span>✅ Selected: {invoiceFile.name}</span>
                      <button type="button" onClick={() => previewFile(invoiceFile)} className="text-blue-700 hover:underline font-medium whitespace-nowrap">
                        🔍 View
                      </button>
                    </div>
                  )}
                  {editingInvoiceId && formData.document_url && !invoiceFile && (
                    <a
                      href={formData.document_url.startsWith('http') ? formData.document_url : `${STATIC_BASE_URL}${formData.document_url}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 hover:underline mt-2 inline-block"
                    >
                      📄 View current document
                    </a>
                  )}
                </div>

                {/* OTHER DETAILS */}

                <h3 className="font-bold text-lg mb-3">
                  Other Details
                </h3>

                <div className="grid md:grid-cols-3 gap-4 mb-6">

                  <div className="group">
                    <FieldLabel text="LUT ARN" />
                    <input
                      value={formData.lut_arn}
                      onChange={e =>
                        setFormData({
                          ...formData,
                          lut_arn: e.target.value
                        })
                      }
                      className="border p-2 rounded w-full"
                    />
                  </div>

                  <div className="group">
                    <FieldLabel text="LUT Filing Date" />
                    <input
                      type="date"
                      value={formData.lut_filing_date}
                      onChange={e =>
                        setFormData({
                          ...formData,
                          lut_filing_date: e.target.value
                        })
                      }
                      className="border p-2 rounded w-full"
                    />
                  </div>

                  <div className="group">
                    <FieldLabel text="Place of Supply" />
                    <input
                      value={formData.place_of_supply}
                      onChange={e =>
                        setFormData({
                          ...formData,
                          place_of_supply: e.target.value
                        })
                      }
                      className="border p-2 rounded w-full"
                    />
                  </div>

                  <div className="group">
                    <FieldLabel text="Currency" />
                    <select
                      value={formData.currency}
                      onChange={e =>
                        setFormData({
                          ...formData,
                          currency: e.target.value
                        })
                      }
                      className="border p-2 rounded w-full"
                    >
                      <option value="INR">INR</option>
                      <option value="USD">USD</option>
                      <option value="EUR">EUR</option>
                      <option value="GBP">GBP</option>
                    </select>
                  </div>

                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formData.is_sez_export}
                      onChange={e =>
                        setFormData({
                          ...formData,
                          is_sez_export: e.target.checked
                        })
                      }
                    />
                    Supply to SEZ / Export
                  </label>

                </div>


                {/* NOTES */}

                <textarea
                  placeholder="Notes"
                  value={formData.notes}
                  onChange={e =>
                    setFormData({
                      ...formData,
                      notes: e.target.value
                    })
                  }
                  className="w-full border p-2 rounded mb-6"
                  rows="3"
                />

                {editingInvoiceId && (
                  <>
                    <div className="mb-6">
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Reason for Update <span className="text-red-500">*</span>
                      </label>
                      <textarea
                        value={editReason}
                        onChange={(e) => setEditReason(e.target.value)}
                        placeholder="Explain why you are modifying this invoice..."
                        rows={3}
                        className="w-full border border-red-300 rounded p-2 focus:border-red-500 focus:ring-2 focus:ring-red-200"
                      />
                    </div>

                    <div className="border-t border-gray-100 pt-4 mb-6">
                      <h4 className="text-sm font-semibold text-gray-700 mb-2">
                        📎 Attach Evidence (Required for Operations Review)
                      </h4>
                      <p className="text-xs text-gray-500 mb-3">
                        Upload payment proof or supporting document — this will trigger a review by the Operations team.
                      </p>
                      <input
                        type="file"
                        accept=".pdf,.jpg,.jpeg,.png"
                        onChange={(e) => {
                          const f = e.target.files?.[0] || null
                          setEditEvidenceFile(f)
                          if (f) setSubmitForApproval(true)
                        }}
                        className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 mb-3"
                      />
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={submitForApproval}
                          onChange={(e) => setSubmitForApproval(e.target.checked)}
                          className="rounded text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-sm text-gray-600 font-medium">Submit for internal approval flow</span>
                      </label>
                    </div>
                  </>
                )}



                <div className="flex justify-end gap-3">

                  <button
                    type="button"
                    onClick={closeFormModal}
                    className="px-5 py-2 border rounded"
                  >
                    Cancel
                  </button>

                  <button
                    type="submit"
                    className="px-5 py-2 bg-blue-600 text-white rounded"
                  >
                    {editingInvoiceId
                      ? ((submitForApproval || editEvidenceFile) ? '📤 Submit for Approval' : '💾 Save Changes')
                      : 'Create Invoice'}
                  </button>

                </div>

              </div>
  )

  return (
    <div className="min-h-screen bg-gray-50 py-6 px-4">

      <div className="max-w-7xl mx-auto">

        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Invoice Management
            </h1>

            <p className="text-gray-600">
              Create and manage sales invoices
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={downloadInvoicesAsCSV}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
            >
              <span>📥</span> Download CSV
            </button>
          </div>
        </div>

        {showInvoicePdfImport && (
          <InvoicePDFImportModal
            onClose={() => setShowInvoicePdfImport(false)}
            onScanned={handlePdfScanned}
          />
        )}

        {showInvoiceImport && (
          <InvoiceCSVImportModal
            onClose={() => setShowInvoiceImport(false)}
            onImportComplete={() => { fetchInvoices() }}
          />
        )}

        {error && (
          <div className="bg-red-100 text-red-700 p-3 rounded mb-4">
            {formatError(error)}
          </div>
        )}

        {/* Invoice Overview stats, mirroring the Purchase Orders page's
            Business Credibility Index card (Total/Completed/Pending). */}
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 mb-4">
          <h2 className="text-xl font-heading font-semibold text-amber-900">Invoice Overview</h2>
          <p className="text-amber-800/90 text-sm mt-1 max-w-2xl">
            A snapshot of your active sales invoices by status.
          </p>
          <div className="mt-4 grid sm:grid-cols-3 gap-3">
            <div className="p-3 rounded-lg bg-white/60 border border-amber-100">
              <p className="text-xs text-amber-700">Total Invoices</p>
              <p className="font-semibold text-amber-900">{invoiceStats.totalCount}</p>
            </div>
            <div className="p-3 rounded-lg bg-white/60 border border-amber-100">
              <p className="text-xs text-amber-700">Paid Invoices</p>
              <p className="font-semibold text-emerald-700">{invoiceStats.completed}</p>
            </div>
            <div className="p-3 rounded-lg bg-white/60 border border-amber-100">
              <p className="text-xs text-amber-700">Pending Invoices</p>
              <p className="font-semibold text-amber-700">{invoiceStats.pending}</p>
            </div>
          </div>
        </div>

        {/* Status filter tabs + Show Archived, mirroring the Purchase
            Orders page's "Open POs" list controls. */}
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <button onClick={() => setStatusFilter('')} className={`text-xs px-2.5 py-1 rounded-lg ${!statusFilter ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-700'}`}>All</button>
            <button onClick={() => setStatusFilter('Draft')} className={`text-xs px-2.5 py-1 rounded-lg ${statusFilter === 'Draft' ? 'bg-yellow-600 text-white' : 'bg-yellow-50 text-yellow-700'}`}>Draft</button>
            <button onClick={() => setStatusFilter('Sent')} className={`text-xs px-2.5 py-1 rounded-lg ${statusFilter === 'Sent' ? 'bg-blue-600 text-white' : 'bg-blue-50 text-blue-700'}`}>Sent</button>
            <button onClick={() => setStatusFilter('Paid')} className={`text-xs px-2.5 py-1 rounded-lg ${statusFilter === 'Paid' ? 'bg-emerald-600 text-white' : 'bg-emerald-50 text-emerald-700'}`}>Paid</button>
            <button onClick={() => setStatusFilter('Overdue')} className={`text-xs px-2.5 py-1 rounded-lg ${statusFilter === 'Overdue' ? 'bg-red-600 text-white' : 'bg-red-50 text-red-700'}`}>Overdue</button>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input
                type="checkbox"
                checked={showArchived}
                onChange={(e) => setShowArchived(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              Show Archived
            </label>
            <p className="text-sm text-gray-500">Total: ₹{invoiceTotal.toLocaleString('en-IN')}</p>
          </div>
        </div>
        {archivedCount > 0 && !showArchived && (
          <p className="text-xs text-gray-500 mb-2">{archivedCount} archived invoice(s) hidden</p>
        )}

        <div className="flex flex-col lg:flex-row gap-4 items-start">

        <div className="bg-white rounded-xl shadow overflow-hidden flex-[2] w-full">

          {loading ? (
            <div className="p-8 text-center">
              Loading invoices...
            </div>
          ) : displayRows.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              No invoices found.
            </div>
          ) : (
            <div className="overflow-x-auto">
            <table className="min-w-full">

              <thead className="bg-gray-100">
                <tr>
                  <th className="p-4 text-left whitespace-nowrap">Invoice #</th>
                  <th className="p-4 text-left whitespace-nowrap">Customer</th>
                  <th className="p-4 text-left whitespace-nowrap">Email</th>
                  <th className="p-4 text-left whitespace-nowrap">Mobile</th>
                  <th className="p-4 text-left whitespace-nowrap">GSTIN</th>
                  <th className="p-4 text-right whitespace-nowrap">Amount</th>
                  <th className="p-4 text-left whitespace-nowrap">Due Date</th>
                  <th className="p-4 text-left whitespace-nowrap">Days Left</th>
                  <th className="p-4 text-left whitespace-nowrap">Status</th>
                  <th className="p-4 text-left whitespace-nowrap">Document</th>
                  <th className="p-4 text-right whitespace-nowrap">Actions</th>
                </tr>
              </thead>

              <tbody>
                {displayRows.map(invoice => (
                  <tr
                    key={invoice.id}
                    className={`border-t ${invoice.archived ? 'opacity-60' : ''}`}
                  >
                    <td className="p-4">
                      <div className="font-medium">
                        {invoice.invoice_number}
                        {invoice.legal_notice_sent_at && <span className="ml-2">⚖️</span>}
                      </div>
                      {approvalBadge(invoice) && (
                        <div className="text-[11px] mt-0.5">{approvalBadge(invoice)}</div>
                      )}
                    </td>

                    <td className="p-4">
                      {invoice.counterparty_name}
                    </td>

                    <td className="p-4 text-sm text-gray-600">
                      {invoice.counterparty_email || '—'}
                    </td>

                    <td className="p-4 text-sm text-gray-600">
                      {invoice.counterparty_phone || '—'}
                    </td>

                    <td className="p-4 whitespace-nowrap">
                      <span className="text-xs font-mono bg-gray-100 px-2 py-1 rounded border border-gray-200 text-gray-700">{invoice.counterparty_gstin || '—'}</span>
                    </td>

                    <td className="p-4 text-right font-semibold whitespace-nowrap">
                      {money(invoice.total, invoice.currency)}
                    </td>

                    <td className="p-4 whitespace-nowrap">
                      {formatDate(invoice.payment_due_date)}
                    </td>

                    <td className="p-4 whitespace-nowrap">
                      {getDaysLeftBadge(invoice)}
                    </td>

                    <td className="p-4 whitespace-nowrap">
                      {getStatusPill(invoice)}
                    </td>

                    <td className="p-4">
                      {invoice.document_url ? (
                        <a href={invoice.document_url.startsWith('http') ? invoice.document_url : `${STATIC_BASE_URL}${invoice.document_url}`} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                          📄 View
                        </a>
                      ) : uploadingDocForInvoiceId === invoice.id ? (
                        <span className="text-gray-400 text-xs">Uploading&hellip;</span>
                      ) : (
                        <label className="text-primary-600 hover:text-primary-800 flex items-center gap-1 cursor-pointer text-sm">
                          <span>📎</span> Upload
                          <input
                            type="file"
                            accept=".pdf,.jpg,.jpeg,.png"
                            className="hidden"
                            onChange={(e) => handleQuickInvoiceDocUpload(invoice, e.target.files?.[0])}
                          />
                        </label>
                      )}
                    </td>

                    <td className="p-4">
                      <div className="flex justify-end gap-1.5">
                        {invoice.payment_completed_at || invoice.status === 'Paid' ? (
                          <span className="p-1.5 rounded-lg bg-emerald-50 text-emerald-600 shadow-sm" title="Paid">
                            🧾
                          </span>
                        ) : (
                          <button
                            onClick={() => handleMarkPaid(invoice)}
                            className="p-1.5 rounded-lg bg-emerald-50 text-emerald-600 hover:bg-emerald-100 hover:text-emerald-700 transition-colors shadow-sm"
                            title="Mark as paid"
                          >
                            ✅
                          </button>
                        )}
                        <button
                          onClick={() => openEditModal(invoice)}
                          className="p-1.5 rounded-lg bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700 transition-colors shadow-sm"
                          title="Edit"
                        >
                          ✏️
                        </button>
                        <button
                          onClick={() => handleSendReminder(invoice)}
                          disabled={invoice.status === 'Paid' || reminderLoadingId === invoice.id}
                          className={`p-1.5 rounded-lg transition-colors shadow-sm ${
                            invoice.status === 'Paid'
                              ? 'bg-gray-100 text-gray-400 cursor-not-allowed opacity-50'
                              : 'bg-indigo-50 text-indigo-600 hover:bg-indigo-100 hover:text-indigo-700'
                          }`}
                          title={invoice.status === 'Paid' ? 'Reminder not available for paid invoices' : 'Send Reminder'}
                        >
                          {reminderLoadingId === invoice.id ? '...' : '📧'}
                        </button>
                        <button
                          onClick={() => handleArchiveInvoice(invoice)}
                          disabled={archivingId === invoice.id}
                          className="p-1.5 rounded-lg bg-amber-50 text-amber-600 hover:bg-amber-100 hover:text-amber-700 transition-colors shadow-sm disabled:opacity-50"
                          title={invoice.archived ? 'Unarchive' : 'Archive'}
                        >
                          {archivingId === invoice.id ? '...' : '🗄️'}
                        </button>
                        <button
                          onClick={() => invoice.status !== 'Paid' && setShowLegalSupportConfirm(invoice)}
                          disabled={invoice.status === 'Paid'}
                          className={`p-1.5 rounded-lg transition-colors shadow-sm ${
                            invoice.legal_support_requested_at
                              ? 'bg-emerald-50 text-emerald-600'
                              : invoice.status === 'Paid' ? 'bg-gray-100 text-gray-400 cursor-not-allowed opacity-50' : 'bg-purple-50 text-purple-600 hover:bg-purple-100 hover:text-purple-700'
                          }`}
                          title={invoice.status === 'Paid' ? 'Not available for paid invoices' : 'Send to Legal Support'}
                        >
                          ⚖️
                        </button>
                        <button
                          onClick={() => handleDelete(invoice)}
                          className="p-1.5 rounded-lg bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700 transition-colors shadow-sm"
                          title="Delete"
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>

            </table>
            </div>
          )}

        </div>

        {/* ADD INVOICE PANEL — always visible next to the list,
            mirroring the Purchase Orders page's "Add PO" panel. Shows
            a placeholder while editing, since editing happens in a
            separate popup instead (matching PurchaseOrders.jsx's
            EditPOModal pattern). */}

        <div ref={formPanelRef} className="card flex-[1] w-full lg:sticky lg:top-4 bg-white rounded-xl shadow-xl overflow-y-auto max-h-[90vh]">

          {editingInvoiceId ? (
            <div className="p-6 text-center text-gray-500">
              <div className="text-4xl mb-3">✏️</div>
              <p className="font-medium">Editing an invoice</p>
              <p className="text-sm mt-1">Finish or cancel editing in the popup to add a new invoice here.</p>
            </div>
          ) : (
            <div>

              <form onSubmit={handleCreate}>

                {renderInvoiceFormBody()}

              </form>

            </div>
          )}

        </div>

        </div>

      </div>


      {/* EDIT INVOICE MODAL — separate popup, mirroring
          PurchaseOrders.jsx's EditPOModal, so editing doesn't just
          silently update the always-visible Add Invoice panel. */}

      {editingInvoiceId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-[200]">

          <div className="bg-white rounded-xl shadow-xl w-full max-w-5xl max-h-[95vh] overflow-y-auto">

            <form onSubmit={handleCreate}>

              {renderInvoiceFormBody()}

            </form>

          </div>

        </div>
      )}


      {/* INVOICE DETAIL / PRINT VIEW */}

      {selectedInvoice && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-[200]">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-3xl max-h-[95vh] overflow-y-auto">

            <div className="invoice-actions" style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '0.5rem',
              padding: '1rem',
            }}>
              <button
                onClick={() => handleDownloadPdf(selectedInvoice)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold"
              >
                Download PDF
              </button>
              <button
                onClick={() => setSelectedInvoice(null)}
                className="px-4 py-2 border border-gray-300 rounded-lg text-sm"
              >
                Close
              </button>
            </div>

            <div className="invoice-paper p-6">

              <h1 className="text-2xl font-bold mb-4">TAX INVOICE</h1>

              <div className="flex justify-between mb-6">

                <div>
                  <h2 className="font-bold text-lg">{selectedInvoice.company_name || 'Company'}</h2>
                  <p className="text-sm text-gray-600">{selectedInvoice.company_address}</p>
                  <p className="text-sm text-gray-600">GSTIN: {selectedInvoice.company_gstin || 'N/A'}</p>
                  {selectedInvoice.cin && <p className="text-sm text-gray-600">CIN: {selectedInvoice.cin}</p>}
                </div>

                <div className="text-right text-sm">
                  <b>Invoice No:</b> {selectedInvoice.invoice_number}
                  <br />
                  <b>Invoice Date:</b> {formatDate(selectedInvoice.invoice_date)}
                  <br />
                  <b>Due Date:</b> {formatDate(selectedInvoice.payment_due_date)}
                </div>

              </div>


              <div className="grid grid-cols-2 gap-6 mb-6">

                <div>
                  <b>Bill To</b>
                  <p>{selectedInvoice.counterparty_name}</p>
                  <p>{selectedInvoice.bill_to?.address}</p>
                  <p>GSTIN: {selectedInvoice.counterparty_gstin}</p>
                  <p>PAN: {selectedInvoice.counterparty_pan}</p>
                  {selectedInvoice.counterparty_email && <p>Email: {selectedInvoice.counterparty_email}</p>}
                  {selectedInvoice.counterparty_phone && <p>Mobile: {selectedInvoice.counterparty_phone}</p>}
                </div>

                <div>
                  <b>Ship To</b>
                  <p>{selectedInvoice.ship_to?.name}</p>
                  <p>{selectedInvoice.ship_to?.address}</p>
                </div>

              </div>


              <table className="w-full border mb-6">

                <thead className="bg-gray-100">
                  <tr>
                    <th className="p-2 text-left">#</th>
                    <th className="p-2 text-left">Description</th>
                    <th className="p-2 text-left">HSN/SAC</th>
                    <th className="p-2 text-left">Qty</th>
                    <th className="p-2 text-left">Rate</th>
                    <th className="p-2 text-left">Amount</th>
                  </tr>
                </thead>

                <tbody>

                  {(selectedInvoice.items || []).map((item, index) => (
                    <tr key={index} className="border-t">
                      <td className="p-2">{index + 1}</td>
                      <td className="p-2">{item.desc}</td>
                      <td className="p-2">{item.hsn}</td>
                      <td className="p-2">{item.qty}</td>
                      <td className="p-2">{money(item.rate, selectedInvoice.currency)}</td>
                      <td className="p-2">{money(item.amount, selectedInvoice.currency)}</td>
                    </tr>
                  ))}

                </tbody>

              </table>


              <div className="flex justify-end mb-6">
                <div className="w-72 space-y-1">
                  <p className="flex justify-between">
                    <span>Sub Total</span> <b>{money(selectedInvoice.subtotal, selectedInvoice.currency)}</b>
                  </p>

                  {selectedInvoice.tax_breakdown?.cgst > 0 && (
                    <p className="flex justify-between">
                      <span>CGST</span> <b>{money(selectedInvoice.tax_breakdown.cgst, selectedInvoice.currency)}</b>
                    </p>
                  )}
                  {selectedInvoice.tax_breakdown?.sgst > 0 && (
                    <p className="flex justify-between">
                      <span>SGST</span> <b>{money(selectedInvoice.tax_breakdown.sgst, selectedInvoice.currency)}</b>
                    </p>
                  )}
                  {selectedInvoice.tax_breakdown?.igst > 0 && (
                    <p className="flex justify-between">
                      <span>IGST</span> <b>{money(selectedInvoice.tax_breakdown.igst, selectedInvoice.currency)}</b>
                    </p>
                  )}

                  <p className="flex justify-between text-lg border-t pt-2">
                    <span>Total</span> <b>{money(selectedInvoice.total, selectedInvoice.currency)}</b>
                  </p>

                  <p className="flex justify-between">
                    <span>Balance Due</span> <b>{money(selectedInvoice.balance_due, selectedInvoice.currency)}</b>
                  </p>
                </div>
              </div>


              <div className="text-sm text-gray-600 space-y-1">
                {selectedInvoice.po_number && (
                  <p><b>PO Number:</b> {selectedInvoice.po_number}</p>
                )}
                {selectedInvoice.msme_no && (
                  <p><b>MSME No:</b> {selectedInvoice.msme_no}</p>
                )}
                {selectedInvoice.place_of_supply && (
                  <p><b>Place of Supply:</b> {selectedInvoice.place_of_supply}</p>
                )}
                {selectedInvoice.lut_arn && (
                  <p><b>LUT ARN:</b> {selectedInvoice.lut_arn}</p>
                )}
                {selectedInvoice.notes && (
                  <p><b>Notes:</b> {selectedInvoice.notes}</p>
                )}
              </div>

            </div>

          </div>
        </div>
      )}

      {reasonModal.open && reasonModal.action === 'MARK_PAID' && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-xl font-bold text-gray-900 mb-4">Mark Invoice as Paid</h3>
            <p className="text-sm text-gray-600 mb-4">
              Invoice <b>{reasonModal.invoice?.invoice_number}</b> — {money(reasonModal.invoice?.total, reasonModal.invoice?.currency)}
            </p>
            <label className="block text-sm font-medium text-gray-700 mb-2">Reason / Note *</label>
            <textarea
              value={reasonText}
              onChange={(e) => setReasonText(e.target.value)}
              placeholder="e.g. Payment received via bank transfer"
              rows={3}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 mb-4"
            />
            <label className="block text-sm font-medium text-gray-700 mb-2">Upload Payment Receipt (optional)</label>
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              onChange={(e) => setPaymentReceipt(e.target.files?.[0])}
              className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 mb-6"
            />
            <div className="flex gap-3">
              <button
                onClick={() => { setReasonModal({ open: false, action: '', invoice: null }); setReasonText(''); setPaymentReceipt(null) }}
                className="flex-1 border border-gray-200 text-gray-600 py-2 rounded-lg text-sm hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmMarkPaid}
                disabled={!reasonText.trim()}
                className={`flex-1 py-2 rounded-lg text-sm transition-colors ${
                  !reasonText.trim() ? 'bg-gray-300 text-gray-500 cursor-not-allowed' : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}

      {reminderModalInvoice && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full flex flex-col max-h-[90vh]">
            <div className="p-6 border-b border-gray-100 flex items-center justify-between">
              <h3 className="text-xl font-bold text-gray-900">Send Payment Reminder</h3>
              <button onClick={closeReminderModal} className="text-gray-400 hover:text-gray-600 transition-colors">
                <span className="text-2xl">&times;</span>
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-6">
              <div className="space-y-4">
                <div className="space-y-1">
                  <label className="text-sm font-semibold text-gray-700">Subject Line</label>
                  <input
                    type="text"
                    value={reminderSubject}
                    onChange={(e) => setReminderSubject(e.target.value)}
                    className="w-full rounded-lg border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-sm font-semibold text-gray-700">Email Body</label>
                  <textarea
                    value={reminderBody}
                    onChange={(e) => setReminderBody(e.target.value)}
                    rows={6}
                    className="w-full rounded-lg border-gray-300 focus:border-blue-500 focus:ring-blue-500 font-sans leading-relaxed"
                  />
                </div>
              </div>

              {/* Legal Notice Section — mirrors PO's ReminderModal */}
              <div className="legal-notice-section">
                <label className="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={reminderIncludeLegalNotice}
                    onChange={(e) => setReminderIncludeLegalNotice(e.target.checked)}
                  />
                  ⚖️ Attach Legal Notice as PDF
                </label>

                {reminderIncludeLegalNotice && (
                  <div className="mt-2">
                    <p className="text-xs text-gray-500">
                      📄 Edit legal notice below. It will be sent as a PDF attachment.
                    </p>
                    <textarea
                      value={reminderLegalNoticeContent}
                      onChange={(e) => setReminderLegalNoticeContent(e.target.value)}
                      rows={12}
                      className="w-full mt-2 rounded-lg border-gray-300 font-mono text-xs focus:border-blue-500 focus:ring-blue-500"
                      placeholder="Legal notice content will appear here..."
                    />
                    <p className="text-[11px] text-gray-400 mt-1">
                      ✅ This will be generated as a PDF and attached to the email
                    </p>
                  </div>
                )}
              </div>

              <div className="border-t border-gray-100 pt-6">
                <h4 className="text-sm font-bold text-gray-900 mb-4 uppercase tracking-wider">Schedule Reminder</h4>
                <div className="space-y-3">
                  <label className="flex items-center cursor-pointer group">
                    <input
                      type="radio"
                      name="invoice-reminder-schedule"
                      value="now"
                      checked={reminderScheduleType === 'now'}
                      onChange={() => setReminderScheduleType('now')}
                      className="h-4 w-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                    />
                    <span className="ml-3 text-sm font-medium text-gray-700 group-hover:text-gray-900">Send Now</span>
                  </label>

                  <label className="flex items-center cursor-pointer group">
                    <input
                      type="radio"
                      name="invoice-reminder-schedule"
                      value="later"
                      checked={reminderScheduleType === 'later'}
                      onChange={() => setReminderScheduleType('later')}
                      className="h-4 w-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                    />
                    <span className="ml-3 text-sm font-medium text-gray-700 group-hover:text-gray-900">Schedule for later</span>
                  </label>

                  {reminderScheduleType === 'later' && (
                    <div className="ml-7">
                      <input
                        type="datetime-local"
                        value={reminderScheduledAt}
                        onChange={(e) => setReminderScheduledAt(e.target.value)}
                        className="rounded-lg border-gray-300 focus:border-blue-500 focus:ring-blue-500 text-sm"
                        required
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="p-6 border-t border-gray-100 flex justify-end gap-3 bg-gray-50/50">
              <button
                onClick={closeReminderModal}
                className="px-6 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 transition-colors font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReminder}
                disabled={reminderSending || (reminderScheduleType === 'later' && !reminderScheduledAt)}
                className="px-8 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {reminderSending ? 'Processing...' : reminderScheduleType === 'later' ? 'Schedule Reminder' : 'Send Reminder'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showInvoiceLegalNoticeConfirm && (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 text-center">
            <div className="text-4xl mb-4">⚖️</div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Send Legal Notice?</h3>
            <p className="text-gray-600 mb-6">
              Are you sure you want to send a legal notice to:<br/>
              <strong>{showInvoiceLegalNoticeConfirm.invoice.counterparty_name} ({showInvoiceLegalNoticeConfirm.invoice.counterparty_email})</strong><br/><br/>
              This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowInvoiceLegalNoticeConfirm(null)}
                className="flex-1 px-6 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors font-medium"
              >
                Cancel
              </button>
              <button
                onClick={() => sendReminderRequest(showInvoiceLegalNoticeConfirm.payload)}
                disabled={reminderSending}
                className="flex-1 px-6 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors font-medium shadow-md disabled:opacity-50"
              >
                {reminderSending ? 'Sending...' : 'Yes, Send'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showLegalSupportConfirm && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6">
            <div className="text-4xl mb-4 text-center">⚖️</div>
            <h3 className="text-xl font-bold text-gray-900 mb-4 text-center">Send to Legal Support Team?</h3>
            <div className="bg-gray-50 rounded-lg p-4 mb-4 text-left text-sm space-y-1">
              <p><strong>Invoice:</strong> {showLegalSupportConfirm.invoice_number}</p>
              <p><strong>Customer:</strong> {showLegalSupportConfirm.counterparty_name}</p>
              <p><strong>Amount:</strong> {money(showLegalSupportConfirm.total, showLegalSupportConfirm.currency)}</p>
              <p><strong>Status:</strong> {showLegalSupportConfirm.status}</p>
            </div>
            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Reason/Note * <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={legalSupportReason}
                  onChange={(e) => setLegalSupportReason(e.target.value)}
                  placeholder="Why do you need legal support?"
                  rows={3}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Upload Evidence * <span className="text-red-500">*</span>
                  <span className="text-gray-400 text-xs ml-1">(PDF, JPG, PNG)</span>
                </label>
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  onChange={(e) => setLegalSupportFile(e.target.files?.[0])}
                  className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                />
                {legalSupportFile && (
                  <p className="text-xs text-gray-500 mt-1 flex items-center gap-3">
                    <span>Selected: {legalSupportFile.name}</span>
                    <button type="button" onClick={() => previewFile(legalSupportFile)} className="text-blue-700 hover:underline font-medium whitespace-nowrap">
                      🔍 View
                    </button>
                  </p>
                )}
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => { setShowLegalSupportConfirm(null); setLegalSupportReason(''); setLegalSupportFile(null) }}
                className="flex-1 px-6 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors font-medium"
              >
                Cancel
              </button>
              <button
                onClick={() => handleSendToLegal(showLegalSupportConfirm)}
                disabled={!legalSupportReason.trim() || !legalSupportFile}
                className="flex-1 px-6 py-2 rounded-lg bg-[#1a237e] text-white hover:bg-[#0d1440] transition-colors font-medium shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Send to Legal Team
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
