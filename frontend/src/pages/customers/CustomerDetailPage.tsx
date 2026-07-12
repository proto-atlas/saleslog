import { useCallback, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../../api/client'
import {
  useCustomer,
  useDeleteCustomer,
  useUpdateCustomer,
} from '../../api/customers'
import {
  CUSTOMER_STATUS,
  customerAreaLabels,
  customerStatusLabels,
  type CustomerStatus,
} from '../../api/enums'
import { useMe, useUsers } from '../../api/users'
import { useCustomerVisits } from '../../api/visits'
import { ActivityTimeline } from '../../components/ActivityTimeline'
import { Button } from '../../components/Button'
import { Dialog } from '../../components/Dialog'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { CustomerStatusBadge } from '../../components/StatusBadge'
import { useToast } from '../../components/toastContext'
import { getAppReferenceTimeMs } from '../../demoMode'
import { formatDateJst, formatDateTimeJst, startOfJstDayMs } from '../../lib/dates'
import { CustomerAgentPanel } from './CustomerAgentPanel'

function NotFoundView() {
  return (
    <EmptyState
      title="顧客が見つかりません"
      description="削除されたか、URL が誤っている可能性があります。"
      action={
        <Link to="/customers" className="text-sm font-medium text-[#1D4ED8] hover:underline">
          顧客一覧へ戻る
        </Link>
      }
    />
  )
}

export function CustomerDetailPage() {
  const { id: idParam } = useParams()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { showToast } = useToast()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const activeTab = searchParams.get('tab') === 'agent' ? 'agent' : 'activity'
  const selectedAgentRunId = parsePositiveInt(searchParams.get('agentRunId'))

  const customerId =
    idParam !== undefined && /^\d+$/.test(idParam) ? Number(idParam) : undefined
  const customer = useCustomer(customerId)
  const visits = useCustomerVisits(customerId)
  const me = useMe()
  const isManager = me.data?.role === 'manager'
  const users = useUsers({ enabled: isManager })
  const updateCustomer = useUpdateCustomer(customerId ?? -1)
  const deleteCustomer = useDeleteCustomer()

  const setActiveTab = useCallback(
    (tab: 'activity' | 'agent') => {
      setSearchParams((current) => {
        const next = new URLSearchParams(current)
        if (tab === 'agent') {
          next.set('tab', 'agent')
        } else {
          next.delete('tab')
          next.delete('agentRunId')
        }
        return next
      })
    },
    [setSearchParams],
  )

  const setSelectedAgentRunId = useCallback(
    (nextRunId: number | undefined, options?: { replace?: boolean }) => {
      setSearchParams((current) => {
        const next = new URLSearchParams(current)
        next.set('tab', 'agent')
        if (nextRunId === undefined) {
          next.delete('agentRunId')
        } else {
          next.set('agentRunId', String(nextRunId))
        }
        return next
      }, options)
    },
    [setSearchParams],
  )

  const [referenceTime] = useState(() => getAppReferenceTimeMs())
  const visitItems = useMemo(
    () => (visits.data?.pages ?? []).flatMap((page) => page.items),
    [visits.data],
  )
  const nextVisit = useMemo(() => {
    // 基準日（JST）以降の予定を対象にする。当日の未完了予定も「次回」に含める。
    const dayStartMs = startOfJstDayMs(referenceTime)
    const upcomingPlanned = visitItems.filter(
      (item) =>
        item.status === 'planned' &&
        new Date(item.visited_at).getTime() >= dayStartMs,
    )
    if (upcomingPlanned.length === 0) return null
    return upcomingPlanned.reduce((nearest, item) =>
      new Date(item.visited_at) < new Date(nearest.visited_at) ? item : nearest,
    )
  }, [visitItems, referenceTime])

  if (customerId === undefined) return <NotFoundView />
  if (customer.isPending) {
    return (
      <div className="flex flex-col gap-4" aria-busy="true">
        <div className="h-10 w-64 animate-pulse rounded-[8px] bg-slate-200" />
        <div className="h-36 animate-pulse rounded-[10px] bg-slate-200" />
        <div className="h-52 animate-pulse rounded-[10px] bg-slate-200" />
      </div>
    )
  }
  if (customer.isError) {
    if (customer.error instanceof ApiError && customer.error.status === 404) {
      return <NotFoundView />
    }
    return <ErrorState onRetry={() => void customer.refetch()} />
  }

  const data = customer.data

  const handleStatusChange = (status: CustomerStatus) => {
    updateCustomer.mutate(
      { status },
      {
        onSuccess: () =>
          showToast(`ステータスを「${customerStatusLabels[status]}」に更新しました`, 'success'),
        onError: () => showToast('更新に失敗しました。もう一度お試しください', 'error'),
      },
    )
  }

  const handleOwnerChange = (ownerId: number) => {
    updateCustomer.mutate(
      { owner_id: ownerId },
      {
        onSuccess: () => showToast('担当者を更新しました', 'success'),
        onError: () => showToast('更新に失敗しました。もう一度お試しください', 'error'),
      },
    )
  }

  return (
    <section className="flex flex-col gap-6">
      {/* ── ページヘッダ ── */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-[22px] font-bold tracking-[-0.02em] text-slate-800">
            {data.name}
          </h1>
          <CustomerStatusBadge status={data.status} />
        </div>
        {isManager && (
          <Button variant="danger" onClick={() => setDeleteOpen(true)}>
            削除
          </Button>
        )}
      </div>

      {/* ── 情報カード 2列 ── */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* 基本情報 */}
        <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
          <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.07em] text-slate-600">
            基本情報
          </h2>
          <dl className="grid grid-cols-[6rem_1fr] gap-y-2.5 text-sm">
            <dt className="text-[13px] text-slate-600">住所</dt>
            <dd className="text-[13px] text-slate-700">{data.address ?? '—'}</dd>
            <dt className="text-[13px] text-slate-600">エリア</dt>
            <dd className="text-[13px] text-slate-700">{customerAreaLabels[data.area]}</dd>
            <dt className="text-[13px] text-slate-600">登録日</dt>
            <dd className="text-[13px] text-slate-700">{formatDateJst(data.created_at)}</dd>
            <dt className="text-[13px] text-slate-600">更新日</dt>
            <dd className="text-[13px] text-slate-700">{formatDateJst(data.updated_at)}</dd>
          </dl>

          <div className="mt-5 flex flex-wrap gap-4 border-t border-slate-100 pt-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="detail-status" className="text-[13px] font-medium text-slate-500">
                ステータス変更
              </label>
              <select
                id="detail-status"
                value={data.status}
                disabled={updateCustomer.isPending}
                onChange={(event) =>
                  handleStatusChange(event.target.value as CustomerStatus)
                }
                className="rounded-[8px] border-[1.5px] border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20 disabled:bg-slate-50 disabled:text-slate-600"
              >
                {CUSTOMER_STATUS.map((status) => (
                  <option key={status} value={status}>
                    {customerStatusLabels[status]}
                  </option>
                ))}
              </select>
            </div>
            {isManager && (
              <div className="flex flex-col gap-1.5">
                <label htmlFor="detail-owner" className="text-[13px] font-medium text-slate-500">
                  担当者変更
                </label>
                <select
                  id="detail-owner"
                  value={data.owner_id}
                  disabled={updateCustomer.isPending}
                  onChange={(event) => handleOwnerChange(Number(event.target.value))}
                  className="rounded-[8px] border-[1.5px] border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20 disabled:bg-slate-50 disabled:text-slate-600"
                >
                  {(users.data?.items ?? []).map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        {/* 次回訪問予定 */}
        <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
          <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.07em] text-slate-600">
            次回訪問予定
          </h2>
          {nextVisit === null ? (
            <p className="text-sm text-slate-600">予定はありません</p>
          ) : (
            <div className="flex items-start gap-3">
              <div className="mt-0.5 h-9 w-[3px] shrink-0 rounded-full bg-[#1D4ED8]" />
              <div>
                <p className="text-[15px] font-semibold text-slate-800">
                  {formatDateTimeJst(nextVisit.visited_at)}
                </p>
                <p className="mt-1 text-[13px] text-slate-500">
                  担当: {nextVisit.user_name}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── タブ ── */}
      <div className="flex flex-col gap-4">
        <div
          role="tablist"
          aria-label="顧客詳細"
          className="flex gap-0 border-b border-slate-200"
        >
          <button
            type="button"
            id="customer-detail-activity-tab"
            role="tab"
            aria-selected={activeTab === 'activity'}
            aria-controls="customer-detail-activity-panel"
            onClick={() => setActiveTab('activity')}
            className={`border-b-2 px-4 py-2.5 text-[13px] font-semibold transition-colors ${
              activeTab === 'activity'
                ? 'border-[#1D4ED8] text-[#1D4ED8]'
                : 'border-transparent text-slate-700 hover:text-slate-800'
            }`}
          >
            活動履歴
          </button>
          <button
            type="button"
            id="customer-detail-agent-tab"
            role="tab"
            aria-selected={activeTab === 'agent'}
            aria-controls="customer-detail-agent-panel"
            onClick={() => setActiveTab('agent')}
            className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-[13px] font-semibold transition-colors ${
              activeTab === 'agent'
                ? 'border-[#1D4ED8] text-[#1D4ED8]'
                : 'border-transparent text-slate-700 hover:text-slate-800'
            }`}
          >
            Agent
            <span className="rounded-full bg-[#1D4ED8] px-1.5 py-0.5 text-[9px] font-bold text-white">
              AI
            </span>
          </button>
        </div>

        {activeTab === 'agent' ? (
          <div
            id="customer-detail-agent-panel"
            role="tabpanel"
            aria-labelledby="customer-detail-agent-tab"
          >
            <CustomerAgentPanel
              customerId={data.id}
              runId={selectedAgentRunId}
              onRunIdChange={setSelectedAgentRunId}
            />
          </div>
        ) : (
          <div
            id="customer-detail-activity-panel"
            role="tabpanel"
            aria-labelledby="customer-detail-activity-tab"
            className="flex flex-col gap-4"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-[16px] font-semibold tracking-[-0.01em] text-slate-800">
                活動履歴
              </h2>
              <Button onClick={() => void navigate(`/visits/new?customer_id=${data.id}`)}>
                + 活動記録を登録
              </Button>
            </div>

            {visits.isPending ? (
              <div className="h-40 animate-pulse rounded-[10px] bg-slate-200" aria-busy="true" />
            ) : visits.isError ? (
              <ErrorState onRetry={() => void visits.refetch()} />
            ) : visitItems.length === 0 ? (
              <EmptyState
                title="まだ活動記録がありません"
                description="「活動記録を登録」から最初の記録を追加してください。"
              />
            ) : (
              <>
                <ActivityTimeline
                  items={visitItems}
                  editHref={(item) => `/visits/${item.id}/edit`}
                />
                {visits.hasNextPage && (
                  <Button
                    variant="secondary"
                    onClick={() => void visits.fetchNextPage()}
                    disabled={visits.isFetchingNextPage}
                  >
                    {visits.isFetchingNextPage ? '読み込み中…' : 'もっと見る'}
                  </Button>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* ── 削除ダイアログ ── */}
      {isManager && (
        <Dialog
          open={deleteOpen}
          onClose={() => setDeleteOpen(false)}
          title="顧客を削除しますか？"
        >
          <div className="flex flex-col gap-5">
            <p className="text-sm text-slate-600">
              「{data.name}」と関連する活動記録がすべて削除されます。この操作は取り消せません。
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setDeleteOpen(false)}>
                キャンセル
              </Button>
              <Button
                variant="danger"
                disabled={deleteCustomer.isPending}
                onClick={() =>
                  deleteCustomer.mutate(data.id, {
                    onSuccess: () => {
                      showToast(`顧客「${data.name}」を削除しました`, 'success')
                      void navigate('/customers')
                    },
                    onError: () =>
                      showToast('削除に失敗しました。もう一度お試しください', 'error'),
                  })
                }
              >
                削除する
              </Button>
            </div>
          </div>
        </Dialog>
      )}
    </section>
  )
}

function parsePositiveInt(value: string | null): number | undefined {
  if (value === null || !/^\d+$/.test(value)) return undefined
  const parsed = Number(value)
  return parsed > 0 ? parsed : undefined
}
