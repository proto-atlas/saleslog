import type { ReactNode } from 'react'

type Props = {
  title: string
  description?: string
  action?: ReactNode
}

export function EmptyState({ title, description, action }: Props) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-[10px] border-2 border-dashed border-slate-200 px-6 py-14 text-center">
      <div className="text-3xl text-slate-300">📭</div>
      <p className="font-semibold text-slate-600">{title}</p>
      {description !== undefined && (
        <p className="text-sm text-slate-600">{description}</p>
      )}
      {action}
    </div>
  )
}
