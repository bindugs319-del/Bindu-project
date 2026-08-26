import PropTypes from 'prop-types'
import { businessCheck } from '../services/api/apiClient'
import TwoTabRequestModal from './shared/TwoTabRequestModal'

const REASON_OPTIONS = [
  { value: 'new_vendor', label: 'Considering as new vendor' },
  { value: 'large_order', label: 'Planning large purchase order' },
  { value: 'partnership', label: 'Potential business partnership' },
  { value: 'credit_check', label: 'Credit worthiness check' },
  { value: 'due_diligence', label: 'Due diligence before contract' },
  { value: 'other', label: 'Other' },
]

function renderForm(form, setForm) {
  return (
    <>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Company Name <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={form.company_name}
          onChange={e => setForm({ ...form, company_name: e.target.value })}
          placeholder="e.g. ABC Solutions Pvt Ltd"
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Company GSTIN <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={form.gstin}
          onChange={e => setForm({ ...form, gstin: e.target.value.toUpperCase() })}
          placeholder="e.g. 22AAAAD0000A1Z5"
          maxLength={15}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Company Registration Number (CIN) (Optional)
        </label>
        <input
          type="text"
          value={form.company_registration_no}
          onChange={e => setForm({ ...form, company_registration_no: e.target.value })}
          placeholder="e.g. U01234XX2020PTC123456"
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Why do you want to know? (Optional)
        </label>
        <select
          value={form.reason}
          onChange={e => setForm({ ...form, reason: e.target.value })}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Select reason...</option>
          {REASON_OPTIONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Additional Information (Optional)
        </label>
        <textarea
          value={form.additional_info}
          onChange={e => setForm({ ...form, additional_info: e.target.value })}
          placeholder="Any specific concerns or questions about this company..."
          rows={3}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
        />
      </div>

      <div className="bg-blue-50 rounded-lg p-4">
        <p className="text-xs font-medium text-blue-800">📋 What happens next:</p>
        <ol className="text-xs text-blue-700 mt-2 space-y-1 list-decimal list-inside">
          <li>Your request goes to Operations team</li>
          <li>They review the company&apos;s business history</li>
          <li>A detailed PDF report is generated</li>
          <li>You receive it in your notifications + email</li>
        </ol>
      </div>
    </>
  )
}

function renderRequestItem(req) {
  return (
    <>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="text-lg font-bold text-gray-900">{req.company_name}</h3>
          <p className="text-xs text-gray-500 mt-1">GSTIN: {req.gstin}</p>
          <p className="text-xs text-gray-400 mt-1">Requested: {new Date(req.created_at).toLocaleDateString('en-IN')}</p>
        </div>
        <div className="text-right">
          <span className={`inline-block px-3 py-1 rounded-full text-xs font-bold ${
            req.status === 'COMPLETED' ? 'bg-green-100 text-green-700' :
            req.status === 'PENDING' ? 'bg-yellow-100 text-yellow-700' :
            'bg-gray-100 text-gray-700'
          }`}>
            {req.status}
          </span>
        </div>
      </div>

      {req.verdict && (
        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm font-bold text-blue-800 mb-2">
            Verdict: {req.verdict}
          </p>
          {req.report_text && (
            <p className="text-xs text-blue-700 mb-3 line-clamp-3">{req.report_text}</p>
          )}
          {req.report_url && (
            <a
              href={req.report_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
            >
              📄 Download Report
            </a>
          )}
        </div>
      )}
    </>
  )
}

const CONFIG = {
  icon: '🏢',
  title: 'Company Safety Check',
  subtitle: 'Request a new check or view your existing requests and reports.',
  colorClass: 'bg-blue-600',
  colorHoverClass: 'hover:bg-blue-700',
  initialForm: { company_name: '', gstin: '', reason: '', additional_info: '', company_registration_no: '' },
  validate: (form) => (!form.company_name || !form.gstin) ? 'Company name and GSTIN are required' : null,
  buildPayload: (form) => ({
    company_name: form.company_name,
    gstin: form.gstin,
    reason: form.reason,
    additional_info: form.additional_info,
  }),
  api: businessCheck,
  successMessage: '✅ Request submitted! Operations team will review and send you a report.',
  emptyIcon: '🔍',
  emptyText: 'No business check requests yet',
  ctaText: 'Request a Check',
  submitLabel: '🔍 Submit Request',
  submittingLabel: '⏳ Submitting...',
  renderForm,
  renderRequestItem,
}

export default function BusinessRequestModal({ onClose, onSuccess }) {
  return <TwoTabRequestModal onClose={onClose} onSuccess={onSuccess} config={CONFIG} />
}

BusinessRequestModal.propTypes = {
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func.isRequired,
}
