import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { getPublicAlertMessage } from '../../services/api/apiClient'

// Shown once per browser session (sessionStorage) rather than nagging on
// every click within the same visit — reappears on a fresh visit/session.
const SESSION_KEY = 'scamAlertDismissed'

// Fallback shown only if the public settings fetch fails outright (e.g.
// the backend is briefly unreachable) — keeps the warning visible rather
// than silently disappearing. Master Admin's saved message is what's
// actually shown under normal operation.
const FALLBACK_MESSAGE = "Important Fraud Alert: We have received reports of unauthorized individuals impersonating CreditDataWatch. For your security, please strictly verify the Account Number and Account Holder's Name before processing any payments."

export default function ScamAlert() {
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (sessionStorage.getItem(SESSION_KEY)) return

    let cancelled = false
    getPublicAlertMessage().then((res) => {
      if (cancelled) return
      const fetched = res.ok ? (res.data?.message || '') : FALLBACK_MESSAGE
      // An explicitly empty message (Master Admin cleared it) means the
      // alert should stay hidden entirely, not fall back to default text.
      if (res.ok && fetched === '') {
        setOpen(false)
        return
      }
      setMessage(fetched || FALLBACK_MESSAGE)
      setOpen(true)
    }).catch(() => {
      if (cancelled) return
      setMessage(FALLBACK_MESSAGE)
      setOpen(true)
    })

    return () => { cancelled = true }
  }, [])

  const dismiss = () => {
    sessionStorage.setItem(SESSION_KEY, '1')
    setOpen(false)
  }

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2 }}
            className="bg-white rounded-2xl shadow-2xl max-w-lg w-full border-l-4 border-red-500 overflow-hidden"
          >
            <div className="bg-gradient-to-r from-red-50 to-amber-50 p-6 flex gap-4">
              <div className="mt-1 flex-shrink-0">
                <svg className="w-7 h-7 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div>
                <h3 className="text-lg font-heading font-bold text-red-900 mb-1">Alert</h3>
                <p className="text-red-800 text-sm md:text-base font-medium whitespace-pre-line">
                  {message}
                </p>
              </div>
            </div>
            <div className="p-4 flex justify-end bg-white">
              <button
                onClick={dismiss}
                className="px-5 py-2 rounded-lg bg-red-600 text-white text-sm font-semibold hover:bg-red-700 transition-colors"
              >
                I Understand
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
