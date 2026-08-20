/**
 * The search/risk/sort filter bar at the top of both credibility index
 * pages — identical structure, only the title and icon tooltip differed.
 */
export default function CredibilityFilterBar({
  title,
  iconTitle,
  q,
  setQ,
  risk,
  setRisk,
  sort,
  setSort,
}) {
  return (
    <div className="bg-white rounded-[20px] p-6 border border-[#E2E8F0] shadow-md">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-full bg-[#F59E0B] text-white flex items-center justify-center text-xl" title={iconTitle}>★</div>
        <p className="text-xl font-bold text-[#0F172A]">{title}</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <input
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder="Search company"
          className="flex-1 min-w-[200px] px-4 py-3 rounded-[8px] border border-[#E2E8F0] text-sm focus:outline-none focus:border-[#3B82F6] focus:ring-2 focus:ring-[rgba(59,130,246,0.15)]"
        />
        <select
          value={risk}
          onChange={e => setRisk(e.target.value)}
          className="px-4 py-3 rounded-[8px] border border-[#E2E8F0] text-sm focus:outline-none focus:border-[#3B82F6] focus:ring-2 focus:ring-[rgba(59,130,246,0.15)]"
        >
          <option value="">All risks</option>
          <option value="Low">Low</option>
          <option value="Medium">Medium</option>
          <option value="High">High</option>
        </select>
        <select
          value={sort}
          onChange={e => setSort(e.target.value)}
          className="px-4 py-3 rounded-[8px] border border-[#E2E8F0] text-sm focus:outline-none focus:border-[#3B82F6] focus:ring-2 focus:ring-[rgba(59,130,246,0.15)]"
        >
          <option value="desc">Top score</option>
          <option value="asc">Lowest score</option>
        </select>
      </div>
    </div>
  )
}

