import { useState, useEffect } from 'react'
import PropTypes from 'prop-types'
import { salesInvoices } from '../../services/api/apiClient'
import * as XLSX from 'xlsx'

const FIELD_ALIASES = {
  invoice_number: ["Invoice #", "Invoice Number", "Invoice No", "Bill No", "Reference"],
  invoice_date: ["Invoice Date", "Date", "Bill Date"],
  payment_due_date: ["Due Date", "Payment Due Date", "Due", "Payment Due"],
  counterparty_name: ["Counterparty", "Counterparty Name", "Customer", "Customer Name", "Client", "Bill To"],
  counterparty_gstin: ["GSTIN", "Counterparty GSTIN", "GSTIN/UIN", "Tax ID", "GST No"],
  counterparty_email: ["Email", "Counterparty Email", "Customer Email", "Contact Email"],
  counterparty_phone: ["Phone", "Mobile", "Counterparty Phone", "Contact"],
  subtotal: ["Subtotal", "Sub Total", "Taxable Amount"],
  tax_rate_percent: ["Tax %", "Tax Rate", "GST %", "GST Rate", "Tax Percent", "GST Percent"],
  tax_amount: ["Tax Amount", "GST Amount", "Tax"],
  total: ["Total", "Amount", "Grand Total", "Invoice Amount"],
  status: ["Status"],
}

const FIELD_LABELS = {
  invoice_number: 'Invoice Number',
  invoice_date: 'Invoice Date',
  payment_due_date: 'Payment Due Date',
  counterparty_name: 'Counterparty Name',
  counterparty_gstin: 'GSTIN',
  counterparty_email: 'Email',
  counterparty_phone: 'Phone',
  subtotal: 'Subtotal',
  tax_rate_percent: 'Tax Rate (%)',
  tax_amount: 'Tax Amount (₹)',
  total: 'Total',
  status: 'Status',
}

const REQUIRED_FIELDS = ['invoice_date', 'payment_due_date', 'counterparty_name']
const VALID_STATUSES = ['Draft', 'Pending Operations Review', 'Pending Master Admin Approval', 'Approved', 'Paid']

const formatDateToISO = (dateStr) => {
  if (!dateStr) return null
  const s = String(dateStr).trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s
  const ddmmyyyy = s.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/)
  if (ddmmyyyy) {
    const [_, d, m, y] = ddmmyyyy
    return `${y}-${m.padStart(2, '0')}-${d.padStart(2, '0')}`
  }
  const d = new Date(s)
  if (!isNaN(d.getTime())) return d.toISOString().split('T')[0]
  return null
}

const parseAmount = (val) => {
  if (val === undefined || val === null) return 0
  const s = String(val).replace(/[₹Rs.,\s%]/g, '')
  const parsed = parseFloat(s)
  return isNaN(parsed) ? 0 : parsed
}

const looksLikePercent = (val) => {
  if (val === undefined || val === null) return false
  return String(val).includes('%')
}

export default function InvoiceCSVImportModal({ onClose, onImportComplete, initialFile }) {
  const [step, setStep] = useState(1)
  const [file, setFile] = useState(null)
  const [rawData, setRawData] = useState([])
  const [headers, setHeaders] = useState([])
  const [mapping, setMapping] = useState({})
  const [importing, setImporting] = useState(false)
  const [importProgress, setImportProgress] = useState(0)
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')

  const applyMapping = (fileHeaders) => {
    const newMapping = {}
    const normalizedHeaders = fileHeaders.map(h => String(h).toLowerCase().trim())
    const claimedIdx = new Set()

    // Pass 1: exact header matches only. This must run for every field
    // before any substring matching happens, so an exact match (e.g. a
    // column literally named "Total") always wins a header away from a
    // looser partial match (e.g. "Tax Amount" partially matching "Amount").
    Object.entries(FIELD_ALIASES).forEach(([field, aliases]) => {
      const idx = normalizedHeaders.findIndex((h, i) => !claimedIdx.has(i) && aliases.some(alias => h === alias.toLowerCase()))
      if (idx !== -1) {
        newMapping[field] = fileHeaders[idx]
        claimedIdx.add(idx)
      }
    })

    // Pass 2: substring matches, only for fields still unmapped, and only
    // considering headers not already claimed by an exact match above.
    Object.entries(FIELD_ALIASES).forEach(([field, aliases]) => {
      if (newMapping[field]) return
      const idx = normalizedHeaders.findIndex((h, i) => !claimedIdx.has(i) && aliases.some(alias => h.includes(alias.toLowerCase())))
      if (idx !== -1) {
        newMapping[field] = fileHeaders[idx]
        claimedIdx.add(idx)
      }
    })

    return newMapping
  }

  const readFile = (selectedFile) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const data = new Uint8Array(e.target.result)
          const workbook = XLSX.read(data, { type: 'array', cellDates: true })
          const sheetName = workbook.SheetNames.find(name => {
            const sheet = workbook.Sheets[name]
            return XLSX.utils.sheet_to_json(sheet).length > 0
          }) || workbook.SheetNames[0]
          const sheet = workbook.Sheets[sheetName]
          const json = XLSX.utils.sheet_to_json(sheet, { raw: false })
          resolve(json)
        } catch (err) {
          reject(err)
        }
      }
      reader.onerror = reject
      reader.readAsArrayBuffer(selectedFile)
    })
  }

  const handleFileChange = async (e) => {
    const selectedFile = e.target.files?.[0]
    if (!selectedFile) return

    const isAllowed = selectedFile.name.endsWith('.csv') ||
      selectedFile.name.endsWith('.xlsx') ||
      selectedFile.name.endsWith('.xls')

    if (!isAllowed) {
      setError('Please select a CSV or Excel file (.csv, .xlsx, .xls)')
      return
    }

    setFile(selectedFile)
    setError('')

    try {
      const data = await readFile(selectedFile)
      if (data && data.length > 0) {
        const fileHeaders = Object.keys(data[0])
        setRawData(data)
        setHeaders(fileHeaders)
        setMapping(applyMapping(fileHeaders))
        setStep(2)
      } else {
        setError('The file appears to be empty.')
      }
    } catch (err) {
      setError('Error reading file: ' + err.message)
    }
  }

  useEffect(() => {
    if (initialFile) {
      handleFileChange({ target: { files: [initialFile] } })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialFile])

  const handleConfirmImport = async () => {
    setImporting(true)
    setError('')
    setImportProgress(0)

    const processedData = rawData.map(row => {
      const rawTotalStr = mapping.total ? String(row[mapping.total] ?? '').trim() : ''
      const rawSubtotalStr = mapping.subtotal ? String(row[mapping.subtotal] ?? '').trim() : ''
      const rawTaxAmountStr = mapping.tax_amount ? String(row[mapping.tax_amount] ?? '').trim() : ''
      const rawTaxRateStr = mapping.tax_rate_percent ? String(row[mapping.tax_rate_percent] ?? '').trim() : ''

      let total = rawTotalStr ? parseAmount(rawTotalStr) : 0
      let subtotal = rawSubtotalStr ? parseAmount(rawSubtotalStr) : 0
      let taxAmount = rawTaxAmountStr ? parseAmount(rawTaxAmountStr) : 0

      // A rate applies if it's explicitly mapped to "Tax Rate (%)", or if
      // whatever got mapped to "Tax Amount" actually contains a % sign
      // (e.g. someone's "Tax" column has "18%" instead of a rupee value).
      const hasExplicitRate = !!rawTaxRateStr
      const taxIsActuallyRate = !hasExplicitRate && looksLikePercent(rawTaxAmountStr)
      const rate = hasExplicitRate ? parseAmount(rawTaxRateStr) : (taxIsActuallyRate ? parseAmount(rawTaxAmountStr) : null)

      if (rate !== null) {
        // We have a percentage rate -- derive amounts from whichever of
        // Subtotal / Total was actually filled in.
        if (rawSubtotalStr) {
          taxAmount = subtotal * (rate / 100)
          total = subtotal + taxAmount
        } else if (rawTotalStr) {
          subtotal = total / (1 + rate / 100)
          taxAmount = total - subtotal
        } else {
          taxAmount = 0
        }
      } else {
        // Flat currency tax amount -- fall back to auto-filling whichever
        // of Total / Subtotal is missing, using the other plus Tax Amount.
        if (!rawTotalStr && rawSubtotalStr) {
          total = subtotal + taxAmount
        } else if (!rawSubtotalStr && rawTotalStr) {
          subtotal = Math.max(total - taxAmount, 0)
        } else if (!rawTotalStr && !rawSubtotalStr) {
          total = 0
          subtotal = 0
        }
      }

      const rawStatus = String(row[mapping.status] || 'Draft').trim()
      const status = VALID_STATUSES.find(s => s.toLowerCase() === rawStatus.toLowerCase()) || 'Draft'

      return {
        invoice_number: String(row[mapping.invoice_number] || '').trim() || undefined,
        invoice_date: formatDateToISO(row[mapping.invoice_date]) || new Date().toISOString().split('T')[0],
        payment_due_date: formatDateToISO(row[mapping.payment_due_date]) || new Date().toISOString().split('T')[0],
        counterparty_name: String(row[mapping.counterparty_name] || '').trim(),
        counterparty_gstin: String(row[mapping.counterparty_gstin] || '').trim() || undefined,
        counterparty_email: String(row[mapping.counterparty_email] || '').trim() || undefined,
        counterparty_phone: String(row[mapping.counterparty_phone] || '').trim() || undefined,
        subtotal: Math.round(subtotal * 100) / 100,
        tax_amount: Math.round(taxAmount * 100) / 100,
        total: Math.round(total * 100) / 100,
        balance_due: total,
        status,
        items: [],
      }
    }).filter(r => r.counterparty_name)

    const skippedRows = []
    let successCount = 0
    let failedCount = 0

    try {
      for (let i = 0; i < processedData.length; i++) {
        const row = processedData[i]
        try {
          const res = await salesInvoices.create(row)
          if (res.ok) {
            successCount++
          } else {
            failedCount++
            skippedRows.push({ ...row, error: res.error })
          }
        } catch (err) {
          failedCount++
          skippedRows.push({ ...row, error: err.message })
        }
        setImportProgress(Math.round(((i + 1) / processedData.length) * 100))
      }

      setResults({
        total: processedData.length,
        success: successCount,
        failed: failedCount,
        skippedData: skippedRows
      })

      if (successCount > 0) onImportComplete()
      setStep(3)
    } catch (err) {
      setError(err.message || 'Failed to process import')
    } finally {
      setImporting(false)
    }
  }

  const downloadSkippedRows = () => {
    if (!results?.skippedData?.length) return
    const csvHeaders = Object.keys(results.skippedData[0]).join(',')
    const rows = results.skippedData.map(r => Object.values(r).join(',')).join('\n')
    const csv = `${csvHeaders}\n${rows}`
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `skipped_invoices_${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4 flex-shrink-0">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-heading font-bold text-gray-900">Import Invoices</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors" type="button" disabled={importing}>
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="flex items-center mt-4 gap-4">
            {[1, 2, 3].map(s => (
              <div key={s} className="flex items-center gap-2">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                  step === s ? 'bg-primary-600 text-white' :
                  step > s ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-500'
                }`}>
                  {step > s ? '✓' : s}
                </div>
                <span className={`text-xs font-medium ${step === s ? 'text-primary-700' : 'text-gray-500'}`}>
                  {s === 1 ? 'Upload' : s === 2 ? 'Review' : 'Results'}
                </span>
                {s < 3 && <div className="w-8 h-px bg-gray-200" />}
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto flex-grow">
          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {typeof error === 'object' ? (error.message || error.detail || JSON.stringify(error)) : String(error)}
            </div>
          )}

          {step === 1 && (
            <div className="space-y-6">
              <div className="bg-primary-50 border border-primary-200 rounded-lg p-4">
                <h3 className="font-semibold text-primary-900 mb-2">Bulk Import</h3>
                <ul className="text-sm text-primary-800 space-y-1">
                  <li>• Upload your file to automatically map columns</li>
                  <li>• Review and confirm before final import</li>
                  <li>• Required: Counterparty Name, Invoice Date, Payment Due Date</li>
                </ul>
              </div>
              <div>
                <label htmlFor="invoice-import-file" className="block text-sm font-medium text-gray-700 mb-2">
                  Select File (CSV or Excel)
                </label>
                <div className="relative group">
                  <input
                    id="invoice-import-file"
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    onChange={handleFileChange}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                  />
                  <div className={`w-full py-12 px-4 border-2 border-dashed rounded-xl flex flex-col items-center justify-center transition-colors ${
                    file ? 'border-primary-300 bg-primary-50' : 'border-gray-300 group-hover:border-primary-400'
                  }`}>
                    <svg className={`w-12 h-12 mb-3 ${file ? 'text-primary-500' : 'text-gray-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    <span className="text-base font-medium text-gray-600">
                      {file ? file.name : 'Click or drag file to upload'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-bold text-gray-900">Step 2: Column Mapping</h3>
                <p className="text-sm text-gray-500">Verify how your Excel columns map to invoice fields.</p>
              </div>

              <div className="border border-gray-200 rounded-xl overflow-hidden">
                <table className="w-full text-left text-sm">
                  <thead className="bg-gray-50 text-gray-700 font-semibold border-b border-gray-200">
                    <tr>
                      <th className="px-4 py-3">Invoice Field</th>
                      <th className="px-4 py-3">Excel Column</th>
                      <th className="px-4 py-3">Match</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {Object.entries(FIELD_LABELS).map(([field, label]) => {
                      const isMapped = !!mapping[field]
                      const isRequired = REQUIRED_FIELDS.includes(field)
                      return (
                        <tr key={field} className={isRequired ? 'bg-white' : 'bg-gray-50/30'}>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-gray-700">{label}</span>
                              {isRequired && <span className="text-red-500">*</span>}
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <select
                              value={mapping[field] || ''}
                              onChange={(e) => setMapping(prev => ({ ...prev, [field]: e.target.value }))}
                              className={`w-full rounded-lg border px-3 py-2 focus:ring-2 focus:ring-primary-200 focus:border-primary-500 outline-none ${
                                !isMapped && isRequired ? 'border-red-200 bg-red-50 text-red-400' : 'border-gray-300 text-gray-900'
                              }`}
                            >
                              <option value="">(Not Mapped)</option>
                              {headers.map(h => (
                                <option key={h} value={h}>{h}</option>
                              ))}
                            </select>
                          </td>
                          <td className="px-4 py-3 text-center">
                            {isMapped ? (
                              <span className="text-green-500">✅</span>
                            ) : isRequired ? (
                              <span className="text-amber-500">⚠️</span>
                            ) : (
                              <span className="text-gray-300">—</span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <p className="text-xs text-blue-800">
                  <strong>Pro Tip:</strong> Ensure Counterparty Name, Invoice Date, and Payment Due Date are correctly mapped for accurate processing. If your tax is a percentage (e.g. 18% GST), map it to "Tax Rate (%)" instead of "Tax Amount" — the rupee tax and Total will be calculated automatically from your Subtotal.
                </p>
              </div>

              <div className="flex items-center justify-between pt-2">
                <p className="text-sm font-bold text-gray-700">
                  {rawData.length} rows will be processed
                </p>
              </div>
            </div>
          )}

          {step === 3 && results && (
            <div className="space-y-6">
              <div className={`rounded-xl border p-6 ${results.failed > 0 ? 'bg-orange-50 border-orange-200' : 'bg-green-50 border-green-200'}`}>
                <div className="flex items-center gap-4 mb-4">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center ${results.failed > 0 ? 'bg-orange-100 text-orange-600' : 'bg-green-100 text-green-600'}`}>
                    {results.failed === 0 ? '✅' : '⚠️'}
                  </div>
                  <div>
                    <h3 className={`text-lg font-bold ${results.failed > 0 ? 'text-orange-900' : 'text-green-900'}`}>Import Finished</h3>
                    <p className={`text-sm ${results.failed > 0 ? 'text-orange-800' : 'text-green-800'}`}>
                      Successfully processed {results.total} rows.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-white/60 p-4 rounded-lg border border-white/50 text-center">
                    <p className="text-xs text-green-600 uppercase font-bold">Imported</p>
                    <p className="text-3xl font-bold text-green-600">{results.success}</p>
                  </div>
                  <div className="bg-white/60 p-4 rounded-lg border border-white/50 text-center">
                    <p className="text-xs text-red-600 uppercase font-bold">Skipped/Failed</p>
                    <p className="text-3xl font-bold text-red-600">{results.failed}</p>
                  </div>
                </div>

                {results.failed > 0 && (
                  <div className="mt-6 flex justify-center">
                    <button
                      onClick={downloadSkippedRows}
                      className="text-sm bg-orange-600 text-white px-4 py-2 rounded-lg hover:bg-orange-700 transition-colors font-medium flex items-center gap-2"
                    >
                      📥 Download Skipped Rows (.csv)
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50 rounded-b-xl flex gap-3 flex-shrink-0">
          <button
            onClick={onClose}
            className="flex-1 px-6 py-3 rounded-lg border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 transition-colors font-medium"
            disabled={importing}
          >
            {step === 3 ? 'Close' : 'Cancel'}
          </button>
          {step === 2 && (
            <button
              onClick={() => setStep(1)}
              className="flex-1 px-6 py-3 rounded-lg border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 transition-colors font-medium"
              disabled={importing}
            >
              Back
            </button>
          )}
          {step === 2 && (
            <div className="flex-1 flex flex-col gap-2">
              {importing && (
                <div className="w-full">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-bold text-primary-700 uppercase">Importing Rows...</span>
                    <span className="text-[10px] font-bold text-primary-700">{importProgress}%</span>
                  </div>
                  <div className="w-full h-2 bg-primary-100 rounded-full overflow-hidden">
                    <div className="h-full bg-primary-600 transition-all duration-300" style={{ width: `${importProgress}%` }} />
                  </div>
                </div>
              )}
              <button
                onClick={handleConfirmImport}
                className="w-full btn-primary disabled:opacity-50"
                disabled={importing}
              >
                {importing ? 'Processing...' : 'Confirm & Import'}
              </button>
            </div>
          )}
          {step === 3 && (
            <button onClick={onClose} className="flex-1 btn-primary">
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

InvoiceCSVImportModal.propTypes = {
  onClose: PropTypes.func.isRequired,
  onImportComplete: PropTypes.func.isRequired,
  initialFile: PropTypes.object,
}
