import { useState, useEffect } from 'react'
import PropTypes from 'prop-types'

/**
 * Shared shell for "submit a request, then view my past requests" modals.
 * Extracted from what were two near-identical components
 * (BusinessRequestModal.jsx and SupportRequestModal.jsx) — the tab
 * switching, loading states, and submit/error handling were identical;
 * only the actual form fields and the per-request-item display genuinely
 * differ, so those are passed in as render functions rather than forced
 * into a shared shape.
 */
export default function TwoTabRequestModal({ onClose, onSuccess, config }) {
  const {
    icon, title, subtitle, colorClass, colorHoverClass,
    initialForm, validate, buildPayload, api, successMessage,
    emptyIcon, emptyText, ctaText, submitLabel, submittingLabel,
    renderForm, renderRequestItem,
  } = config

  const [activeTab, setActiveTab] = useState('new')
  const [form, setForm] = useState(initialForm)
  const [loading, setLoading] = useState(false)
  const [myRequests, setMyRequests] = useState([])
  const [requestsLoading, setRequestsLoading] = useState(false)
  const [error, setError] = useState(null)

  const loadMyRequests = async () => {
    setRequestsLoading(true)
    try {
      const res = await api.getMy()
      if (res.ok) {
        setMyRequests(res.data || [])
      }
    } catch (e) {
      console.error('Failed to load requests:', e)
    }
    setRequestsLoading(false)
  }

  useEffect(() => {
    if (activeTab === 'my') {
      loadMyRequests()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab])

  const handleSubmit = async () => {
    const validationError = validate(form)
    if (validationError) {
      setError(validationError)
      return
    }
    setLoading(true)
    setError(null)

    try {
      await api.create(buildPayload(form))
      onSuccess?.()
      setForm(initialForm)
      setActiveTab('my')
      alert(successMessage)
    } catch (e) {
      console.error('Request submission error:', e)
      setError('Connection failed. Please try again.')
    }
    setLoading(false)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl">
        <div className="p-6 border-b">
          <h2 className="text-xl font-bold text-gray-900">
            {icon} {title}
          </h2>
          <p className="text-sm text-gray-500 mt-1">{subtitle}</p>

          <div className="flex gap-2 mt-4">
            <button
              onClick={() => setActiveTab('new')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'new' ? `${colorClass} text-white` : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              New Request
            </button>
            <button
              onClick={() => setActiveTab('my')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'my' ? `${colorClass} text-white` : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              My Requests
            </button>
          </div>
        </div>

        <div className="p-6 max-h-[60vh] overflow-y-auto">
          {activeTab === 'new' && (
            <div className="space-y-4">
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">
                  {error}
                </div>
              )}
              {renderForm(form, setForm)}
            </div>
          )}

          {activeTab === 'my' && (
            <div className="space-y-4">
              {requestsLoading && (
                <div className="text-center py-8 text-gray-500 text-sm">
                  Loading your requests...
                </div>
              )}

              {!requestsLoading && myRequests.length === 0 && (
                <div className="text-center py-8">
                  <div className="text-4xl mb-2">{emptyIcon}</div>
                  <p className="text-sm text-gray-500">{emptyText}</p>
                  <button
                    onClick={() => setActiveTab('new')}
                    className={`mt-4 px-4 py-2 ${colorClass} text-white rounded-lg text-sm font-medium ${colorHoverClass} transition-colors`}
                  >
                    {ctaText}
                  </button>
                </div>
              )}

              {!requestsLoading && myRequests.length > 0 && (
                <div className="space-y-4">
                  {myRequests.map((req) => (
                    <div key={req.id} className="border border-gray-200 rounded-xl p-4">
                      {renderRequestItem(req)}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="p-6 border-t flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 border border-gray-200 text-gray-600 py-2 rounded-lg text-sm hover:bg-gray-50"
          >
            Close
          </button>
          {activeTab === 'new' && (
            <button
              onClick={handleSubmit}
              disabled={loading}
              className={`flex-1 ${colorClass} text-white py-2 rounded-lg text-sm font-medium ${colorHoverClass} disabled:opacity-50`}
            >
              {loading ? submittingLabel : submitLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

TwoTabRequestModal.propTypes = {
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func,
  config: PropTypes.object.isRequired,
}
