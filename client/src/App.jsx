import { BrowserRouter, useLocation } from 'react-router-dom'
import AppRoutes from './routes'
import { AuthProvider } from './state/authContext'
import ErrorBoundary from './components/common/ErrorBoundary'

// Keying the boundary by pathname means that if a page throws and gets
// caught, navigating to a *different* route (even by typing a URL or
// going back) mounts a fresh boundary instead of staying stuck showing
// the error screen forever — only a hard reload used to be able to
// recover from a caught render error before this.
function RouteScopedErrorBoundary({ children }) {
  const location = useLocation()
  return <ErrorBoundary key={location.pathname}>{children}</ErrorBoundary>
}

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <RouteScopedErrorBoundary>
          <AppRoutes />
        </RouteScopedErrorBoundary>
      </AuthProvider>
    </BrowserRouter>
  )
}
