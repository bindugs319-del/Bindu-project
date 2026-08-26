import { useState, useEffect } from 'react'
import PropTypes from 'prop-types'
import ModalShell from './ModalShell'

/**
 * Shared upload -> scan -> review -> confirm flow for both PO and Invoice
 * PDF/photo import. Extracted from what were two nearly-identical
 * components (PDFImportModal.jsx and InvoicePDFImportModal.jsx) to remove
 * ~450 lines of duplicated JSX/logic between them — everything that
 * differs between "import a PO" and "import an invoice" is passed in via
 * `config` instead.
 */
export default function DocumentImportModal({ onClose, onImportComplete, initialFile, config }) {
  const { title, subtitle, fieldLabels, dateFields, numberFields, requiredFields,
    scanFn, importFn, entityLabel, entityNumberField } = config

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
    const res = await scanFn(selectedFile)
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

  // Auto-run when opened with a file already chosen (e.g. drag-drop from elsewhere)
  useEffect(() => {
    if (initialFile) runScan(initialFile)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialFile])

  const setField = (key, value) => setFields(prev => ({ ...prev, [key]: value }))

  const handleConfirm = async () => {
    setStep('importing')
    setError('')
    const res = await importFn({ ...fields, file })
    if (!res.ok) {
      setError(res.error || `Failed to save this ${entityLabel.toLowerCase()}.`)
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

  const entityNumberValue = fields[entityNumberField]

  return (
    <ModalShell
      title={title}
      subtitle={subtitle}
      onClose={onClose}
      footer={
        step !== 'done' ? (
          <>
            <button
              onClick={onClose}
              className="flex-1 px-6 py-3 rounded-lg border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 transition-colors font-medium"
            >
              Cancel
            </button>
            {step === 'review' && (
              <button onClick={handleConfirm} className="flex-1 btn-primary">
                {willUpdateExisting ? `Confirm & Update ${entityLabel}` : `Confirm & Create ${entityLabel}`}
              </button>
            )}
          </>
        ) : (
          <button onClick={onClose} className="flex-1 btn-primary">Done</button>
        )
      }
    >
      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {step === 'upload' && (
        <div className="relative group">
          <label htmlFor="doc-scan-file" className="block text-sm font-medium text-gray-700 mb-2">
            Select {entityLabel} PDF
          </label>
          <input
            id="doc-scan-file"
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
            <span className="text-xs text-gray-400 mt-1">Text-based PDFs read most reliably; scanned/photographed documents use OCR and need a quick review</span>
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
              ? `An open ${entityLabel.toLowerCase()} with number "${entityNumberValue}" already exists — confirming will update it, not create a duplicate.`
              : `No existing open ${entityLabel.toLowerCase()} with this number — confirming will create a new one.`}
          </div>

          {warnings.length > 0 && (
            <div className="rounded-lg px-3 py-2 text-xs border bg-yellow-50 border-yellow-200 text-yellow-800 space-y-1">
              {warnings.map((w, i) => <div key={i}>⚠️ {w}</div>)}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {Object.keys(fieldLabels).map((key) => (
              <div key={key} className={requiredFields.includes(key) ? 'sm:col-span-2' : ''}>
                <label className="block text-xs font-medium text-gray-500 mb-1">{fieldLabels[key]}</label>
                <input
                  type={dateFields.includes(key) ? 'date' : numberFields.includes(key) ? 'number' : 'text'}
                  value={fields[key] ?? ''}
                  onChange={(e) => setField(key, e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-200"
                />
              </div>
            ))}
          </div>
          {config.extraNote && (
            <p className="text-xs text-gray-400">{config.extraNote}</p>
          )}
        </div>
      )}

      {step === 'importing' && (
        <div className="text-center py-10 text-gray-500 text-sm">Saving {entityLabel.toLowerCase()}&hellip;</div>
      )}

      {step === 'done' && result && (
        <div className="text-center py-10">
          <div className="text-4xl mb-3">✅</div>
          <p className="text-base font-semibold text-gray-900">
            {result.action === 'updated' ? `Existing ${entityLabel.toLowerCase()} updated` : `New ${entityLabel.toLowerCase()} created`}
          </p>
          <p className="text-sm text-gray-500 mt-1">{entityLabel} {entityNumberValue} saved successfully.</p>
        </div>
      )}
    </ModalShell>
  )
}

DocumentImportModal.propTypes = {
  onClose: PropTypes.func.isRequired,
  onImportComplete: PropTypes.func,
  initialFile: PropTypes.object,
  config: PropTypes.shape({
    title: PropTypes.string.isRequired,
    subtitle: PropTypes.string.isRequired,
    fieldLabels: PropTypes.object.isRequired,
    dateFields: PropTypes.array.isRequired,
    numberFields: PropTypes.array.isRequired,
    requiredFields: PropTypes.array.isRequired,
    scanFn: PropTypes.func.isRequired,
    importFn: PropTypes.func.isRequired,
    entityLabel: PropTypes.string.isRequired,
    entityNumberField: PropTypes.string.isRequired,
    extraNote: PropTypes.string,
  }).isRequired,
}
