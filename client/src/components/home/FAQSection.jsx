import FAQAccordion from '../marketing/FAQAccordion'

const faqs = [
  {
    q: 'What Goes Into Your Credit Score?',
    a: 'Think of a credit score as a numerical summary of your payment habits. It is a three-digit number that tells suppliers how reliable you are based on your past transactions. The score is calculated using an intelligent algorithm that evaluates key financial factors for businesses and individuals alike.',
  },
  {
    q: 'Best Practices for Credit Score Enhancement?',
    a: '1. Punctuality: Pay all bills on or before the due date. 2. Resolution: Clear any outstanding dues listed on CreditDataWatch. 3. Trust: Foster strong connections with your creditors. Master these three areas to unlock a higher credit score.',
  },
  {
    q: 'What additional benefits come with a Subscription?',
    a: 'Think of Registration as getting your ID card—it creates your account using your personal details. Subscription is like paying your monthly dues—it ensures you keep receiving the service, content, or premium access you need over time.',
  },
  {
    q: 'Is GST registration a mandatory prerequisite for accessing Credit-Data-Watch services?',
    a: 'Access to Credit-Data-Watch services is restricted to GST-registered entities only. Please ensure your organization possesses a valid GSTIN before proceeding.',
  },
  {
    q: 'What is the procedure for registering on the Credit-Data-Watch platform?',
    a: 'Credit-Data-Watch is an easy-to-use platform available exclusively to users with a valid GST Number. Please watch the Demo for more details.',
  },
]

export default function FAQSection() {
  return (
    <section className="section-padding" style={{ background: 'linear-gradient(180deg, #FFFFFF 0%, #EFF6FF 100%)' }}>
      <div className="container-custom max-w-4xl">
        <div className="text-center mb-8">
          <div className="inline-block w-20 h-1 bg-gradient-to-r from-[#1E3A8A] to-[#3B82F6] rounded-full mb-4" />
          <h2 className="text-3xl md:text-4xl font-heading font-bold mb-3 text-[#0F172A]">Help & Education</h2>
          <p className="text-lg text-[#475569]">Common questions about CreditDataWatch</p>
        </div>
        <FAQAccordion faqs={faqs} defaultOpenIndex={0} cardClassName="bg-white rounded-2xl" />
      </div>
    </section>
  )
}
