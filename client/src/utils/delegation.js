/**
 * Read-only "view another account" modes, scoped to ONE browser tab
 * (sessionStorage), so the viewer's other tabs stay normal:
 *  - kind 'admin':  our admin viewing a client (X-Delegated-Grant: grantId)
 *  - kind 'branch': a head office viewing one of its branches
 *                   (X-Branch-View: branchCompanyId)
 * The backend re-checks permission and blocks writes on every request.
 */
export const DELEGATION_HEADER = 'X-Delegated-Grant'
export const BRANCH_VIEW_HEADER = 'X-Branch-View'
const STORAGE_KEY = 'cdw_delegated_grant'

export function getDelegation() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const value = JSON.parse(raw)
    if (value?.kind === 'branch') return value.branchCompanyId ? value : null
    return value?.grantId ? { kind: 'admin', ...value } : null
  } catch {
    return null
  }
}

export function setDelegation({ kind = 'admin', grantId, branchCompanyId, companyName, expiresAt }) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ kind, grantId, branchCompanyId, companyName, expiresAt }))
  } catch {
    // storage unavailable — delegation simply won't activate
  }
}

/** Where to go when the view ends (exit, revoked, expired). */
export function delegationHomePath(d = getDelegation()) {
  return d?.kind === 'branch' ? '/organization/branches' : '/admin/client-access'
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
  if (!d) return {}
  return d.kind === 'branch' ? { [BRANCH_VIEW_HEADER]: d.branchCompanyId } : { [DELEGATION_HEADER]: d.grantId }
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
