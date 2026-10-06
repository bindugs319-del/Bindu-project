import { useState, useEffect } from 'react'
import { subscriptions } from '../../services/api/apiClient'

const emptyForm = {
  name: '',
  display_name: '',
  description: '',
  price: '',
  validity_days: '',
  follow_up_limit: '',
  legal_assistance_limit: '',
}

// Auto-derives the internal `name` (e.g. "royal_plan") from what the
// admin actually types in Display Name (e.g. "Royal"), so the form only
// asks for one thing a human would naturally fill in, not two.
function slugify(displayName) {
  return displayName
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

export default function ManagePlans() {
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [editingId, setEditingId] = useState(null) // null = not editing; 'new' = creating
  const [formData, setFormData] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    void fetchPlans()
  }, [])

  const fetchPlans = async () => {
    setLoading(true)
    try {
      const res = await subscriptions.adminListPlans()
      if (res.ok) {
        setPlans(res.data?.data || res.data || [])
      } else {
        setMessage(res.error || 'Failed to load plans')
      }
    } catch (err) {
      setMessage('Network error while loading plans')
    }
    setLoading(false)
  }

  const openEdit = (plan) => {
    setFormData({
      name: plan.name,
      display_name: plan.display_name,
      description: plan.description || '',
      price: plan.price,
      validity_days: plan.validity_days,
      follow_up_limit: plan.follow_up_limit ?? '',
      legal_assistance_limit: plan.legal_assistance_limit ?? '',
    })
    setEditingId(plan.id)
    setMessage('')
  }

  const openCreate = () => {
    setFormData(emptyForm)
    setEditingId('new')
    setMessage('')
  }

  const closeForm = () => {
    setEditingId(null)
    setFormData(emptyForm)
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    setMessage('')
    try {
      const isNew = editingId === 'new'
      const payload = {
        display_name: formData.display_name,
        description: formData.description || null,
        price: Number(formData.price),
        validity_days: Number(formData.validity_days),
        follow_up_limit: Number(formData.follow_up_limit),
        legal_assistance_limit: Number(formData.legal_assistance_limit),
      }
      const res = isNew
        ? await subscriptions.adminCreatePlan({ ...payload, name: slugify(formData.display_name) })
        : await subscriptions.adminUpdatePlan(editingId, payload)

      if (res.ok) {
        setMessage(isNew ? '✅ Plan created.' : '✅ Plan updated.')
        closeForm()
        fetchPlans()
      } else {
        setMessage(res.error || 'Failed to save plan')
      }
    } catch (err) {
      setMessage('Network error while saving plan')
    }
    setSaving(false)
  }

  const handleDeactivate = async (plan) => {
    if (!window.confirm(`Deactivate "${plan.display_name}"? It will stop appearing on the public Offerings page — existing subscribers already on it are not affected.`)) return
    try {
      const res = await subscriptions.adminDeactivatePlan(plan.id)
      if (res.ok) {
        setMessage(`✅ "${plan.display_name}" deactivated.`)
        fetchPlans()
      } else {
        setMessage(res.error || 'Failed to deactivate plan')
      }
    } catch (err) {
      setMessage('Network error while deactivating plan')
    }
  }

  const handleActivate = async (plan) => {
    try {
      const res = await subscriptions.adminUpdatePlan(plan.id, { is_active: true })
      if (res.ok) {
        setMessage(`✅ "${plan.display_name}" is active again.`)
        fetchPlans()
      } else {
        setMessage(res.error || 'Failed to activate plan')
      }
    } catch (err) {
      setMessage('Network error while activating plan')
    }
  }

  return (
    <div className="max-w-5xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#0F172A]">Manage Plans</h1>
          <p className="text-sm text-gray-500 mt-1">
            Editing here updates the public Offerings page directly — Base, Royal, and any other tier shown to visitors all come from this list.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm"
        >
          + Add New Plan
        </button>
      </div>

      {message && (
        <div className="mb-4 rounded-lg bg-blue-50 border border-blue-200 px-4 py-3 text-sm text-blue-800">
          {message}
        </div>
      )}

      {loading ? (
        <p className="text-gray-500">Loading plans…</p>
      ) : (
        <div className="bg-white rounded-xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-100">
              <tr>
                <th className="p-3 text-left">Plan</th>
                <th className="p-3 text-right">Price</th>
                <th className="p-3 text-right">Validity</th>
                <th className="p-3 text-right">Legal Incidents</th>
                <th className="p-3 text-right">Follow-ups</th>
                <th className="p-3 text-center">Status</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {plans.map((plan) => (
                <tr key={plan.id} className="border-t">
                  <td className="p-3">
                    <div className="font-semibold">{plan.display_name}</div>
                    {plan.description && <div className="text-xs text-gray-500">{plan.description}</div>}
                  </td>
                  <td className="p-3 text-right">₹{plan.price?.toLocaleString('en-IN')}</td>
                  <td className="p-3 text-right">{plan.validity_days} days</td>
                  <td className="p-3 text-right">{plan.legal_assistance_limit}</td>
                  <td className="p-3 text-right">{plan.follow_up_limit}</td>
                  <td className="p-3 text-center">
                    <span className={`px-2 py-1 rounded-full text-xs font-semibold ${plan.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {plan.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="p-3 text-right space-x-2">
                    <button onClick={() => openEdit(plan)} className="text-blue-600 hover:underline text-xs font-semibold">Edit</button>
                    {plan.is_active ? (
                      <button onClick={() => handleDeactivate(plan)} className="text-red-500 hover:underline text-xs font-semibold">Deactivate</button>
                    ) : (
                      <button onClick={() => handleActivate(plan)} className="text-green-600 hover:underline text-xs font-semibold">Activate</button>
                    )}
                  </td>
                </tr>
              ))}
              {plans.length === 0 && (
                <tr><td colSpan={7} className="p-6 text-center text-gray-400">No plans yet — click "Add New Plan" to create the first one.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {editingId !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-[200]">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <h2 className="text-lg font-bold text-[#0F172A] mb-4">
              {editingId === 'new' ? 'Add New Plan' : `Edit ${formData.display_name}`}
            </h2>
            <form onSubmit={handleSave} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Display Name <span className="text-red-500">*</span></label>
                <input required value={formData.display_name} onChange={e => setFormData({ ...formData, display_name: e.target.value })} className="border p-2 rounded w-full" placeholder="e.g. Royal" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Description</label>
                <input value={formData.description} onChange={e => setFormData({ ...formData, description: e.target.value })} className="border p-2 rounded w-full" placeholder="e.g. For growing businesses." />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Price (₹) <span className="text-red-500">*</span></label>
                  <input required type="number" min="0" step="1" value={formData.price} onChange={e => setFormData({ ...formData, price: e.target.value })} className="border p-2 rounded w-full" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Validity (days) <span className="text-red-500">*</span></label>
                  <input required type="number" min="1" step="1" value={formData.validity_days} onChange={e => setFormData({ ...formData, validity_days: e.target.value })} className="border p-2 rounded w-full" placeholder="e.g. 30" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Legal Incidents <span className="text-red-500">*</span></label>
                  <input required type="number" min="0" step="1" value={formData.legal_assistance_limit} onChange={e => setFormData({ ...formData, legal_assistance_limit: e.target.value })} className="border p-2 rounded w-full" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Follow-up Limit <span className="text-red-500">*</span></label>
                  <input required type="number" min="0" step="1" value={formData.follow_up_limit} onChange={e => setFormData({ ...formData, follow_up_limit: e.target.value })} className="border p-2 rounded w-full" />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={closeForm} className="flex-1 px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 font-medium text-sm">Cancel</button>
                <button type="submit" disabled={saving} className="flex-1 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm disabled:opacity-60">
                  {saving ? 'Saving…' : editingId === 'new' ? 'Create Plan' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
