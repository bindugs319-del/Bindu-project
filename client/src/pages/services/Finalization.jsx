import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import PageHero from '../../components/shared/PageHero'

export default function Finalization() {
  const steps = [
    {
      title: 'Document Collection',
      description: 'Gather all relevant invoices, POs, delivery receipts, and communication records',
    },
    {
      title: 'Verification & Review',
      description: 'CreditDataWatch team verifies all documents and checks for completeness',
    },
    {
      title: 'Defaulter Reporting',
      description: 'Case is published on the platform after CA certificate and ledger verification',
    },
    {
      title: 'Settlement Tracking',
      description: 'Monitor payment progress and update status as settlement occurs',
    },
    {
      title: 'Case Closure',
      description: 'Close the case once payment is received and update defaulter status',
    },
  ]

  const requirements = [
    'Valid GSTIN of both parties',
    'Updated ledger showing outstanding amount',
    'Chartered Accountant certificate with UDIN number',
    'Invoice copies and delivery proofs',
    'Communication trail (emails, WhatsApp, letters)',
    'Any other supporting documents',
  ]

  return (
    <div className="min-h-screen bg-gray-50">

      <PageHero
        icon="✅"
        title="Finalization Steps"
        subtitle="Complete guide to finalizing defaulter cases on CreditDataWatch."
        exploreLabel="Explore Other Services"
        tiles={[
          { title: 'Report Overdue Payer', to: '/services/report-overdue' },
          { title: 'Credit Management', to: '/services/credit-management' },
          { title: 'Partners Credit Overdue Report', to: '/services/partners-report' },
        ]}
      />

      <section className="section-padding">
      <div className="container-custom max-w-5xl">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">

          {/* Introduction */}
          <div className="card space-y-4">
            <h2 className="text-2xl font-heading font-bold text-primary-700">Settlement & Case Closure Process</h2>
            <p className="text-gray-700 leading-relaxed">
              Finalization Steps guide you through the complete process of documenting, reporting, tracking, and closing defaulter cases on the CreditDataWatch platform. Our structured approach ensures that all parties are informed and the process remains transparent.
            </p>
            <p className="text-gray-700 leading-relaxed">
              Whether you're filing a new case or settling an existing one, following these steps will help you maintain proper documentation and legal compliance throughout the process.
            </p>
          </div>

          {/* Step-by-Step Process */}
          <div className="space-y-6">
            <h2 className="text-2xl font-heading font-bold text-center">Step-by-Step Process</h2>
            {steps.map((step, idx) => (
              <div key={step.title} className="card border-l-4 border-primary-600">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary-600 text-white flex items-center justify-center font-heading font-bold">
                    {idx + 1}
                  </div>
                  <div className="flex-1">
                    <h3 className="text-xl font-heading font-semibold text-gray-900 mb-2">{step.title}</h3>
                    <p className="text-gray-700">{step.description}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Document Requirements */}
          <div className="card space-y-4">
            <h2 className="text-2xl font-heading font-bold text-primary-700">Required Documents Checklist</h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              To ensure smooth processing of your defaulter case, please prepare the following documents:
            </p>
            <div className="space-y-2">
              {requirements.map((req) => (
                <div key={req} className="flex items-start gap-3">
                  <span className="mt-1 text-green-600">✓</span>
                  <p className="text-gray-700">{req}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Important Notes */}
          <div className="card bg-amber-50 border-amber-50">
            <h3 className="text-lg font-heading font-bold text-amber-900 mb-3">Important Notes</h3>
            <ul className="space-y-2 text-amber-800">
              <li className="flex items-start gap-2">
                <span>•</span>
                <span>Processing typically takes 2-3 working days after document submission</span>
              </li>
              <li className="flex items-start gap-2">
                <span>•</span>
                <span>All documents must be in PDF format and clearly legible</span>
              </li>
              <li className="flex items-start gap-2">
                <span>•</span>
                <span>CA certificate must include a valid UDIN number for verification</span>
              </li>
              <li className="flex items-start gap-2">
                <span>•</span>
                <span>Settlement updates must be made within 7 days of payment receipt</span>
              </li>
              <li className="flex items-start gap-2">
                <span>•</span>
                <span>Failure to update settlement may result in support tickets from defaulter party</span>
              </li>
            </ul>
          </div>

          {/* Post-Settlement */}
          <div className="card space-y-4">
            <h2 className="text-2xl font-heading font-bold text-primary-700">After Settlement</h2>
            <p className="text-gray-700 leading-relaxed">
              Once payment is received, the reporting party must update the case status on the CreditDataWatch platform. This is crucial as:
            </p>
            <ul className="space-y-2 text-gray-700 ml-6 list-disc">
              <li>It stops automated follow-up reminders to the defaulter</li>
              <li>It updates the defaulter's credit profile positively</li>
              <li>It maintains platform accuracy and trust</li>
              <li>It helps the defaulter restore their business reputation</li>
            </ul>
            <p className="text-gray-700 leading-relaxed mt-4">
              Navigate to Dashboard → Search for Invoice no→ Update Status to "Closed" to complete the finalization process.
            </p>
          </div>

          {/* CTA Section */}
          <div className="card bg-primary-50 border-primary-200 text-center space-y-4">
            <h3 className="text-2xl font-heading font-bold text-primary-900">Need Help with Finalization?</h3>
            <p className="text-gray-700">Our specialists are here to guide you through the process</p>
            <div className="flex justify-center gap-4">
              <Link to="/appointment" className="btn-primary">
                Book Consultation
              </Link>
              <Link to="/contact" className="btn-secondary">
                Contact Support
              </Link>
            </div>
          </div>

        </motion.div>
      </div>
      </section>
    </div>
  )
}
