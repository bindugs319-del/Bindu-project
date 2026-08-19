import { useState } from 'react'
import StarDisplay from './StarDisplay'
import { credibilityIndex } from '../../services/api/apiClient'

/**
 * "Network Trust Intelligence" table + "Can't find the company you're
 * looking for?" request form. This exact block was duplicated verbatim
 * between CredibilityIndex.jsx and InvCredibilityIndex.jsx — it doesn't
 * depend on PO vs Invoice context, so it's extracted here, along with
 * its own local state (the rating-request form isn't used anywhere else
 * on either page, so there's no need for the parent pages to own it).
 */
export default function NetworkTrustIntelligence({ globalCredibilityIndex, q }) {
  const [ratingRequestCompany, setRatingRequestCompany] = useState('')
  const [ratingRequestSubmitting, setRatingRequestSubmitting] = useState(false)

  const handleRequestCompanyRating = async () => {
    const name = ratingRequestCompany.trim()
    if (!name) return
    setRatingRequestSubmitting(true)
    try {
      const res = await credibilityIndex.requestCompanyRating(name)
      if (res.ok) {
        alert(res.data?.message || 'Rating Request Sent! Our team will update the registry within 24 hours.')
        setRatingRequestCompany('')
      } else {
        alert(res.error || 'Failed to send rating request. Please try again.')
      }
    } catch {
      alert('Failed to send rating request. Please try again.')
    }
    setRatingRequestSubmitting(false)
  }

  return (
    <>
            {/* Section 2: Network Trust Intelligence */}
            <div className="space-y-4">
              <div>
                <h2 className="text-xl font-bold text-[#0F172A] mb-1">Network Trust Intelligence</h2>
                <div style={{ width: '60px', height: '3px', backgroundColor: '#F59E0B' }}></div>
                <p className="text-sm text-[#475569] mt-3">Companies reviewed and verified on CreditDataWatch.</p>
              </div>
              <div className="bg-white rounded-[12px] border border-[#E2E8F0] shadow-md overflow-hidden relative">
                <div className="scrollable-container relative max-h-[500px] overflow-y-auto">
                  <table className="w-full">
                    <thead className="bg-[#F9FAFB] sticky top-0 z-10 backdrop-blur-sm">
                      <tr>
                        <th className="py-4 px-6 text-left text-xs font-bold text-[#374151] uppercase tracking-widest border-b border-[#E2E8F0]">Company</th>
                        <th className="py-4 px-6 text-left text-xs font-bold text-[#374151] uppercase tracking-widest border-b border-[#E2E8F0]">Partner Trust Score</th>
                        <th className="py-4 px-6 text-left text-xs font-bold text-[#374151] uppercase tracking-widest border-b border-[#E2E8F0]">AI Credit Risk Verdict</th>
                        <th className="py-4 px-6 text-left text-xs font-bold text-[#374151] uppercase tracking-widest border-b border-[#E2E8F0]">Status</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-[#F3F4F6]">
                      {globalCredibilityIndex.filter(r => r.company_name.toLowerCase().includes(q.toLowerCase())).length === 0 ? (
                        <tr><td colSpan="4" className="py-8 text-center text-[#9CA3AF]">No companies in the Network Trust Intelligence yet.</td></tr>
                      ) : (
                        globalCredibilityIndex.filter(r => r.company_name.toLowerCase().includes(q.toLowerCase())).map(r => {
                          const trustScore = Number(r.partner_trust_score || 0)
                          const stars = Math.round(trustScore)
                          const verdict = r.ai_credit_risk_verdict || 'Not Rated'
                          const isNotRated = verdict === 'Not Rated'
                          const verdictColor = verdict === 'Low Risk'
                            ? 'text-[#16A34A]'
                            : verdict === 'Medium Risk'
                              ? 'text-[#F59E0B]'
                              : verdict === 'High Risk'
                                ? 'text-[#DC2626]'
                                : 'text-[#9CA3AF]'
                          const verdictIcon = verdict === 'Low Risk' ? '✅' : verdict === 'Medium Risk' ? '⚠️' : verdict === 'High Risk' ? '❌' : '—'
                          const status = r.credibility_status || 'Standard'
                          const isVerified = status === 'Credibility Verified' || status === 'Verified'

                          return (
                            <tr key={r.id} className="transition-colors duration-150 hover:bg-[#EFF6FF]/60 even:bg-[#F9FAFB]/60">
                              <td className="py-4 px-6 font-medium text-[#0F172A]">{r.company_name}</td>
                              <td className="py-4 px-6">
                                <div className="flex items-center gap-2">
                                  <StarDisplay stars={stars} color={isNotRated ? 'text-[#D1D5DB]' : 'text-amber-400'} />
                                  <span className="text-xs font-semibold text-[#F59E0B]">{trustScore.toFixed(1)}</span>
                                </div>
                              </td>
                              <td className="py-4 px-6">
                                <span className={`text-sm font-medium ${verdictColor}`}>
                                  {verdictIcon} {isNotRated ? 'Not Rated' : verdict}
                                </span>
                              </td>
                              <td className="py-4 px-6">
                                <span className={`px-3 py-1 rounded-full text-xs font-semibold ${isVerified ? 'bg-[#DBEAFE] text-[#1E40AF]' : 'bg-[#F3F4F6] text-[#4B5563]'}`}>
                                  {isVerified ? 'Verified' : 'Standard'}
                                </span>
                              </td>
                            </tr>
                          )
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Can't find the company you are looking for? */}
            <div className="bg-white rounded-[12px] border border-[#E2E8F0] shadow-md p-8 text-center space-y-3">
              <h3 className="text-lg font-bold text-[#0F172A]">Can't find the company you are looking for?</h3>
              <p className="text-sm text-[#475569] max-w-2xl mx-auto">
                If a company (like Infosys, TCS, etc.) is not listed in our Network Trust Intelligence registry yet, you
                can request our team to fetch and calculate their global credibility star rating.
              </p>
              <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
                <input
                  value={ratingRequestCompany}
                  onChange={e => setRatingRequestCompany(e.target.value)}
                  placeholder="Company name"
                  className="w-full sm:w-72 px-4 py-3 rounded-[8px] border border-[#E2E8F0] text-sm focus:outline-none focus:border-[#3B82F6] focus:ring-2 focus:ring-[rgba(59,130,246,0.15)]"
                />
                <button
                  onClick={handleRequestCompanyRating}
                  disabled={ratingRequestSubmitting || !ratingRequestCompany.trim()}
                  className="px-6 py-3 rounded-[8px] bg-[#1D4ED8] text-white text-sm font-semibold hover:bg-[#1E40AF] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {ratingRequestSubmitting ? 'Sending...' : 'Request Company Rating'}
                </button>
              </div>
            </div>
    </>
  )
}
