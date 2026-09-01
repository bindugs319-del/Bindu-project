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
    <section className="py-10 bg-white border-y border-primary-100 overflow-hidden">
      <div className="container-custom">
        <div className="flex items-center justify-center gap-8 md:gap-16 flex-wrap">
          {items.map((item) => (
            <div key={item.label} className="text-center">
              <div className="text-4xl md:text-5xl font-heading font-bold bg-gradient-primary bg-clip-text text-transparent mb-1">
                {item.value}
              </div>
              <div className="text-text-secondary text-sm md:text-base font-medium">
                {item.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default TrustTicker
