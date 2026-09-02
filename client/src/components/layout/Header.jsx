import { useState, useEffect, useRef } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '../../state/authContext'
import { api } from '../../services/api/apiClient'
import NotificationBell from '../NotificationBell'

// A nav item that shows a small dropdown of 2 options on click, closing
// when an option is chosen or when clicking anywhere outside it.
function NavDropdown({ label, options }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <motion.button
        type="button"
        whileHover={{ y: -1 }}
        onClick={() => setOpen((prev) => !prev)}
        className="relative flex items-center gap-1 text-sm font-medium text-[#374151] hover:text-[#1E3A8A] transition-all duration-200"
      >
        {label}
        <svg className={`w-3.5 h-3.5 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </motion.button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            className="absolute left-0 top-full mt-2 w-56 bg-white rounded-xl shadow-lg border border-[#E2E8F0] py-2 z-50"
          >
            {options.map((opt) => (
              <NavLink
                key={opt.to}
                to={opt.to}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `block px-4 py-2.5 text-sm font-medium transition-colors ${
                    isActive ? 'text-[#1E3A8A] bg-primary-50' : 'text-[#374151] hover:bg-primary-50/60 hover:text-[#1E3A8A]'
                  }`
                }
              >
                {opt.label}
              </NavLink>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function Header() {
  const [open, setOpen] = useState(false)
  const { user, isAuthenticated } = useAuth()
  const [profile, setProfile] = useState(null)

  const role = String(user?.role || '').toUpperCase()
  const isMasterAdmin = role === 'MASTER_ADMIN'

  const navLinks = [
    { label: 'About', to: '/about' },
    { label: 'Services', to: '/services' },
    { label: 'Solutions', to: '/solutions' },
  ]

  const contactLink = { label: 'Contact', to: '/contact' }

  // Combined dropdown replacing 3 separate top-level links (Offerings,
  // Membership, Wallet), matching the Invoice/PO dropdown pattern —
  // named "Membership Hub" per explicit request.
  const membershipHubOptions = [
    { label: 'Offerings', to: '/offerings' },
    { label: 'Membership', to: '/membership' },
    { label: 'Wallet', to: '/wallet' },
  ]

  const invoiceOptions = [
    { label: 'Invoice Dashboard', to: '/invoice-dashboard' },
    { label: 'Invoice Credibility Index', to: '/inv-credibility-index' },
  ]

  const poOptions = [
    // "PO Dashboard" means the actual PO management page (Open POs, Add
    // PO, import/export) for every role — it used to call
    // getDashboardLink() here, which sent Master Admin to their own
    // Control Center instead, since that's their "home" dashboard. That
    // meant Master Admin had no way to reach the PO list at all (even
    // though RoleRoute already grants them access once there — there
    // was just never a link pointing at it).
    { label: 'PO Dashboard', to: '/dashboard/user' },
    { label: 'PO Credibility Index', to: '/credibility-index' },
    ...(isMasterAdmin ? [{ label: 'Admin Control Center', to: '/dashboard/admin' }] : []),
  ]

  useEffect(() => {
    if (isAuthenticated && user) {
      loadProfile()
    }
  }, [isAuthenticated, user])

  // Refresh profile when window gains focus (user returns from another tab/page)
  useEffect(() => {
    const handleFocus = () => {
      if (isAuthenticated && user) {
        loadProfile()
      }
    }
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [isAuthenticated, user])

  // Listen for custom event to refresh profile (triggered from Account page after upload)
  useEffect(() => {
    const handleProfileUpdate = () => {
      if (isAuthenticated && user) {
        loadProfile()
      }
    }
    window.addEventListener('profileUpdated', handleProfileUpdate)
    return () => window.removeEventListener('profileUpdated', handleProfileUpdate)
  }, [isAuthenticated, user])

  const loadProfile = async () => {
    try {
      const response = await api.get('/account/profile')
      if (response.ok && response.data?.data) {
        setProfile(response.data.data)
      } else {
        // If profile doesn't exist, create an empty profile object
        setProfile(null)
      }
    } catch (err) {
      // Profile might not exist yet, that's okay
      setProfile(null)
    }
  }

  return (
    <header 
      className="sticky top-0 z-[100] bg-white/92 backdrop-blur-[12px] border-b border-[#E2E8F0] shadow-[0_2px_16px_rgba(30,58,138,0.06)]"
    >
      <div className="container-custom h-[72px] flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 sm:gap-3 mr-8">
          <motion.div whileHover={{ scale: 1.05 }} transition={{ type: "spring", stiffness: 400 }}>
            {profile?.company_logo_url ? (
              <img 
                src={profile.company_logo_url} 
                alt="Logo" 
                className="h-8 w-8 sm:h-10 sm:w-10 rounded-xl object-cover shadow-lg"
              />
            ) : (
              <div className="h-8 w-8 sm:h-10 sm:w-10 rounded-xl bg-gradient-primary text-white font-heading font-bold text-base sm:text-xl flex items-center justify-center shadow-lg">
                CD
              </div>
            )}
          </motion.div>
          <div className="flex flex-col leading-tight">
            <span className="font-heading font-extrabold text-xl sm:text-2xl text-[#1E3A8A]">CreditDataWatch</span>
            <span className="text-[10px] sm:text-xs text-[#64748B]">India's Credit Intelligence Hub</span>
          </div>
        </Link>

        <nav className="hidden lg:flex items-center gap-6">
          {navLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `relative text-sm font-medium transition-all duration-200 ${
                  isActive ? 'text-[#1E3A8A] font-bold' : 'text-[#374151] hover:text-[#1E3A8A]'
                }`
              }
            >
              {({ isActive }) => (
                <motion.span whileHover={{ y: -1 }}>
                  {link.label}
                  <span className={`absolute bottom-0 left-0 right-0 h-0.5 bg-[#3B82F6] rounded-full transition-all duration-200 ${isActive ? 'w-full' : 'w-0 hover:w-full'}`}></span>
                </motion.span>
              )}
            </NavLink>
          ))}
          <NavDropdown label="Membership Hub" options={membershipHubOptions} />
          <NavLink
            key={contactLink.to}
            to={contactLink.to}
            className={({ isActive }) =>
              `relative text-sm font-medium transition-all duration-200 ${
                isActive ? 'text-[#1E3A8A] font-bold' : 'text-[#374151] hover:text-[#1E3A8A]'
              }`
            }
          >
            {({ isActive }) => (
              <motion.span whileHover={{ y: -1 }}>
                {contactLink.label}
                <span className={`absolute bottom-0 left-0 right-0 h-0.5 bg-[#3B82F6] rounded-full transition-all duration-200 ${isActive ? 'w-full' : 'w-0 hover:w-full'}`}></span>
              </motion.span>
            )}
          </NavLink>
          <NavDropdown label="Invoice" options={invoiceOptions} />
          <NavDropdown label="PO" options={poOptions} />
          {/* Always-visible Login link — separate from the account avatar below,
              so it stays in the nav even after you're logged in. */}
          <NavLink
            to="/auth/login"
            className={({ isActive }) =>
              `relative text-sm font-medium transition-all duration-200 ${
                isActive ? 'text-[#1E3A8A] font-bold' : 'text-[#374151] hover:text-[#1E3A8A]'
              }`
            }
          >
            {({ isActive }) => (
              <motion.span whileHover={{ y: -1 }}>
                Login
                <span className={`absolute bottom-0 left-0 right-0 h-0.5 bg-[#3B82F6] rounded-full transition-all duration-200 ${isActive ? 'w-full' : 'w-0 hover:w-full'}`}></span>
              </motion.span>
            )}
          </NavLink>
          {isAuthenticated ? (
            <div className="flex items-center gap-2 ml-3">
              <NotificationBell />
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                <Link
                  to="/account"
                  className="flex items-center gap-2 px-3 py-2 rounded-xl bg-primary-50 border-2 border-[#DBEAFE] hover:shadow-md transition-all duration-200"
                >
                  <div className="w-8 h-8 rounded-full bg-gradient-primary text-white font-heading font-bold text-xs flex items-center justify-center overflow-hidden shadow-md">
                    {profile?.profile_photo_url ? (
                      <img src={profile.profile_photo_url} alt="Profile" className="w-full h-full object-cover" />
                    ) : user?.company_name ? (
                      user.company_name.charAt(0).toUpperCase()
                    ) : (
                      '👤'
                    )}
                  </div>
                  <span className="text-xs font-semibold text-text-primary truncate max-w-[120px]">
                    {user?.company_name || user?.email || 'User'}
                  </span>
                </Link>
              </motion.div>
            </div>
          ) : (
            <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
              <Link to="/appointment" className="btn-primary text-xs">
                Book Appointment
              </Link>
            </motion.div>
          )}
        </nav>
        
        {/* Tablet nav */}
        <nav className="hidden md:flex lg:hidden items-center gap-4">
          {navLinks.slice(0, 3).map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `relative text-sm font-medium transition-all duration-200 ${
                  isActive ? 'text-[#1E3A8A] font-bold' : 'text-[#374151] hover:text-[#1E3A8A]'
                }`
              }
            >
              {({ isActive }) => (
                <motion.span whileHover={{ y: -1 }}>
                  {link.label}
                  <span className={`absolute bottom-0 left-0 right-0 h-0.5 bg-[#3B82F6] rounded-full transition-all duration-200 ${isActive ? 'w-full' : 'w-0 hover:w-full'}`}></span>
                </motion.span>
              )}
            </NavLink>
          ))}
          {isAuthenticated ? (
            <div className="flex items-center gap-2 ml-2">
              <NavLink
                to="/auth/login"
                className={({ isActive }) =>
                  `text-sm font-medium transition-all duration-200 ${
                    isActive ? 'text-[#1E3A8A] font-bold' : 'text-[#374151] hover:text-[#1E3A8A]'
                  }`
                }
              >
                Login
              </NavLink>
              <NotificationBell />
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                <Link 
                  to="/account" 
                  className="flex items-center gap-2 px-2 py-1.5 rounded-xl bg-primary-50 border-2 border-[#DBEAFE] hover:shadow-md transition-all duration-200"
                >
                  <div className="w-7 h-7 rounded-full bg-gradient-primary text-white font-heading font-bold text-xs flex items-center justify-center overflow-hidden shadow-md">
                    {profile?.profile_photo_url ? (
                      <img src={profile.profile_photo_url} alt="Profile" className="w-full h-full object-cover" />
                    ) : user?.company_name ? (
                      user.company_name.charAt(0).toUpperCase()
                    ) : (
                      '👤'
                    )}
                  </div>
                </Link>
              </motion.div>
            </div>
          ) : (
            <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
              <Link to="/auth/login" className="btn-primary text-xs">
                Login
              </Link>
            </motion.div>
          )}
        </nav>

        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="md:hidden p-2 rounded-xl border border-[#E2E8F0] bg-white text-text-primary shadow-sm transition-all duration-200"
          onClick={() => setOpen((prev) => !prev)}
          aria-label="Toggle menu"
        >
          <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {open ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </motion.button>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0, y: -10 }}
            animate={{ height: 'auto', opacity: 1, y: 0 }}
            exit={{ height: 0, opacity: 0, y: -10 }}
            className="md:hidden bg-white border-b border-[#E2E8F0] shadow-md"
            transition={{ type: "spring", stiffness: 200, damping: 20 }}
          >
            <div className="container-custom py-6 space-y-4">
              {navLinks.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  className={({ isActive }) =>
                    `block text-base font-semibold py-2 ${isActive ? 'text-[#1E3A8A] bg-primary-50 rounded-lg px-3' : 'text-text-secondary hover:text-[#1E3A8A] hover:bg-primary-50/50 rounded-lg px-3'}`
                  }
                  onClick={() => setOpen(false)}
                >
                  {link.label}
                </NavLink>
              ))}

              {/* Membership Hub (Offerings/Membership/Wallet) — same
                  always-expanded sub-group treatment as Invoice/PO below. */}
              <div>
                <div className="px-3 text-xs font-bold uppercase tracking-wide text-[#94A3B8] mb-1">Membership Hub</div>
                {membershipHubOptions.map((opt) => (
                  <NavLink
                    key={opt.to}
                    to={opt.to}
                    className={({ isActive }) =>
                      `block text-base font-semibold py-2 pl-6 ${isActive ? 'text-[#1E3A8A] bg-primary-50 rounded-lg px-3' : 'text-text-secondary hover:text-[#1E3A8A] hover:bg-primary-50/50 rounded-lg px-3'}`
                    }
                    onClick={() => setOpen(false)}
                  >
                    {opt.label}
                  </NavLink>
                ))}
              </div>

              <NavLink
                key={contactLink.to}
                to={contactLink.to}
                className={({ isActive }) =>
                  `block text-base font-semibold py-2 ${isActive ? 'text-[#1E3A8A] bg-primary-50 rounded-lg px-3' : 'text-text-secondary hover:text-[#1E3A8A] hover:bg-primary-50/50 rounded-lg px-3'}`
                }
                onClick={() => setOpen(false)}
              >
                {contactLink.label}
              </NavLink>

              {/* Invoice / PO — shown as always-expanded sub-groups here
                  since the mobile menu is already a scrollable list; a
                  nested toggle would just add an extra tap. */}
              <div>
                <div className="px-3 text-xs font-bold uppercase tracking-wide text-[#94A3B8] mb-1">Invoice</div>
                {invoiceOptions.map((opt) => (
                  <NavLink
                    key={opt.to}
                    to={opt.to}
                    className={({ isActive }) =>
                      `block text-base font-semibold py-2 pl-6 ${isActive ? 'text-[#1E3A8A] bg-primary-50 rounded-lg px-3' : 'text-text-secondary hover:text-[#1E3A8A] hover:bg-primary-50/50 rounded-lg px-3'}`
                    }
                    onClick={() => setOpen(false)}
                  >
                    {opt.label}
                  </NavLink>
                ))}
              </div>

              <div>
                <div className="px-3 text-xs font-bold uppercase tracking-wide text-[#94A3B8] mb-1">PO</div>
                {poOptions.map((opt) => (
                  <NavLink
                    key={opt.to}
                    to={opt.to}
                    className={({ isActive }) =>
                      `block text-base font-semibold py-2 pl-6 ${isActive ? 'text-[#1E3A8A] bg-primary-50 rounded-lg px-3' : 'text-text-secondary hover:text-[#1E3A8A] hover:bg-primary-50/50 rounded-lg px-3'}`
                    }
                    onClick={() => setOpen(false)}
                  >
                    {opt.label}
                  </NavLink>
                ))}
              </div>
              
              {/* Always-visible Login link, same as desktop/tablet */}
              <Link
                to="/auth/login"
                className="block text-base font-semibold text-text-secondary hover:text-[#1E3A8A] py-2 px-3"
                onClick={() => setOpen(false)}
              >
                Login
              </Link>

              {isAuthenticated ? (
                <Link
                  to="/account"
                  className="flex items-center gap-3 px-4 py-3 rounded-xl bg-primary-50 border border-[#DBEAFE]"
                  onClick={() => setOpen(false)}
                >
                  <div className="w-9 h-9 rounded-full bg-gradient-primary text-white font-heading font-bold text-sm flex items-center justify-center overflow-hidden">
                    {profile?.profile_photo_url ? (
                      <img src={profile.profile_photo_url} alt="Profile" className="w-full h-full object-cover" />
                    ) : user?.company_name ? (
                      user.company_name.charAt(0).toUpperCase()
                    ) : (
                      '👤'
                    )}
                  </div>
                  <span className="text-sm font-semibold text-text-primary">
                    {user?.company_name || user?.email || 'User'}
                  </span>
                </Link>
              ) : (
                <Link
                  to="/appointment"
                  className="btn-primary w-full text-center"
                  onClick={() => setOpen(false)}
                >
                  Book Appointment
                </Link>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  )
}
