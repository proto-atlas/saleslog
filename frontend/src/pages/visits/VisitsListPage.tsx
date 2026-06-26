import { useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import type { VisitListItem } from '../../api/client'
import {
  VISIT_STATUS,
  activityTypeLabels,
  visitStatusLabels,
} from '../../api/enums'
import { useMe, useUsers } from '../../api/users'
import { useVisitsList } from '../../api/visits'
import { DataTable, type DataTableColumn } from '../../components/DataTable'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Pagination } from '../../components/Pagination'
import { VisitStatusBadge } from '../../components/StatusBadge'
import { DEFAULT_PAGE_SIZE } from '../../lib/customerListParams'
import { formatDateTimeJst } from '../../lib/dates'
import {
  buildVisitListSearch,
  parseVisitListParams,
  toVisitListApiParams,
  type VisitListUrlParams,
} from '../../lib/visitListParams'

export function VisitsListPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  const params = useMemo(() => parseVisitListParams(searchParams), [searchParams])
  const me = useMe()
  const roleReady = me.data !== undefined
  const isManager = me.data?.role === 'manager'
  const effectiveParams = useMemo(
    () => (isManager ? params : { ...params, user_id: undefined }),
    [isManager, params],
  )
  const apiParams = useMemo(() => toVisitListApiParams(effectiveParams), [effectiveParams])
  const visits = useVisitsList(apiParams, { enabled: roleReady })
  const users = useUsers({ enabled: roleReady && isManager })

  const updateParams = (patch: Partial<VisitListUrlParams>) => {
    setSearchParams(buildVisitListSearch({ ...params, page: undefined, ...patch }))
  }

  const unrecordedOnly = params.unrecorded === true

  const columns: DataTableColumn<VisitListItem>[] = [
    {
      key: 'visited_at',
      header: '日時',
      render: (row) => (
        <span className="text-[13px] text-slate-700">{formatDateTimeJst(row.visited_at)}</span>
      ),
    },
    {
      key: 'activity_type',
      header: '種別',
      render: (row) => (
        <span className="text-[13px] text-slate-700">{activityTypeLabels[row.activity_type]}</span>
      ),
    },
    {
      key: 'status',
      header: 'ステータス',
      render: (row) => <VisitStatusBadge status={row.status} />,
    },
    {
      key: 'customer',
      header: '顧客名',
      render: (row) => (
        <span className="text-[13px] font-semibold text-slate-800">{row.customer_name}</span>
      ),
    },
    {
      key: 'user',
      header: '担当者',
      render: (row) => (
        <span className="text-[13px] text-slate-500">{row.user_name}</span>
      ),
    },
  ]

  const page = params.page ?? 1
  const total = visits.data?.total ?? 0

  if (me.isError) {
    return (
      <section className="flex flex-col gap-4">
        <h1 className="text-[22px] font-bold tracking-[-0.02em] text-slate-800">活動記録一覧</h1>
        <ErrorState onRetry={() => void me.refetch()} />
      </section>
    )
  }

  return (
    <section className="flex flex-col gap-5">
      <h1 className="text-[22px] font-bold tracking-[-0.02em] text-slate-800">活動記録一覧</h1>

      {/* フィルタバー */}
      <div className="rounded-[10px] border border-slate-200/80 bg-white p-4 shadow-[0_1px_4px_rgba(30,41,59,0.04)]">
        <div className="flex flex-wrap items-center gap-3">
          {/* ステータス */}
          <select
            aria-label="ステータス"
            value={params.status ?? ''}
            disabled={unrecordedOnly}
            onChange={(event) =>
              updateParams({
                status:
                  event.target.value === ''
                    ? undefined
                    : (event.target.value as VisitListUrlParams['status']),
              })
            }
            className="rounded-[8px] border-[1.5px] border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20 disabled:bg-slate-100 disabled:text-slate-600"
          >
            <option value="">ステータス: すべて</option>
            {VISIT_STATUS.map((status) => (
              <option key={status} value={status}>
                {visitStatusLabels[status]}
              </option>
            ))}
          </select>

          {/* 担当者 (manager only) */}
          {isManager && (
            <select
              aria-label="担当者"
              value={params.user_id !== undefined ? String(params.user_id) : ''}
              onChange={(event) =>
                updateParams({
                  user_id:
                    event.target.value === '' ? undefined : Number(event.target.value),
                })
              }
              className="rounded-[8px] border-[1.5px] border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20"
            >
              <option value="">担当者: すべて</option>
              {(users.data?.items ?? []).map((user) => (
                <option key={user.id} value={user.id}>
                  {user.name}
                </option>
              ))}
            </select>
          )}

          {/* 期間 */}
          <div className="flex items-center gap-2">
            <input
              aria-label="開始日"
              type="date"
              value={params.from ?? ''}
              disabled={unrecordedOnly}
              onChange={(event) =>
                updateParams({
                  from: event.target.value === '' ? undefined : event.target.value,
                })
              }
              className="rounded-[8px] border-[1.5px] border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20 disabled:bg-slate-100 disabled:text-slate-600"
            />
            <span className="text-sm text-slate-600">〜</span>
            <input
              aria-label="終了日"
              type="date"
              value={params.to ?? ''}
              disabled={unrecordedOnly}
              onChange={(event) =>
                updateParams({
                  to: event.target.value === '' ? undefined : event.target.value,
                })
              }
              className="rounded-[8px] border-[1.5px] border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20 disabled:bg-slate-100 disabled:text-slate-600"
            />
          </div>

          {/* 入力漏れのみ */}
          <label className="flex cursor-pointer items-center gap-2 rounded-[8px] border-[1.5px] border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:border-[#1D4ED8]/50 hover:bg-[#F8FAFF]">
            <input
              type="checkbox"
              checked={unrecordedOnly}
              onChange={(event) =>
                updateParams({
                  unrecorded: event.target.checked ? true : undefined,
                  ...(event.target.checked
                    ? { status: undefined, from: undefined, to: undefined }
                    : {}),
                })
              }
              className="size-4 accent-[#3D6FFF]"
            />
            入力漏れのみ
          </label>
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={visits.data?.items ?? []}
        rowKey={(row) => row.id}
        isLoading={visits.isPending}
        errorMessage={visits.isError ? 'データの取得に失敗しました' : null}
        onRetry={() => void visits.refetch()}
        onRowClick={(row) => void navigate(`/visits/${row.id}/edit`)}
        rowActionLabel={(row) =>
          `${row.customer_name} ${formatDateTimeJst(row.visited_at)}の活動記録を開く`
        }
        emptyState={
          unrecordedOnly ? (
            <EmptyState
              title="入力漏れはありません"
              description="予定日時を過ぎたままの活動記録はありません。"
            />
          ) : (
            <EmptyState
              title="該当する活動記録がありません"
              description="絞り込み条件を変更してください。"
            />
          )
        }
      />

      <Pagination
        page={page}
        pageSize={DEFAULT_PAGE_SIZE}
        total={total}
        onPageChange={(nextPage) => updateParams({ page: nextPage })}
      />
    </section>
  )
}
