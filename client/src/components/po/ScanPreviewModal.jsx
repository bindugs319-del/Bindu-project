import { useState } from 'react'
import PropTypes from 'prop-types'
import * as XLSX from 'xlsx'

export default function ScanPreviewModal({ onClose, onProceedToImport }) {
  const [file, setFile] = useState(null)
  const [headers, setHeaders] = useState([])
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

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
    setLoading(true)

    try {
      const data = await readFile(selectedFile)
      if (data && data.length > 0) {
        setHeaders(Object.keys(data[0]))
        setRows(data)
      } else {
        setError('The file appears to be empty.')
        setHeaders([])
        setRows([])
      }
    } catch (err) {
      setError('Error reading file: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-5xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4 flex-shrink-0">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-heading font-bold text-gray-900">Scan File</h2>
              <p className="text-sm text-gray-500 mt-1">
                Preview everything in your file before importing anything &mdash; nothing is uploaded yet.
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
              type="button"
            >
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

          {!file && (
            <div className="relative group">
              <input
                id="scan-file"
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={handleFileChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
              />
              <div className="w-full py-12 px-4 border-2 border-dashed border-gray-300 group-hover:border-primary-400 rounded-xl flex flex-col items-center justify-center transition-colors">
                <svg className="w-12 h-12 mb-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <span className="text-base font-medium text-gray-600">Click or drag file to scan</span>
              </div>
            </div>
          )}

          {loading && (
            <div className="text-center py-8 text-gray-500 text-sm">Reading file&hellip;</div>
          )}

          {!loading && file && rows.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-600">
                  <span className="font-semibold text-gray-900">{file.name}</span> &mdash; {rows.length} row{rows.length !== 1 ? 's' : ''}, {headers.length} column{headers.length !== 1 ? 's' : ''} detected
                </p>
                <button
                  onClick={() => { setFile(null); setRows([]); setHeaders([]); setError('') }}
                  className="text-xs text-primary-600 hover:underline font-medium"
                >
                  Choose a different file
                </button>
              </div>

              <div className="border border-gray-200 rounded-xl overflow-auto max-h-[50vh]">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 text-gray-700 font-semibold border-b border-gray-200 sticky top-0">
                    <tr>
                      <th className="px-3 py-2 text-gray-400">#</th>
                      {headers.map(h => (
                        <th key={h} className="px-3 py-2 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {rows.map((row, idx) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-3 py-2 text-gray-400">{idx + 1}</td>
                        {headers.map(h => (
                          <td key={h} className="px-3 py-2 whitespace-nowrap text-gray-700">
                            {row[h] !== undefined && row[h] !== null ? String(row[h]) : ''}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50 rounded-b-xl flex gap-3 flex-shrink-0">
          <button
            onClick={onClose}
            className="flex-1 px-6 py-3 rounded-lg border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 transition-colors font-medium"
          >
            Close
          </button>
          {file && rows.length > 0 && (
            <button
              onClick={() => onProceedToImport(file)}
              className="flex-1 btn-primary"
            >
              Looks Good &mdash; Proceed to Import
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

ScanPreviewModal.propTypes = {
  onClose: PropTypes.func.isRequired,
  onProceedToImport: PropTypes.func.isRequired,
}
