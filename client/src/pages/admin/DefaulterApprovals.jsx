import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { admin } from '../../services/api/apiClient'

export default function DefaulterApprovals() {
  const navigate = useNavigate()
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [busyId, setBusyId] = useState(null)

  useEffect(() => {
    fetchPending()
  }, [])

  const fetchPending = async () => {
    setLoading(true)
    try {
      const res = await admin.getPendingDefaulters()
      if (res.ok) {
        setCases(res.data?.data || res.data || [])
      } else {
        setMessage(res.error || 'Failed to load pending cases')
      }
    } catch (err) {
      setMessage('Network error while loading pending cases')
    }
    setLoading(false)
  }

  const handleAction = async (caseId, action) => {
    const notes = action === 'reject' ? (prompt('Reason for rejection:') || '') : 'Approved'
    if (action === 'reject' && !notes) return

    setBusyId(caseId)
    setMessage('')
    try {
      const res = await admin.verifyDefaulterCase(caseId, action, notes)
      if (res.ok) {
        setMessage(action === 'approve'
          ? '✅ Case approved — 50 points credited to the reporting user\'s wallet.'
          : '✅ Case rejected.')
        setCases(prev => prev.filter(c => c.id !== caseId))
      } else {
        setMessage(res.error || `Failed to ${action} case`)
      }
    } catch (err) {
      setMessage(`Failed to ${action} case`)
    }
    setBusyId(null)
  }

  if (loading) return <div className="p-8 text-center text-gray-500">Loading pending defaulter cases...</div>

  return (
    <div className="max-w-4xl mx-auto p-6 min-h-screen">
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-[#1E3A8A] transition-colors mb-4"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back
      </button>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">🚩 Defaulter Case Approvals</h1>
        <p className="text-sm text-gray-500 mt-1">Review reported defaulter cases. Approving credits the reporting user 50 wallet points.</p>
      </div>

      {message && (
        <div className="mb-4 bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-800">
          {message}
        </div>
      )}

      {cases.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-2xl p-12 text-center shadow-sm">
          <p className="text-4xl mb-4">✅</p>
          <p className="text-gray-900 font-bold text-lg">No pending defaulter cases</p>
          <p className="text-gray-500 text-sm mt-2">All reported cases have been reviewed.</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {cases.map(c => (
            <div key={c.id} className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center flex-wrap gap-2 mb-2">
                    <span className="font-bold text-gray-900 text-lg">{c.business_name}</span>
                    <span className="bg-amber-100 text-amber-700 text-xs px-2.5 py-1 rounded-full font-bold uppercase tracking-wider">
                      Pending
                    </span>
                  </div>
                  <div className="grid sm:grid-cols-2 gap-y-1 gap-x-4 text-sm text-gray-600">
                    <p>GSTIN: <span className="font-medium text-gray-900">{c.business_gstin || '—'}</span></p>
                    <p>Amount: <span className="font-bold text-blue-600">₹{Number(c.amount).toLocaleString('en-IN')}</span></p>
                    <p>Reported: <span className="font-medium text-gray-900">{new Date(c.created_at).toLocaleDateString()}</span></p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => handleAction(c.id, 'reject')}
                    disabled={busyId === c.id}
                    className="px-4 py-2 rounded-lg border border-red-200 text-red-600 font-semibold text-sm hover:bg-red-50 disabled:opacity-50 transition-colors"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => handleAction(c.id, 'approve')}
                    disabled={busyId === c.id}
                    className="px-4 py-2 rounded-lg bg-[#1E3A8A] text-white font-semibold text-sm hover:bg-[#16306B] disabled:opacity-50 transition-colors"
                  >
                    {busyId === c.id ? 'Working...' : 'Approve (+50 pts)'}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
