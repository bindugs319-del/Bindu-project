/**
 * Aggregate a list of records (POs, invoices, etc.) into a monthly
 * { name, count, amount } series for the last `monthsBack` months,
 * for use with StatsChart. Real data in, real chart out — no demo
 * numbers involved.
 *
 * @param {Array} rows - records to aggregate
 * @param {Object} opts
 * @param {(row: any) => string|Date} opts.getDate - returns the row's date
 * @param {(row: any) => number} opts.getAmount - returns the row's ₹ amount
 * @param {number} [opts.monthsBack=6] - how many trailing months to include
 */
export function buildMonthlySeries(rows, { getDate, getAmount, monthsBack = 6 }) {
  const now = new Date()
  const months = []
  for (let i = monthsBack - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    months.push({
      key: `${d.getFullYear()}-${d.getMonth()}`,
      name: d.toLocaleDateString('en-US', { month: 'short' }),
      count: 0,
      amount: 0,
    })
  }
  const byKey = new Map(months.map(m => [m.key, m]))

  for (const row of Array.isArray(rows) ? rows : []) {
    const raw = getDate(row)
    if (!raw) continue
    const d = new Date(raw)
    if (Number.isNaN(d.getTime())) continue
    const key = `${d.getFullYear()}-${d.getMonth()}`
    const bucket = byKey.get(key)
    if (!bucket) continue // outside the trailing window
    bucket.count += 1
    bucket.amount += Number(getAmount(row)) || 0
  }

  return months.map(({ key, ...rest }) => rest)
}
