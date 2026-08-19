import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { accountProfile } from '../services/api/apiClient'

function formatError(error) {
  if (error === null || error === undefined) return ''
  if (typeof error === 'string') return error

  if (Array.isArray(error)) {
    return error
      .map((e) => {
        if (typeof e === 'string') return e
        if (e && typeof e === 'object') {
          const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : null
          const msg = e.msg || e.message || JSON.stringify(e)
          return field ? `${field}: ${msg}` : msg
        }
        return String(e)
      })
      .join('; ')
  }

  if (typeof error === 'object') {
    if (error.detail) return formatError(error.detail)
    if (error.message) return error.message
    try {
      return JSON.stringify(error)
    } catch {
      return String(error)
    }
  }

  return String(error)
}

export default function CompanyProfile() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

  const [form, setForm] = useState({
    name: '',
    registered_name: '',
    email: '',
    phone: '',
    gstin: '',
    address: '',
    pan: '',
    cin: '',
    msme_no: '',
    bank_account_name: '',
    bank_account_number: '',
    bank_ifsc: '',
    bank_name: '',
    bank_upi_id: '',
  })

  useEffect(() => {
    loadProfile()
  }, [])

  const loadProfile = async () => {
    setLoading(true)
    setError(null)

    const res = await accountProfile.get()
    if (res.ok) {
      const p = res.data || {}
      setForm({
        name: p.name || '',
        registered_name: p.registered_name || '',
        email: p.email || '',
        phone: p.phone || '',
        gstin: p.gstin && p.gstin !== 'N/A' ? p.gstin : '',
        address: p.address || '',
        pan: p.pan && p.pan !== 'N/A' ? p.pan : '',
        cin: p.cin || '',
        msme_no: p.msme_no || '',
        bank_account_name: p.bank_account_name || '',
        bank_account_number: p.bank_account_number || '',
        bank_ifsc: p.bank_ifsc || '',
        bank_name: p.bank_name || '',
        bank_upi_id: p.bank_upi_id || '',
      })
    } else {
      setError(res.error)
    }

    setLoading(false)
  }

  const handleChange = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }))
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setSuccess(null)

    const res = await accountProfile.update(form)

    if (res.ok) {
      setSuccess('Company profile saved.')
      loadProfile()
    } else {
      setError(res.error)
    }

    setSaving(false)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 py-6 px-4">
        <div className="max-w-3xl mx-auto text-center p-8 text-gray-500">
          Loading company profile...
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-6 px-4">
      <div className="max-w-3xl mx-auto">

        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 mb-4"
        >
          ← Back
        </button>

        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">
            Company Profile
          </h1>
          <p className="text-gray-600">
            These details are used to auto-fill new invoices — your
            company name, GSTIN, PAN, CIN, and bank details are
            snapshotted onto every invoice you create.
          </p>
        </div>

        {error && (
          <div className="bg-red-100 text-red-700 p-3 rounded mb-4">
            {formatError(error)}
          </div>
        )}

        {success && (
          <div className="bg-green-100 text-green-700 p-3 rounded mb-4">
            {success}
          </div>
        )}

        <form onSubmit={handleSave} className="bg-white rounded-xl shadow p-6 space-y-6">

          <div>
            <h2 className="font-bold text-lg mb-3">Company Details</h2>

            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  Display Name
                </label>
                <input
                  value={form.name}
                  onChange={handleChange('name')}
                  className="w-full border p-2 rounded"
                  placeholder="e.g. Preflex Solutions"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  Registered Company Name *
                </label>
                <input
                  required
                  value={form.registered_name}
                  onChange={handleChange('registered_name')}
                  className="w-full border p-2 rounded"
                  placeholder="e.g. Preflex Solutions Private Limited"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  Email *
                </label>
                <input
                  required
                  type="email"
                  value={form.email}
                  onChange={handleChange('email')}
                  className="w-full border p-2 rounded"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  Phone *
                </label>
                <input
                  required
                  value={form.phone}
                  onChange={handleChange('phone')}
                  className="w-full border p-2 rounded"
                />
              </div>

              <div className="md:col-span-2">
                <label className="block text-sm text-gray-600 mb-1">
                  Address
                </label>
                <textarea
                  value={form.address}
                  onChange={handleChange('address')}
                  className="w-full border p-2 rounded"
                  rows="3"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  GSTIN
                </label>
                <input
                  value={form.gstin}
                  onChange={handleChange('gstin')}
                  className="w-full border p-2 rounded"
                  placeholder="15 characters"
                  maxLength={15}
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  PAN
                </label>
                <input
                  value={form.pan}
                  onChange={handleChange('pan')}
                  className="w-full border p-2 rounded"
                  placeholder="10 characters"
                  maxLength={10}
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  CIN (Corporate Identification Number)
                </label>
                <input
                  value={form.cin}
                  onChange={handleChange('cin')}
                  className="w-full border p-2 rounded"
                  placeholder="e.g. U72900KA2015PTC123456"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  MSME Registration No.
                </label>
                <input
                  value={form.msme_no}
                  onChange={handleChange('msme_no')}
                  className="w-full border p-2 rounded"
                />
              </div>
            </div>
          </div>

          <div className="border-t pt-6">
            <h2 className="font-bold text-lg mb-3">
              Bank / Payment Details
            </h2>
            <p className="text-sm text-gray-500 mb-3">
              Shown on invoices so customers know where to send payment.
            </p>

            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  Bank Name
                </label>
                <input
                  value={form.bank_name}
                  onChange={handleChange('bank_name')}
                  className="w-full border p-2 rounded"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  Account Holder Name
                </label>
                <input
                  value={form.bank_account_name}
                  onChange={handleChange('bank_account_name')}
                  className="w-full border p-2 rounded"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  Account Number
                </label>
                <input
                  value={form.bank_account_number}
                  onChange={handleChange('bank_account_number')}
                  className="w-full border p-2 rounded"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  IFSC Code
                </label>
                <input
                  value={form.bank_ifsc}
                  onChange={handleChange('bank_ifsc')}
                  className="w-full border p-2 rounded"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  UPI ID
                </label>
                <input
                  value={form.bank_upi_id}
                  onChange={handleChange('bank_upi_id')}
                  className="w-full border p-2 rounded"
                  placeholder="e.g. company@bank"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 border-t pt-6">
            <Link
              to="/invoices"
              className="px-5 py-2 border rounded text-center"
            >
              Back to Invoices
            </Link>
            <button
              type="submit"
              disabled={saving}
              className="px-5 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Company Profile'}
            </button>
          </div>

        </form>

      </div>
    </div>
  )
}
