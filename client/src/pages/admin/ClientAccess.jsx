import { useCallback, useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useAuth } from '../../state/authContext'
import { clientAccess } from '../../services/api/apiClient'
import AuthorizedClientsPanel from '../../components/admin-access/AuthorizedClientsPanel'
import { formatWhen, timeLeft } from '../../utils/delegation'

function AllGrants() {
  const [grants, setGrants] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    const res = await clientAccess.all()
    setGrants(res.ok ? (res.data?.grants || []) : [])
    setLoading(false)
  }, [])

  useEffect(() => { void load() }, [load])

  const revoke = async (id) => {
    if (!window.confirm('Revoke this grant? The admin loses access immediately.')) return
    await clientAccess.revoke(id)
    void load()
  }

  if (loading) return <p className="text-sm text-gray-500">Loading…</p>
  if (grants.length === 0) return <p className="text-sm text-gray-500 italic">No active grants.</p>
  return (
    <div className="bg-white rounded-[16px] shadow-[0_4px_24px_rgba(30,58,138,0.08)] overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="bg-[#F8FAFF] text-[11px] uppercase tracking-wide">
          <tr>
            <th className="px-4 py-3">Client</th>
            <th className="px-4 py-3">Admin</th>
            <th className="px-4 py-3">Granted</th>
            <th className="px-4 py-3">Expires</th>
            <th className="px-4 py-3">Last viewed</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-[#E2E8F0]">
          {grants.map((g) => (
            <tr key={g.id}>
              <td className="px-4 py-3"><span className="font-semibold">{g.client.company_name}</span><br /><span className="text-xs text-gray-500">{g.client.gstin}</span></td>
              <td className="px-4 py-3">{g.admin?.name || g.admin?.email}<br /><span className="text-xs text-gray-500">{g.admin?.role}</span></td>
              <td className="px-4 py-3">{formatWhen(g.granted_at)}</td>
              <td className="px-4 py-3">in {timeLeft(g.expires_at)}</td>
              <td className="px-4 py-3">{formatWhen(g.last_viewed_at)}</td>
              <td className="px-4 py-3 text-right">
                <button type="button" onClick={() => revoke(g.id)} className="px-3 py-1 rounded-lg bg-red-600 text-white font-semibold hover:bg-red-700">Revoke</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const EVENT_LABELS = {
  CODE_GENERATED: 'Code generated',
  CODE_CANCELLED: 'Code cancelled',
  REDEEMED: 'Code redeemed',
  REDEEM_FAILED: 'Failed redeem',
  VIEWED: 'Viewed',
  WRITE_BLOCKED: 'Write blocked',
  REVOKED: 'Revoked',
  EXPIRED: 'Expired',
}

function AuditLog() {
  const [items, setItems] = useState([])
  const [event, setEvent] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    void clientAccess.audit({ limit: 300, event }).then((res) => {
      setItems(res.ok ? (res.data?.items || []) : [])
      setLoading(false)
    })
  }, [event])

  return (
    <div className="space-y-3">
      <select value={event} onChange={(e) => setEvent(e.target.value)} className="px-3 py-2 rounded-xl border border-gray-200 text-sm">
        <option value="">All events</option>
        {Object.entries(EVENT_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {!loading && (
        <div className="bg-white rounded-[16px] shadow-[0_4px_24px_rgba(30,58,138,0.08)] overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F8FAFF] uppercase tracking-wide">
              <tr>
                <th className="px-3 py-2">Time</th>
                <th className="px-3 py-2">Event</th>
                <th className="px-3 py-2">Admin</th>
                <th className="px-3 py-2">Client</th>
                <th className="px-3 py-2">Resource / path</th>
                <th className="px-3 py-2">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E8F0]">
              {items.map((i) => (
                <tr key={i.id} className={i.event === 'WRITE_BLOCKED' || i.event === 'REDEEM_FAILED' ? 'bg-red-50' : ''}>
                  <td className="px-3 py-2 whitespace-nowrap">{formatWhen(i.at)}</td>
                  <td className="px-3 py-2 font-semibold">{EVENT_LABELS[i.event] || i.event}</td>
                  <td className="px-3 py-2">{i.admin_email || '—'}{i.admin_role ? ` (${i.admin_role})` : ''}</td>
                  <td className="px-3 py-2">{i.client_company || '—'}</td>
                  <td className="px-3 py-2">{i.resource || ''}{i.path ? <span className="text-gray-500"> {i.method} {i.path}</span> : ''}</td>
                  <td className="px-3 py-2">{i.ip || '—'}</td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan="6" className="px-3 py-6 text-center text-gray-500 italic">No events.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/** Admin page: redeem client codes, see authorized clients; Super Admin also sees all grants + audit. */
export default function ClientAccess() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const isSuper = String(user?.role || '').toUpperCase() === 'MASTER_ADMIN'
  const [tab, setTab] = useState('mine')
  const ended = params.get('ended')

  const tabs = [
    { id: 'mine', label: 'My client accounts' },
    ...(isSuper ? [{ id: 'all', label: 'All active grants' }, { id: 'audit', label: 'Audit log' }] : []),
  ]

  return (
    <section className="container-custom py-10">
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-3xl font-heading font-bold text-[#0F172A]">Client Access</h1>
            <p className="text-sm text-[#475569] mt-1">
              Read-only access to client accounts, granted by the client with a one-time code. Every view is logged
              and the client can revoke access at any time.
            </p>
          </div>
          {isSuper && (
            <Link to="/admin/organizations" className="px-3 py-2 rounded-lg border border-[#DBEAFE] text-sm font-semibold text-[#1E3A8A] hover:bg-[#F0F4FF]">
              Branch limits →
            </Link>
          )}
        </div>

        {ended && (
          <div className="rounded-xl bg-amber-50 border border-amber-300 p-3 text-sm text-amber-900">
            Your view of that client account ended (it expired, was revoked, or you exited).
          </div>
        )}

        {tabs.length > 1 && (
          <div className="flex gap-2 border-b border-[#E2E8F0]">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={`px-4 py-2 text-sm font-semibold -mb-px border-b-2 ${tab === t.id ? 'border-[#1E3A8A] text-[#1E3A8A]' : 'border-transparent text-[#475569]'}`}
              >
                {t.label}
              </button>
            ))}
          </div>
        )}

        {tab === 'mine' && <AuthorizedClientsPanel showRedeem title="Clients who authorized you" />}
        {tab === 'all' && isSuper && <AllGrants />}
        {tab === 'audit' && isSuper && <AuditLog />}
      </div>
    </section>
  )
}
