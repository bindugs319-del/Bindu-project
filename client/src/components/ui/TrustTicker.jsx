import { useState, useEffect } from 'react'
import { getPublicTrustTicker } from '../../services/api/apiClient'

const DEFAULT_ITEMS = [
  { label: 'Average Trust Score', value: '98%' },
  { label: 'Verified Companies', value: '12,450' },
  { label: 'Secure Transactions', value: '4,56,780+' },
]

const TrustTicker = () => {
  const [items, setItems] = useState(DEFAULT_ITEMS)

  useEffect(() => {
    let cancelled = false
    getPublicTrustTicker().then((res) => {
      if (cancelled) return
      if (res.ok && Array.isArray(res.data?.items) && res.data.items.length === 3) {
        setItems(res.data.items)
      }
    }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  return (
    <section
      className="py-8 overflow-hidden"
      style={{ background: 'linear-gradient(180deg, #F8FAFC 0%, #EFF6FF 100%)' }}
    >
      <div className="container-custom">
        <div
          className="rounded-[16px] px-6 py-6 md:py-8 flex items-stretch justify-center gap-0 flex-wrap md:flex-nowrap"
          style={{
            background: '#FFFFFF',
            boxShadow: '0 8px 30px -12px rgba(30, 58, 138, 0.18)',
            border: '1px solid #E2E8F0',
          }}
        >
          {items.map((item, idx) => (
            <div key={item.label} className="flex items-center flex-1 min-w-[160px]">
              {idx > 0 && (
                <div className="hidden md:block w-px self-stretch bg-[#E2E8F0] mx-6 lg:mx-10" />
              )}
              <div className="text-center w-full px-4 py-2">
                <div
                  className="text-2xl md:text-3xl lg:text-4xl font-heading font-extrabold mb-1"
                  style={{
                    background: 'linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    backgroundClip: 'text',
                  }}
                >
                  {item.value}
                </div>
                <div className="text-[#64748B] text-xs md:text-sm font-semibold uppercase tracking-wide">
                  {item.label}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default TrustTicker
