import { Link } from 'react-router'

import type { VisitListItem } from '../api/client'
import type { VisitStatus } from '../api/enums'
import { activityTypeLabels } from '../api/enums'
import { formatDateTimeJst } from '../lib/dates'
import { VisitStatusBadge } from './StatusBadge'

type Props = {
  items: VisitListItem[]
  editHref?: (item: VisitListItem) => string
}

const DOT_COLORS: Record<VisitStatus, string> = {
  done:      'bg-emerald-500 ring-emerald-500',
  planned:   'bg-[#1D4ED8] ring-[#3D6FFF]',
  cancelled: 'bg-slate-300 ring-slate-300',
}

export function ActivityTimeline({ items, editHref }: Props) {
  return (
    <div className="relative pl-6">
      {/* 縦ライン */}
      {items.length > 1 && (
        <div className="pointer-events-none absolute left-[9px] top-4 bottom-4 w-[2px] bg-slate-200" />
      )}

      <ol className="relative flex flex-col gap-0">
        {items.map((item) => (
          <li key={item.id} className="relative pb-3 last:pb-0">
            {/* ドット */}
            <div
              className={`absolute left-[-24px] top-[14px] h-[10px] w-[10px] rounded-full border-2 border-white ring-2 ${DOT_COLORS[item.status]}`}
            />

            {/* カード */}
            <div className="rounded-[9px] border border-slate-200/80 bg-white px-4 py-3 shadow-[0_1px_3px_rgba(30,41,59,0.04)]">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <span className="text-[13px] font-semibold text-slate-800">
                    {activityTypeLabels[item.activity_type]}
                  </span>
                  <VisitStatusBadge status={item.status} />
                </div>
                <div className="flex shrink-0 items-center gap-3 text-xs text-slate-500">
                  <span>{item.user_name}</span>
                  <span>{formatDateTimeJst(item.visited_at)}</span>
                  {editHref !== undefined && (
                    <Link
                      to={editHref(item)}
                      className="font-medium text-[#1D4ED8] hover:underline"
                    >
                      編集
                    </Link>
                  )}
                </div>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
