import { useEffect, useState } from 'react'
import { getPublicBusinessStats } from '../../services/api/apiClient'

const DEFAULT_STATS = [
  { label: 'Highest No. of Defaulters by a Single Customer', value: '668+' },
  { label: 'Total Number of MSMEs Connected', value: '39+ Lakhs' },
  { label: 'Average Percentage of Settlements', value: '59%' },
  { label: 'Total amount reported defaulter', value: '4578+ Crores' },
]

const AnimatedStatValue = ({ value }) => (
  <span
    className="text-lg md:text-xl lg:text-2xl font-heading font-extrabold"
    style={{ color: 'white' }}
  >
    {value}
  </span>
)

export default function StatsSection() {
  const [stats, setStats] = useState(DEFAULT_STATS)

  useEffect(() => {
    let cancelled = false
    getPublicBusinessStats().then((res) => {
      if (cancelled) return
      if (res.ok && Array.isArray(res.data?.items) && res.data.items.length === 4) {
        setStats(res.data.items)
      }
    }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  return (
    <section className="section-padding" style={{ background: 'linear-gradient(180deg, #EFF6FF 0%, #DBEAFE 100%)' }}>
      <div className="container-custom">
        <div
          className="text-center mb-8"
        >
          <div className="inline-block w-24 h-1 bg-gradient-to-r from-[#1E3A8A] to-[#3B82F6] rounded-full mb-4" />
          <h2 className="text-xl sm:text-2xl font-heading font-bold text-[#0F172A] mb-3">
            Trusted by Thousands of Businesses
          </h2>
          <p className="text-[#475569] text-lg">
            Real-time stats showing our platform's impact across India
          </p>
        </div>

        <div className="grid gap-4 md:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat) => (
            <div
              key={stat.label}
              className="card relative overflow-hidden rounded-[14px] max-w-[220px] mx-auto w-full"
              style={{
                background: 'linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%)',
                boxShadow: '0 10px 40px -10px rgba(30, 58, 138, 0.35)',
                transition: 'transform 0.3s ease, box-shadow 0.3s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-8px) scale(1.02)'
                e.currentTarget.style.boxShadow = '0 25px 60px -10px rgba(30, 58, 138, 0.45)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0) scale(1)'
                e.currentTarget.style.boxShadow = '0 10px 40px -10px rgba(30, 58, 138, 0.35)'
              }}
            >
              <div className="absolute top-0 right-0 w-16 h-16 bg-gradient-to-bl from-blue-400/30 to-transparent -mt-8 -mr-8 rounded-full" />
              <div className="relative p-2">
                <AnimatedStatValue value={stat.value} />
                <p className="mt-1 text-xs md:text-sm text-white/90 font-medium leading-snug">{stat.label}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
