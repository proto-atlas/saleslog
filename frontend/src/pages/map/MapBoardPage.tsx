import { useMemo } from 'react'
import { Link } from 'react-router'

import type { CustomerListItem } from '../../api/client'
import { useCustomersList } from '../../api/customers'
import {
  CUSTOMER_AREA,
  CUSTOMER_STATUS,
  customerAreaLabels,
  customerStatusLabels,
} from '../../api/enums'
import { useMe, useUsers } from '../../api/users'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { CustomerStatusBadge } from '../../components/StatusBadge'
import { formatDateJst } from '../../lib/dates'

const BOARD_PAGE_SIZE = 100

export function MapBoardPage() {
  const me = useMe()
  const isManager = me.data?.role === 'manager'
  const customers = useCustomersList({ page_size: BOARD_PAGE_SIZE })
  const users = useUsers({ enabled: me.data !== undefined && isManager })

  const userNames = useMemo(() => {
    const map = new Map<number, string>()
    if (isManager) {
      for (const user of users.data?.items ?? []) {
        map.set(user.id, user.name)
      }
    }
    return map
  }, [isManager, users.data])

  const byArea = useMemo(() => {
    const groups = new Map<string, CustomerListItem[]>(
      CUSTOMER_AREA.map((area) => [area, []]),
    )
    for (const customer of customers.data?.items ?? []) {
      groups.get(customer.area)?.push(customer)
    }
    return groups
  }, [customers.data])

  if (customers.isPending) {
    return (
      <div className="flex gap-4 overflow-x-auto" aria-busy="true">
        {CUSTOMER_AREA.map((area) => (
          <div
            key={area}
            className="h-72 w-60 shrink-0 animate-pulse rounded-[10px] bg-slate-200"
          />
        ))}
      </div>
    )
  }
  if (customers.isError) {
    return <ErrorState onRetry={() => void customers.refetch()} />
  }
  if ((customers.data.items ?? []).length === 0) {
    return (
      <section className="flex flex-col gap-5">
        <h1 className="text-[22px] font-bold tracking-[-0.02em] text-slate-800">
          エリア別ボード
        </h1>
        <EmptyState
          title="まだ顧客が登録されていません"
          description="顧客を登録すると、エリア別のボードに表示されます。"
        />
      </section>
    )
  }

  return (
    <section className="flex flex-col gap-5">
      <h1 className="text-[22px] font-bold tracking-[-0.02em] text-slate-800">
        エリア別ボード
      </h1>
      <div className="flex items-start gap-4 overflow-x-auto pb-4">
        {CUSTOMER_AREA.map((area) => {
          const items = byArea.get(area) ?? []
          const statusCounts = CUSTOMER_STATUS.map((status) => ({
            status,
            count: items.filter((item) => item.status === status).length,
          })).filter((entry) => entry.count > 0)

          return (
            <div
              key={area}
              role="group"
              aria-label={`${customerAreaLabels[area]} ${items.length}件`}
              className="flex w-60 shrink-0 flex-col rounded-[10px] border border-slate-200/80 bg-[#F5F7FA] shadow-[0_1px_4px_rgba(30,41,59,0.06)]"
            >
              {/* 列ヘッダ */}
              <div className="rounded-t-[10px] border-b border-slate-200/80 bg-white px-4 py-3">
                <div className="flex items-center justify-between">
                  <p className="text-[13px] font-semibold text-slate-800">
                    {customerAreaLabels[area]}
                  </p>
                  <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
                    {items.length}
                  </span>
                </div>
                {statusCounts.length > 0 && (
                  <p className="mt-1.5 text-[10px] text-slate-600">
                    {statusCounts
                      .map(
                        (entry) =>
                          `${customerStatusLabels[entry.status]} ${entry.count}`,
                      )
                      .join(' · ')}
                  </p>
                )}
              </div>

              {/* カードリスト */}
              <ul className="flex max-h-[60vh] flex-col gap-2 overflow-y-auto p-2">
                {items.length === 0 ? (
                  <li className="px-2 py-6 text-center text-xs text-slate-600">
                    顧客なし
                  </li>
                ) : (
                  items.map((customer) => (
                    <li key={customer.id}>
                      <Link
                        to={`/customers/${customer.id}`}
                        className="block rounded-[8px] border border-slate-200/80 bg-white p-3 shadow-[0_1px_2px_rgba(30,41,59,0.04)] transition-all hover:border-[#1D4ED8]/40 hover:shadow-[0_2px_8px_rgba(61,111,255,0.1)]"
                      >
                        <p className="text-[13px] font-semibold text-slate-800">
                          {customer.name}
                        </p>
                        <div className="mt-1.5 flex items-center justify-between">
                          <CustomerStatusBadge status={customer.status} />
                          {isManager && (
                            <span className="text-[10px] text-slate-600">
                              {userNames.get(customer.owner_id) ?? ''}
                            </span>
                          )}
                        </div>
                        <p className="mt-1.5 text-[10px] text-slate-600">
                          最終訪問:{' '}
                          {customer.last_visited_at === null
                            ? 'なし'
                            : formatDateJst(customer.last_visited_at)}
                        </p>
                      </Link>
                    </li>
                  ))
                )}
              </ul>
            </div>
          )
        })}
      </div>
    </section>
  )
}
