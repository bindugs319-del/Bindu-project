import { useState, useEffect } from 'react'
import { getTrustTicker, updateTrustTicker } from '../services/api/apiClient'

export default function TrustTickerSection({ token }) {
  const [items, setItems] = useState([])
  const [updatedBy, setUpdatedBy] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const res = await getTrustTicker()
      if (res.ok) {
        setItems(res.data?.items || [])
        setUpdatedBy(res.data?.updated_by || null)
      }
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  useEffect(() => { load() }, [token])

  const updateValue = (idx, value) => {
    setItems(prev => prev.map((it, i) => i === idx ? { ...it, value } : it))
  }

  const save = async () => {
    if (items.some(it => !it.value?.trim())) {
      setError('Every value must be filled in')
      return
    }
    setError('')
    setSaving(true)
    try {
      const res = await updateTrustTicker(items)
      if (res.ok) {
        await load()
        alert('✅ Trust ticker updated')
      } else {
        alert(`❌ ${res.error || 'Failed to update trust ticker'}`)
      }
    } catch (e) {
      alert('Connection failed')
    }
    setSaving(false)
  }

  if (loading) return null

  return (
    <div className="bg-white rounded-xl shadow-sm border border-blue-100 overflow-hidden">
      <div className="px-3 py-1.5 border-b bg-gray-50/50 flex justify-between items-center">
        <h2 className="text-xs font-bold text-gray-800 flex items-center gap-1.5"><span>📊</span> Homepage trust ticker</h2>
        {updatedBy && <span className="text-[11px] text-gray-400">Updated by {updatedBy}</span>}
      </div>
      <div className="p-2.5">
        <div className="grid grid-cols-3 gap-1.5">
          {items.map((item, idx) => (
            <div key={item.label} className="bg-gray-50 rounded-lg p-1.5 text-center">
              <p className="text-[11px] text-gray-500 mb-1">{item.label}</p>
              <input
                value={item.value}
                onChange={(e) => updateValue(idx, e.target.value)}
                className="w-full text-center text-xs font-semibold rounded border-gray-300 focus:border-blue-500 focus:ring-blue-500 h-6 px-1"
              />
            </div>
          ))}
        </div>
        {error && <p className="text-[11px] text-red-600 mt-1.5">{error}</p>}
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
