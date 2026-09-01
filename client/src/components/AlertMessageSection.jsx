import { useState, useEffect } from 'react'
import { getAlertMessage, updateAlertMessage } from '../services/api/apiClient'

export default function AlertMessageSection({ token }) {
  const [message, setMessage] = useState('')
  const [updatedBy, setUpdatedBy] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await getAlertMessage()
      if (res.ok) {
        setMessage(res.data?.message || '')
        setUpdatedBy(res.data?.updated_by || null)
      }
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  useEffect(() => { load() }, [token])

  const save = async () => {
    setSaving(true)
    try {
      const res = await updateAlertMessage(message)
      if (res.ok) {
        await load()
        alert('✅ Alert message updated')
      } else {
        alert(`❌ ${res.error || 'Failed to update alert message'}`)
      }
    } catch (e) {
      alert('Connection failed')
    }
    setSaving(false)
  }

  if (loading) return null

  return (
    <div className="bg-white rounded-xl shadow-sm border border-red-100 overflow-hidden">
      <div className="px-3 py-1.5 border-b bg-gray-50/50 flex justify-between items-center">
        <h2 className="text-xs font-bold text-gray-800 flex items-center gap-1.5"><span>⚠️</span> Alert message</h2>
        {updatedBy && <span className="text-[11px] text-gray-400">Updated by {updatedBy}</span>}
      </div>
      <div className="p-2.5">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={2}
          placeholder="Leave empty to hide the alert on the homepage"
          className="w-full rounded-lg border-gray-300 text-xs focus:border-blue-500 focus:ring-blue-500"
        />
        <div className="flex justify-end mt-2">
          <button
            onClick={save}
            disabled={saving}
            className="px-2.5 py-1 rounded-md bg-blue-600 text-white text-[11px] font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
