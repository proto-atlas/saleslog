import { Button } from './Button'

type Props = {
  message?: string
  onRetry: () => void
}

export function ErrorState({
  message = 'データの取得に失敗しました',
  onRetry,
}: Props) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-4 rounded-[10px] border border-red-100 bg-red-50/70 px-6 py-10 text-center"
    >
      <div className="text-2xl">⚠️</div>
      <p className="text-sm font-medium text-red-800">{message}</p>
      <Button variant="secondary" onClick={onRetry}>
        再試行
      </Button>
    </div>
  )
}
