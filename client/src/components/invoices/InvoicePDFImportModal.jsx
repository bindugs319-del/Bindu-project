import { useState, useEffect } from 'react'
import PropTypes from 'prop-types'
import { salesInvoices } from '../../services/api/apiClient'

const FIELD_LABELS = {
  invoice_number: 'Invoice Number',
  counterparty_name: 'Counterparty Name',
  counterparty_gstin: 'GSTIN',
  counterparty_email: 'Email',
  counterparty_phone: 'Phone',
  subtotal: 'Subtotal',
  tax_amount: 'Tax Amount (₹)',
  total: 'Total',
  invoice_date: 'Invoice Date',
  payment_due_date: 'Payment Due Date',
}

const DATE_FIELDS = new Set(['invoice_date', 'payment_due_date'])
const NUMBER_FIELDS = new Set(['subtotal', 'tax_amount', 'total'])

export default function InvoicePDFImportModal({ onClose, onImportComplete, initialFile }) {
  const [step, setStep] = useState(initialFile ? 'scanning' : 'upload') // upload | scanning | review | importing | done
  const [file, setFile] = useState(initialFile || null)
  const [fields, setFields] = useState({})
  const [warnings, setWarnings] = useState([])
  const [willUpdateExisting, setWillUpdateExisting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const runScan = async (selectedFile) => {
    setFile(selectedFile)
    setError('')
    setStep('scanning')
    const res = await salesInvoices.scanPdf(selectedFile)
    if (!res.ok) {
      setError(res.error || 'Failed to read this PDF.')
      setStep('upload')
      return
    }
    const data = res.data?.data || res.data || {}
    setFields(data.fields || {})
    setWarnings(data.warnings || [])
    setWillUpdateExisting(!!data.will_update_existing)
    setStep('review')
  }

  const handleFileChange = (e) => {
    const selectedFile = e.target.files?.[0]
    if (!selectedFile) return
    if (!/\.(pdf|jpe?g|png)$/i.test(selectedFile.name)) {
      setError('Please select a PDF or an image (.pdf, .jpg, .jpeg, .png)')
      return
    }
    runScan(selectedFile)
  }

  useEffect(() => {
    if (initialFile) runScan(initialFile)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialFile])

  const setField = (key, value) => setFields(prev => ({ ...prev, [key]: value }))

  const handleConfirm = async () => {
    setStep('importing')
    setError('')
    const res = await salesInvoices.importPdf(fields)
    if (!res.ok) {
      setError(res.error || 'Failed to save this invoice.')
      setStep('review')
      return
    }
    const data = res.data?.data || res.data || {}
    setResult(data)
    setStep('done')
    onImportComplete?.()
  }

  const reset = () => {
    setFile(null)
    setFields({})
    setWarnings([])
    setError('')
    setResult(null)
    setStep('upload')
  }

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4 flex-shrink-0">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-heading font-bold text-gray-900">Import Invoice from PDF</h2>
              <p className="text-sm text-gray-500 mt-1">
                Upload a Tax Invoice PDF — we&rsquo;ll read it and fill in the fields for you to confirm.
              </p>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors" type="button">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto flex-grow">
          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {step === 'upload' && (
            <div className="relative group">
              <label htmlFor="invoice-pdf-scan-file" className="block text-sm font-medium text-gray-700 mb-2">
                Select Invoice PDF
              </label>
              <input
                id="invoice-pdf-scan-file"
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={handleFileChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10 top-7"
              />
              <div className="w-full py-12 px-4 border-2 border-dashed border-gray-300 group-hover:border-primary-400 rounded-xl flex flex-col items-center justify-center transition-colors">
                <svg className="w-12 h-12 mb-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <span className="text-base font-medium text-gray-600">Click or drag a PDF or photo to import</span>
                <span className="text-xs text-gray-400 mt-1">Text-based PDFs read most reliably; scanned/photographed invoices use OCR and need a quick review</span>
              </div>
            </div>
          )}

          {step === 'scanning' && (
            <div className="text-center py-10 text-gray-500 text-sm">Reading PDF&hellip;</div>
          )}

          {step === 'review' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-600">
                  <span className="font-semibold text-gray-900">{file?.name}</span>
                </p>
                <button onClick={reset} className="text-xs text-primary-600 hover:underline font-medium">
                  Choose a different file
                </button>
              </div>

              <div className={`rounded-lg px-3 py-2 text-xs border ${willUpdateExisting ? 'bg-amber-50 border-amber-200 text-amber-800' : 'bg-green-50 border-green-200 text-green-700'}`}>
                {willUpdateExisting
                  ? `An open invoice with number "${fields.invoice_number}" already exists — confirming will update it, not create a duplicate.`
                  : 'No existing open invoice with this number — confirming will create a new one.'}
              </div>

              {warnings.length > 0 && (
                <div className="rounded-lg px-3 py-2 text-xs border bg-yellow-50 border-yellow-200 text-yellow-800 space-y-1">
                  {warnings.map((w, i) => <div key={i}>⚠️ {w}</div>)}
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {Object.keys(FIELD_LABELS).map((key) => (
                  <div key={key} className={key === 'counterparty_name' || key === 'invoice_number' ? 'sm:col-span-2' : ''}>
                    <label className="block text-xs font-medium text-gray-500 mb-1">{FIELD_LABELS[key]}</label>
                    <input
                      type={DATE_FIELDS.has(key) ? 'date' : NUMBER_FIELDS.has(key) ? 'number' : 'text'}
                      value={fields[key] ?? ''}
                      onChange={(e) => setField(key, e.target.value)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-200"
                    />
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-400">
                Note: line items aren&rsquo;t read from the PDF. A new invoice is created with no items; an existing invoice keeps its current items.
              </p>
            </div>
          )}

          {step === 'importing' && (
            <div className="text-center py-10 text-gray-500 text-sm">Saving invoice&hellip;</div>
          )}

          {step === 'done' && result && (
            <div className="text-center py-10">
              <div className="text-4xl mb-3">✅</div>
              <p className="text-base font-semibold text-gray-900">
                {result.action === 'updated' ? 'Existing invoice updated' : 'New invoice created'}
              </p>
              <p className="text-sm text-gray-500 mt-1">Invoice {fields.invoice_number} saved successfully.</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50 rounded-b-xl flex gap-3 flex-shrink-0">
          {step !== 'done' ? (
            <>
              <button
                onClick={onClose}
                className="flex-1 px-6 py-3 rounded-lg border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 transition-colors font-medium"
              >
                Cancel
              </button>
              {step === 'review' && (
                <button onClick={handleConfirm} className="flex-1 btn-primary">
                  {willUpdateExisting ? 'Confirm & Update Invoice' : 'Confirm & Create Invoice'}
                </button>
              )}
            </>
          ) : (
            <button onClick={onClose} className="flex-1 btn-primary">Done</button>
          )}
        </div>
      </div>
    </div>
  )
}

InvoicePDFImportModal.propTypes = {
  onClose: PropTypes.func.isRequired,
  onImportComplete: PropTypes.func,
  initialFile: PropTypes.object,
}
