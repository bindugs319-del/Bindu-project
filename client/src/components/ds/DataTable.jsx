import { useMemo, useState, useEffect } from 'react'
import PropTypes from 'prop-types'
import { ArrowUp, ArrowDown, ChevronsUpDown, ChevronLeft, ChevronRight, AlertCircle, Inbox } from 'lucide-react'
import EmptyState from './EmptyState'
import Button from './Button'

const PAGE_SIZES = [10, 25, 50]

function compare(a, b) {
  if (a == null && b == null) return 0
  if (a == null) return 1
  if (b == null) return -1
  if (typeof a === 'number' && typeof b === 'number') return a - b
  return String(a).localeCompare(String(b), 'en-IN', { numeric: true, sensitivity: 'base' })
}

/**
 * Design-system data table (presentation only — sorts/paginates the rows
 * it is given; never fetches).
 *
 * columns: [{ key, header, render?(row), sortValue?(row), sortable?, align?: 'left'|'right',
 *             className?, headerClassName? }]
 */
export default function DataTable({
  columns,
  rows,
  rowKey = (r) => r.id,
  loading = false,
  error = null,
  onRetry,
  empty,
  caption,
  initialSort = null,
  pageSize: initialPageSize = 10,
  paginate = true,
  maxHeight,
  rowClassName,
  toolbar,
  footer,
}) {
  const [sort, setSort] = useState(initialSort) // { key, dir: 'asc'|'desc' }
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(initialPageSize)

  const sorted = useMemo(() => {
    if (!sort) return rows
    const col = columns.find((c) => c.key === sort.key)
    if (!col) return rows
    const get = col.sortValue || ((r) => r[col.key])
    const out = [...rows].sort((a, b) => compare(get(a), get(b)))
    return sort.dir === 'desc' ? out.reverse() : out
  }, [rows, sort, columns])

  const pageCount = paginate ? Math.max(1, Math.ceil(sorted.length / pageSize)) : 1
  useEffect(() => { if (page > pageCount - 1) setPage(0) }, [page, pageCount])
  const visible = paginate ? sorted.slice(page * pageSize, page * pageSize + pageSize) : sorted

  const toggleSort = (key) => {
    setSort((s) => {
      if (!s || s.key !== key) return { key, dir: 'asc' }
      if (s.dir === 'asc') return { key, dir: 'desc' }
      return null
    })
  }

  const from = sorted.length === 0 ? 0 : page * pageSize + 1
  const to = Math.min(sorted.length, (page + 1) * pageSize)

  let bodyState = null
  if (loading) bodyState = 'loading'
  else if (error) bodyState = 'error'
  else if (rows.length === 0) bodyState = 'empty'

  return (
    <div className="bg-surface-card border border-ink-200 rounded-card shadow-xs overflow-hidden">
      {toolbar && <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-200 px-4 py-3">{toolbar}</div>}

      <div className="relative overflow-auto" style={maxHeight ? { maxHeight } : undefined}>
        <table className="min-w-full text-left">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead className="sticky top-0 z-10 bg-ink-100">
            <tr>
              {columns.map((col) => {
                const sortable = col.sortable !== false && !!(col.sortValue || col.sortable)
                const active = sort?.key === col.key
                let ariaSort
                if (active) ariaSort = sort.dir === 'asc' ? 'ascending' : 'descending'
                let SortIcon = ChevronsUpDown
                if (active) SortIcon = sort.dir === 'asc' ? ArrowUp : ArrowDown
                return (
                  <th
                    key={col.key}
                    scope="col"
                    aria-sort={ariaSort}
                    className={`px-4 py-2.5 text-overline uppercase text-ink-600 whitespace-nowrap border-b border-ink-200 ${col.align === 'right' ? 'text-right' : ''} ${col.headerClassName || ''}`}
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(col.key)}
                        className={`inline-flex items-center gap-1 rounded uppercase hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${col.align === 'right' ? 'flex-row-reverse' : ''} ${active ? 'text-ink-900' : ''}`}
                      >
                        {col.header}
                        <SortIcon aria-hidden="true" className={`h-3 w-3 ${active ? 'text-ink-700' : 'text-ink-400'}`} />
                      </button>
                    ) : col.header}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            {bodyState === 'loading' && Array.from({ length: 4 }).map((_, i) => (
              // eslint-disable-next-line react/no-array-index-key
              <tr key={`sk-${i}`} aria-hidden="true">
                {columns.map((col) => (
                  <td key={col.key} className="px-4 py-3"><div className="h-4 rounded skeleton-shimmer" /></td>
                ))}
              </tr>
            ))}
            {bodyState === 'error' && (
              <tr>
                <td colSpan={columns.length}>
                  <EmptyState
                    icon={AlertCircle}
                    title="Couldn’t load this data"
                    description={typeof error === 'string' ? error : 'Please try again.'}
                    action={onRetry ? <Button size="sm" onClick={onRetry}>Retry</Button> : null}
                  />
                </td>
              </tr>
            )}
            {bodyState === 'empty' && (
              <tr>
                <td colSpan={columns.length}>
                  {empty || <EmptyState icon={Inbox} title="Nothing here yet" />}
                </td>
              </tr>
            )}
            {!bodyState && visible.map((row) => (
              <tr key={rowKey(row)} className={`hover:bg-ink-50 ${rowClassName ? rowClassName(row) : ''}`}>
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`px-4 py-3 text-small text-ink-700 align-middle ${col.align === 'right' ? 'text-right tabular-nums' : ''} ${col.className || ''}`}
                  >
                    {col.render ? col.render(row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {(paginate && !bodyState && sorted.length > 0) && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink-200 px-4 py-2.5 text-small text-ink-600">
          <div className="flex items-center gap-2">
            <label htmlFor={`ps-${caption || 'table'}`} className="text-caption text-ink-500">Rows</label>
            <select
              id={`ps-${caption || 'table'}`}
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value)); setPage(0) }}
              className="h-8 rounded-control border border-ink-200 bg-white px-2 text-small focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            >
              {PAGE_SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
            {footer}
          </div>
          <div className="flex items-center gap-2">
            <span className="tabular-nums" aria-live="polite">{from}–{to} of {sorted.length}</span>
            <button
              type="button"
              aria-label="Previous page"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-control border border-ink-200 bg-white hover:bg-ink-50 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            >
              <ChevronLeft aria-hidden="true" className="h-4 w-4" />
            </button>
            <button
              type="button"
              aria-label="Next page"
              disabled={page >= pageCount - 1}
              onClick={() => setPage((p) => p + 1)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-control border border-ink-200 bg-white hover:bg-ink-50 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            >
              <ChevronRight aria-hidden="true" className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

DataTable.propTypes = {
  columns: PropTypes.arrayOf(PropTypes.shape({
    key: PropTypes.string.isRequired,
    header: PropTypes.node.isRequired,
    render: PropTypes.func,
    sortValue: PropTypes.func,
    sortable: PropTypes.bool,
    align: PropTypes.oneOf(['left', 'right']),
    className: PropTypes.string,
    headerClassName: PropTypes.string,
  })).isRequired,
  rows: PropTypes.array.isRequired,
  rowKey: PropTypes.func,
  loading: PropTypes.bool,
  error: PropTypes.oneOfType([PropTypes.string, PropTypes.bool]),
  onRetry: PropTypes.func,
  empty: PropTypes.node,
  caption: PropTypes.string,
  initialSort: PropTypes.shape({ key: PropTypes.string, dir: PropTypes.oneOf(['asc', 'desc']) }),
  pageSize: PropTypes.number,
  paginate: PropTypes.bool,
  maxHeight: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  rowClassName: PropTypes.func,
  toolbar: PropTypes.node,
  footer: PropTypes.node,
}
