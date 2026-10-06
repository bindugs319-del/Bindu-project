import BusinessRequestModal from '../BusinessRequestModal'
import SupportRequestModal from '../SupportRequestModal'

// The Business Safety Check + Support Request modal pair shared by
// Dashboard.jsx and InvoiceDashboard.jsx, which previously had identical
// copies of this markup.
export default function DashboardRequestModals({
  showBizRequest, setShowBizRequest,
  showSupportRequest, setShowSupportRequest,
}) {
  return (
    <>
      {showBizRequest && (
        <BusinessRequestModal
          onClose={() => setShowBizRequest(false)}
          onSuccess={() => {
            setShowBizRequest(false)
          }}
        />
      )}
      {showSupportRequest && (
        <SupportRequestModal
          onClose={() => setShowSupportRequest(false)}
          onSuccess={() => {
            setShowSupportRequest(false)
          }}
        />
      )}
    </>
  )
}
