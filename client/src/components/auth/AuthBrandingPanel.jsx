/**
 * The left-hand gradient branding panel shown on AuthLanding, Login, and
 * Register — identical markup across all three, only the headline and
 * subtext differ, so they're passed in as props instead of duplicating
 * the whole ~80-line block per page.
 */
import { Link } from 'react-router-dom'

export default function AuthBrandingPanel({ heading, subtext }) {
  return (
      <div 
        className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden"
        style={{
          background: 'linear-gradient(135deg, #0F172A 0%, #1E3A8A 60%, #1D4ED8 100%)'
        }}
      >
        {/* Dot Grid Pattern */}
        <div 
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage: 'radial-gradient(circle, #ffffff 1px, transparent 1px)',
            backgroundSize: '24px 24px'
          }}
        />
        
        {/* Decorative Circle */}
        <div 
          className="absolute bottom-[-150px] right-[-150px] rounded-full"
          style={{
            width: '400px',
            height: '400px',
            backgroundColor: '#0F172A',
            opacity: 0.05
          }}
        />
        
        {/* Top Logo */}
        <div className="relative z-10">
          <Link to="/" className="inline-flex items-center gap-3">
            <div className="h-12 w-12 rounded-xl bg-white text-[#1E3A8A] font-bold text-2xl flex items-center justify-center">CD</div>
            <span className="font-bold text-2xl text-white">CreditDataWatch</span>
          </Link>
        </div>

        {/* Middle Content */}
        <div className="relative z-10 max-w-md">
          <h2 className="text-4xl font-bold text-white mb-4">
            {heading}
          </h2>
          <p className="text-[#93C5FD] text-lg mb-8">
            {subtext}
          </p>
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-6 h-6 rounded-full bg-white flex items-center justify-center">
                <svg className="w-4 h-4 text-[#1E3A8A]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span className="text-white font-medium text-lg">Secure</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-6 h-6 rounded-full bg-white flex items-center justify-center">
                <svg className="w-4 h-4 text-[#1E3A8A]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span className="text-white font-medium text-lg">Trusted</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-6 h-6 rounded-full bg-white flex items-center justify-center">
                <svg className="w-4 h-4 text-[#1E3A8A]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span className="text-white font-medium text-lg">Verified</span>
            </div>
          </div>
        </div>
        
        {/* Bottom Content */}
        <div className="relative z-10">
          <p className="text-[#93C5FD] text-sm">
            © 2024 CreditDataWatch. All rights reserved.
          </p>
        </div>
      </div>
  )
}
