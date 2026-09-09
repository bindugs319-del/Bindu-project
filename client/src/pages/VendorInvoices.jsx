import { useState, useEffect, useCallback, useRef } from 'react'
import { vendorInvoices as vendorInvoicesApi, STATIC_BASE_URL } from '../services/api/apiClient'
import VendorInvoicePDFImportModal from '../components/vendor-invoices/VendorInvoicePDFImportModal'

/**
 * OEM / Vendor Bills — Accounts Payable: bills RECEIVED from a vendor.
 * Mirrors Invoices.jsx (Accounts Receivable) in look and feel, but the
 * form itself is deliberately leaner to match what VendorInvoice
 * actually models: no PO linkage, no Bill To/Ship To split (just one
 * "Vendor Details" block — this document's vendor IS the counterparty,
 * there's no second party to ship to), no LUT/SEZ/export fields, and no
 * Draft/Sent lifecycle — a received bill is either Unpaid or Paid.
 */
export default function VendorInvoices() {
  const emptyForm = {
    vendor_name: '',
    // Generic tax ID (VAT/GSTIN/FEIN/CIN/TAN/Chamber of Commerce/Other) —
    // replaces the old India-only GSTIN/PAN pair. See vendor_invoice_scan_service.py
    // for how the Import PDF flow auto-detects both the value and the type.
    vendor_tax_id: '',
    vendor_tax_id_type: '',
    vendor_email: '',
    vendor_phone: '',
    vendor_address: '',
    invoice_number: '',
    invoice_date: '',
    payment_due_date: '',
    payment_terms: '',
    place_of_supply: '',
    currency: 'INR',
    items: [{ desc: '', hsn: '', qty: 1, rate: 0, amount: 0 }],
    subtotal: 0,
    tax_breakdown: null,
    tax_amount: 0,
    total: 0,
    balance_due: 0,
    notes: '',
    document_url: '',
    document_filename: '',
  }

  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showArchived, setShowArchived] = useState(false)
  const [activeFilter, setActiveFilter] = useState('All')

  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingInvoiceId, setEditingInvoiceId] = useState(null)
  const [formData, setFormData] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const [vendorInvoiceFile, setVendorInvoiceFile] = useState(null)
  const [showPdfImport, setShowPdfImport] = useState(false)
  const [pdfScanBanner, setPdfScanBanner] = useState(null)

  const [markPaidModal, setMarkPaidModal] = useState(null) // invoice or null
  const [markPaidReason, setMarkPaidReason] = useState('')
  const [markPaidFile, setMarkPaidFile] = useState(null)
  const [markingPaid, setMarkingPaid] = useState(false)

  const [paidDetailsInvoice, setPaidDetailsInvoice] = useState(null)
  const [deleteConfirm, setDeleteConfirm] = useState(null)

  // Default recipient for automatic (5-days-before-due, then daily until
  // paid — see _daily_tasks_runner in main.py) and manual "Send Reminder"
  // vendor-invoice reminders. App-wide, set once here rather than
  // per-invoice — see /vendor-invoices/settings.
  const [reminderEmail, setReminderEmail] = useState('')
  const [reminderEmailSaved, setReminderEmailSaved] = useState('')
  const [savingReminderEmail, setSavingReminderEmail] = useState(false)
  const [sendingReminderId, setSendingReminderId] = useState(null)

  const formPanelRef = useRef(null)

  const fetchInvoices = useCallback(async () => {
    setLoading(true)
    try {
      const response = await vendorInvoicesApi.list({ limit: 100, include_archived: showArchived })
      if (response.ok) {
        setInvoices(response.data?.invoices || response.data || [])
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

  useEffect(() => {
    vendorInvoicesApi.getSettings().then(res => {
      if (res.ok) {
        const email = res.data?.vendor_reminder_email || ''
        setReminderEmail(email)
        setReminderEmailSaved(email)
      }
    })
  }, [])

  const saveReminderEmail = async () => {
    if (reminderEmail === reminderEmailSaved) return
    setSavingReminderEmail(true)
    const res = await vendorInvoicesApi.updateSettings(reminderEmail)
    if (res.ok) {
      setReminderEmailSaved(reminderEmail)
    }
    setSavingReminderEmail(false)
  }

  const handleSendReminder = async (inv) => {
    setSendingReminderId(inv.id)
    const res = await vendorInvoicesApi.sendReminder(inv.id)
    setSendingReminderId(null)
    if (!res.ok) {
      alert(res.error || 'Failed to send reminder.')
    }
  }

  const calculateTotals = (items) => {
    const subtotal = items.reduce((sum, item) => sum + (Number(item.amount) || 0), 0)
    setFormData(prev => ({
      ...prev,
      items,
      subtotal,
      total: subtotal + (Number(prev.tax_amount) || 0),
      balance_due: subtotal + (Number(prev.tax_amount) || 0),
    }))
  }

  const updateItem = (index, field, value) => {
    const items = [...formData.items]
    items[index] = { ...items[index], [field]: value }
    const qty = Number(items[index].qty) || 0
    const rate = Number(items[index].rate) || 0
    items[index].amount = qty * rate
    calculateTotals(items)
  }

  const addItem = () => {
    setFormData(prev => ({
      ...prev,
      items: [...prev.items, { desc: '', hsn: '', qty: 1, rate: 0, amount: 0 }],
    }))
  }

  const removeItem = (index) => {
    if (formData.items.length === 1) return
    const items = formData.items.filter((_, i) => i !== index)
    calculateTotals(items)
  }

  const closeFormModal = () => {
    setShowCreateModal(false)
    setEditingInvoiceId(null)
    setFormData(emptyForm)
    setVendorInvoiceFile(null)
    setFormError('')
    setPdfScanBanner(null)
  }

  const openCreateModal = () => {
    setFormData(emptyForm)
    setEditingInvoiceId(null)
    setFormError('')
    setPdfScanBanner(null)
    setShowCreateModal(true)
  }

  const openEditModal = (invoice) => {
    setFormData({
      vendor_name: invoice.vendor_name || '',
      vendor_tax_id: invoice.vendor_tax_id || '',
      vendor_tax_id_type: invoice.vendor_tax_id_type || '',
      vendor_email: invoice.vendor_email || '',
      vendor_phone: invoice.vendor_phone || '',
      vendor_address: invoice.vendor_address || '',
      invoice_number: invoice.invoice_number || '',
      invoice_date: invoice.invoice_date || '',
      payment_due_date: invoice.payment_due_date || '',
      payment_terms: invoice.payment_terms || '',
      place_of_supply: invoice.place_of_supply || '',
      currency: invoice.currency || 'INR',
      items: invoice.items && invoice.items.length > 0 ? invoice.items : emptyForm.items,
      subtotal: invoice.subtotal || 0,
      tax_breakdown: invoice.tax_breakdown || null,
      tax_amount: invoice.tax_amount || 0,
      total: invoice.total || 0,
      balance_due: invoice.balance_due || 0,
      notes: invoice.notes || '',
      document_url: invoice.document_url || '',
      document_filename: invoice.document_filename || '',
    })
    setEditingInvoiceId(invoice.id)
    setFormError('')
    setPdfScanBanner(null)
    setShowCreateModal(true)
  }

  // Fills the form directly from a scanned vendor PDF's fields/items —
  // same "no separate save step" flow as the Sales Invoice PDF import.
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
      setIfFound('vendor_name', fields.vendor_name)
      setIfFound('vendor_tax_id', fields.vendor_tax_id)
      setIfFound('vendor_tax_id_type', fields.vendor_tax_id_type)
      setIfFound('vendor_email', fields.vendor_email)
      setIfFound('vendor_phone', fields.vendor_phone)
      setIfFound('vendor_address', fields.vendor_address)
      setIfFound('invoice_number', fields.invoice_number)
      setIfFound('invoice_date', fields.invoice_date)
      setIfFound('payment_due_date', fields.payment_due_date)
      setIfFound('payment_terms', fields.payment_terms)
      setIfFound('place_of_supply', fields.place_of_supply)
      setIfFound('currency', fields.currency)

      if (mappedItems) {
        next.items = mappedItems
      } else if (fields.subtotal !== undefined || fields.total !== undefined) {
        next.subtotal = fields.subtotal ?? prev.subtotal
        next.tax_amount = fields.tax_amount ?? prev.tax_amount
        next.total = fields.total ?? prev.total
        next.balance_due = fields.total ?? prev.balance_due
      }
      return next
    })

    if (mappedItems) {
      calculateTotals(mappedItems)
    }

    setPdfScanBanner({ fileName, itemsFound: (items || []).length, warnings: warnings || [] })
    formPanelRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setFormError('')

    if (!formData.vendor_name.trim()) {
      setFormError('Vendor name is required.')
      return
    }
    if (!formData.invoice_number.trim()) {
      setFormError('Invoice number is required.')
      return
    }
    if (!formData.invoice_date || !formData.payment_due_date) {
      setFormError('Invoice date and payment due date are required.')
      return
    }

    setSaving(true)
    const payload = {
      ...formData,
      vendor_tax_id: formData.vendor_tax_id || null,
      vendor_tax_id_type: formData.vendor_tax_id ? (formData.vendor_tax_id_type || 'OTHER') : null,
      items: formData.items.filter(it => it.desc && it.desc.trim()),
    }

    const response = editingInvoiceId
      ? await vendorInvoicesApi.update(editingInvoiceId, payload)
      : await vendorInvoicesApi.create(payload)

    if (!response.ok) {
      setFormError(response.error || 'Failed to save vendor invoice.')
      setSaving(false)
      return
    }

    const savedId = editingInvoiceId || response.data?.id
    if (vendorInvoiceFile && savedId) {
      await vendorInvoicesApi.uploadDocument(savedId, vendorInvoiceFile)
    }

    setSaving(false)
    closeFormModal()
    fetchInvoices()
  }

  const handleArchive = async (invoice) => {
    await vendorInvoicesApi.archive(invoice.id)
    fetchInvoices()
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return
    await vendorInvoicesApi.delete(deleteConfirm.id)
    setDeleteConfirm(null)
    fetchInvoices()
  }

  const openMarkPaid = (invoice) => {
    setMarkPaidModal(invoice)
    setMarkPaidReason('')
    setMarkPaidFile(null)
  }

  const submitMarkPaid = async () => {
    if (!markPaidModal) return
    setMarkingPaid(true)
    const res = await vendorInvoicesApi.markPaid(
      markPaidModal.id,
      markPaidReason || `Paid vendor invoice ${markPaidModal.invoice_number}`,
      markPaidFile
    )
    setMarkingPaid(false)
    if (res.ok) {
      setMarkPaidModal(null)
      fetchInvoices()
    }
  }

  const money = (value, currency = 'INR') => {
    try {
      return new Intl.NumberFormat('en-IN', { style: 'currency', currency: currency || 'INR', minimumFractionDigits: 2 }).format(Number(value) || 0)
    } catch {
      return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(Number(value) || 0)
    }
  }

  const calculateDaysLeft = (dueDateStr) => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const dueDate = new Date(dueDateStr)
    dueDate.setHours(0, 0, 0, 0)
    return Math.floor((dueDate - today) / (1000 * 60 * 60 * 24))
  }

  const getDaysLeftBadge = (row) => {
    if (row.status === 'Paid') return <span className="text-gray-400">—</span>
    const daysLeft = calculateDaysLeft(row.payment_due_date)
    if (daysLeft > 7) return <span className="text-emerald-600 font-medium">{daysLeft} days left</span>
    if (daysLeft >= 1 && daysLeft <= 7) return <span className="text-amber-600 font-medium">{daysLeft} days left ⚠️</span>
    if (daysLeft === 0) return <span className="text-red-600 font-bold">Due Today!</span>
    return <span className="text-red-600 font-bold">0 days</span>
  }

  const isOverdue = (row) => row.status !== 'Paid' && calculateDaysLeft(row.payment_due_date) < 0

  const filteredInvoices = invoices.filter(inv => {
    if (activeFilter === 'All') return true
    if (activeFilter === 'Unpaid') return inv.status !== 'Paid'
    if (activeFilter === 'Paid') return inv.status === 'Paid'
    if (activeFilter === 'Overdue') return isOverdue(inv)
    return true
  })

  const totalAmount = filteredInvoices.reduce((sum, inv) => sum + (Number(inv.total) || 0), 0)

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#0F172A]">OEM / Vendor Bills</h1>
          <p className="text-gray-500 text-sm mt-1">Bills received from your vendors — Accounts Payable.</p>
        </div>
      </div>

      <div className="grid lg:grid-cols-[1fr_480px] gap-6 items-start">

        {/* LIST */}
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            {['All', 'Unpaid', 'Overdue', 'Paid'].map(f => (
              <button
                key={f}
                onClick={() => setActiveFilter(f)}
                className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
                  activeFilter === f ? 'bg-[#0F172A] text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {f}
              </button>
            ))}
            <label className="flex items-center gap-2 text-sm text-gray-600 ml-2">
              <input type="checkbox" checked={showArchived} onChange={e => setShowArchived(e.target.checked)} />
              Show Archived
            </label>
            <span className="ml-auto text-sm text-gray-500">Total: <strong className="text-gray-800">{money(totalAmount)}</strong></span>
          </div>

          <div className="bg-white rounded-xl shadow-sm border overflow-x-auto">
            {loading ? (
              <div className="p-8 text-center text-gray-400">Loading…</div>
            ) : error ? (
              <div className="p-8 text-center text-red-500">{error}</div>
            ) : filteredInvoices.length === 0 ? (
              <div className="p-8 text-center text-gray-400">
                <div className="text-4xl mb-2">📭</div>
                <p>No vendor bills found</p>
              </div>
            ) : (
              <table className="w-full text-sm min-w-[720px]">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="p-4 text-left whitespace-nowrap">Vendor</th>
                    <th className="p-4 text-left whitespace-nowrap">Invoice #</th>
                    <th className="p-4 text-left whitespace-nowrap">Amount</th>
                    <th className="p-4 text-left whitespace-nowrap">Due Date</th>
                    <th className="p-4 text-left whitespace-nowrap">Days Left</th>
                    <th className="p-4 text-left whitespace-nowrap">Status</th>
                    <th className="p-4 text-left whitespace-nowrap">Document</th>
                    <th className="p-4 text-right whitespace-nowrap">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {filteredInvoices.map(inv => (
                    <tr key={inv.id} className="hover:bg-gray-50">
                      <td className="p-4 font-medium text-gray-800">{inv.vendor_name}</td>
                      <td className="p-4 font-mono text-blue-600">{inv.invoice_number}</td>
                      <td className="p-4 font-semibold">{money(inv.total, inv.currency)}</td>
                      <td className="p-4 text-gray-500">{inv.payment_due_date ? new Date(inv.payment_due_date).toLocaleDateString('en-IN') : '—'}</td>
                      <td className="p-4">{getDaysLeftBadge(inv)}</td>
                      <td className="p-4">
                        <span className={`text-xs px-2 py-1 rounded-full font-semibold ${
                          inv.status === 'Paid' ? 'bg-green-100 text-green-700' :
                          isOverdue(inv) ? 'bg-red-100 text-red-700' :
                          'bg-orange-100 text-orange-700'
                        }`}>
                          {inv.status === 'Paid' ? 'Paid' : isOverdue(inv) ? 'Overdue' : 'Unpaid'}
                        </span>
                      </td>
                      <td className="p-4">
                        {inv.document_url ? (
                          <a
                            href={inv.document_url.startsWith('http') ? inv.document_url : `${STATIC_BASE_URL}${inv.document_url}`}
                            target="_blank" rel="noopener noreferrer"
                            className="text-blue-600 hover:underline whitespace-nowrap"
                          >
                            📄 View
                          </a>
                        ) : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="p-4">
                        <div className="flex items-center justify-end gap-1.5">
                          {inv.status === 'Paid' ? (
                            <button
                              onClick={() => setPaidDetailsInvoice(inv)}
                              className="p-1.5 rounded-lg bg-emerald-50 text-emerald-600 hover:bg-emerald-100 transition-colors"
                              title="View payment details"
                            >
                              🧾
                            </button>
                          ) : (
                            <button
                              onClick={() => openMarkPaid(inv)}
                              className="p-1.5 rounded-lg bg-green-50 text-green-600 hover:bg-green-100 transition-colors"
                              title="Mark as paid"
                            >
                              ✅
                            </button>
                          )}
                          <button
                            onClick={() => openEditModal(inv)}
                            disabled={inv.status === 'Paid'}
                            className="p-1.5 rounded-lg bg-orange-50 text-orange-600 hover:bg-orange-100 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                            title={inv.status === 'Paid' ? "Paid bills can't be edited" : 'Edit'}
                          >
                            ✏️
                          </button>
                          <button
                            onClick={() => handleSendReminder(inv)}
                            disabled={inv.status === 'Paid' || sendingReminderId === inv.id}
                            className="p-1.5 rounded-lg bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                            title={inv.status === 'Paid' ? 'Reminder not available for paid bills' : 'Send Reminder'}
                          >
                            {sendingReminderId === inv.id ? '…' : '📧'}
                          </button>
                          <button
                            onClick={() => handleArchive(inv)}
                            className="p-1.5 rounded-lg bg-purple-50 text-purple-600 hover:bg-purple-100 transition-colors"
                            title={inv.archived ? 'Unarchive' : 'Archive'}
                          >
                            🗄️
                          </button>
                          <button
                            onClick={() => setDeleteConfirm(inv)}
                            className="p-1.5 rounded-lg bg-red-50 text-red-600 hover:bg-red-100 transition-colors"
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
            )}
          </div>
        </div>

        {/* ADD / EDIT PANEL */}
        <div ref={formPanelRef} className="min-w-0 bg-white rounded-xl shadow-sm border p-6 sticky top-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-primary-600">
              {editingInvoiceId ? 'Edit Vendor Invoice' : 'Add Vendor Invoice'}
            </h2>
            {(editingInvoiceId || formData.vendor_name || formData.invoice_number) && (
              <button onClick={closeFormModal} className="text-sm text-gray-400 hover:text-gray-600">Clear</button>
            )}
          </div>

          <button
            type="button"
            onClick={() => setShowPdfImport(true)}
            className="w-full mb-6 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition-colors"
          >
            📥 Import Vendor Bill (PDF)
          </button>

          <div className="mb-6 rounded-xl border border-gray-200 bg-gray-50 p-4">
            <label className="block text-sm font-semibold text-gray-700 mb-1">Reminder Email</label>
            <p className="text-xs text-gray-500 mb-2">
              Set once — every vendor bill's payment reminders (automatic, starting 5 days before the due date and
              repeating daily until paid, plus manual "Send Reminder") go to this address until you change it.
            </p>
            <div className="flex gap-2">
              <input
                type="email"
                value={reminderEmail}
                onChange={e => setReminderEmail(e.target.value)}
                onBlur={saveReminderEmail}
                placeholder="e.g. accounts@yourcompany.com"
                className="flex-1 border p-2 rounded-lg text-sm"
              />
              {savingReminderEmail && <span className="text-xs text-gray-400 self-center">Saving…</span>}
              {!savingReminderEmail && reminderEmail && reminderEmail === reminderEmailSaved && (
                <span className="text-xs text-green-600 self-center">Saved</span>
              )}
            </div>
          </div>

          {pdfScanBanner && (
            <div className="mb-6 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">
                    Filled from {pdfScanBanner.fileName} — review the fields below, fill in anything missed, then save.
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
                <button type="button" onClick={() => setPdfScanBanner(null)} className="text-green-700 hover:text-green-900 font-bold leading-none" aria-label="Dismiss">×</button>
              </div>
            </div>
          )}

          {formError && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{formError}</div>
          )}

          <form onSubmit={handleSubmit}>

            {/* VENDOR DETAILS */}
            <h3 className="font-bold text-lg mb-3">Vendor Details</h3>
            <div className="grid md:grid-cols-2 gap-4 mb-6">
              <div className="md:col-span-2">
                <label className="block text-xs font-medium text-gray-600 mb-1">Vendor Name <span className="text-red-500">*</span></label>
                <input required value={formData.vendor_name} onChange={e => setFormData({ ...formData, vendor_name: e.target.value })} className="border p-2 rounded w-full" />
              </div>
              <div className="md:col-span-2">
                <label className="block text-xs font-medium text-gray-600 mb-1">Vendor Address</label>
                <textarea value={formData.vendor_address} onChange={e => setFormData({ ...formData, vendor_address: e.target.value })} className="border p-2 rounded w-full" rows="2" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Tax ID</label>
                <input value={formData.vendor_tax_id} onChange={e => setFormData({ ...formData, vendor_tax_id: e.target.value })} placeholder="e.g. GSTIN, VAT, FEIN number" className="border p-2 rounded w-full" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Tax ID Type</label>
                <select value={formData.vendor_tax_id_type} onChange={e => setFormData({ ...formData, vendor_tax_id_type: e.target.value })} className="border p-2 rounded w-full bg-white">
                  <option value="">Select type…</option>
                  <option value="GSTIN">GSTIN</option>
                  <option value="PAN">PAN</option>
                  <option value="VAT">VAT</option>
                  <option value="FEIN">FEIN</option>
                  <option value="CIN">CIN</option>
                  <option value="TAN">TAN</option>
                  <option value="COC">Chamber of Commerce</option>
                  <option value="OTHER">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Vendor Email</label>
                <input type="email" value={formData.vendor_email} onChange={e => setFormData({ ...formData, vendor_email: e.target.value })} className="border p-2 rounded w-full" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Vendor Mobile</label>
                <input type="tel" value={formData.vendor_phone} onChange={e => setFormData({ ...formData, vendor_phone: e.target.value })} className="border p-2 rounded w-full" />
              </div>
            </div>

            {/* INVOICE INFO */}
            <h3 className="font-bold text-lg mb-3">Invoice Information</h3>
            <div className="grid md:grid-cols-3 gap-4 mb-6">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Invoice Number <span className="text-red-500">*</span></label>
                <input required value={formData.invoice_number} onChange={e => setFormData({ ...formData, invoice_number: e.target.value })} className="border p-2 rounded w-full" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Invoice Date <span className="text-red-500">*</span></label>
                <input required type="date" value={formData.invoice_date} onChange={e => setFormData({ ...formData, invoice_date: e.target.value })} className="border p-2 rounded w-full" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Payment Due Date <span className="text-red-500">*</span></label>
                <input required type="date" value={formData.payment_due_date} onChange={e => setFormData({ ...formData, payment_due_date: e.target.value })} className="border p-2 rounded w-full" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Payment Terms</label>
                <input value={formData.payment_terms} onChange={e => setFormData({ ...formData, payment_terms: e.target.value })} className="border p-2 rounded w-full" placeholder="e.g. Net 30" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Place of Supply</label>
                <input value={formData.place_of_supply} onChange={e => setFormData({ ...formData, place_of_supply: e.target.value })} className="border p-2 rounded w-full" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Currency</label>
                <select value={formData.currency} onChange={e => setFormData({ ...formData, currency: e.target.value })} className="border p-2 rounded w-full">
                  <option value="INR">INR</option>
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                  <option value="GBP">GBP</option>
                </select>
              </div>
            </div>

            {/* ITEMS */}
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-bold text-lg">Items</h3>
              <button type="button" onClick={addItem} className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-3 py-1.5 rounded-lg">+ Add Item</button>
            </div>
            <div className="overflow-x-auto mb-6">
              <table className="w-full text-sm min-w-[500px]">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="p-2 text-left">Description</th>
                    <th className="p-2 text-left">HSN/SAC</th>
                    <th className="p-2 text-left">Qty</th>
                    <th className="p-2 text-left">Rate</th>
                    <th className="p-2 text-left">Amount</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {formData.items.map((item, idx) => (
                    <tr key={idx} className="border-b">
                      <td className="p-2"><input value={item.desc} onChange={e => updateItem(idx, 'desc', e.target.value)} className="border p-1.5 rounded w-full" /></td>
                      <td className="p-2"><input value={item.hsn || ''} onChange={e => updateItem(idx, 'hsn', e.target.value)} className="border p-1.5 rounded w-full" /></td>
                      <td className="p-2"><input type="number" min="0" step="any" value={item.qty} onChange={e => updateItem(idx, 'qty', e.target.value)} className="border p-1.5 rounded w-20" /></td>
                      <td className="p-2"><input type="number" min="0" step="any" value={item.rate} onChange={e => updateItem(idx, 'rate', e.target.value)} className="border p-1.5 rounded w-24" /></td>
                      <td className="p-2 font-medium">{money(item.amount, formData.currency)}</td>
                      <td className="p-2">
                        {formData.items.length > 1 && (
                          <button type="button" onClick={() => removeItem(idx)} className="text-red-500 hover:text-red-700">✕</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex justify-end mb-6">
              <div className="w-full max-w-xs space-y-1 text-sm">
                <div className="flex justify-between"><span className="text-gray-500">Subtotal</span><span>{money(formData.subtotal, formData.currency)}</span></div>
                <div className="flex justify-between font-bold text-base border-t pt-1"><span>Total</span><span>{money(formData.total, formData.currency)}</span></div>
              </div>
            </div>

            {/* DOCUMENT */}
            <h3 className="font-bold text-lg mb-3">Vendor's Document</h3>
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">Upload their invoice/PDF (optional)</label>
              <input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={e => setVendorInvoiceFile(e.target.files?.[0] || null)} />
              {vendorInvoiceFile && <p className="text-sm text-gray-500 mt-1">Selected: {vendorInvoiceFile.name}</p>}
              {editingInvoiceId && formData.document_url && !vendorInvoiceFile && (
                <p className="text-sm text-gray-500 mt-1">
                  Current: <a href={formData.document_url.startsWith('http') ? formData.document_url : `${STATIC_BASE_URL}${formData.document_url}`} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">{formData.document_filename || 'View document'}</a>
                </p>
              )}
            </div>

            <label className="block text-xs font-medium text-gray-600 mb-1">Notes</label>
            <textarea value={formData.notes} onChange={e => setFormData({ ...formData, notes: e.target.value })} className="w-full border p-2 rounded mb-6" rows="3" placeholder="Notes" />

            <div className="flex gap-3">
              <button type="button" onClick={closeFormModal} className="flex-1 px-6 py-2.5 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 font-medium">Cancel</button>
              <button type="submit" disabled={saving} className="flex-1 px-6 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold disabled:opacity-60">
                {saving ? 'Saving…' : editingInvoiceId ? 'Save Changes' : 'Add Vendor Invoice'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {showPdfImport && (
        <VendorInvoicePDFImportModal onClose={() => setShowPdfImport(false)} onScanned={handlePdfScanned} />
      )}

      {markPaidModal && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-xl font-bold text-gray-900 mb-1">Mark as Paid</h3>
            <p className="text-sm text-gray-500 mb-4">{markPaidModal.vendor_name} — {markPaidModal.invoice_number}</p>
            <label className="block text-xs font-medium text-gray-600 mb-1">Note (optional)</label>
            <textarea value={markPaidReason} onChange={e => setMarkPaidReason(e.target.value)} className="w-full border p-2 rounded mb-4" rows="2" placeholder="e.g. Paid via bank transfer" />
            <label className="block text-xs font-medium text-gray-600 mb-1">Payment Receipt (optional)</label>
            <input type="file" onChange={e => setMarkPaidFile(e.target.files?.[0] || null)} className="mb-6" />
            <div className="flex gap-3">
              <button onClick={() => setMarkPaidModal(null)} className="flex-1 px-6 py-2.5 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 font-medium">Cancel</button>
              <button onClick={submitMarkPaid} disabled={markingPaid} className="flex-1 px-6 py-2.5 rounded-lg bg-green-600 hover:bg-green-700 text-white font-semibold disabled:opacity-60">
                {markingPaid ? 'Saving…' : 'Confirm Paid'}
              </button>
            </div>
          </div>
        </div>
      )}

      {paidDetailsInvoice && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
            <div className="text-4xl mb-3 text-center">🧾</div>
            <h3 className="text-xl font-bold text-gray-900 mb-1 text-center">Payment Receipt</h3>
            <p className="text-center text-sm text-gray-500 mb-4">Vendor Invoice {paidDetailsInvoice.invoice_number}</p>
            <div className="bg-gray-50 rounded-lg p-4 mb-4 text-sm space-y-1">
              <p><strong>Vendor:</strong> {paidDetailsInvoice.vendor_name}</p>
              <p><strong>Amount:</strong> {money(paidDetailsInvoice.total, paidDetailsInvoice.currency)}</p>
              <p><strong>Status:</strong> {paidDetailsInvoice.status}</p>
              <p><strong>Paid on:</strong> {paidDetailsInvoice.payment_completed_at ? new Date(paidDetailsInvoice.payment_completed_at).toLocaleString('en-IN') : '—'}</p>
            </div>
            {paidDetailsInvoice.payment_receipt_url ? (
              <a
                href={paidDetailsInvoice.payment_receipt_url.startsWith('http') ? paidDetailsInvoice.payment_receipt_url : `${STATIC_BASE_URL}${paidDetailsInvoice.payment_receipt_url}`}
                target="_blank" rel="noopener noreferrer"
                className="block text-center bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-2.5 rounded-lg transition-colors mb-3"
              >
                📄 View / Download Receipt {paidDetailsInvoice.payment_receipt_filename ? `(${paidDetailsInvoice.payment_receipt_filename})` : ''}
              </a>
            ) : (
              <p className="text-center text-sm text-gray-400 mb-3">No receipt file was uploaded for this payment.</p>
            )}
            <button onClick={() => setPaidDetailsInvoice(null)} className="w-full px-6 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 font-medium">Close</button>
          </div>
        </div>
      )}

      {deleteConfirm && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-sm w-full p-6 text-center">
            <div className="text-4xl mb-3">⚠️</div>
            <h3 className="text-lg font-bold text-gray-900 mb-2">Delete this vendor bill?</h3>
            <p className="text-sm text-gray-500 mb-6">{deleteConfirm.vendor_name} — {deleteConfirm.invoice_number}. This can't be undone.</p>
            <div className="flex gap-3">
              <button onClick={() => setDeleteConfirm(null)} className="flex-1 px-6 py-2.5 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 font-medium">Cancel</button>
              <button onClick={handleDelete} className="flex-1 px-6 py-2.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold">Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
