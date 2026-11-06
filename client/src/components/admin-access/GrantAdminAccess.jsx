import { useCallback, useEffect, useState } from 'react'
import { accessGrants } from '../../services/api/apiClient'
import { formatWhen, timeLeft } from '../../utils/delegation'

const DURATIONS = [
  { hours: 24, label: '24 hours' },
  { hours: 72, label: '3 days' },
  { hours: 168, label: '7 days' },
]

const STATUS_STYLES = {
  ACTIVE: 'bg-emerald-100 text-emerald-700',
  REVOKED: 'bg-gray-200 text-gray-600',
  EXPIRED: 'bg-gray-100 text-gray-500',
}

/**
 * Client account settings: let our admin team VIEW this account (read-only)
 * via a one-time authorization code the client sends us.
 */
export default function GrantAdminAccess() {
  const [duration, setDuration] = useState(24)
  const [generated, setGenerated] = useState(null)
  const [copied, setCopied] = useState(false)
  const [grants, setGrants] = useState([])
  const [pending, setPending] = useState([])
  const [activity, setActivity] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    const [list, act] = await Promise.all([accessGrants.list(), accessGrants.activity()])
    if (list.ok) {
      setGrants(list.data?.grants || [])
      setPending(list.data?.pending_codes || [])
    }
    if (act.ok) setActivity(act.data?.items || [])
  }, [])

  useEffect(() => {
    void load()
    const id = setInterval(() => { void load() }, 30000)
    return () => clearInterval(id)
  }, [load])

  const generate = async () => {
    setBusy(true)
    setError('')
    setCopied(false)
    const res = await accessGrants.generate(duration)
    setBusy(false)
    if (!res.ok) {
      setError(res.error || 'Could not generate a code')
      return
    }
    setGenerated(res.data)
    void load()
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(generated.message)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  const revoke = async (grantId) => {
    if (!window.confirm('Revoke this access? The admin will lose access immediately.')) return
    const res = await accessGrants.revoke(grantId)
    if (!res.ok) setError(res.error || 'Could not revoke')
    void load()
  }

  const cancelCode = async (codeId) => {
    const res = await accessGrants.cancelCode(codeId)
    if (!res.ok) setError(res.error || 'Could not cancel code')
    if (generated?.code_id === codeId) setGenerated(null)
    void load()
  }

  const active = grants.filter((g) => g.status === 'ACTIVE')
  const past = grants.filter((g) => g.status !== 'ACTIVE')

  return (
    <div className="card">
      <h2 className="text-xl font-heading font-semibold text-gray-900 mb-1">Grant Admin Access</h2>
      <p className="text-sm text-gray-600 mb-4">
        Let the CreditDataWatch team <strong>view</strong> your account (read-only) to help you.
        They can never change anything or see your password, and you can revoke access at any time.
      </p>

      {/* Generate */}
      <div className="flex flex-col sm:flex-row sm:items-end gap-3">
        <div>
          <label htmlFor="grant-duration" className="text-sm font-semibold text-gray-700">Access duration</label>
          <select
            id="grant-duration"
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
            className="mt-1 block w-full sm:w-44 px-3 py-2 rounded-xl border border-gray-200 text-sm"
          >
            {DURATIONS.map((d) => <option key={d.hours} value={d.hours}>{d.label}</option>)}
          </select>
        </div>
        <button type="button" onClick={generate} disabled={busy} className="btn-primary disabled:opacity-60">
          {busy ? 'Generating…' : 'Generate authorization code'}
        </button>
      </div>
      {error && <p className="text-sm text-red-600 mt-3">{error}</p>}

      {generated && (
        <div className="mt-4 rounded-xl border-2 border-amber-300 bg-amber-50 p-4">
          <p className="text-sm font-semibold text-amber-900 mb-2">
            Copy this message and send it to our team (email, WhatsApp, etc.). It is shown only once and must be
            used within 30 minutes.
          </p>
          <textarea
            readOnly
            value={generated.message}
            rows={4}
            className="w-full font-mono text-xs p-3 rounded-lg border border-amber-200 bg-white"
            onFocus={(e) => e.target.select()}
          />
          <div className="flex items-center gap-3 mt-2">
            <button type="button" onClick={copy} className="btn-primary text-sm">{copied ? 'Copied ✓' : 'Copy message'}</button>
            <button type="button" onClick={() => setGenerated(null)} className="text-sm text-gray-600 hover:underline">Done</button>
          </div>
        </div>
      )}

      {/* Unused codes */}
      {pending.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Codes not used yet</h3>
          <ul className="space-y-2">
            {pending.map((c) => (
              <li key={c.id} className="flex items-center justify-between text-sm bg-gray-50 rounded-lg px-3 py-2">
                <span>{c.duration_hours / 24} day{c.duration_hours > 24 ? 's' : ''} access · code expires in {timeLeft(c.redeem_by)}</span>
                <button type="button" onClick={() => cancelCode(c.id)} className="text-red-600 font-semibold hover:underline">Cancel</button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Grants */}
      <div className="mt-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Active access</h3>
        {active.length === 0 ? (
          <p className="text-sm text-gray-500">No one currently has access to your account.</p>
        ) : (
          <ul className="space-y-2">
            {active.map((g) => (
              <li key={g.id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-sm border border-emerald-200 bg-emerald-50 rounded-lg px-3 py-2">
                <div>
                  <span className="font-semibold">{g.used_by}</span> · since {formatWhen(g.granted_at)} · expires in {timeLeft(g.expires_at)}
                  {g.last_viewed_at && <span className="text-gray-500"> · last viewed {formatWhen(g.last_viewed_at)}</span>}
                </div>
                <button type="button" onClick={() => revoke(g.id)} className="px-3 py-1 rounded-lg bg-red-600 text-white font-semibold hover:bg-red-700">
                  Revoke
                </button>
              </li>
            ))}
          </ul>
        )}
        {past.length > 0 && (
          <details className="mt-3">
            <summary className="text-sm text-gray-600 cursor-pointer">Past access ({past.length})</summary>
            <ul className="mt-2 space-y-1">
              {past.map((g) => (
                <li key={g.id} className="text-sm text-gray-600 flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${STATUS_STYLES[g.status] || ''}`}>{g.status}</span>
                  {g.used_by} · {formatWhen(g.granted_at)} → {formatWhen(g.revoked_at || g.expires_at)}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>

      {/* Activity */}
      <div className="mt-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Admin activity on your account</h3>
        {activity.length === 0 ? (
          <p className="text-sm text-gray-500">No activity yet.</p>
        ) : (
          <ul className="space-y-1 max-h-60 overflow-y-auto">
            {activity.map((a) => (
              <li key={`${a.at}-${a.text}`} className="text-sm text-gray-700">
                {a.text} <span className="text-gray-500">on {formatWhen(a.at)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
