import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import PropTypes from 'prop-types'
import FeatureCardGrid from '../components/marketing/FeatureCardGrid'
import HeroTileGrid from '../components/home/HeroTileGrid'

function FAQSection({ faqs }) {
  const [open, setOpen] = useState(null)
  return (
    <div className="space-y-3">
      {faqs.map((faq, i) => (
        <div key={faq.q} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <button onClick={() => setOpen(open === faq.q ? null : faq.q)}
            className="w-full text-left px-6 py-4 flex items-center justify-between">
            <span className="font-semibold text-gray-800 text-sm pr-4">{faq.q}</span>
            <span className="text-blue-600 text-xl flex-shrink-0">{open === faq.q ? '−' : '+'}</span>
          </button>
          {open === faq.q && (
            <div className="px-6 pb-4 border-l-4 border-blue-500">
              <p className="text-gray-600 text-sm leading-relaxed whitespace-pre-line">
                {faq.a.includes('support@preflexsol.com') ? (
                  <>
                    {faq.a.split('support@preflexsol.com').map((part, idx) => (
                      idx === 0 ? part : (
                        <>
                          <a key={idx} href="mailto:support@preflexsol.com" className="text-blue-600 underline">support@preflexsol.com</a>
                          {part}
                        </>
                      )
                    ))}
                  </>
                ) : (
                  faq.a
                )}
              </p>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

FAQSection.propTypes = {
  faqs: PropTypes.arrayOf(PropTypes.shape({
    q: PropTypes.string.isRequired,
    a: PropTypes.string.isRequired
  })).isRequired
}

const reportOverdueFaqs = [
  { q: "Q1. Definition of a Defaulting Purchasing Party?", a: "A defaulter is a business that fails to pay its suppliers on time. CreditDataWatch offers a reliable, accessible database of these entities, compiling reports submitted exclusively by our network of GST-registered members." },
  { q: "Q2. Required Documentation for Defaulter Verification?", a: "To substantiate a defaulter claim, members must upload an updated ledger for the defaulting party alongside a valid PO and a valid GST number. Please be aware that CreditDataWatch reserves the right to request further documentation if required for verification." },
  { q: "Q3. We submitted documents but the defaulter hasn't appeared on the list yet?", a: "We submitted the required documents, but the defaulting party has not yet appeared on the list. We uploaded the verification files, but the defaulter is still not showing up on the portal. I provided all the necessary documentation, but the defaulter's name hasn't been added to the records yet. Please contact us at support@preflexsol.com" },
  { q: "Q4. My balance is settled but I'm still receiving collection follow-ups?", a: "We understand that you have already settled your payment! To stop the automatic reminders, please contact the business or CreditDataWatch support team (support@preflexsol.com) with supporting documents. As soon as we receive the request we will update this information on the CreditDataWatch portal, and all follow-up communications will cease immediately." },
  { q: "Q5. Does it cost anything to add a defaulter to the list?", a: "For registered CreditDataWatch members, the process of listing a defaulter is easy." }
]

const creditManagementFaqs = [
  { q: "Q1. What is Business Credit Management?", a: "It is a clear and organized way to track the credit you extend to your buyers. This process covers every step, from agreeing on a deal to making sure you get paid on time." },
  { q: "Q2. How do we help stop late payments?", a: "We provide automated tools that handle your payment reminders and follow-ups. If a buyer still ignores their bill, registered members can report them on our platform. Because being listed as a defaulter hurts a buyer's nationwide credit reputation, they are much more likely to pay you on time. This system acts as a shield for your cash flow." },
  { q: "Q3. What are the main benefits?", a: "Our tools help you avoid bad debt while maintaining healthy relationships with your clients. Key perks include:\n\nAutomatic Tracking: The system monitors deals and sends reminders without manual effort.\nDigital Proof: Get instant electronic confirmation for all your credit agreements.\nProfessional Standard: Handle your payment collections in a formal and respectful way.\nSimple Resolutions: Make it easy for both parties to settle unpaid bills.\nBetter Cash Flow: Keep your incoming money steady and predictable.\nStronger Reputation: Build trust and credibility in the market.\nQualified Legal Support: Secure expert legal representation from our vetted network." },
  { q: "Q4. Do I need documents to report a defaulter?", a: "Yes. The Global Rating Dashboard updates with defaulter information only after the necessary supporting documents have been submitted and reviewed." },
  { q: "Q5. How does this affect my own business credit score?", a: "Using our tools actively proves that you run a reliable company. When you regularly use the platform to track your deals, settle dues quickly, and maintain clean records, you build a very strong and positive credit profile for your own business." }
]

export default function Services() {
  // Clicking a tile navigates to /services#section-id — React Router's
  // client-side navigation doesn't auto-scroll to hash fragments the way
  // a normal page load would, so this does it manually whenever the hash
  // changes (matches the same fix used on the Solutions page).
  const location = useLocation()
  useEffect(() => {
    if (!location.hash) return
    const el = document.querySelector(location.hash)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [location.hash])

  return (
    <div className="min-h-screen bg-gray-50">

      {/* Hero */}
      <section 
        className="py-10 px-4 text-white text-center"
        style={{ 
          background: 'linear-gradient(135deg, #0F172A 0%, #1E3A8A 60%, #1D4ED8 100%)',
        }}
      >
        <div className="max-w-5xl mx-auto">
          <h1 className="text-xl sm:text-2xl font-bold mb-3">Our Services</h1>
          <div 
            className="mx-auto mb-4"
            style={{ 
              width: '48px', 
              height: '3px', 
              backgroundColor: '#F59E0B' 
            }}
          ></div>
          <p className="text-[#93C5FD] text-base max-w-3xl mx-auto">
            Comprehensive credit intelligence, risk management, and debt recovery tools designed for Indian businesses and MSMEs.
          </p>
          <div className="mt-10 text-left">
            <HeroTileGrid
              columns="grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
              tiles={[
                { title: 'Report Overdue Payer', to: '/services/report-overdue' },
                { title: 'Credit Management', to: '/services/credit-management' },
                { title: 'Partners Credit Overdue Report', to: '/services/partners-report' },
                { title: 'Finalization Steps', to: '/services/finalization' },
              ]}
            />
          </div>
        </div>
      </section>

      {/* SECTION 1 — Report Overdue Payer */}
      <section id="report-overdue-payer" className="py-8 px-4 bg-white" style={{ marginBottom: '24px' }}>
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-3xl">⚠️</span>
            <div>
              <h2 style={{ fontSize: '28px', fontWeight: 700, color: '#0F172A' }}>Report Overdue Payer</h2>
              <div style={{ width: '48px', height: '3px', backgroundColor: '#F59E0B', marginTop: '4px' }}></div>
            </div>
          </div>

          <div className="space-y-3">
            {/* Card 1 */}
            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }} className="font-bold mb-3">
                Expose Corporate Defaulters
              </h3>
              <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="leading-relaxed">
                For registered CreditDataWatch members, reporting a business defaulter is quick and easy. When you report a defaulter, you not only open the door to recovering your dues via the CreditDataWatch settlement portal, but you also shield other MSMEs from dealing with chronic non-payers. Because the Credit Information Report and Defaulters List are accessible to all our members.              </p>
            </div>

            {/* Card 2 */}
            <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
              <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }} className="font-bold mb-3">
                Guidelines and Eligibility for Reporting Commercial Credit Defaulters
              </h3>
              <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="leading-relaxed">
              Businesses and MSMEs with a valid GST number and an active Credit Datawatch membership can report credit defaulters. To ensure acceptable accuracy, every report is thoroughly checked and verified by a Credit Datawatch specialist. This meticulous process guarantees that all information and defaulter lists on our portal are genuine and reliable. Furthermore, reporting a defaulter is a seamless and entirely free process for our members — simply fill in the required details under the "Create Invoice" section, and you are ready to go.
              </p>
            </div>

            {/* Card 3 */}
            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }} className="font-bold mb-3">
                Prerequisites and Documentation for Reporting a Defaulting Business
              </h3>
              <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="leading-relaxed">
                To successfully report a business as a credit defaulter, you must submit key documents, including the defaulting party's ledger and a CA-certified statement of the due amount containing a valid UDIN. Once submitted, the CreditDataWatch expert team rigorously verifies the information. Upon successful review, the credibility index will be updated.  
              </p>
            </div>

            {/* Card 4 */}
            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }} className="font-bold mb-3">
                What is the Process for Verifying a Reported Defaulter?
              </h3>
              <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="leading-relaxed mb-4">
                Credit Datawatch is committed to protecting the reputations of genuine businesses. We follow strict, standardized procedures to thoroughly verify every claim before adding any entity to our defaulters list. By taking every reasonable precaution, we ensure that the information on our portal remains reliable.                </p>
              <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="leading-relaxed">
                CreditDataWatch serves as a platform to list defaulters reported by our registered members and to track the payments. If the reporting member and the defaulting party reach a mutual agreement and settle the outstanding amount, the member has the option to remove the defaulter's name from the portal. Please note that the settlement process is facilitated between the members and the defaulting party using CreditDataWatch platform. The decision to remove a name from the defaulters list rests entirely at the discretion of the reporting member.
              </p>
            </div>
          </div>

          <div className="mt-6">
            <h3 style={{ fontSize: '14px', fontWeight: 500 }} className="text-xl font-bold text-gray-800 mb-4">Frequently Asked Questions</h3>
            <FAQSection faqs={reportOverdueFaqs} />
          </div>
        </div>
      </section>

      {/* SECTION 2 — Streamlined Credit Management */}
      <section id="streamlined-credit-management" className="py-8 px-4 bg-gray-50" style={{ marginBottom: '24px' }}>
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-3xl">💳</span>
            <div>
              <h2 style={{ fontSize: '28px', fontWeight: 700, color: '#0F172A' }}>Credit Management</h2>
              <div style={{ width: '48px', height: '3px', backgroundColor: '#F59E0B', marginTop: '4px' }}></div>
            </div>
          </div>

          <div className="space-y-3">
            {/* Intro */}
            <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="text-lg mb-8 max-w-3xl leading-relaxed">
              Safeguard your B2B transactions with our Business Credit Management tool. Because most supplier-buyer deals involve credit, the threat of non-payment is always present. CreditDataWatch helps you drastically reduce the risk of financial or material defaults by digitizing the entire process. From the initial agreement to digital acknowledgments and final tracking, we keep your credit transactions secure, transparent, and highly organized.
            </p>

            {/* Our Operating Mechanism */}
            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }} className="font-bold mb-3">
                Our Operating Mechanism
              </h3>
              <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="leading-relaxed">
                Credit details will be entered manually or via automatic bulk invoice/PO uploads. Credit Data Watch members are given the option to upload supporting attachments. These uploads are approved by the Credit Data Watch support team to appear in the global star ratings. This visibility immediately impacts the defaulter's credit score, warning other businesses and decreasing their overall market credibility.
              </p>
            </div>

            {/* What Our Platform Delivers */}
            <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }} className="text-xl font-bold mb-4">
              What Our Platform Delivers
            </h3>
            <FeatureCardGrid items={[
              { icon: '✅', title: 'Systematized Confirmations', desc: 'Auto-acceptance capabilities streamline agreements between vendors and clients.' },
              { icon: '🔔', title: 'Scheduled Follow-Ups', desc: 'Maintain consistent cash flow with automated payment nudges sent before and after due dates.' },
              { icon: '📊', title: 'Frictionless Reporting', desc: 'Seamlessly flag defaulting businesses once a deadline lapses, supported by documentation.' },
              { icon: '📉', title: 'Credit Impact', desc: 'Deter chronic non-payment by lowering the defaulting party\'s credibility rating.' },
              { icon: '⚖️', title: 'Legal Support', desc: 'Access options for formal legal notices and professional legal assistance through qualified lawyers.' },
            ]} />

            {/* Why Choose Our Credit Management System? */}
            <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }} className="text-xl font-bold mb-4">
              Why Choose Our Credit Management System?
            </h3>
            <FeatureCardGrid columns="md:grid-cols-2" className="!gap-3" items={[
              ['🤖', 'Zero Manual Effort', 'Let automated reminders do the heavy lifting for you.'],
              ['🏢', 'Corporate Standards', 'Upgrade your collection strategy with a highly professional tone.'],
              ['📋', 'All-in-One Dashboard', 'Keep a close eye on every single credit exchange in one convenient place.'],
              ['🔒', 'Frictionless Settlements', 'Resolve pending payments smoothly and easily.'],
              ['⏱️', 'Time & Money Saved', 'Cut down on collection costs and reclaim your working hours.'],
              ['🚀', 'Fearless Expansion', 'Grow your enterprise safely, knowing your credit lines are thoroughly protected.'],
            ]} />
          </div>

          <div className="mt-6">
            <h3 style={{ fontSize: '14px', fontWeight: 500 }} className="text-xl font-bold text-gray-800 mb-4">Frequently Asked Questions</h3>
            <FAQSection faqs={creditManagementFaqs} />
          </div>
        </div>
      </section>

      {/* SECTION 3 — Partners Credit Overdue Report */}
      <section id="partners-credit-overdue-report" className="py-8 px-4 bg-white">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-3xl">🤝</span>
            <div>
              <h2 style={{ fontSize: '28px', fontWeight: 700, color: '#0F172A' }}>Partners Credit Overdue Report</h2>
              <div style={{ width: '48px', height: '3px', backgroundColor: '#F59E0B', marginTop: '4px' }}></div>
            </div>
          </div>

          <div className="space-y-3">
            {/* Intro */}
            <div className="mb-8">
              <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }}>Utilize Collective Credit Intelligence</h3>
              <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="text-lg mb-4 max-w-3xl leading-relaxed">
                Access the Collaborative Overdue Registry to identify high-risk payment defaulters. Missing a name? Email <a href="mailto:support@preflexsol.com" className="text-blue-600 underline">support@preflexsol.com</a> with the vendor's GSTN, and our team will assist. Use this collective data to streamline your due diligence and safeguard your business against credit risks. To maintain the highest standards, our dedicated specialists manually review and validate every report. This ensures you receive only the most trustworthy insights into payment habits, historical disputes, and resolution trends throughout the country.
              </p>
            </div>

            {/* Key Features */}
            <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }} className="text-xl font-bold mb-4">
              Key Features
            </h3>
            <FeatureCardGrid items={[
              { icon: '🔐', title: 'Verified Network Data', desc: 'Review authenticated default records from a wide range of partner businesses.' },
              { icon: '🏭', title: 'Cross-Sector Analysis', desc: 'Compare credit backgrounds across multiple different industries.' },
              { icon: '🚨', title: 'Risk Detection', desc: 'Identify potential non-payers early with our proactive warning system.' },
              { icon: '📈', title: 'Trend Monitoring', desc: 'Spot specific defaulting patterns within your particular trade sector.' },
            ]} />

            {/* The Step-by-Step Process */}
            <div className="mb-8">
              <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }} className="text-xl font-bold mb-4">
                The Step-by-Step Process
              </h3>
              <div className="bg-white border border-[#e0e6f0] rounded-lg p-4">
                <div className="relative pl-8 space-y-6">
                  <div className="absolute left-3 top-2 bottom-2 w-0.5 bg-[#dce6f5]"></div>
                  {[
                    ['Identify the Business', 'Simply input the GSTIN of the entity you wish to investigate.'],
                    ['Access Validated Data', 'Instantly retrieve a list of confirmed defaults reported.'],
                    ['Evaluate the Risk', 'Examine past payment behaviors, unpaid balances, and how they handled previous settlements.'],
                    ['Execute Confidently', 'Use these professional insights to set safe credit boundaries and protect your revenue.'],
                  ].map(([title, desc], idx) => (
                    <div key={idx} className="relative">
                      <div className="absolute -left-8 w-6 h-6 rounded-full bg-[#185FA5] flex items-center justify-center text-white text-xs font-bold">
                        {idx + 1}
                      </div>
                      <p className="font-bold text-gray-800" style={{ fontSize: '15px' }}>{title}</p>
                      <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="mt-1">{desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Resolution & Finalization Guide */}
            <div id="resolution-finalization-guide" className="bg-white rounded-xl p-4 border border-gray-200">
              <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }} className="text-xl font-bold text-primary-700 mb-4">
                Resolution & Finalization Guide
              </h3>
              
              <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="text-gray-700 text-sm leading-relaxed mb-6">
                Our Case Closure Framework provides a systematic path for documenting, publishing, and resolving default claims on the CreditDataWatch portal. This structured workflow ensures full transparency for both the creditor and the debtor throughout the recovery lifecycle.
              </p>
              
              <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="text-gray-700 text-sm leading-relaxed mb-6">
                By adhering to these protocols, you ensure that your records remain legally sound and that your business stays compliant with industry standards during every phase of the dispute.
              </p>

              {/* 5-Step Workflow */}
              <h4 className="font-bold text-primary-700 mb-3">The 5-Step Workflow:</h4>
              <div className="space-y-3 mb-6">
                {[
                  ['1', 'Evidence Compilation', 'Organize all necessary financial records, including purchase orders, invoices, and proof of fulfillment.'],
                  ['2', 'Audit & Validation', 'The CreditDataWatch internal team reviews your submission to ensure all data is accurate and complete.'],
                  ['3', 'Formal Publication', 'Once the GSTIN and ledger are authenticated, the default is officially listed on the Credit DataWatch Global rating dashboard.'],
                  ['4', 'Monitoring Progress', 'Keep track of recovery milestones and record any payments as they arrive.'],
                  ['5', 'Final De-listing', 'Once the debt is fully satisfied, close the file to refresh the business\'s status on the platform.'],
                ].map(([num, title, desc]) => (
                  <div key={num} className="flex items-start gap-3">
                    <span className="bg-primary-600 text-white w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs flex-shrink-0 mt-0.5">{num}</span>
                    <div>
                      <p className="font-semibold text-primary-700 text-sm">{title}</p>
                      <p className="text-gray-700 text-xs mt-0.5">{desc}</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Essential Documentation Checklist */}
              <h4 className="font-bold text-primary-700 mb-3">Essential Documentation Checklist:</h4>
              <ul className="list-disc list-inside text-gray-700 text-sm space-y-1 mb-6">
                <li>Tax Identifiers: Valid GSTIN for both the claimant and the defaulting entity.</li>
                <li>Financial Statement: A current account ledger highlighting the exact overdue balance.</li>
                <li>Transactional Proof: Copies of all relevant bills and delivery confirmations.</li>
                <li>Interaction History: A log of previous collection attempts.</li>
                <li>Supplementary Evidence: Any additional files that support your claim.</li>
              </ul>

              {/* Critical Guidelines */}
              <h4 className="font-bold text-primary-700 mb-3">Critical Guidelines:</h4>
              <ul className="list-disc list-inside text-gray-700 text-sm space-y-1 mb-6">
                <li>Timeline: Verification usually takes 1 to 2 business days following a complete submission.</li>
                <li>File Standards: All uploads must be clearly readable and submitted in PDF format.</li>
                <li>GSTIN Requirement: To safeguard against fraudulent activity, any registration without a valid GSTIN will not be accepted.</li>
                <li>Update Window: Creditors are required to log a settlement within 2 to 3 days of receiving funds.</li>
                <li>Member Accountability: Neglecting to update a settled status may lead to administrative disputes or support tickets initiated by the other party.</li>
              </ul>

              {/* Post-Settlement Protocol */}
              <h4 className="font-bold text-primary-700 mb-3">Post-Settlement Protocol:</h4>
              <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="text-gray-700 text-sm leading-relaxed mb-4">
                When a payment is successfully received, the reporting member must mark the case as resolved/Closed. Updating the status is vital because:
              </p>
              <ul className="list-disc list-inside text-gray-700 text-sm space-y-1 mb-6">
                <li>Halts Collections: It immediately terminates all automated recovery alerts sent to the debtor.</li>
                <li>Reputation Recovery: It allows the business to begin restoring its credit standing.</li>
                <li>Data Integrity: It ensures Credit DataWatch database reflects real-time accuracy.</li>
                <li>Professionalism: It restores the business relationship between both parties.</li>
              </ul>

              <div className="bg-gray-100 rounded-lg p-3">
                <p className="font-semibold text-primary-700 text-sm mb-2">How to Finish:</p>
                <p className="text-gray-700 text-xs">Go to User Dashboard → Search Invoice No → Mark as "Closed"</p>
              </div>
            </div>
          </div>
        </div>
      </section>

    </div>
  )
}
