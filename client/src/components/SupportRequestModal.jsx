import { supportRequests } from '../services/api/apiClient'
import TwoTabRequestModal from './shared/TwoTabRequestModal'

const REQUEST_TYPES = ['General', 'Technical Support', 'Billing', 'Feature Request', 'Account Issue', 'Other']
const REQUEST_TYPE_LABELS = {
  General: 'General Inquiry',
  Billing: 'Billing / Payment',
}

function renderForm(form, setForm) {
  return (
    <>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Request Type <span className="text-red-500">*</span>
        </label>
        <select
          value={form.request_type}
          onChange={e => setForm({ ...form, request_type: e.target.value })}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
        >
          {REQUEST_TYPES.map(t => (
            <option key={t} value={t}>{REQUEST_TYPE_LABELS[t] || t}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Request Details <span className="text-red-500">*</span>
        </label>
        <textarea
          value={form.request_details}
          onChange={e => setForm({ ...form, request_details: e.target.value })}
          placeholder="Describe your request or issue in detail..."
          rows={4}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
        />
      </div>
    </>
  )
}

function renderRequestItem(req) {
  return (
    <>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-bold text-gray-900">{req.request_type}</h3>
            <span className={`inline-block px-3 py-1 rounded-full text-xs font-bold ${
              req.status === 'RESOLVED' ? 'bg-green-100 text-green-700' :
              req.status === 'PENDING' ? 'bg-yellow-100 text-yellow-700' :
              'bg-gray-100 text-gray-700'
            }`}>
              {req.status}
            </span>
          </div>
          <p className="text-sm text-gray-600 mt-1">{req.request_details}</p>
          <p className="text-xs text-gray-400 mt-1">
            Submitted: {req.created_at ? new Date(req.created_at).toLocaleString('en-IN') : ''}
          </p>
        </div>
      </div>

      {req.admin_response && (
        <div className="mt-4 p-4 bg-purple-50 border border-purple-200 rounded-lg">
          <p className="text-sm font-bold text-purple-800 mb-2">
            Admin Response
          </p>
          <p className="text-sm text-purple-700">{req.admin_response}</p>
        </div>
      )}
    </>
  )
}

const CONFIG = {
  icon: '📋',
  title: 'Support & Additional Requests',
  subtitle: 'Submit a new support request or view your existing requests.',
  colorClass: 'bg-purple-600',
  colorHoverClass: 'hover:bg-purple-700',
  initialForm: { request_type: 'General', request_details: '' },
  validate: (form) => !form.request_details ? 'Request details are required' : null,
  buildPayload: (form) => ({
    request_type: form.request_type,
    request_details: form.request_details,
  }),
  api: supportRequests,
  successMessage: '✅ Support request submitted successfully! We will get back to you soon.',
  emptyIcon: '📋',
  emptyText: 'No support requests yet',
  ctaText: 'Submit a Request',
  submitLabel: '📋 Submit Request',
  submittingLabel: '⏳ Submitting...',
  renderForm,
  renderRequestItem,
}

export default function SupportRequestModal({ onClose, onSuccess }) {
  return <TwoTabRequestModal onClose={onClose} onSuccess={onSuccess} config={CONFIG} />
}
