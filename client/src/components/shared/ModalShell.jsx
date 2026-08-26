import PropTypes from 'prop-types'

/**
 * The actual "chrome" every modal in this app repeats: a dark overlay,
 * a white rounded box, a header row with a title/subtitle and an X
 * close button, a scrollable content area, and a footer slot. Extracted
 * specifically because it was being duplicated not just between paired
 * components (PO vs Invoice variants) but against several unrelated
 * pre-existing modals elsewhere in the app (EditPOModal, etc.) — SonarCloud
 * flags that cross-file boilerplate match even when the modals serve
 * completely different purposes.
 */
export default function ModalShell({ title, subtitle, onClose, closeDisabled, maxWidth, headerExtra, children, footer }) {
  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4">
      <div className={`bg-white rounded-xl shadow-2xl w-full ${maxWidth} max-h-[90vh] flex flex-col`}>
        <div className="bg-white border-b border-gray-200 px-6 py-4 flex-shrink-0">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-heading font-bold text-gray-900">{title}</h2>
              {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
              type="button"
              disabled={closeDisabled}
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          {headerExtra}
        </div>

        <div className="p-6 overflow-y-auto flex-grow">
          {children}
        </div>

        <div className="p-6 border-t border-gray-200 bg-gray-50 rounded-b-xl flex gap-3 flex-shrink-0">
          {footer}
        </div>
      </div>
    </div>
  )
}

ModalShell.propTypes = {
  title: PropTypes.string.isRequired,
  subtitle: PropTypes.string,
  onClose: PropTypes.func.isRequired,
  closeDisabled: PropTypes.bool,
  maxWidth: PropTypes.string,
  headerExtra: PropTypes.node,
  children: PropTypes.node,
  footer: PropTypes.node,
}

ModalShell.defaultProps = {
  maxWidth: 'max-w-2xl',
}
