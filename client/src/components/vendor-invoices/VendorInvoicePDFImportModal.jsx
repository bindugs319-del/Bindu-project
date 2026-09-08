import { useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { vendorInvoices } from '../../services/api/apiClient'
import ModalShell from '../shared/ModalShell'

/**
 * Upload -> scan flow for filling the Add Vendor Invoice form from a
 * vendor's own PDF. Mirrors InvoicePDFImportModal.jsx exactly — same
 * "just fill the form, no separate save step" design — pointed at the
 * vendor-invoices scan endpoint instead.
 */
export default function VendorInvoicePDFImportModal({ onClose, onScanned, initialFile }) {
  const [step, setStep] = useState(initialFile ? 'scanning' : 'upload') // upload | scanning
  const [error, setError] = useState('')

  const runScan = async (selectedFile) => {
    setError('')
    setStep('scanning')
    const res = await vendorInvoices.scanPdf(selectedFile)
    if (!res.ok) {
      setError(res.error || 'Failed to read this PDF.')
      setStep('upload')
      return
    }
    const data = res.data?.data || res.data || {}
    onScanned?.({
      fields: data.fields || {},
      items: data.items || [],
      warnings: data.warnings || [],
      fileName: selectedFile.name,
    })
    onClose()
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

  return (
    <ModalShell
      title="Import Vendor Bill from PDF"
      subtitle="Upload the invoice your vendor sent you — we'll read it and fill in the Add Vendor Invoice form for you to review."
      onClose={onClose}
      closeDisabled={step === 'scanning'}
      footer={
        <button
          onClick={onClose}
          disabled={step === 'scanning'}
          className="flex-1 px-6 py-3 rounded-lg border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 transition-colors font-medium disabled:opacity-50"
        >
          Cancel
        </button>
      }
    >
      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {step === 'upload' && (
        <div className="relative group">
          <label htmlFor="vendor-invoice-scan-file" className="block text-sm font-medium text-gray-700 mb-2">
            Select the Vendor's Invoice PDF
          </label>
          <input
            id="vendor-invoice-scan-file"
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            onChange={handleFileChange}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10 top-7"
          />
          <div className="w-full py-12 px-4 border-2 border-dashed border-gray-300 group-hover:border-primary-400 rounded-xl flex flex-col items-center justify-center transition-colors">
            <svg className="w-12 h-12 mb-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <span className="text-base font-medium text-gray-600">Click or drag the vendor's PDF or photo to import</span>
            <span className="text-xs text-gray-400 mt-1">Text-based PDFs read most reliably; scanned/photographed documents use OCR and need a closer review</span>
          </div>
        </div>
      )}

      {step === 'scanning' && (
        <div className="text-center py-10 text-gray-500 text-sm">Reading PDF&hellip;</div>
      )}
    </ModalShell>
  )
}

VendorInvoicePDFImportModal.propTypes = {
  onClose: PropTypes.func.isRequired,
  onScanned: PropTypes.func,
  initialFile: PropTypes.object,
}
