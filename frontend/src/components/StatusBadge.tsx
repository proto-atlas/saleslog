import type { CustomerStatus, VisitStatus } from '../api/enums'
import { customerStatusLabels, visitStatusLabels } from '../api/enums'

type Tone = 'gray' | 'blue' | 'green' | 'red' | 'yellow'

const TONE_CLASSES: Record<Tone, string> = {
  gray:   'bg-slate-100 text-slate-600',
  blue:   'bg-blue-50 text-blue-700',
  green:  'bg-emerald-50 text-emerald-700',
  red:    'bg-red-50 text-red-700',
  yellow: 'bg-amber-50 text-amber-700',
}

export function StatusBadge({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span
      className={`inline-block rounded-[5px] px-2 py-0.5 text-[11px] font-semibold ${TONE_CLASSES[tone]}`}
    >
      {label}
    </span>
  )
}

const CUSTOMER_STATUS_TONES: Record<CustomerStatus, Tone> = {
  prospect:    'blue',
  negotiating: 'yellow',
  won:         'green',
  lost:        'red',
  dormant:     'gray',
}

export function CustomerStatusBadge({ status }: { status: CustomerStatus }) {
  return (
    <StatusBadge
      label={customerStatusLabels[status]}
      tone={CUSTOMER_STATUS_TONES[status]}
    />
  )
}

const VISIT_STATUS_TONES: Record<VisitStatus, Tone> = {
  planned:   'blue',
  done:      'green',
  cancelled: 'gray',
}

export function VisitStatusBadge({ status }: { status: VisitStatus }) {
  return (
    <StatusBadge
      label={visitStatusLabels[status]}
      tone={VISIT_STATUS_TONES[status]}
    />
  )
}
