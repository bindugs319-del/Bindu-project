/**
 * Client-authorized read-only "view access" for admins.
 *
 * The active grant lives in sessionStorage, so it is scoped to the ONE
 * browser tab opened via "Open account" — the admin's other tabs stay normal.
 * apiClient adds the X-Delegated-Grant header from here; the backend checks
 * the grant (owner, expiry, revocation, read-only) on every request.
 */
export const DELEGATION_HEADER = 'X-Delegated-Grant'
const STORAGE_KEY = 'cdw_delegated_grant'

export function getDelegation() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const value = JSON.parse(raw)
    return value?.grantId ? value : null
  } catch {
    return null
  }
}

export function setDelegation({ grantId, companyName, expiresAt }) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ grantId, companyName, expiresAt }))
  } catch {
    // storage unavailable — delegation simply won't activate
  }
}

export function clearDelegation() {
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}

export function isDelegated() {
  return !!getDelegation()
}

/** Headers to spread into raw fetch() calls that bypass apiClient. */
export function delegationHeaders() {
  const d = getDelegation()
  return d ? { [DELEGATION_HEADER]: d.grantId } : {}
}

/** "5h 12m", "2d 3h", "4m" — or "expired". */
export function timeLeft(iso, now = Date.now()) {
  if (!iso) return ''
  const ms = new Date(iso).getTime() - now
  if (!(ms > 0)) return 'expired'
  const mins = Math.floor(ms / 60000)
  const days = Math.floor(mins / 1440)
  const hours = Math.floor((mins % 1440) / 60)
  const m = mins % 60
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${m}m`
  return `${Math.max(m, 1)}m`
}

export function formatWhen(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}
