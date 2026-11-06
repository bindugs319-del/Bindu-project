import { useCallback, useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { Link } from 'react-router-dom'
import { clientAccess } from '../../services/api/apiClient'
import { formatWhen, timeLeft } from '../../utils/delegation'

function money(value, currency = 'INR') {
  try {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: currency || 'INR' }).format(Number(value) || 0)
  } catch {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(value) || 0)
  }
}

/** Opens a full read-only view of the client's account in a new tab. */
export function openClientAccount(grantId) {
  window.open(`/client-view/${grantId}`, '_blank', 'noopener')
}

function RedeemBox({ onRedeemed }) {
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!code.trim()) return
    setBusy(true)
    setMsg(null)
    const res = await clientAccess.redeem(code.trim())
    setBusy(false)
    if (res.ok) {
      setCode('')
      setMsg({ ok: true, text: res.message || 'Access granted (read-only).' })
      onRedeemed?.()
    } else {
      setMsg({ ok: false, text: res.error || 'Could not redeem this code.' })
    }
  }

  return (
    <form onSubmit={submit} className="rounded-xl border border-[#DBEAFE] bg-[#F8FAFF] p-4">
      <label htmlFor="redeem-code" className="text-sm font-semibold text-[#0F172A]">Paste the client&apos;s authorization code or message</label>
      <div className="flex flex-col sm:flex-row gap-2 mt-2">
        <textarea
          id="redeem-code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          rows={2}
          placeholder="CDW-XXXX-XXXX-…"
          className="flex-1 px-3 py-2 rounded-xl border border-gray-200 text-sm font-mono"
        />
        <button type="submit" disabled={busy || !code.trim()} className="btn-primary text-sm disabled:opacity-60 sm:self-start">
          {busy ? 'Checking…' : 'Redeem code'}
        </button>
      </div>
      {msg && <p className={`text-sm mt-2 ${msg.ok ? 'text-emerald-700' : 'text-red-600'}`}>{msg.text}</p>}
    </form>
  )
}

RedeemBox.propTypes = { onRedeemed: PropTypes.func }

function ClientInvoices({ grantId }) {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    void clientAccess.clientInvoices(grantId).then((res) => {
      if (!alive) return
      if (res.ok) setRows(res.data?.invoices || [])
      else setError(res.error || 'Could not load invoices')
    })
    return () => { alive = false }
  }, [grantId])

  if (error) return <p className="text-sm text-red-600 px-4 pb-4">{error}</p>
  if (rows === null) return <p className="text-sm text-gray-500 px-4 pb-4">Loading invoices…</p>
  if (rows.length === 0) return <p className="text-sm text-gray-500 px-4 pb-4">This client has no invoices yet.</p>
  return (
    <div className="overflow-x-auto px-4 pb-4">
      <table className="w-full text-left text-sm">
        <thead className="text-[11px] uppercase tracking-wide text-[#475569]">
          <tr>
            <th className="py-2 pr-4">Invoice#</th>
            <th className="py-2 pr-4">Customer</th>
            <th className="py-2 pr-4">Amount</th>
            <th className="py-2 pr-4">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#E2E8F0]">
          {rows.map((inv) => (
            <tr key={inv.id}>
              <td className="py-2 pr-4 font-semibold text-[#1E3A8A]">{inv.invoice_number}</td>
              <td className="py-2 pr-4 text-[#475569]">{inv.counterparty_name}</td>
              <td className="py-2 pr-4">{money(inv.total, inv.currency)}</td>
              <td className="py-2 pr-4">{inv.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

ClientInvoices.propTypes = { grantId: PropTypes.string.isRequired }

/**
 * Clients who have authorized the current admin (read-only view access).
 * Used at the bottom of Customer Invoice and on the Client Access page.
 */
export default function AuthorizedClientsPanel({ showRedeem = false, title = 'Authorized Client Accounts', refreshKey = 0 }) {
  const [grants, setGrants] = useState([])
  const [loading, setLoading] = useState(true)
  const [openInvoices, setOpenInvoices] = useState({})

  const load = useCallback(async () => {
    const res = await clientAccess.mine()
    setGrants(res.ok ? (res.data?.grants || []) : [])
    setLoading(false)
  }, [])

  useEffect(() => { void load() }, [load, refreshKey])

  const release = async (grantId) => {
    if (!window.confirm('Give up your access to this client account?')) return
    await clientAccess.revoke(grantId)
    void load()
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <h2 className="text-base font-bold text-[#0F172A] uppercase tracking-wide">{title}</h2>
        {!showRedeem && (
          <Link to="/admin/client-access" className="text-xs text-[#3B82F6] font-bold hover:underline">Redeem a code →</Link>
        )}
      </div>

      {showRedeem && <RedeemBox onRedeemed={load} />}

      <div className="bg-white rounded-[16px] shadow-[0_4px_24px_rgba(30,58,138,0.08)] divide-y divide-[#E2E8F0]">
        {loading && <p className="p-6 text-sm text-gray-500">Loading…</p>}
        {!loading && grants.length === 0 && (
          <p className="p-6 text-sm text-[#475569] italic">
            No client has authorized you yet. When a client sends you an authorization code, redeem it on the Client Access page.
          </p>
        )}
        {grants.map((g) => (
          <div key={g.id}>
            <div className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div>
                <p className="font-semibold text-[#0F172A]">{g.client.company_name}</p>
                <p className="text-xs text-[#475569]">
                  {g.client.gstin || '—'} · {g.client.email || '—'}
                </p>
                <p className="text-xs text-[#475569] mt-1">
                  Read-only · expires in <strong>{timeLeft(g.expires_at)}</strong> ({formatWhen(g.expires_at)})
                  {g.last_viewed_at && <> · last viewed {formatWhen(g.last_viewed_at)}</>}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setOpenInvoices((s) => ({ ...s, [g.id]: !s[g.id] }))}
                  className="px-3 py-1.5 rounded-lg border border-[#DBEAFE] text-sm font-semibold text-[#1E3A8A] hover:bg-[#F0F4FF]"
                >
                  {openInvoices[g.id] ? 'Hide invoices' : 'Show invoices'}
                </button>
                <button type="button" onClick={() => openClientAccount(g.id)} className="btn-primary text-sm">
                  Open account
                </button>
                <button type="button" onClick={() => release(g.id)} className="px-3 py-1.5 rounded-lg text-sm text-gray-600 hover:text-red-600">
                  Release
                </button>
              </div>
            </div>
            {openInvoices[g.id] && <ClientInvoices grantId={g.id} />}
          </div>
        ))}
      </div>
    </div>
  )
}

AuthorizedClientsPanel.propTypes = {
  showRedeem: PropTypes.bool,
  title: PropTypes.string,
  refreshKey: PropTypes.number,
}
