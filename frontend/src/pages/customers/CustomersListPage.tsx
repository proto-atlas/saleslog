import { useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import type { CustomerListItem } from '../../api/client'
import { useCustomersList, type CustomerListParams } from '../../api/customers'
import {
  CUSTOMER_AREA,
  CUSTOMER_STATUS,
  customerAreaLabels,
  customerStatusLabels,
} from '../../api/enums'
import { useMe, useUsers } from '../../api/users'
import { Button } from '../../components/Button'
import { DataTable, type DataTableColumn } from '../../components/DataTable'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Pagination } from '../../components/Pagination'
import { CustomerStatusBadge } from '../../components/StatusBadge'
import { useToast } from '../../components/toastContext'
import {
  buildCustomerListSearch,
  DEFAULT_PAGE_SIZE,
  parseCustomerListParams,
} from '../../lib/customerListParams'
import { formatDateJst } from '../../lib/dates'
import { CustomerCreateDialog } from './CustomerCreateDialog'

const SEARCH_DEBOUNCE_MS = 300

export function CustomersListPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [dialogOpen, setDialogOpen] = useState(false)

  const params = useMemo(
    () => parseCustomerListParams(searchParams),
    [searchParams],
  )
  const me = useMe()
  const roleReady = me.data !== undefined
  const isManager = me.data?.role === 'manager'
  const listParams = useMemo(
    () => (isManager ? params : { ...params, owner_id: undefined }),
    [isManager, params],
  )
  const customers = useCustomersList(listParams, { enabled: roleReady })
  const users = useUsers({ enabled: roleReady && isManager })

  const [searchText, setSearchText] = useState(params.search ?? '')
  const debounceRef = useRef<number | undefined>(undefined)
  const [lastParamSearch, setLastParamSearch] = useState(params.search)
  if (params.search !== lastParamSearch) {
    setLastParamSearch(params.search)
    setSearchText(params.search ?? '')
  }

  const updateParams = (
    patch: Partial<CustomerListParams>,
    options: { replace?: boolean } = {},
  ) => {
    const next = { ...params, page: undefined, ...patch }
    setSearchParams(buildCustomerListSearch(next), { replace: options.replace })
  }

  const handleSearchChange = (value: string) => {
    setSearchText(value)
    window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(() => {
      updateParams({ search: value.trim() === '' ? undefined : value }, { replace: true })
    }, SEARCH_DEBOUNCE_MS)
  }

  const userNames = useMemo(() => {
    const map = new Map<number, string>()
    for (const user of users.data?.items ?? []) {
      map.set(user.id, user.name)
    }
    return map
  }, [users.data])

  const columns: DataTableColumn<CustomerListItem>[] = [
    {
      key: 'name',
      header: '顧客名',
      sortKey: 'name',
      render: (row) => (
        <Link
          to={`/customers/${row.id}`}
          className="font-semibold text-[#1D4ED8] hover:underline"
          onClick={(event) => event.stopPropagation()}
        >
          {row.name}
        </Link>
      ),
    },
    {
      key: 'area',
      header: 'エリア',
      render: (row) => (
        <span className="text-[13px] text-slate-700">{customerAreaLabels[row.area]}</span>
      ),
    },
    {
      key: 'status',
      header: 'ステータス',
      render: (row) => <CustomerStatusBadge status={row.status} />,
    },
    ...(isManager
      ? [
          {
            key: 'owner',
            header: '担当者',
            render: (row: CustomerListItem) => (
              <span className="text-[13px] text-slate-700">
                {userNames.get(row.owner_id) ?? `ID: ${row.owner_id}`}
              </span>
            ),
          } satisfies DataTableColumn<CustomerListItem>,
        ]
      : []),
    {
      key: 'last_visited_at',
      header: '最終訪問日',
      render: (row) => (
        <span className="text-[13px] text-slate-500">
          {row.last_visited_at === null ? '—' : formatDateJst(row.last_visited_at)}
        </span>
      ),
    },
    {
      key: 'updated_at',
      header: '更新日',
      sortKey: 'updated_at',
      render: (row) => (
        <span className="text-[13px] text-slate-500">{formatDateJst(row.updated_at)}</span>
      ),
    },
  ]

  const page = params.page ?? 1
  const pageSize = params.page_size ?? DEFAULT_PAGE_SIZE
  const total = customers.data?.total ?? 0
  const hasFilter =
    params.search !== undefined ||
    params.area !== undefined ||
    params.status !== undefined ||
    listParams.owner_id !== undefined

  if (me.isError) {
    return (
      <section className="flex flex-col gap-4">
        <h1 className="text-[22px] font-bold tracking-[-0.02em] text-slate-800">顧客一覧</h1>
        <ErrorState onRetry={() => void me.refetch()} />
      </section>
    )
  }

  return (
    <section className="flex flex-col gap-5">
      {/* ── ヘッダ ── */}
      <div className="flex items-center justify-between">
        <h1 className="text-[22px] font-bold tracking-[-0.02em] text-slate-800">顧客一覧</h1>
        <Button onClick={() => setDialogOpen(true)}>+ 顧客を登録</Button>
      </div>

      {/* ── フィルタバー ── */}
      <div className="rounded-[10px] border border-slate-200/80 bg-white p-4 shadow-[0_1px_4px_rgba(30,41,59,0.04)]">
        <div className="flex flex-wrap items-center gap-3">
          {/* 検索 */}
          <div className="relative flex-1" style={{ minWidth: '200px', maxWidth: '280px' }}>
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-600">
              🔍
            </span>
            <input
              aria-label="検索（顧客名）"
              type="search"
              value={searchText}
              onChange={(event) => handleSearchChange(event.target.value)}
              placeholder="顧客名で検索"
              maxLength={80}
              className="w-full rounded-[8px] border-[1.5px] border-slate-200 py-2 pl-9 pr-3 text-sm text-slate-800 placeholder:text-slate-600 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20"
            />
          </div>

          {/* エリア */}
          <select
            id="filter-area"
            aria-label="エリア"
            value={params.area ?? ''}
            onChange={(event) =>
              updateParams({
                area: event.target.value === '' ? undefined : (event.target.value as CustomerListParams['area']),
              })
            }
            className="rounded-[8px] border-[1.5px] border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20"
          >
            <option value="">エリア: すべて</option>
            {CUSTOMER_AREA.map((area) => (
              <option key={area} value={area}>
                {customerAreaLabels[area]}
              </option>
            ))}
          </select>

          {/* ステータス */}
          <select
            id="filter-status"
            aria-label="ステータス"
            value={params.status ?? ''}
            onChange={(event) =>
              updateParams({
                status:
                  event.target.value === '' ? undefined : (event.target.value as CustomerListParams['status']),
              })
            }
            className="rounded-[8px] border-[1.5px] border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20"
          >
            <option value="">ステータス: すべて</option>
            {CUSTOMER_STATUS.map((status) => (
              <option key={status} value={status}>
                {customerStatusLabels[status]}
              </option>
            ))}
          </select>

          {/* 担当者 (manager only) */}
          {isManager && (
            <select
              id="filter-owner"
              aria-label="担当者"
              value={params.owner_id !== undefined ? String(params.owner_id) : ''}
              onChange={(event) =>
                updateParams({
                  owner_id:
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

          {/* アクティブフィルターチップ */}
          {hasFilter && (
            <div className="flex flex-wrap items-center gap-2">
              {params.search !== undefined && (
                <span className="flex items-center gap-1 rounded-full border border-[#C7D8FF] bg-[#EEF3FF] px-3 py-1 text-[11px] font-semibold text-[#1D4ED8]">
                  「{params.search}」
                  <button
                    type="button"
                    onClick={() => updateParams({ search: undefined })}
                    className="ml-0.5 font-bold"
                    aria-label="検索をクリア"
                  >
                    ×
                  </button>
                </span>
              )}
              {params.area !== undefined && (
                <span className="flex items-center gap-1 rounded-full border border-[#C7D8FF] bg-[#EEF3FF] px-3 py-1 text-[11px] font-semibold text-[#1D4ED8]">
                  {customerAreaLabels[params.area]}
                  <button
                    type="button"
                    onClick={() => updateParams({ area: undefined })}
                    className="ml-0.5 font-bold"
                    aria-label="エリアフィルターをクリア"
                  >
                    ×
                  </button>
                </span>
              )}
              {params.status !== undefined && (
                <span className="flex items-center gap-1 rounded-full border border-[#C7D8FF] bg-[#EEF3FF] px-3 py-1 text-[11px] font-semibold text-[#1D4ED8]">
                  {customerStatusLabels[params.status]}
                  <button
                    type="button"
                    onClick={() => updateParams({ status: undefined })}
                    className="ml-0.5 font-bold"
                    aria-label="ステータスフィルターをクリア"
                  >
                    ×
                  </button>
                </span>
              )}
              <button
                type="button"
                onClick={() =>
                  updateParams({
                    search: undefined,
                    area: undefined,
                    status: undefined,
                    owner_id: undefined,
                  })
                }
                className="text-[11px] font-medium text-slate-600 hover:text-slate-600 hover:underline"
              >
                すべてクリア
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── テーブル ── */}
      <DataTable
        columns={columns}
        rows={customers.data?.items ?? []}
        rowKey={(row) => row.id}
        isLoading={customers.isPending}
        errorMessage={customers.isError ? 'データの取得に失敗しました' : null}
        onRetry={() => void customers.refetch()}
        sort={params.sort}
        onSortChange={(sort) =>
          updateParams({ sort: sort as CustomerListParams['sort'] })
        }
        onRowClick={(row) => void navigate(`/customers/${row.id}`)}
        rowActionLabel={(row) => `${row.name}を開く`}
        emptyState={
          hasFilter ? (
            <EmptyState
              title="該当する顧客がいません"
              description="検索条件を変更してください。"
            />
          ) : (
            <EmptyState
              title="まだ顧客が登録されていません"
              action={<Button onClick={() => setDialogOpen(true)}>顧客を登録</Button>}
            />
          )
        }
      />

      <Pagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={(nextPage) => updateParams({ page: nextPage })}
      />

      <CustomerCreateDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreated={(customer) => {
          setDialogOpen(false)
          showToast(`顧客「${customer.name}」を登録しました`, 'success')
        }}
      />
    </section>
  )
}
