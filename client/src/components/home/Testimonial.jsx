

const testimonials = [
  {
    name: 'Customer Corner',
    role: 'Partner',
    quote: 'Outstanding partner for accounts receivable. Their approach is firm yet respectful, and the results speak for themselves. Our cash flow has improved significantly.',
  }
]

export default function Testimonial() {
  return (
    <section className="section-padding" style={{ background: 'linear-gradient(180deg, #EFF6FF 0%, #FFFFFF 100%)' }}>
      <div className="container-custom">
        <div className="text-center mb-8">
          <div className="inline-block w-20 h-1 bg-gradient-to-r from-[#1E3A8A] to-[#3B82F6] rounded-full mb-4" />
          <h2 className="text-3xl md:text-4xl font-heading font-bold text-[#0F172A]">Customer Trust</h2>
          <p className="text-lg text-[#475569]">Signals from early adopters</p>
        </div>
        {/* max-w-xl mx-auto instead of a 2-column grid: with only one
            testimonial today, a 2-column grid left an awkward empty
            column beside it. This centers the single card instead —
            revisit if a second testimonial is added later. */}
        <div className="max-w-xl mx-auto">
          {testimonials.map((item) => (
            <div
              key={item.name}
              className="card bg-white rounded-2xl"
              style={{
                boxShadow: '0 10px 40px -10px rgba(30, 58, 138, 0.15)',
              }}
            >
              <div className="flex items-center gap-3 mb-4">
                <div 
                  className="h-12 w-12 rounded-full font-heading font-bold flex items-center justify-center"
                  style={{
                    background: 'linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%)',
                    color: 'white'
                  }}
                >
                  {item.name.split(' ').map((p) => p[0]).join('').slice(0, 2)}
                </div>
                <div>
                  <p className="font-semibold text-[#0F172A]">{item.name}</p>
                  <p className="text-sm text-[#475569]">{item.role}</p>
                </div>
              </div>
              <p className="text-[#475569] leading-relaxed">“{item.quote}”</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
