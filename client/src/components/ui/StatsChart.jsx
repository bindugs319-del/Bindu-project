import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

// Fallback used only if a page forgets to pass real data — keeps the
// component from rendering an empty chart, but every real caller
// (PO_dashboard, invoice_dashboard) now passes actual aggregated data.
const FALLBACK_DATA = [
  { name: 'Jan', count: 0, amount: 0 },
  { name: 'Feb', count: 0, amount: 0 },
  { name: 'Mar', count: 0, amount: 0 },
  { name: 'Apr', count: 0, amount: 0 },
  { name: 'May', count: 0, amount: 0 },
  { name: 'Jun', count: 0, amount: 0 },
]

/**
 * Monthly Performance Overview chart.
 *
 * Renders two lines on independent axes since "count" (e.g. number of
 * POs/invoices raised in a month) and "amount" (total ₹ value for that
 * month) are different scales — sharing one axis was making the smaller
 * series look flat/invisible.
 *
 * `data`: [{ name: 'Jan', count: 3, amount: 45000 }, ...] — the caller
 * is responsible for aggregating its own real records (POs, invoices,
 * etc.) into this shape; this component only renders it.
 */
const StatsChart = ({
  data = FALLBACK_DATA,
  title = 'Monthly Performance Overview',
  countLabel = 'Count',
  amountLabel = 'Amount (₹)',
}) => {
  return (
    <div className="card">
      <h3 className="text-lg font-heading font-bold text-text-primary mb-4">
        {title}
      </h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E0E7FF" />
            <XAxis dataKey="name" stroke="#6B7280" />
            <YAxis yAxisId="count" stroke="#4F46E5" allowDecimals={false} />
            <YAxis yAxisId="amount" orientation="right" stroke="#7C3AED" tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
            <Tooltip
              contentStyle={{
                backgroundColor: 'white',
                borderRadius: '12px',
                border: '1px solid #E0E7FF',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
              }}
              formatter={(value, key) => key === 'amount' ? [`₹${Number(value).toLocaleString('en-IN')}`, amountLabel] : [value, countLabel]}
            />
            <Legend formatter={(key) => key === 'amount' ? amountLabel : countLabel} />
            <Line
              yAxisId="count"
              type="monotone"
              dataKey="count"
              stroke="#4F46E5"
              strokeWidth={3}
              dot={{ fill: '#4F46E5', r: 5 }}
              activeDot={{ r: 8 }}
            />
            <Line
              yAxisId="amount"
              type="monotone"
              dataKey="amount"
              stroke="#7C3AED"
              strokeWidth={3}
              dot={{ fill: '#7C3AED', r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default StatsChart
