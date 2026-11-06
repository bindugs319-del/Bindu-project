import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { clientAccess } from '../../services/api/apiClient'
import { setDelegation } from '../../utils/delegation'

/**
 * Entry point for "Open account": verifies the grant belongs to this admin
 * and is active, switches THIS tab into read-only client view, then reloads
 * into the client's dashboard (so the whole app loads as the client sees it).
 */
export default function ClientView() {
  const { grantId } = useParams()
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    void clientAccess.session(grantId).then((res) => {
      if (!alive) return
      if (!res.ok || res.data?.status !== 'ACTIVE') {
        setError(res.error || 'This access has expired or was revoked.')
        return
      }
      setDelegation({
        grantId,
        companyName: res.data.client?.company_name,
        expiresAt: res.data.expires_at,
      })
      window.location.replace('/dashboard')
    })
    return () => { alive = false }
  }, [grantId])

  return (
    <div className="container-custom py-16">
      <div className="card max-w-lg mx-auto text-center">
        {error ? (
          <>
            <p className="text-red-600 font-semibold">{error}</p>
            <Link to="/admin/client-access" className="btn-primary inline-block mt-4">Back to Client Access</Link>
          </>
        ) : (
          <p className="text-gray-600">Opening client account (read-only)…</p>
        )}
      </div>
    </div>
  )
}
