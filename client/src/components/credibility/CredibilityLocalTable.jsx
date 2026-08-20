import { Link } from 'react-router-dom'
import StarDisplay from './StarDisplay'

/**
 * The "Direct Trade Reliability (local CBI)" table — identical structure
 * between CredibilityIndex.jsx (PO-based) and InvCredibilityIndex.jsx
 * (invoice-based), just with different heading/label/link text and a
 * slightly different formula for the second (unpaid) progress-bar
 * segment, both passed in as props to preserve exact original behavior.
 */
export default function CredibilityLocalTable({
  heading,
  description,
  fulfillmentLabel,
  emptyMessage,
  viewPathPrefix,
  filtered,
  unpaidPercent,
}) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-[#0F172A] mb-1">{heading}</h2>
        <div style={{ width: '60px', height: '3px', backgroundColor: '#F59E0B' }}></div>
        <p className="text-sm text-[#475569] mt-3">{description}</p>
      </div>
      <div className="bg-white rounded-[12px] border border-[#E2E8F0] shadow-md overflow-hidden relative">
        <div className="scrollable-container relative max-h-[500px] overflow-y-auto">
          <table className="w-full">
            <thead className="bg-[#F9FAFB] sticky top-0 z-10 backdrop-blur-sm">
              <tr>
                <th className="py-4 px-6 text-left text-xs font-bold text-[#374151] uppercase tracking-widest border-b border-[#E2E8F0]">Company</th>
                <th className="py-4 px-6 text-left text-xs font-bold text-[#374151] uppercase tracking-widest border-b border-[#E2E8F0]">Performance</th>
                <th className="py-4 px-6 text-left text-xs font-bold text-[#374151] uppercase tracking-widest border-b border-[#E2E8F0]">Grade</th>
                <th className="py-4 px-6 text-left text-xs font-bold text-[#374151] uppercase tracking-widest border-b border-[#E2E8F0]">Risk</th>
                <th className="py-4 px-6 text-left text-xs font-bold text-[#374151] uppercase tracking-widest border-b border-[#E2E8F0]">{fulfillmentLabel}</th>
                <th className="py-4 px-6 text-left text-xs font-bold text-[#374151] uppercase tracking-widest border-b border-[#E2E8F0]">View</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-[#F3F4F6]">
              {filtered.length === 0 ? (
                <tr><td colSpan="6" className="py-8 text-center text-[#9CA3AF]">{emptyMessage}</td></tr>
              ) : (
                filtered.map(r => (
                  <tr key={r.company_name} className="transition-colors duration-150 hover:bg-[#EFF6FF]/60 even:bg-[#F9FAFB]/60">
                    <td className="py-4 px-6 font-medium text-[#0F172A]">{r.company_name}</td>
                    <td className="py-4 px-6">
                      <StarDisplay stars={r.stars} color="text-emerald-500" />
                    </td>
                    <td className="py-4 px-6">
                      <span className={`px-3 py-1 rounded-full text-xs font-semibold ${r.grade === 'A' ? 'bg-[#D1FAE5] text-[#065F46]' : r.grade === 'B' ? 'bg-[#DBEAFE] text-[#1E40AF]' : r.grade === 'C' ? 'bg-[#FEF3C7] text-[#92400E]' : 'bg-[#FEE2E2] text-[#991B1B]'}`}>
                        {r.grade}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      <span className={`${(r.risk || r.risk_level) === 'Low' ? 'text-[#16A34A]' : (r.risk || r.risk_level) === 'Medium' ? 'text-[#F59E0B]' : 'text-[#DC2626]'}`}>
                        {(r.risk || r.risk_level) === 'Low' ? '✅ Low' : (r.risk || r.risk_level) === 'Medium' ? '⚠️ Medium' : '❌ High'}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      <div className="min-w-[180px]">
                        <div className="w-full h-[6px] rounded-full bg-[#E2E8F0] overflow-hidden">
                          <div className="h-full bg-[#16A34A] inline-block" style={{ width: `${r.total_pos ? Math.round((r.paid_pos / r.total_pos) * 100) : 0}%` }} />
                          <div className="h-full bg-[#F59E0B] inline-block" style={{ width: `${unpaidPercent(r)}%` }} />
                        </div>
                        <div className="text-xs text-[#475569] mt-2">{r.paid_pos}/{r.total_pos} Paid</div>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <Link to={`${viewPathPrefix}/${r.company_id}`} className="text-[#1D4ED8] font-medium hover:underline">View</Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
