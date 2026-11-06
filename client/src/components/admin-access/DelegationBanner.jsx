import { useEffect, useState } from 'react'
import { clientAccess } from '../../services/api/apiClient'
import { clearDelegation, getDelegation, timeLeft } from '../../utils/delegation'

function exitClientView(reason) {
  clearDelegation()
  window.close() // works when this tab was opened by "Open account"
  setTimeout(() => {
    window.location.replace(`/admin/client-access${reason ? `?ended=${reason}` : ''}`)
  }, 150)
}

/**
 * Persistent banner shown while an admin views a client account (read-only).
 * Re-checks the grant every 30s so revocation/expiry is noticed even when idle;
 * the backend independently rejects every request once the grant ends.
 */
export default function DelegationBanner() {
  const [delegation] = useState(getDelegation)
  const [, tick] = useState(0)

  useEffect(() => {
    if (!delegation) return undefined
    const clock = setInterval(() => tick((n) => n + 1), 30000)
    const check = async () => {
      const res = await clientAccess.session(delegation.grantId)
      if (!res.ok || res.data?.status !== 'ACTIVE') exitClientView('1')
    }
    const poll = setInterval(() => { void check() }, 30000)
    void check()
    return () => {
      clearInterval(clock)
      clearInterval(poll)
    }
  }, [delegation])

  if (!delegation) return null

  return (
    <div
      role="alert"
      className="sticky top-0 z-[100] w-full bg-red-600 text-white shadow-lg"
    >
      <div className="container-custom flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
        <p className="font-semibold">
          👁 Viewing <span className="underline">{delegation.companyName || 'client'}</span> (read-only)
          <span className="font-normal"> · access expires in {timeLeft(delegation.expiresAt)}</span>
        </p>
        <button
          type="button"
          onClick={() => exitClientView('')}
          className="px-3 py-1 rounded-lg bg-white text-red-700 font-bold hover:bg-red-50"
        >
          Exit
        </button>
      </div>
    </div>
  )
}
