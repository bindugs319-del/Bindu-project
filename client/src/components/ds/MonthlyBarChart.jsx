import { useState } from 'react'
import PropTypes from 'prop-types'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { BarChart3 } from 'lucide-react'
import Card, { CardHeader } from './Card'
import SegmentedControl from './SegmentedControl'
import EmptyState from './EmptyState'
import { formatCount, formatINR, formatINRCompact } from '../../utils/format'

const BRAND = '#1E3A8A' // brand-600
const GRID = '#E2E8F0' // ink-200
const AXIS = '#64748B' // ink-500

/**
 * Honest monthly chart: bars (a zero month shows as no bar, not a curve
 * passing through it), ONE metric at a time on ONE axis, switchable
 * between count and ₹ value. Data: [{ name, count, amount }].
 */
export default function MonthlyBarChart({
  data, title, description, countLabel = 'Count', amountLabel = 'Value', loading = false,
}) {
  const [metric, setMetric] = useState('count')
  const isAmount = metric === 'amount'
  const hasData = data.some((d) => (Number(d.count) || 0) > 0 || (Number(d.amount) || 0) > 0)
  const total = data.reduce((s, d) => s + (Number(d[metric]) || 0), 0)
  const fmt = (v) => (isAmount ? formatINR(v) : formatCount(v))
  const chartSummary = data.map((d) => d.name + ' ' + fmt(d[metric])).join(', ')

  return (
    <Card>
      <CardHeader
        title={title}
        description={description}
        actions={(
          <SegmentedControl
            label="Chart metric"
            value={metric}
            onChange={setMetric}
            options={[{ value: 'count', label: 'Count' }, { value: 'amount', label: 'Value (₹)' }]}
          />
        )}
      />
      {loading && <div className="mt-5 h-60 rounded-control skeleton-shimmer" aria-hidden="true" />}
      {!loading && !hasData && (
        <div className="mt-5 h-60 rounded-control border border-dashed border-ink-200 flex items-center justify-center">
          <EmptyState
            compact
            icon={BarChart3}
            title="No invoices in this period"
            description="Monthly totals will appear here once you raise invoices."
          />
        </div>
      )}
      {!loading && hasData && (
        <>
          <p className="mt-4 text-caption text-ink-500">
            {isAmount ? amountLabel : countLabel} · last {data.length} months
            <span className="ml-2 text-ink-900 font-semibold tabular-nums">{fmt(total)}</span>
          </p>
          <div className="mt-2 h-60" role="img" aria-label={`${title}: ${chartSummary}`}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }} barCategoryGap="30%">
                <CartesianGrid vertical={false} stroke={GRID} />
                <XAxis dataKey="name" tickLine={false} axisLine={{ stroke: GRID }} tick={{ fill: AXIS, fontSize: 12 }} />
                <YAxis
                  allowDecimals={false}
                  tickLine={false}
                  axisLine={false}
                  width={isAmount ? 64 : 32}
                  tick={{ fill: AXIS, fontSize: 12 }}
                  tickFormatter={(v) => (isAmount ? formatINRCompact(v) : formatCount(v))}
                />
                <Tooltip
                  cursor={{ fill: '#F1F5F9' }}
                  contentStyle={{ borderRadius: 8, border: `1px solid ${GRID}`, boxShadow: '0 12px 32px rgba(15,23,42,0.14)', fontSize: 13 }}
                  formatter={(v) => [fmt(v), isAmount ? amountLabel : countLabel]}
                />
                <Bar dataKey={metric} fill={BRAND} radius={[4, 4, 0, 0]} maxBarSize={40} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </Card>
  )
}

MonthlyBarChart.propTypes = {
  data: PropTypes.arrayOf(PropTypes.shape({
    name: PropTypes.string,
    count: PropTypes.number,
    amount: PropTypes.number,
  })).isRequired,
  title: PropTypes.string.isRequired,
  description: PropTypes.string,
  countLabel: PropTypes.string,
  amountLabel: PropTypes.string,
  loading: PropTypes.bool,
}
