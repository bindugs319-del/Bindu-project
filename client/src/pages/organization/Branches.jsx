import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Building2, FileText, IndianRupee, AlertTriangle, ClipboardList, Eye, Check, X, Trash2, Info } from 'lucide-react'
import { organization } from '../../services/api/apiClient'
import PageHeader from '../../components/ds/PageHeader'
import KpiCard from '../../components/ds/KpiCard'
import Card, { CardHeader } from '../../components/ds/Card'
import Button from '../../components/ds/Button'
import Badge from '../../components/ds/Badge'
import DataTable from '../../components/ds/DataTable'
import EmptyState from '../../components/ds/EmptyState'
import { formatCount, formatINR, formatINRCompact, formatDateShort } from '../../utils/format'

/** Opens a read-only view of a branch's account in a new tab. */
function openBranch(branchCompanyId) {
  window.open(`/branch-view/${branchCompanyId}`, '_blank', 'noopener')
}

/**
 * Head office: combined totals across all branches, per-branch breakdown,
 * pending branch requests, and read-only "Open branch".
 */
export default function Branches() {
  const [params] = useSearchParams()
  const [status, setStatus] = useState(null)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState(params.get('ended') ? 'Your view of that branch ended.' : '')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    const st = await organization.status()
    setStatus(st.ok ? st.data : null)
    if (st.ok && st.data?.type === 'HEAD_OFFICE') {
      const sm = await organization.summary()
      if (sm.ok) setSummary(sm.data)
      else setError(sm.error || 'Could not load branch totals')
    }
    setLoading(false)
  }, [])

  useEffect(() => { void load() }, [load])

  const act = async (fn, linkId, confirmText) => {
    if (confirmText && !window.confirm(confirmText)) return
    setMessage('')
    const res = await fn(linkId)
    if (!res.ok) setError(res.error || 'Something went wrong')
    else setMessage(res.message || 'Done')
    void load()
  }

  if (!loading && status?.type !== 'HEAD_OFFICE') {
    return (
      <section className="min-h-screen bg-surface-page py-8">
        <div className="container-custom space-y-6">
          <PageHeader eyebrow="Organisation" title="Branches" />
          <Card>
            <EmptyState
              icon={Building2}
              title="This company isn’t a head office"
              description="Set your company up as a head office from Account → Organisation to add branches."
              action={<Button to="/account" variant="primary">Go to Account</Button>}
            />
          </Card>
        </div>
      </section>
    )
  }

  const pending = (status?.branches || []).filter((b) => b.status === 'PENDING')
  const totals = summary?.totals || {}
  const limit = status?.branch_limit ?? 0
  const used = status?.approved_count ?? 0
  const branchRows = (summary?.rows || [])

  const columns = [
    {
      key: 'label',
      header: 'Branch',
      sortable: true,
      render: (r) => (
        <div>
          <p className="font-medium text-ink-900">{r.label}</p>
          <p className="font-mono text-caption text-ink-500">{r.gstin}</p>
        </div>
      ),
    },
    { key: 'invoices', header: 'Invoices', align: 'right', sortable: true, render: (r) => formatCount(r.invoices) },
    {
      key: 'outstanding', header: 'Outstanding', align: 'right', sortable: true,
      className: 'font-semibold text-ink-900', render: (r) => formatINR(r.outstanding),
    },
    {
      key: 'overdue_invoices', header: 'Overdue', align: 'right', sortable: true,
      render: (r) => (r.overdue_invoices > 0
        ? <span className="font-semibold text-danger-600">{formatCount(r.overdue_invoices)}</span>
        : '0'),
    },
    { key: 'purchase_orders', header: 'POs', align: 'right', sortable: true, render: (r) => formatCount(r.purchase_orders) },
    { key: 'defaulter_cases', header: 'Defaulter cases', align: 'right', sortable: true, render: (r) => formatCount(r.defaulter_cases) },
    {
      key: 'actions', header: <span className="sr-only">Actions</span>, align: 'right', sortable: false,
      render: (r) => (r.is_head_office ? <Badge tone="neutral" dot={false}>You</Badge> : (
        <div className="flex justify-end gap-2">
          <Button size="sm" icon={Eye} onClick={() => openBranch(r.company_id)}>Open branch</Button>
          <Button
            size="sm"
            variant="ghost"
            icon={Trash2}
            aria-label={`Remove ${r.label}`}
            onClick={() => act(organization.remove, r.link_id, `Remove ${r.label} as a branch? You will lose access to its data.`)}
          >
            Remove
          </Button>
        </div>
      )),
    },
  ]

  return (
    <section className="min-h-screen bg-surface-page py-8">
      <div className="container-custom space-y-6">
        <PageHeader
          eyebrow="Organisation"
          title="Branches"
          description={status?.company ? `${status.company.name} · head office` : undefined}
          actions={(
            <span className="text-small text-ink-600">
              Branches used <span className="font-semibold text-ink-900 tabular-nums">{used} of {limit}</span>
            </span>
          )}
        />

        {message && (
          <div role="status" className="flex items-start gap-2 rounded-control border border-brand-100 bg-brand-50 p-3 text-small text-brand-700">
            <Info aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" /> {message}
          </div>
        )}
        {error && (
          <div role="alert" className="flex items-start gap-2 rounded-control border border-danger-200 bg-danger-50 p-3 text-small text-danger-700">
            <AlertTriangle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" /> {error}
          </div>
        )}
        {limit === 0 && !loading && (
          <div className="flex items-start gap-2 rounded-control border border-warning-200 bg-warning-50 p-3 text-small text-warning-700">
            <Info aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
            Your branch limit is 0, so you can’t approve branches yet. Contact CreditDataWatch to set how many branches you can add.
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard label="Invoices (all branches)" icon={FileText} value={formatCount(totals.invoices)} loading={loading} />
          <KpiCard
            label="Outstanding"
            icon={IndianRupee}
            value={formatINRCompact(totals.outstanding)}
            context={formatINR(totals.outstanding)}
            tone={(totals.outstanding || 0) > 0 ? 'warning' : 'neutral'}
            loading={loading}
          />
          <KpiCard
            label="Overdue invoices"
            icon={AlertTriangle}
            value={formatCount(totals.overdue_invoices)}
            tone={(totals.overdue_invoices || 0) > 0 ? 'danger' : 'neutral'}
            context={(totals.overdue_invoices || 0) > 0 ? 'Needs follow-up' : 'All on time'}
            loading={loading}
          />
          <KpiCard label="Purchase orders" icon={ClipboardList} value={formatCount(totals.purchase_orders)} loading={loading} />
        </div>

        {pending.length > 0 && (
          <Card>
            <CardHeader
              title={`Branch requests (${pending.length})`}
              description="Companies asking to join as your branch. Their GSTIN shares your PAN."
            />
            <ul className="mt-4 divide-y divide-ink-100">
              {pending.map((b) => (
                <li key={b.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div>
                    <p className="text-body font-medium text-ink-900">{b.branch_name} · {b.company.name}</p>
                    <p className="text-caption text-ink-500">
                      <span className="font-mono">{b.company.gstin}</span> · requested {formatDateShort(b.requested_at)}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="primary" icon={Check} disabled={used >= limit} onClick={() => act(organization.approve, b.id)}>
                      Approve
                    </Button>
                    <Button size="sm" icon={X} onClick={() => act(organization.reject, b.id, `Reject the request from ${b.company.name}?`)}>
                      Reject
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
            {used >= limit && (
              <p className="mt-2 text-caption text-warning-700">All {limit} branch slot(s) are in use. Contact CreditDataWatch to raise your limit.</p>
            )}
          </Card>
        )}

        <DataTable
          caption="Branches"
          columns={columns}
          rows={branchRows}
          rowKey={(r) => r.company_id}
          loading={loading}
          paginate={branchRows.length > 10}
          empty={<EmptyState icon={Building2} title="No branches yet" />}
          toolbar={(
            <div>
              <h2 className="text-heading text-ink-900">By branch</h2>
              <p className="text-small text-ink-500">Each branch sees only its own data. Open a branch to view its full account (read-only).</p>
            </div>
          )}
        />
      </div>
    </section>
  )
}
