import { useCallback, useEffect, useState } from 'react'
import { Building2, GitBranch, Network } from 'lucide-react'
import { organization } from '../../services/api/apiClient'
import Card, { CardHeader } from '../ds/Card'
import Button from '../ds/Button'
import Badge from '../ds/Badge'

/**
 * Account → Organisation: independent company / head office / branch.
 * Only the company admin can change anything; others see the status.
 */
export default function OrganisationSettings() {
  const [org, setOrg] = useState(null)
  const [mode, setMode] = useState(null) // null | 'join'
  const [hqGstin, setHqGstin] = useState('')
  const [branchName, setBranchName] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)

  const load = useCallback(async () => {
    const res = await organization.status()
    if (res.ok) setOrg(res.data)
  }, [])

  useEffect(() => { void load() }, [load])

  const run = async (fn, okText) => {
    setBusy(true)
    setMsg(null)
    const res = await fn()
    setBusy(false)
    if (res.ok) {
      setMsg({ ok: true, text: res.message || okText })
      setMode(null)
      setOrg(res.data?.type ? res.data : org)
      void load()
    } else {
      setMsg({ ok: false, text: res.error || 'Something went wrong' })
    }
  }

  if (!org || org.type === 'NONE') return null
  const canManage = org.can_manage

  let body
  if (org.type === 'HEAD_OFFICE') {
    body = (
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          <Network aria-hidden="true" className="mt-0.5 h-5 w-5 text-brand-600" />
          <div>
            <p className="text-body font-medium text-ink-900">Head office</p>
            <p className="text-small text-ink-500">
              {org.approved_count} of {org.branch_limit} branch slot(s) used
              {org.branches.some((b) => b.status === 'PENDING') && ' · requests waiting for approval'}
            </p>
          </div>
        </div>
        <Button to="/organization/branches" variant="primary" size="sm">Manage branches</Button>
      </div>
    )
  } else if (org.type === 'BRANCH') {
    const pending = org.link_status === 'PENDING'
    body = (
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          <GitBranch aria-hidden="true" className="mt-0.5 h-5 w-5 text-brand-600" />
          <div>
            <p className="text-body font-medium text-ink-900">
              {org.branch_name} branch of {org.head_office?.name}
              <Badge tone={pending ? 'warning' : 'success'} className="ml-2">{pending ? 'Waiting for approval' : 'Linked'}</Badge>
            </p>
            <p className="text-small text-ink-500">
              Head office GSTIN <span className="font-mono">{org.head_office?.gstin}</span>.
              {pending ? ' The head office must approve your request.' : ' Your head office can view your data (read-only). You see only your own data.'}
            </p>
          </div>
        </div>
        {pending && canManage && (
          <Button size="sm" disabled={busy} onClick={() => run(organization.cancelRequest, 'Request cancelled')}>Cancel request</Button>
        )}
      </div>
    )
  } else {
    body = (
      <div className="mt-4 space-y-4">
        <div className="flex items-start gap-3">
          <Building2 aria-hidden="true" className="mt-0.5 h-5 w-5 text-ink-400" />
          <p className="text-small text-ink-600">
            Your company is independent. If it has branches in other states (each with its own GSTIN), set it up as a
            head office to see all branches’ data in one place. If it <em>is</em> a branch, link it to its head office.
          </p>
        </div>
        {canManage && mode === null && (
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="primary"
              disabled={busy}
              onClick={() => {
                if (window.confirm('Make this company a head office? Branches can then ask to link to you.')) {
                  void run(organization.becomeHeadOffice, 'Your company is now a head office')
                }
              }}
            >
              Make this a head office
            </Button>
            <Button size="sm" onClick={() => setMode('join')}>Link to a head office</Button>
          </div>
        )}
        {canManage && mode === 'join' && (
          <form
            className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
            onSubmit={(e) => {
              e.preventDefault()
              void run(() => organization.requestBranch(hqGstin.trim().toUpperCase(), branchName.trim()), 'Request sent')
            }}
          >
            <div>
              <label htmlFor="hq-gstin" className="text-caption font-medium text-ink-700">Head office GSTIN</label>
              <input
                id="hq-gstin"
                value={hqGstin}
                onChange={(e) => setHqGstin(e.target.value.toUpperCase())}
                maxLength={15}
                required
                placeholder="29ABCDE1234F1Z5"
                className="mt-1 h-9 w-full rounded-control border border-ink-200 px-3 font-mono text-small focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              />
            </div>
            <div>
              <label htmlFor="branch-name" className="text-caption font-medium text-ink-700">Branch name</label>
              <input
                id="branch-name"
                value={branchName}
                onChange={(e) => setBranchName(e.target.value)}
                maxLength={120}
                required
                placeholder="e.g. Pune"
                className="mt-1 h-9 w-full rounded-control border border-ink-200 px-3 text-small focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              />
            </div>
            <div className="flex gap-2">
              <Button type="submit" variant="primary" size="md" disabled={busy || hqGstin.length !== 15 || branchName.trim().length < 2}>
                Send request
              </Button>
              <Button variant="ghost" onClick={() => setMode(null)}>Cancel</Button>
            </div>
          </form>
        )}
        {!canManage && <p className="text-caption text-ink-500">Only your company admin can change this.</p>}
      </div>
    )
  }

  return (
    <Card>
      <CardHeader title="Organisation" description="Head office and branches" />
      {body}
      {msg && <p className={`mt-3 text-small ${msg.ok ? 'text-success-700' : 'text-danger-600'}`} role="status">{msg.text}</p>}
    </Card>
  )
}
