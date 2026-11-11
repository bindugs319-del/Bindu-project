import { useEffect, useState } from 'react'
import { clientAccess, organization } from '../../services/api/apiClient'
import { clearDelegation, delegationHomePath, getDelegation, timeLeft } from '../../utils/delegation'

function exitView(delegation, reason) {
  const home = delegationHomePath(delegation)
  clearDelegation()
  window.close() // works when this tab was opened by "Open account" / "Open branch"
  setTimeout(() => {
    window.location.replace(`${home}${reason ? `?ended=${reason}` : ''}`)
  }, 150)
}

/**
 * Persistent banner shown while viewing another account read-only:
 * an admin viewing a client, or a head office viewing a branch.
 * Re-checks access every 30s so revocation/removal is noticed even when
 * idle; the backend independently rejects every request once access ends.
 */
export default function DelegationBanner() {
  const [delegation] = useState(getDelegation)
  const [, tick] = useState(0)
  const isBranch = delegation?.kind === 'branch'

  useEffect(() => {
    if (!delegation) return undefined
    const clock = setInterval(() => tick((n) => n + 1), 30000)
    const check = async () => {
      const res = isBranch
        ? await organization.branchSession(delegation.branchCompanyId)
        : await clientAccess.session(delegation.grantId)
      if (!res.ok || res.data?.status !== 'ACTIVE') exitView(delegation, '1')
    }
    const poll = setInterval(() => { void check() }, 30000)
    void check()
    return () => {
      clearInterval(clock)
      clearInterval(poll)
    }
  }, [delegation, isBranch])

  if (!delegation) return null

  return (
    <div role="alert" className="sticky top-0 z-[100] w-full bg-red-600 text-white shadow-lg">
      <div className="container-custom flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
        <p className="font-semibold">
          👁 Viewing {isBranch ? 'branch ' : ''}<span className="underline">{delegation.companyName || (isBranch ? 'branch' : 'client')}</span> (read-only)
          {!isBranch && <span className="font-normal"> · access expires in {timeLeft(delegation.expiresAt)}</span>}
        </p>
        <button
          type="button"
          onClick={() => exitView(delegation, '')}
          className="px-3 py-1 rounded-lg bg-white text-red-700 font-bold hover:bg-red-50"
        >
          Exit
        </button>
      </div>
    </div>
  )
}
