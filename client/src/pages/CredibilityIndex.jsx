import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../state/authContext'
import { purchaseOrders, credibility, ratings, credibilityIndex } from '../services/api/apiClient'
import { logActivity, ACTIONS } from '../utils/activityLogger'
import TrustGauge from '../components/ui/TrustGauge'
import CompanyHoverCard from '../components/ui/CompanyHoverCard'
import AnimatedVerifiedBadge from '../components/ui/AnimatedVerifiedBadge'
import NetworkTrustIntelligence from '../components/credibility/NetworkTrustIntelligence'
import CredibilityFilterBar from '../components/credibility/CredibilityFilterBar'
import CredibilityLocalTable from '../components/credibility/CredibilityLocalTable'

export default function CredibilityIndex() {
  const { loading, user } = useAuth()
  const [poRows, setPoRows] = useState([])
  const [companies, setCompanies] = useState([])
  const [globalCbi, setGlobalCbi] = useState([])
  const [globalCredibilityIndex, setGlobalCredibilityIndex] = useState([])
  const [q, setQ] = useState('')
  const [risk, setRisk] = useState('')
  const [sort, setSort] = useState('desc')

  useEffect(() => {
    logActivity(ACTIONS.VIEW_CREDIBILITY) 
    async function loadPOs() {
      try {
        const res = await purchaseOrders.list(1, 1000, true)
        const items = Array.isArray(res?.data?.items) ? res.data.items : Array.isArray(res?.data) ? res.data : []
        setPoRows(items)
      } catch {
        setPoRows([])
      }
    }
    loadPOs()
    const onChanged = () => loadPOs()
    window.addEventListener('poChanged', onChanged)
    return () => window.removeEventListener('poChanged', onChanged)
  }, [user])

  useEffect(() => { 
    async function loadFromBackend() { 
      try { 
        const res = await credibility.list()
        if (res.ok && Array.isArray(res.data)) { 
          setCompanies(res.data) 
        } 
        
        const cbiRes = await ratings.getGlobalCbi()
        if (cbiRes.ok && Array.isArray(cbiRes.data)) {
          setGlobalCbi(cbiRes.data)
        }

        const gciRes = await credibilityIndex.getIndex()
        if (gciRes.ok && Array.isArray(gciRes.data)) {
          setGlobalCredibilityIndex(gciRes.data)
        }
      } catch (err) { 
        console.error( 
          'Credibility fetch error:', 
          err 
        ) 
      } 
    } 
    loadFromBackend() 
  }, [user]) 

  const computedCompanies = useMemo(() => {
    // Note: Main logic moved to backend, this is for fallback/compatibility
    const byVendor = new Map()
    for (const po of poRows) {
      const vendor = (po.vendor || '').trim()
      if (!vendor) continue
      const arr = byVendor.get(vendor) || []
      arr.push(po)
      byVendor.set(vendor, arr)
    }
    const toMetrics = (vendorPOs) => {
      const total = vendorPOs.length
      const paid = vendorPOs.filter(p => p.payment_completed_at || String(p.status || '').toLowerCase() === 'closed').length
      const pending = vendorPOs.filter(p => {
        const s = String(p.status || '').toLowerCase()
        return s.includes('open') || s.includes('pending')
      }).length
      const score = total ? Math.round((paid / total) * 100) : 0
      let grade = 'D'
      if (score >= 90) grade = 'A'
      else if (score >= 75) grade = 'B'
      else if (score >= 50) grade = 'C'
      const risk = score >= 80 ? 'Low' : score >= 50 ? 'Medium' : 'High'
      
      // Star rating calculation based on SOP rules
      const percentage = total ? (paid / total) * 100 : 0
      let stars = 1
      if (percentage >= 90) stars = 5
      else if (percentage >= 75) stars = 4
      else if (percentage >= 60) stars = 3
      else if (percentage >= 40) stars = 2
      
      return { total, paid, pending, score, grade, risk, stars }
    }
    const out = []
    for (const [vendor, vpos] of byVendor.entries()) {
      const m = toMetrics(vpos)
      out.push({
        company_id: null,
        company_name: vendor,
        ...m,
      })
    }
    return out
  }, [poRows])

  if (loading) return <div className="p-6">Loading...</div>

  let filtered = companies.filter(r => r.company_name.toLowerCase().includes(q.toLowerCase()))
  if (risk) filtered = filtered.filter(r => String((r.risk || r.risk_level) || '').toLowerCase() === risk.toLowerCase())
  filtered.sort((a, b) => (sort === 'asc' ? (a.score || 0) - (b.score || 0) : (b.score || 0) - (a.score || 0)))

  return (
    <div className="min-h-screen bg-[#F0F4FF]">
      <style>{`
        .scrollable-container::-webkit-scrollbar { width: 6px; } 
        .scrollable-container::-webkit-scrollbar-track { background: #F0F4FF; border-radius: 999px; } 
        .scrollable-container::-webkit-scrollbar-thumb { background: #93C5FD; border-radius: 999px; } 
        .scrollable-container::-webkit-scrollbar-thumb:hover { background: #3B82F6; }
        .scrollable-container::after {
          content: '';
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
          height: 40px;
          background: linear-gradient(to bottom, transparent, rgba(255,255,255,0.9));
          pointer-events: none;
        }
      `}</style>
      {/* Navy Gradient Header */}
      <section 
        className="py-20 px-4 text-white text-center"
        style={{ 
          background: 'linear-gradient(135deg, #0F172A 0%, #1E3A8A 60%, #1D4ED8 100%)'
        }}
      >
        <div className="max-w-5xl mx-auto">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">Credibility Index</h1>
          {/* Gold Underline */}
          <div 
            className="mx-auto mb-4"
            style={{ width: '60px', height: '3px', backgroundColor: '#F59E0B' }}
          ></div>
          <p className="text-[#93C5FD] text-lg max-w-3xl mx-auto">
            CreditDataWatch's Credibility Index is India's first GST-anchored business credit scoring system.
            It measures the payment reliability and financial trustworthiness of businesses based on verified,
            member-submitted data — giving you a real-time view of who to trust in the market.
          </p>
        </div>
      </section>

      {/* Feature Cards */}
      <section className="py-16 px-4 bg-[#F0F4FF]">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-[#0F172A] mb-2">How It Works</h2>
            <div 
              className="mx-auto"
              style={{ width: '60px', height: '3px', backgroundColor: '#F59E0B' }}
            ></div>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              { icon: '⭐', title: 'Global Rating Dashboard', desc: 'Every verified defaulter is listed on the Global Rating Dashboard, immediately impacting their credit score and decreasing their market credibility.', color: '#1E3A8A' },
              { icon: '📉', title: 'Credit Score Impact', desc: 'When a business is reported and verified as a defaulter, their credibility rating drops across the Indian market — motivating prompt settlement.', color: '#3B82F6' },
              { icon: '✅', title: 'Restoration on Settlement', desc: 'Once dues are cleared and the case marked Settled/Closed, the business can begin restoring its credit standing on the platform.', color: '#16A34A' },
              { icon: '🔐', title: 'GST-Verified Data Only', desc: 'Only GST-registered members can submit reports, ensuring the Credibility Index reflects genuine, verified business behaviour.', color: '#0F172A' },
              { icon: '🌍', title: 'National Visibility', desc: 'A business listed as a defaulter faces national exposure — visible to all CreditDataWatch members across India.', color: '#F59E0B' },
              { icon: '📊', title: 'Risk Benchmarking', desc: 'Compare your credit health against industry standards and identify where your credit cycle may need strengthening.', color: '#7C3AED' },
            ].map((item, index) => (
              <div 
                key={item.title} 
                className="bg-white rounded-[14px] p-6 shadow-md transition-all duration-200 ease-out hover:-translate-y-1"
                style={{ borderLeft: `4px solid ${item.color}` }}
              >
                <div 
                  className="w-12 h-12 rounded-full flex items-center justify-center text-2xl mb-4"
                  style={{ backgroundColor: `${item.color}15` }}
                >
                  {item.icon}
                </div>
                <h4 className="font-bold text-[#0F172A] mb-2 text-base">{item.title}</h4>
                <p className="text-[#475569] text-sm leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Main Content */}
      <section className="py-16 px-4">
        <div className="container-custom max-w-5xl mx-auto space-y-8">
          <CredibilityFilterBar
            title="Business Credibility Index"
            iconTitle="Credibility Index"
            q={q} setQ={setQ}
            risk={risk} setRisk={setRisk}
            sort={sort} setSort={setSort}
          />

          <div className="space-y-10">
            <CredibilityLocalTable
              heading="Direct Trade Reliability (Local CBI)"
              description="Credibility based on your direct business history with these companies."
              fulfillmentLabel="PO Fulfillment"
              emptyMessage="No local business history found."
              viewPathPrefix="/credibility-index"
              filtered={filtered}
              unpaidPercent={r => r.total_pos ? Math.round((r.unpaid / r.total_pos) * 100) : 0}
            />

            <NetworkTrustIntelligence
              globalCredibilityIndex={globalCredibilityIndex}
              q={q}
            />
          </div>
        </div>
      </section>
    </div>
  )
}
