/**
 * Reusable "feature card" grid used across the marketing pages
 * (Services, Solutions, etc). Extracted because the exact same card
 * markup/styles were copy-pasted 8 times across those pages with only
 * the icon/title/desc data changing — that duplication is what SonarQube
 * was flagging.
 *
 * Accepts items as either:
 *   - objects: { icon, title, desc }
 *   - 3-tuples: [icon, title, desc]
 * so it's a drop-in replacement for both array shapes already in use.
 */
export default function FeatureCardGrid({ items, columns = 'grid-cols-2', className = '' }) {
  const normalized = items.map((item) =>
    Array.isArray(item)
      ? { icon: item[0], title: item[1], desc: item[2] }
      : item
  );

  return (
    <div className={`grid ${columns} gap-4 mb-8 ${className}`}>
      {normalized.map((item, idx) => (
        <FeatureCard key={item.title ?? idx} {...item} />
      ))}
    </div>
  );
}

function FeatureCard({ icon, title, desc }) {
  return (
    <div
      className="relative overflow-hidden transition-all duration-250 ease-out hover:-translate-y-1"
      style={{
        backgroundColor: '#fff',
        borderRadius: '16px',
        boxShadow: '0 4px 24px rgba(30, 58, 138, 0.08)',
        padding: '24px',
      }}
    >
      <div
        className="flex items-center justify-center mb-3"
        style={{
          width: '48px',
          height: '48px',
          backgroundColor: '#EFF6FF',
          borderRadius: '8px',
        }}
      >
        <span style={{ color: '#3B82F6', fontSize: '24px' }}>{icon}</span>
      </div>
      <h4
        style={{
          fontSize: '1.1rem',
          fontWeight: 700,
          color: '#1E3A8A',
          marginBottom: '4px',
        }}
      >
        {title}
      </h4>
      <p
        style={{
          fontSize: '0.9rem',
          color: '#475569',
          lineHeight: 1.6,
        }}
      >
        {desc}
      </p>
      <div
        className="absolute bottom-0 left-0 h-0.5 bg-[#1E3A8A] transition-all duration-250 ease-out"
        style={{ width: '0' }}
        onMouseOver={(e) => {
          e.currentTarget.style.width = '100%';
        }}
        onMouseOut={(e) => {
          e.currentTarget.style.width = '0';
        }}
      ></div>
    </div>
  );
}
