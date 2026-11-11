import { useCallback, useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { Network, Search } from 'lucide-react'
import { organization } from '../../services/api/apiClient'
import PageHeader from '../../components/ds/PageHeader'
import DataTable from '../../components/ds/DataTable'
import EmptyState from '../../components/ds/EmptyState'
import Button from '../../components/ds/Button'
import Badge from '../../components/ds/Badge'

function LimitEditor({ row, onSaved }) {
  const [value, setValue] = useState(String(row.branch_limit))
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const dirty = Number(value) !== row.branch_limit

  const save = async () => {
    setBusy(true)
    setErr('')
    const res = await organization.setBranchLimit(row.company_id, Number(value))
    setBusy(false)
    if (res.ok) onSaved()
    else setErr(res.error || 'Could not save')
  }

  return (
    <div className="flex items-center justify-end gap-2">
      <label className="sr-only" htmlFor={`limit-${row.company_id}`}>Branch limit for {row.company_name}</label>
      <input
        id={`limit-${row.company_id}`}
        type="number"
        min={0}
        max={500}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="h-8 w-20 rounded-control border border-ink-200 px-2 text-right text-small tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
      />
      <Button size="sm" variant={dirty ? 'primary' : 'secondary'} disabled={!dirty || busy || value === ''} onClick={save}>
        Save
      </Button>
      {err && <span className="text-caption text-danger-600">{err}</span>}
    </div>
  )
}

LimitEditor.propTypes = {
  row: PropTypes.shape({
    company_id: PropTypes.string.isRequired,
    company_name: PropTypes.string,
    branch_limit: PropTypes.number.isRequired,
  }).isRequired,
  onSaved: PropTypes.func.isRequired,
}

/** Super Admin: how many branches each head office may have. */
export default function Organizations() {
  const [q, setQ] = useState('')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async (query = '') => {
    setLoading(true)
    const res = await organization.listOrganisations(query)
    setRows(res.ok ? (res.data?.items || []) : [])
    setError(res.ok ? '' : (res.error || 'Could not load'))
    setLoading(false)
  }, [])

  useEffect(() => { void load() }, [load])

  const columns = [
    {
      key: 'company_name', header: 'Company', sortable: true,
      render: (r) => (
        <div>
          <p className="font-medium text-ink-900">{r.company_name}</p>
          <p className="font-mono text-caption text-ink-500">{r.gstin}</p>
        </div>
      ),
    },
    {
      key: 'is_headquarters', header: 'Type', sortable: false,
      render: (r) => (r.is_headquarters ? <Badge tone="info">Head office</Badge> : <Badge tone="neutral">Not a head office</Badge>),
    },
    { key: 'approved_count', header: 'Branches', align: 'right', sortable: true },
    { key: 'pending_count', header: 'Pending', align: 'right', sortable: true },
    {
      key: 'branch_limit', header: 'Branch limit', align: 'right', sortable: true,
      render: (r) => <LimitEditor key={`${r.company_id}-${r.branch_limit}`} row={r} onSaved={() => load(q)} />,
    },
  ]

  return (
    <section className="min-h-screen bg-surface-page py-8">
      <div className="container-custom space-y-6">
        <PageHeader
          eyebrow="Super Admin"
          title="Branch limits"
          description="Set how many branches each head office may add. Head offices can’t approve branches beyond their limit."
        />
        <DataTable
          caption="Head offices"
          columns={columns}
          rows={rows}
          rowKey={(r) => r.company_id}
          loading={loading}
          error={error || null}
          onRetry={() => load(q)}
          empty={(
            <EmptyState
              icon={Network}
              title={q ? 'No companies match' : 'No head offices yet'}
              description={q ? 'Try another GSTIN or name.' : 'Search by GSTIN or name to set a limit for any company in advance.'}
            />
          )}
          toolbar={(
            <form
              className="flex flex-wrap items-center gap-2"
              onSubmit={(e) => { e.preventDefault(); void load(q.trim()) }}
            >
              <div className="relative">
                <Search aria-hidden="true" className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
                <input
                  type="search"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Search any company by GSTIN or name"
                  aria-label="Search companies"
                  className="h-8 w-72 rounded-control border border-ink-200 bg-white pl-8 pr-2 text-small focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                />
              </div>
              <Button size="sm" type="submit">Search</Button>
              {q && <Button size="sm" variant="ghost" onClick={() => { setQ(''); void load('') }}>Show head offices</Button>}
            </form>
          )}
        />
      </div>
    </section>
  )
}
