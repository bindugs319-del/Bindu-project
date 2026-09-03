/**
 * Short helper message shown on hover — no visible icon.
 *
 * Renders as an absolutely-positioned popup that stays hidden until the
 * nearest ancestor with the "group" class is hovered (mouse) or has focus
 * within it (tapping into an input on mobile). Place this next to a
 * field's label, inside a wrapper that has `group` so the popup shows,
 * and make sure a positioned ancestor exists (this component's own
 * parent works fine if given `relative`) so the popup anchors correctly.
 */
export default function InfoTooltip({ text, className = '' }) {
  if (!text) return null

  return (
    <span
      role="tooltip"
      className={`pointer-events-none absolute z-30 bottom-full left-0 mb-1.5 w-56 max-w-[80vw] rounded-lg bg-gray-900 text-white text-[11px] leading-snug font-normal normal-case px-3 py-2 shadow-lg opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100 ${className}`}
    >
      {text}
    </span>
  )
}
