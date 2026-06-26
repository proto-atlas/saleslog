import { Button } from './Button'

type Props = {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, pageSize, total, onPageChange }: Props) {
  if (total === 0) return null
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <nav aria-label="ページネーション" className="flex items-center justify-between">
      <p className="text-sm text-slate-700">
        全 <span className="font-semibold text-slate-700">{total}</span> 件中{' '}
        {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} 件を表示
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          ← 前へ
        </Button>
        <span className="min-w-[4rem] text-center text-sm font-medium text-slate-600">
          {page} / {totalPages}
        </span>
        <Button
          variant="secondary"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          次へ →
        </Button>
      </div>
    </nav>
  )
}
