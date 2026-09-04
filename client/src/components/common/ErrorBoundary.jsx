import { Component } from 'react'

/**
 * Catches render-time errors anywhere below it in the tree. Without this,
 * an uncaught error while rendering a page (e.g. after clicking a nav
 * link and landing on a component that reads a field before its data has
 * loaded) unmounts the whole app and leaves a blank white page — the
 * error is usually sitting in the browser console the whole time, but
 * there's nothing on screen to explain it or offer a way back.
 *
 * This does not fix the underlying bug in whichever page throws; it only
 * stops that bug from taking down the entire page. If this starts
 * showing up, check the browser console for the actual stack trace —
 * that's what points at the real fix.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('Unhandled error while rendering:', error, info?.componentStack)
  }

  handleReload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
          <div className="max-w-md w-full text-center">
            <div className="text-5xl mb-4">⚠️</div>
            <h1 className="text-xl font-bold text-gray-900 mb-2">Something went wrong</h1>
            <p className="text-gray-500 mb-6">
              This page hit an unexpected error. Reloading usually fixes it — if it keeps
              happening on the same page, please let us know what you were doing.
            </p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={this.handleReload}
                className="px-6 py-2.5 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 transition-colors"
              >
                Reload Page
              </button>
              <a
                href="/"
                className="px-6 py-2.5 rounded-lg border border-gray-300 text-gray-700 font-medium hover:bg-gray-50 transition-colors"
              >
                Go Home
              </a>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
