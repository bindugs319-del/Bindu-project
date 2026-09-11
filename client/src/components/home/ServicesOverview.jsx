import { Link } from 'react-router-dom'

export default function ServicesOverview() {
  return (
    <section className="section-padding bg-white">
      <div className="container-custom">
        <div className="grid lg:grid-cols-2 gap-10 items-start">
          {/* Copy */}
          <div>
            <div className="w-24 h-1 mx-auto bg-gradient-to-r from-[#1E3A8A] to-[#3B82F6] rounded-full mb-4" />
            <h2 className="text-xl sm:text-2xl font-heading font-bold text-[#0F172A] mb-3">
              What CreditDataWatch Does
            </h2>
            <p className="text-[#475569] text-base mb-4 leading-relaxed">
              CreditDataWatch is India's credit intelligence hub for B2B businesses and MSMEs.
              We help you validate trade partners, report overdue payers, manage credit risk,
              and recover outstanding dues — all backed by GST-verified data.
            </p>
            <ul className="space-y-2 mb-6">
              {[
                'Report and verify business defaulters',
                'Check a partner\'s credibility before you extend credit',
                'Track purchase orders, invoices, and settlements in one place',
                'Access legal support for recovery when needed',
              ].map((item) => (
                <li key={item} className="flex items-start gap-2 text-[#334155] text-sm">
                  <span className="text-[#3B82F6] mt-0.5">✓</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <Link
              to="/services"
              className="inline-block px-6 py-3 rounded-[10px] font-bold text-white transition-all duration-200 hover:scale-105"
              style={{ background: 'linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%)' }}
            >
              Explore Our Services
            </Link>
          </div>

          {/* Flow diagram (same one used on About Us) — the source image is a
              tall portrait infographic, so it's capped to a sane width here
              instead of stretching to fill the full grid column. */}
          <div className="flex justify-center lg:justify-end">
            <div
              className="card max-w-[380px] sm:max-w-[430px] w-full"
              style={{ borderTop: '3px solid #1E3A8A', boxShadow: '0 4px 24px rgba(30, 58, 138, 0.15)' }}
            >
              <img
                src="/flow-diagram.png"
                alt="How CreditDataWatch works"
                className="w-full rounded-lg border border-gray-200"
              />
              <p className="text-center text-xs text-[#64748B] mt-3">
                From reporting an overdue payer to settlement — end to end
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
