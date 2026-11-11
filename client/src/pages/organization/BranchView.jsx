import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { organization } from '../../services/api/apiClient'
import { setDelegation } from '../../utils/delegation'

/**
 * Entry point for "Open branch": checks this head office may view the branch,
 * switches THIS tab into read-only branch view, then reloads into the
 * branch's dashboard (so the app loads exactly as the branch sees it).
 */
export default function BranchView() {
  const { companyId } = useParams()
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    void organization.branchSession(companyId).then((res) => {
      if (!alive) return
      if (!res.ok || res.data?.status !== 'ACTIVE') {
        setError(res.error || 'You can’t view this branch.')
        return
      }
      setDelegation({
        kind: 'branch',
        branchCompanyId: companyId,
        companyName: `${res.data.branch_name} · ${res.data.company_name || ''}`.replace(/ · $/, ''),
      })
      window.location.replace('/dashboard')
    })
    return () => { alive = false }
  }, [companyId])

  return (
    <div className="container-custom py-16">
      <div className="card max-w-lg mx-auto text-center">
        {error ? (
          <>
            <p className="text-red-600 font-semibold">{error}</p>
            <Link to="/organization/branches" className="btn-primary inline-block mt-4">Back to Branches</Link>
          </>
        ) : (
          <p className="text-gray-600">Opening branch account (read-only)…</p>
        )}
      </div>
    </div>
  )
}
