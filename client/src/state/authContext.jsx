/**
 * Authentication Context & Hook
 * 
 * Manages:
 * - Current logged-in user state
 * - User subscription and plan
 * - Feature access control
 * - Authentication status
 */

import { createContext, useContext, useState, useEffect, useRef, useMemo, useCallback } from 'react'
import PropTypes from 'prop-types'
import authService from '../services/authService'

// Create auth context
const AuthContext = createContext(null)

// How often to proactively refresh the access token while the user is
// active, in milliseconds. Kept comfortably under the backend's 30-minute
// ACCESS_TOKEN_EXPIRE_MINUTES so the token never actually expires during
// normal use — previously the app only refreshed *reactively*, after a
// request had already failed with 401, which is what let people get
// dropped to the login page mid-session.
const SILENT_REFRESH_INTERVAL_MS = 10 * 60 * 1000 // 10 minutes

// How long the user can go with zero interaction (no click, key press,
// mouse movement, scroll, or touch) before being treated as "really"
// inactive and logged out. Well above the access-token lifetime on
// purpose: an active user is kept in via the silent refresh above and
// should never hit this; it only fires for a genuinely abandoned tab.
const IDLE_LOGOUT_MS = 15 * 60 * 1000 // 15 minutes

// User-interaction events that count as "still active". Deliberately
// lightweight (no per-event network calls) — these just bump a
// timestamp in a ref, which the idle-check interval below reads.
const ACTIVITY_EVENTS = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart']

/**
 * AuthProvider Component - Wrap your app with this
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(localStorage.getItem('access_token') || localStorage.getItem('token') || null)
  const [subscription, setSubscription] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const lastActivityRef = useRef(Date.now())

  // Load user on mount (if already authenticated)
  const loadUser = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      
      const token = localStorage.getItem('access_token') || localStorage.getItem('token')
      if (!token) {
        setUser(null)
        setLoading(false)
        return null
      }

      // Try to fetch current user (will fail if not authenticated)
      const userResponse = await authService.getCurrentUser()
      if (userResponse.ok && userResponse.data) {
        setUser(userResponse.data)
        setToken(token)
        
        // Also fetch subscription info
        const subResponse = await authService.getSubscription()
        if (subResponse.ok && subResponse.data) {
          setSubscription(subResponse.data)
        }
        return userResponse.data
      } else {
        // Not authenticated
        setUser(null)
        setToken(null)
        setSubscription(null)
        return null
      }
    } catch (err) {
      console.error('Failed to load user:', err)
      setError(err.message)
      setUser(null)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const logout = useCallback(async () => {
    try {
      await authService.logout()
    } catch (err) {
      console.error('Logout error:', err)
    } finally {
      setUser(null)
      setToken(null)
      setSubscription(null)
    }
  }, [])

  useEffect(() => {
    void loadUser()
  }, [loadUser])

  // Reset the idle clock the moment someone actually becomes logged in
  // (fresh login, or an existing session found on page load) — NOT just
  // once at component mount. Without this, lastActivityRef still held
  // whatever time the page first loaded, even if the person took a
  // while to type their credentials in; the first click right after
  // logging in could then compute an idle time already past 15 minutes
  // and log them straight back out — a login-then-instant-logout loop.
  useEffect(() => {
    if (user) {
      lastActivityRef.current = Date.now()
    }
  }, [user])

  // Track user interaction so the idle-logout check below can tell a
  // genuinely abandoned tab apart from someone quietly reading a page.
  // Only bothers wiring up listeners once logged in — no point tracking
  // activity for a signed-out visitor.
  //
  // IMPORTANT: this checks elapsed idle time *before* resetting the
  // clock, not after. If it only reset the clock, then the very act of
  // coming back and moving the mouse or scrolling — right when you'd
  // already been idle past the limit — would silently reset the timer
  // in the same instant the polling check below was supposed to catch
  // it, so the logout would never actually fire. Checking first closes
  // that race: the returning activity event itself is what triggers the
  // logout if you were already over the limit.
  useEffect(() => {
    if (!user) return undefined

    const markActive = () => {
      const now = Date.now()
      const idleFor = now - lastActivityRef.current
      if (idleFor >= IDLE_LOGOUT_MS) {
        void logout()
        return
      }
      lastActivityRef.current = now
    }

    ACTIVITY_EVENTS.forEach((evt) => window.addEventListener(evt, markActive, { passive: true }))
    // Tab visibility changes (switching back to this tab) don't fire
    // mouse/keyboard events on their own, so check then too — otherwise
    // someone who tabs back in and just looks, without touching
    // anything, wouldn't get caught until their next actual interaction.
    document.addEventListener('visibilitychange', markActive)

    return () => {
      ACTIVITY_EVENTS.forEach((evt) => window.removeEventListener(evt, markActive))
      document.removeEventListener('visibilitychange', markActive)
    }
  }, [user, logout])

  // Backstop for the case where the tab stays open, visible, and
  // completely untouched the whole time — no activity event ever fires
  // to trigger the check above, so this polls independently.
  useEffect(() => {
    if (!user) return undefined

    const interval = setInterval(() => {
      const idleFor = Date.now() - lastActivityRef.current
      if (idleFor >= IDLE_LOGOUT_MS) {
        void logout()
      }
    }, 60 * 1000) // check once a minute

    return () => clearInterval(interval)
  }, [user, logout])

  // Proactively renew the access token on a timer instead of waiting for
  // a request to fail first. This is what actually keeps an active user
  // logged in indefinitely — the reactive refresh in apiClient.js is
  // still there as a safety net for the moment right around a refresh
  // boundary, but this is what prevents ever hitting that path during
  // normal use.
  useEffect(() => {
    if (!user) return undefined

    const interval = setInterval(async () => {
      // Skip refreshing a token nobody's going to use — if the tab's
      // been idle longer than the refresh interval itself, the
      // idle-logout check below will end the session on its own next.
      const idleFor = Date.now() - lastActivityRef.current
      if (idleFor > SILENT_REFRESH_INTERVAL_MS) return
      try {
        await authService.refreshToken()
      } catch (err) {
        console.error('Silent token refresh failed:', err)
      }
    }, SILENT_REFRESH_INTERVAL_MS)

    return () => clearInterval(interval)
  }, [user])

  const login = useCallback(async (credentials) => {
    try {
      setLoading(true)
      setError(null)
      
      const response = await authService.login(credentials)
      if (!response.ok) {
        setError(response.error)
        setLoading(false)
        return false
      }
      
      // Reload user data immediately
      const userData = await loadUser()
      return !!userData
    } catch (err) {
      setError(err.message)
      setLoading(false)
      return false
    }
  }, [loadUser])

  const register = useCallback(async (userData) => {
    try {
      setLoading(true)
      setError(null)
      
      const response = await authService.register(userData)
      if (!response.ok) {
        setError(response.error)
        return false
      }
      
      return true
    } catch (err) {
      setError(err.message)
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  const updateProfile = useCallback(async (updates) => {
    try {
      setError(null)
      const response = await authService.updateProfile(updates)
      if (!response.ok) {
        setError(response.error)
        return false
      }
      
      // Update local user state
      if (response.data) {
        setUser(response.data)
      }
      return true
    } catch (err) {
      setError(err.message)
      return false
    }
  }, [])

  /**
   * Check if user can access a specific feature
   * @param {string} feature - Feature name (PO_MANAGEMENT, REPORT_OVERDUE, etc.)
   * @returns {boolean}
   */
  const canAccessFeature = useCallback((feature) => {
    if (!user) return false
    const role = String(user.role || '').toUpperCase()
    if (role === 'MASTER_ADMIN') return true
    // Check user-level bypass flags first
    if (user.subscription_bypass || user.full_access) return true
    // Then check subscription data
    return Boolean(subscription?.is_active)
  }, [user, subscription])

  /**
   * Get remaining days in subscription
   * @returns {number|null}
   */
  const getDaysRemaining = useCallback(() => {
    if (!subscription?.expiry_date) return null
    
    const expiryDate = new Date(subscription.expiry_date)
    const today = new Date()
    const diffTime = expiryDate - today
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
    
    return Math.max(0, diffDays)
  }, [subscription])

  const value = useMemo(() => ({
    // State
    user,
    token,
    subscription,
    isAuthenticated: !!user,
    loading,
    error,
    
    // Actions
    login,
    register,
    logout,
    updateProfile,
    loadUser,
    
    // Helpers
    canAccessFeature,
    getDaysRemaining,
  }), [
    user,
    token,
    subscription,
    loading,
    error,
    login,
    register,
    logout,
    updateProfile,
    loadUser,
    canAccessFeature,
    getDaysRemaining,
  ])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

AuthProvider.propTypes = {
  children: PropTypes.node.isRequired,
}

/**
 * Hook to use auth context
 * @throws {Error} if used outside AuthProvider
 * @returns {object} auth context value
 */
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}

export default AuthContext
