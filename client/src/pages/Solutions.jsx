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
              <p className="text-gray-600 text-sm leading-relaxed whitespace-pre-line">{faq.a}</p>
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

const b2bFaqs = [
  { q: "Q1. What solutions does CreditDataWatch provide for B2B companies?", a: "Our B2B suite includes a variety of tools designed to safeguard your trade credit. These include comprehensive business credit profiles, automated payment alerts, financial tracking, defaulter registries, and debt resolution services. We also provide risk benchmarking to help you compare your credit health against industry standards. Together, these services make managing business relationships much more efficient." },
  { q: "Q2. How do automated payment alerts improve B2B operations?", a: "Automated alerts take the manual work out of chasing payments. The system sends scheduled notifications via email to remind your clients about upcoming or overdue bills. By staying on top of these deadlines automatically, you can reduce late payments and ensure your business maintains a healthy, steady cash flow." },
  { q: "Q3. Is it possible to report a business for non-payment?", a: "Yes. If a business entity or MSME fails to honor its payment commitments, registered members can issue legal notices and request assistance through CreditDataWatch's Legal Support feature. The defaulting MSME will be listed on CreditDataWatch's Global Rating Dashboard, ensuring visibility across the network. This shared intelligence helps other businesses identify and avoid high-risk partners. Public listing also motivates debtors to settle dues promptly, fostering accountability and encouraging fair business practices." },
  { q: "Q4. Why should I check a Business Credit Report before a partnership?", a: "A Business Credit Report acts as a financial background check. It details a company's past payment habits, current debt levels, and overall financial reliability. By reviewing this report before signing a contract, you can accurately judge the risk of working with a new buyer or supplier, helping you build partnerships based on facts rather than guesswork." },
  { q: "Q5. How does the payment settlement process work?", a: "Render as vertical timeline:\nStep 1 — Reporting: The unpaid debt is logged on the platform.\nStep 2 — Notification: We initiate communication with the buyer to inform them of the report.\nStep 3 — Resolution: Both parties can use our tools to track and negotiate terms.\nStep 4 — Completion: Once the payment is received, the creditor marks the case as \"Settled.\"\nStep 5 — Status Update: The listing is updated or removed based on the agreement, helping the buyer restore their credit standing." }
]

const msmeFaqs = [
  { q: "Q1. What information is found in a CreditDataWatch MSME Credit Report?", a: "Our reports provide a deep dive into a business's financial reliability. They include detailed repayment patterns, current debt levels, and overall credit health scores. By analyzing these risk metrics and industry trends, your business can gain the clarity needed to make safe and smart financial choices." },
  { q: "Q2. What is the best way to manage a payment default from an MSME?", a: "We offer a proactive system for handling non-payments. Through our platform, registered members can track defaulting entities, receive real-time alerts on risky behaviors, and implement proven credit risk strategies. This allows you to address payment issues early and protect your company's revenue." },
  { q: "Q3. Why should an MSME focus on building a high credit rating?", a: "A solid credit rating acts as a \"financial resume\" for your business. It significantly boosts your market credibility, making it easier to secure large contracts and high-value partnerships. Additionally, a strong rating is often a prerequisite for accessing government subsidies, lower interest rates, and priority status in public procurement." },
  { q: "Q4. How does CreditDataWatch help MSMEs grow?", a: "We empower small businesses by providing them with the tools to compete on a larger scale. Our members benefit from expert credit assessments, automated registration help, and data-driven insights. These services help your business stand out in professional networks and build long-term trust with investors and lenders." }
]

const businessCreditFaqs = [
  { q: "Q1. What exactly is the CreditDataWatch Business Credit Bureau?", a: "CreditDataWatch is a platform specifically designed to offer end-to-end credit intelligence and oversight for the B2B sector. Our system allows vendors and purchasers to digitize their deals, secure formal acknowledgments, and flag non-paying entities. By centralizing this data, we foster a culture of honesty and reliability in commercial trade." },
  { q: "Q2. What is the process for reporting a non-paying business?", a: "To list a defaulter, simply create an account on the CreditDataWatch portal using your valid GSTIN. After logging in, you can submit the details of the defaulting party, including the specific transaction records and their history of missed payments. Once authenticated, the entity is added to our national database, serving as a warning to the community and helping you recover your funds." },
  { q: "Q3. How does the Automated Payment Alerts system work?", a: "This tool removes the stress of manual collections by scheduling automatic nudges for your clients. The platform dispatches reminders via email, ensuring your invoices stay top-of-mind. The system is designed to track engagement and can increase the frequency or tone of the alerts if a payment remains outstanding, significantly boosting your chances of getting paid on time." },
  { q: "Q4. In what ways can CreditDataWatch help my company grow?", a: "Integrating CreditDataWatch into your daily operations offers several strategic advantages: risk assessment (review financial track records before signing contracts), accountability (officially log and monitor non-payment cases), efficiency (automate your entire collection workflow), financial health (keep cash flow steady and predictable), and market standing (build a reputation as a credit-disciplined business)." }
]

const businessDebtFaqs = [
  { q: "Q1. How does CreditDataWatch help businesses manage debt?", a: "CreditDataWatch provides a unified platform that enables companies to handle debt challenges more effectively. With features such as defaulter reporting, payment history tracking, and structured settlement tools, businesses can take proactive steps to recover dues and maintain stronger cash flow." },
  { q: "Q2. How can I report a defaulter?", a: "Businesses holding a valid GSTIN can sign up on CreditDataWatch. After registration, they can upload supporting documents like ledgers or auditor-verified statements. Once verified, the defaulter's details are published, alerting other businesses and assisting in recovery." },
  { q: "Q3. What is the process for settling a debt?", a: "Render as vertical timeline:\nStep 1 — Report the Defaulter: Add the non-paying business to the CreditDataWatch system.\nStep 2 — Negotiate Terms: Work with the defaulter to agree on repayment conditions.\nStep 3 — Confirm Settlement: Update the record once dues are cleared.\nStep 4 — Ensure Transparency: The defaulter's past record remains visible, encouraging accountability in future transactions." },
  { q: "Q4. How do automated reminders support debt recovery?", a: "CreditDataWatch's reminder system reduces manual effort by sending automated alerts via email. This consistent follow-up increases the likelihood of timely payments and helps businesses stay on top of collections." },
  { q: "Q5. Are there fees for using CreditDataWatch?", a: "Basic defaulter reporting is free for registered members. Advanced features — such as detailed credit ratings, automated reminders, and premium debt-management tools — are available through subscription plans, offering deeper insights and stronger recovery mechanisms." }
]

export default function Solutions() {
  // Clicking a card (from this page or from the homepage) navigates to
  // /solutions#section-id — React Router's client-side navigation doesn't
  // auto-scroll to hash fragments the way a normal page load would, so
  // this does it manually whenever the hash changes.
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
          <h1 className="text-xl sm:text-2xl font-bold mb-3">Our Solutions</h1>
          <div 
            className="mx-auto mb-4"
            style={{ 
              width: '48px', 
              height: '3px', 
              backgroundColor: '#F59E0B' 
            }}
          ></div>
          <p className="text-[#93C5FD] text-base max-w-3xl mx-auto">
            Empowering Indian businesses with advanced credit intelligence, risk management, and debt recovery tools built for the modern economy.
          </p>
          <div className="mt-10 text-left">
            <HeroTileGrid
              columns="grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
              tiles={[
                { title: 'B2B Solutions', to: '/solutions/b2b' },
                { title: 'MSME Solutions', to: '/solutions/msme' },
                { title: 'Business Credit', to: '/solutions/business-credit' },
                { title: 'Business Debt', to: '/solutions/business-debt' },
              ]}
            />
          </div>
        </div>
      </section>

      {/* SECTION 1 — B2B Solutions */}
      <section id="b2b-solutions" className="py-8 px-4 bg-white" style={{ marginBottom: '24px' }}>
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-3xl">🏢</span>
            <div>
              <h2 style={{ fontSize: '28px', fontWeight: 700, color: '#0F172A' }}>B2B Solutions</h2>
              <div style={{ width: '48px', height: '3px', backgroundColor: '#F59E0B', marginTop: '4px' }}></div>
            </div>
          </div>

          <div className="space-y-3">
            <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }}>
              Empowering Enterprises through Strategic B2B Innovation
            </h3>
            <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="leading-relaxed">
              In the current high-stakes commercial market, the strength and agility of your B2B tools are vital for long-term scalability. CreditDataWatch provides a specialized suite of B2B services — risk mitigation, exhaustive credit evaluation, debt resolution, and a Zero-Default Standard — designed to revolutionize your operational framework.
            </p>

            <FeatureCardGrid columns="grid-cols-2 gap-4" items={[
                { icon: '🛡️', title: 'B2B Risk Mitigation', desc: 'Using sophisticated predictive modeling to pinpoint potential financial threats.' },
                { icon: '🔬', title: 'Exhaustive Evaluation', desc: 'Sector-specific data for a 360-degree view of reliability.' },
                { icon: '💼', title: 'Debt Resolution', desc: 'Expert support navigating the settlement process on your behalf.' },
                { icon: '🎯', title: 'Zero-Default Standard', desc: 'Proactive defense system to eliminate bad debt at source.' },
              ]} />

            <Link
              to="/solutions/b2b"
              className="inline-flex items-center gap-2 text-sm font-semibold text-[#1E3A8A] hover:text-[#1D4ED8] transition-colors"
            >
              Learn more about B2B Solutions
              <span aria-hidden="true">→</span>
            </Link>
          </div>

          <div className="mt-6">
            <h3 style={{ fontSize: '14px', fontWeight: 500 }} className="text-xl font-bold text-gray-800 mb-4">Frequently Asked Questions</h3>
            <FAQSection faqs={b2bFaqs} />
          </div>
        </div>
      </section>

      {/* SECTION 2 — MSME Solutions */}
      <section id="msme-solutions" className="py-8 px-4 bg-gray-50" style={{ marginBottom: '24px' }}>
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-3xl">🏭</span>
            <div>
              <h2 style={{ fontSize: '28px', fontWeight: 700, color: '#0F172A' }}>MSME Solutions</h2>
              <div style={{ width: '48px', height: '3px', backgroundColor: '#F59E0B', marginTop: '4px' }}></div>
            </div>
          </div>

          <div className="space-y-3">
            <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }}>
              Driving National Growth: The Power of Indian MSMEs
            </h3>
            <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="leading-relaxed">
              Micro, Small, and Medium Enterprises (MSMEs) generate roughly 29% of India's GDP. CreditDataWatch simplifies MSME registration, credit rating, and enrollment — cutting through paperwork with guided onboarding, live validation, and real-time tracking.
            </p>

            <FeatureCardGrid columns="grid-cols-2 gap-4" items={[
                { icon: '🧭', title: 'Guided Onboarding', desc: 'Step-by-step assistance to ensure every detail is captured accurately.' },
                { icon: '✅', title: 'Live Validation', desc: 'Instant error-checking to prevent delays or application rejections.' },
                { icon: '📡', title: 'Live Tracking', desc: 'Real-time alerts and progress updates, providing complete visibility into application status.' },
                { icon: '🌍', title: 'Establish Market Trust', desc: 'A verified, positive credit profile makes your business more attractive to investors.' },
              ]} />

            <Link
              to="/solutions/msme"
              className="inline-flex items-center gap-2 text-sm font-semibold text-[#1E3A8A] hover:text-[#1D4ED8] transition-colors"
            >
              Learn more about MSME Solutions
              <span aria-hidden="true">→</span>
            </Link>
          </div>

          <div className="mt-6">
            <h3 style={{ fontSize: '14px', fontWeight: 500 }} className="text-xl font-bold text-gray-800 mb-4">Frequently Asked Questions</h3>
            <FAQSection faqs={msmeFaqs} />
          </div>
        </div>
      </section>

      {/* SECTION 3 — Business Credit */}
      <section id="business-credit" className="py-8 px-4 bg-white" style={{ marginBottom: '24px' }}>
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-3xl">📊</span>
            <div>
              <h2 style={{ fontSize: '28px', fontWeight: 700, color: '#0F172A' }}>Business Credit</h2>
              <div style={{ width: '48px', height: '3px', backgroundColor: '#F59E0B', marginTop: '4px' }}></div>
            </div>
          </div>

          <div className="space-y-3">
            <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }}>
              Advanced Credit Intelligence with Automated Recovery Tools
            </h3>
            <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="leading-relaxed">
              In the fast-paced world of modern commerce, maintaining financial stability requires a combination of accurate data and proactive collection strategies. CreditDataWatch provides smart reporting, risk evaluation, and automated follow-up systems designed to secure your revenue and eliminate the risk of bad debt.
            </p>

            <Link
              to="/solutions/business-credit"
              className="inline-flex items-center gap-2 text-sm font-semibold text-[#1E3A8A] hover:text-[#1D4ED8] transition-colors"
            >
              Learn more about Business Credit
              <span aria-hidden="true">→</span>
            </Link>
          </div>

          <div className="mt-6">
            <h3 style={{ fontSize: '14px', fontWeight: 500 }} className="text-xl font-bold text-gray-800 mb-4">Frequently Asked Questions</h3>
            <FAQSection faqs={businessCreditFaqs} />
          </div>
        </div>
      </section>

      {/* SECTION 4 — Business Debt */}
      <section id="business-debt" className="py-8 px-4 bg-gray-50">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-3xl">⚖️</span>
            <div>
              <h2 style={{ fontSize: '28px', fontWeight: 700, color: '#0F172A' }}>Business Debt</h2>
              <div style={{ width: '48px', height: '3px', backgroundColor: '#F59E0B', marginTop: '4px' }}></div>
            </div>
          </div>

          <div className="space-y-3">
            <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#1a3c6e' }}>
              Managing Business Debts with CreditDataWatch
            </h3>
            <p style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }} className="leading-relaxed">
              Armed with holistic business credit reporting, small businesses gain insight into the creditworthiness of prospective partners, customers, or suppliers — helping minimize the risk of bad debt through defaulter reporting, payment history tracking, and structured settlement tools.
            </p>

            <Link
              to="/solutions/business-debt"
              className="inline-flex items-center gap-2 text-sm font-semibold text-[#1E3A8A] hover:text-[#1D4ED8] transition-colors"
            >
              Learn more about Business Debt
              <span aria-hidden="true">→</span>
            </Link>
          </div>

          <div className="mt-6">
            <h3 style={{ fontSize: '14px', fontWeight: 500 }} className="text-xl font-bold text-gray-800 mb-4">Frequently Asked Questions</h3>
            <FAQSection faqs={businessDebtFaqs} />
          </div>
        </div>
      </section>

    </div>
  )
}
