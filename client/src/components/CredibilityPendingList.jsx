import { useState, useEffect } from 'react'
import { credibilityIndex } from '../services/api/apiClient'

export default function CredibilityPendingList({ type, title, description, onRefresh }) {
  const [loading, setLoading] = useState(false)
  const [reviews, setReviews] = useState([])
  const [selectedReview, setSelectedReview] = useState(null)
  const [formData, setFormData] = useState({})

  const loadReviews = async () => {
    setLoading(true)
    try {
      let res
      if (type === 'financial') {
        res = await credibilityIndex.getPendingFinancial()
      } else if (type === 'legal') {
        res = await credibilityIndex.getPendingLegal()
      } else if (type === 'operations') {
        res = await credibilityIndex.getPendingOperations()
      } else if (type === 'master-admin') {
        res = await credibilityIndex.getPendingMasterAdmin()
      }
      
      if (res.ok && Array.isArray(res.data)) {
        setReviews(res.data)
      }
    } catch (e) {
      console.error('Failed to load reviews:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (reviewId, approve) => {
    setLoading(true)
    try {
      let payload = { approve, ...formData }
      if (type === 'financial') {
        await credibilityIndex.submitFinancialReview(reviewId, payload)
      } else if (type === 'legal') {
        await credibilityIndex.submitLegalReview(reviewId, payload)
      } else if (type === 'operations') {
        await credibilityIndex.submitOperationsReview(reviewId, payload)
      } else if (type === 'master-admin') {
        await credibilityIndex.submitMasterAdminDecision(reviewId, payload)
      }
      await loadReviews()
      if (onRefresh) onRefresh()
      setSelectedReview(null)
    } catch (e) {
      console.error('Failed to submit review:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadReviews()
  }, [])

  return (
    <div className="card mb-6">
      <h3 className="text-lg font-heading font-bold mb-2">{title}</h3>
      <p className="text-sm text-gray-600 mb-4">{description}</p>

      {loading ? (
        <div className="text-center py-4">Loading...</div>
      ) : reviews.length === 0 ? (
        <div className="text-center text-gray-500 py-4">No pending reviews.</div>
      ) : (
        <div className="space-y-3">
          {reviews.map(review => (
            <div key={review.id} className="border rounded-lg p-3 hover:border-blue-300">
              <div className="flex justify-between items-start">
                <div>
                  <h4 className="font-semibold">{review.company_name}</h4>
                  {review.company_registration_no && (
                    <p className="text-sm text-gray-600">Reg. No: {review.company_registration_no}</p>
                  )}
                  <p className="text-xs text-gray-500">Submitted: {new Date(review.created_at).toLocaleString()}</p>
                </div>
                <button
                  onClick={() => setSelectedReview(selectedReview?.id === review.id ? null : review)}
                  className="btn-secondary text-sm"
                >
                  {selectedReview?.id === review.id ? 'Close' : 'Review'}
                </button>
              </div>

              {selectedReview?.id === review.id && (
                <div className="mt-4 space-y-4 border-t pt-4">
                  {type === 'financial' && (
                    <div className="space-y-3">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Financial Health Score (1-10)
                        </label>
                        <input
                          type="number"
                          min="1"
                          max="10"
                          value={formData.financial_health_score || ''}
                          onChange={(e) => setFormData({...formData, financial_health_score: parseInt(e.target.value)})}
                          className="input"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Payment History
                        </label>
                        <select
                          value={formData.payment_history || ''}
                          onChange={(e) => setFormData({...formData, payment_history: e.target.value})}
                          className="input"
                        >
                          <option value="">Select</option>
                          <option value="Excellent">Excellent</option>
                          <option value="Good">Good</option>
                          <option value="Average">Average</option>
                          <option value="Poor">Poor</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Financial Risk Level
                        </label>
                        <select
                          value={formData.financial_risk_level || ''}
                          onChange={(e) => setFormData({...formData, financial_risk_level: e.target.value})}
                          className="input"
                        >
                          <option value="">Select</option>
                          <option value="Low">Low</option>
                          <option value="Medium">Medium</option>
                          <option value="High">High</option>
                        </select>
                      </div>
                    </div>
                  )}

                  {type === 'legal' && (
                    <div className="space-y-3">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Legal Status
                        </label>
                        <select
                          value={formData.legal_status || ''}
                          onChange={(e) => setFormData({...formData, legal_status: e.target.value})}
                          className="input"
                        >
                          <option value="">Select</option>
                          <option value="Clean">Clean</option>
                          <option value="Minor Disputes">Minor Disputes</option>
                          <option value="Active Litigation">Active Litigation</option>
                          <option value="Blacklisted">Blacklisted</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Compliance Score (1-10)
                        </label>
                        <input
                          type="number"
                          min="1"
                          max="10"
                          value={formData.compliance_score || ''}
                          onChange={(e) => setFormData({...formData, compliance_score: parseInt(e.target.value)})}
                          className="input"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Number of Court Cases
                        </label>
                        <input
                          type="number"
                          min="0"
                          value={formData.court_cases || ''}
                          onChange={(e) => setFormData({...formData, court_cases: parseInt(e.target.value)})}
                          className="input"
                        />
                      </div>
                    </div>
                  )}

                  {type === 'operations' && (
                    <div className="space-y-3">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Operational Reliability
                        </label>
                        <select
                          value={formData.operational_reliability || ''}
                          onChange={(e) => setFormData({...formData, operational_reliability: e.target.value})}
                          className="input"
                        >
                          <option value="">Select</option>
                          <option value="Excellent">Excellent</option>
                          <option value="Good">Good</option>
                          <option value="Average">Average</option>
                          <option value="Poor">Poor</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Dispute History
                        </label>
                        <select
                          value={formData.dispute_history || ''}
                          onChange={(e) => setFormData({...formData, dispute_history: e.target.value})}
                          className="input"
                        >
                          <option value="">Select</option>
                          <option value="None">None</option>
                          <option value="Minor">Minor</option>
                          <option value="Major">Major</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Partner Trust Score (1-5)
                        </label>
                        <input
                          type="number"
                          step="0.5"
                          min="1"
                          max="5"
                          value={formData.partner_trust_score || ''}
                          onChange={(e) => setFormData({...formData, partner_trust_score: parseFloat(e.target.value)})}
                          className="input"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          AI Credit Risk Verdict
                        </label>
                        <select
                          value={formData.ai_credit_risk_verdict || ''}
                          onChange={(e) => setFormData({...formData, ai_credit_risk_verdict: e.target.value})}
                          className="input"
                        >
                          <option value="">Select</option>
                          <option value="Low Risk">Low Risk</option>
                          <option value="Medium Risk">Medium Risk</option>
                          <option value="High Risk">High Risk</option>
                          <option value="Not Rated">Not Rated</option>
                        </select>
                      </div>
                    </div>
                  )}

                  {type === 'master-admin' && (
                    <div className="space-y-3">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Partner Trust Score (1-5)
                        </label>
                        <input
                          type="number"
                          step="0.5"
                          min="1"
                          max="5"
                          value={formData.partner_trust_score || ''}
                          onChange={(e) => setFormData({...formData, partner_trust_score: parseFloat(e.target.value)})}
                          className="input"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          AI Credit Risk Verdict
                        </label>
                        <select
                          value={formData.ai_credit_risk_verdict || ''}
                          onChange={(e) => setFormData({...formData, ai_credit_risk_verdict: e.target.value})}
                          className="input"
                        >
                          <option value="">Select</option>
                          <option value="Low Risk">Low Risk</option>
                          <option value="Medium Risk">Medium Risk</option>
                          <option value="High Risk">High Risk</option>
                          <option value="Not Rated">Not Rated</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Credibility Status
                        </label>
                        <select
                          value={formData.credibility_status || 'Standard'}
                          onChange={(e) => setFormData({...formData, credibility_status: e.target.value})}
                          className="input"
                        >
                          <option value="Standard">Standard</option>
                          <option value="Credibility Verified">Credibility Verified</option>
                        </select>
                      </div>
                    </div>
                  )}

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                    <textarea
                      value={formData.notes || ''}
                      onChange={(e) => setFormData({...formData, notes: e.target.value})}
                      className="input"
                      rows={3}
                    />
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={() => handleSubmit(review.id, false)}
                      className="btn-secondary bg-red-100 border-red-200 text-red-700"
                      disabled={loading}
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => handleSubmit(review.id, true)}
                      className="btn-primary"
                      disabled={loading}
                    >
                      Approve & Forward
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <button onClick={loadReviews} className="text-sm text-blue-600 hover:text-blue-800 mt-3">
        Refresh
      </button>
    </div>
  )
}
