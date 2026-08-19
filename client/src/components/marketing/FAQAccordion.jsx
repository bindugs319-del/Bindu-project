import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

/**
 * Expand/collapse FAQ list used on ReportOverdue, BusinessCredit,
 * CreditManagement, and BusinessDebt — identical markup and behavior in
 * all 4 pages (only minor inline-style differences), so extracted here.
 * `openFaq` is local/self-contained state — no page used it for anything
 * outside this accordion.
 */
export default function FAQAccordion({ faqs, defaultOpenIndex = -1 }) {
  const [openFaq, setOpenFaq] = useState(defaultOpenIndex)

  return (
    <div className="space-y-3">
      {faqs.map((item, idx) => (
        <button
          key={item.q}
          type="button"
          className="card cursor-pointer w-full text-left"
          onClick={() => setOpenFaq(openFaq === idx ? -1 : idx)}
        >
          <div className="flex items-start justify-between gap-4">
            <p style={{ fontSize: '14px', fontWeight: 500 }} className="font-semibold text-gray-900">{item.q}</p>
            <svg
              className={`h-5 w-5 text-primary-600 transition-transform flex-shrink-0 ${openFaq === idx ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
          <AnimatePresence initial={false}>
            {openFaq === idx && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.25 }}
                className="overflow-hidden whitespace-pre-line"
              >
                <p style={{ fontSize: '14px', color: '#555' }} className="text-gray-700 mt-3 leading-relaxed">{item.a}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </button>
      ))}
    </div>
  )
}
