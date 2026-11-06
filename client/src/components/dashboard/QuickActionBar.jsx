import PropTypes from 'prop-types'
import { FileWarning, Users, Handshake, UsersRound, ShieldCheck, LifeBuoy, Lock } from 'lucide-react'
import Button from '../ds/Button'
import { useQuickActions } from './QuickActions'

const ICONS = {
  '/defaulters/report': FileWarning,
  '/defaulters': Users,
  '/settlement': Handshake,
  '/admin/team': UsersRound,
}

/**
 * Compact quick actions: the first (Report Overdue Payer) is the primary
 * action; the rest are secondary; help-type actions are tertiary.
 * Same destinations and plan gating as the old QuickActionsRow.
 */
export default function QuickActionBar({ context, onCheckSafety, onSupportRequest }) {
  const actions = useQuickActions(context)

  return (
    <nav aria-label="Quick actions" className="flex flex-wrap items-center gap-2">
      {actions.map((a, i) => {
        const Icon = ICONS[a.id] || FileWarning
        return (
          <Button key={a.id} to={a.to} variant={i === 0 ? 'primary' : 'secondary'} icon={Icon}>
            {a.label}
            {a.locked && (
              <span className="inline-flex items-center gap-1 rounded-full bg-warning-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-warning-700 ring-1 ring-inset ring-warning-200">
                <Lock aria-hidden="true" className="h-2.5 w-2.5" />
                Upgrade
              </span>
            )}
          </Button>
        )
      })}
      <span aria-hidden="true" className="mx-1 hidden h-6 w-px bg-ink-200 sm:block" />
      <Button variant="ghost" icon={ShieldCheck} onClick={onCheckSafety}>Check company safety</Button>
      <Button variant="ghost" icon={LifeBuoy} onClick={onSupportRequest}>Support request</Button>
    </nav>
  )
}

QuickActionBar.propTypes = {
  context: PropTypes.oneOf(['po', 'invoice', null]),
  onCheckSafety: PropTypes.func.isRequired,
  onSupportRequest: PropTypes.func.isRequired,
}
