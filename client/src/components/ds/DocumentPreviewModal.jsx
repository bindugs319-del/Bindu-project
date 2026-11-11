import { useEffect, useRef, useState } from 'react'
import PropTypes from 'prop-types'
import { X, Download, ExternalLink, Loader2, AlertCircle } from 'lucide-react'
import Button from './Button'

const IMAGE_RE = /\.(png|jpe?g|gif|webp)$/i

/**
 * In-page document preview (PDF or image) in a modal.
 *
 * Give it EITHER `url` (an existing file, e.g. an uploaded document) OR
 * `load` (async () => ({ ok, blob, filename, error }), e.g. a generated
 * PDF fetched with auth). Esc or the X closes it; focus returns to the
 * button that opened it.
 */
export default function DocumentPreviewModal({ open, title, url, load, filename, onClose }) {
  const [state, setState] = useState({ status: 'idle', src: null, name: filename, error: '' })
  const closeRef = useRef(null)
  const openerRef = useRef(null)
  // Keep latest callbacks in refs so callers can pass inline functions
  // without re-triggering the load on every render.
  const loadRef = useRef(load)
  const closeFnRef = useRef(onClose)
  loadRef.current = load
  closeFnRef.current = onClose
  const hasLoader = !!load

  useEffect(() => {
    if (!open) return undefined
    openerRef.current = document.activeElement
    let objectUrl = null
    let alive = true

    if (url) {
      setState({ status: 'ready', src: url, name: filename || url.split('/').pop(), error: '' })
    } else if (hasLoader) {
      setState({ status: 'loading', src: null, name: filename, error: '' })
      void loadRef.current().then((res) => {
        if (!alive) return
        if (res.ok) {
          objectUrl = URL.createObjectURL(res.blob)
          setState({ status: 'ready', src: objectUrl, name: res.filename || filename, error: '' })
        } else {
          setState({ status: 'error', src: null, name: filename, error: res.error || 'Could not load the document' })
        }
      })
    }

    const onKey = (e) => { if (e.key === 'Escape') closeFnRef.current() }
    window.addEventListener('keydown', onKey)
    setTimeout(() => closeRef.current?.focus(), 0)
    return () => {
      alive = false
      window.removeEventListener('keydown', onKey)
      if (objectUrl) URL.revokeObjectURL(objectUrl)
      openerRef.current?.focus?.()
    }
  }, [open, url, hasLoader, filename])

  if (!open) return null
  const isImage = state.src && (IMAGE_RE.test(state.name || '') || IMAGE_RE.test(url || ''))

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-ink-900/60 p-4" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div role="dialog" aria-modal="true" aria-label={title} className="flex h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-card bg-surface-card shadow-overlay">
        <div className="flex items-center justify-between gap-3 border-b border-ink-200 px-4 py-3">
          <h2 className="truncate text-heading text-ink-900">{title}</h2>
          <div className="flex items-center gap-2">
            {state.status === 'ready' && (
              <>
                <Button size="sm" icon={ExternalLink} onClick={() => window.open(state.src, '_blank', 'noopener')}>Open in new tab</Button>
                <a
                  href={state.src}
                  download={state.name || 'document'}
                  className="inline-flex h-8 items-center gap-2 rounded-control bg-brand-600 px-3 text-small font-medium text-white shadow-xs hover:bg-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
                >
                  <Download aria-hidden="true" className="h-3.5 w-3.5" /> Download
                </a>
              </>
            )}
            <button
              ref={closeRef}
              type="button"
              aria-label="Close preview"
              onClick={onClose}
              className="inline-flex h-8 w-8 items-center justify-center rounded-control text-ink-600 hover:bg-ink-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            >
              <X aria-hidden="true" className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div className="relative flex-1 bg-ink-100">
          {state.status === 'loading' && (
            <div className="absolute inset-0 flex items-center justify-center gap-2 text-small text-ink-600">
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> Preparing PDF…
            </div>
          )}
          {state.status === 'error' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-small text-danger-700">
              <AlertCircle aria-hidden="true" className="h-5 w-5" /> {state.error}
            </div>
          )}
          {state.status === 'ready' && (isImage ? (
            <div className="flex h-full items-center justify-center overflow-auto p-4">
              <img src={state.src} alt={title} className="max-h-full max-w-full rounded shadow-raised" />
            </div>
          ) : (
            <iframe title={title} src={state.src} className="h-full w-full border-0 bg-white" />
          ))}
        </div>
        <p className="border-t border-ink-200 px-4 py-2 text-caption text-ink-500">
          If the preview stays blank, use “Open in new tab” — some file hosts don’t allow previews inside other sites.
        </p>
      </div>
    </div>
  )
}

DocumentPreviewModal.propTypes = {
  open: PropTypes.bool.isRequired,
  title: PropTypes.string.isRequired,
  url: PropTypes.string,
  load: PropTypes.func,
  filename: PropTypes.string,
  onClose: PropTypes.func.isRequired,
}
