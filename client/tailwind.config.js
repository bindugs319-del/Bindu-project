/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // ---------------------------------------------------------------
      // Design system tokens (logged-in app). See docs/DESIGN-SYSTEM.md.
      // New UI uses ONLY these: brand / ink / surface / success /
      // warning / danger, the text-* type scale, rounded-control /
      // rounded-card, and shadow-xs / shadow-raised / shadow-overlay.
      // The older keys further below stay for not-yet-migrated pages.
      // ---------------------------------------------------------------
      colors: {
        brand: {
          50: '#F0F4FA',
          100: '#DCE4F2',
          200: '#B9C9E5',
          300: '#8DA5D2',
          400: '#5677B6',
          500: '#2F5299',
          600: '#1E3A8A', // primary
          700: '#182F70',
          800: '#132557',
          900: '#0C1838',
        },
        ink: {
          900: '#0F172A', // headings, key numbers
          700: '#334155', // body text
          600: '#475569', // secondary text
          500: '#64748B', // muted / captions (AA on white)
          400: '#94A3B8', // placeholders, disabled
          300: '#CBD5E1', // strong borders
          200: '#E2E8F0', // borders, dividers
          100: '#F1F5F9', // subtle fills, table header
          50: '#F8FAFC', // hover fills
        },
        surface: {
          page: '#F6F7F9',
          card: '#FFFFFF',
          sunken: '#F1F5F9',
        },
        warning: {
          50: '#FFFBEB',
          100: '#FEF3C7',
          200: '#FDE68A',
          500: '#D97706',
          600: '#B45309',
          700: '#92400E',
        },
        'primary-light': '#3B82F6',
        'bg-main': '#F0F4FF',
        'bg-card': '#FFFFFF',
        'text-primary': '#0F172A',
        'text-secondary': '#475569',
        border: '#E2E8F0',
        primary: {
          50: '#EEF2FF',
          100: '#DBEAFE',
          200: '#BFDBFE',
          300: '#93C5FD',
          400: '#60A5FA',
          500: '#3B82F6',
          600: '#2563EB',
          700: '#1D4ED8',
          800: '#1E40AF',
          900: '#1E3A8A',
        },
        accent: {
          50: '#FFFBEB',
          100: '#FEF3C7',
          200: '#FDE68A',
          300: '#FCD34D',
          400: '#FBBF24',
          500: '#F59E0B',
          600: '#D97706',
          700: '#B45309',
          800: '#92400E',
          900: '#78350F',
        },
        success: {
          50: '#F0FDF4',
          100: '#DCFCE7',
          200: '#BBF7D0',
          300: '#86EFAC',
          400: '#4ADE80',
          500: '#16A34A',
          600: '#15803D',
          700: '#166534',
          800: '#14532D',
          900: '#052E16',
        },
        danger: {
          50: '#FEF2F2',
          100: '#FEE2E2',
          200: '#FECACA',
          300: '#FCA5A5',
          400: '#F87171',
          500: '#DC2626',
          600: '#B91C1C',
          700: '#991B1B',
          800: '#7F1D1D',
          900: '#450A0A',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        heading: ['"Plus Jakarta Sans"', 'sans-serif'],
      },
      spacing: {
        '128': '32rem',
        '144': '36rem',
      },
      // Type scale: [size, { lineHeight, fontWeight? }]
      fontSize: {
        'display': ['1.875rem', { lineHeight: '2.25rem', fontWeight: '600', letterSpacing: '-0.02em' }], // 30 — KPI hero numbers
        'title': ['1.5rem', { lineHeight: '2rem', fontWeight: '600', letterSpacing: '-0.01em' }], // 24 — page title
        'heading': ['1rem', { lineHeight: '1.5rem', fontWeight: '600' }], // 16 — card/section title
        'body': ['0.875rem', { lineHeight: '1.25rem' }], // 14 — default UI text
        'small': ['0.8125rem', { lineHeight: '1.125rem' }], // 13 — table cells, secondary
        'caption': ['0.75rem', { lineHeight: '1rem' }], // 12 — labels, metadata
        'overline': ['0.6875rem', { lineHeight: '1rem', fontWeight: '600', letterSpacing: '0.06em' }], // 11 — eyebrows, table headers
      },
      borderRadius: {
        'control': '0.5rem', // 8px — buttons, inputs, badges
        'card': '0.75rem', // 12px — cards, tables, panels
      },
      boxShadow: {
        'xs': '0 1px 2px rgba(15, 23, 42, 0.05)',
        'raised': '0 1px 3px rgba(15, 23, 42, 0.08), 0 1px 2px rgba(15, 23, 42, 0.04)',
        'overlay': '0 12px 32px rgba(15, 23, 42, 0.14)',
        'card': '0 4px 24px rgba(30, 58, 138, 0.08)',
        'card-hover': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
      },
      backgroundImage: {
        'gradient-primary': 'linear-gradient(to right, #1E3A8A, #3B82F6)',
        'gradient-hero': 'linear-gradient(135deg, #1E3A8A 0%, #3B82F6 50%, #F59E0B 100%)',
      }
    },
  },
  plugins: [],
}
