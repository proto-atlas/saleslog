import { ClipboardList, Users } from 'lucide-react'
import { Link } from 'react-router'

import { useDashboardSummary } from '../api/dashboard'
import { CUSTOMER_AREA, customerAreaLabels } from '../api/enums'
import { useMe } from '../api/users'
import { BarList } from '../components/charts/BarList'
import { TrendChart } from '../components/charts/TrendChart'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { formatDateTimeJst } from '../lib/dates'

export function DashboardPage() {
  const summary = useDashboardSummary()
  const me = useMe()

  if (summary.isPending) {
    return (
      <div className="flex flex-col gap-5" aria-busy="true">
        <div className="h-8 w-48 animate-pulse rounded-[8px] bg-slate-200" />
        <div className="grid gap-4 md:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-[10px] bg-slate-200" />
          ))}
        </div>
        <div className="h-56 animate-pulse rounded-[10px] bg-slate-200" />
      </div>
    )
  }
  if (summary.isError) {
    return <ErrorState onRetry={() => void summary.refetch()} />
  }

  const data = summary.data

  return (
    <section className="flex flex-col gap-6">
      <h1 className="text-[22px] font-bold tracking-[-0.02em] text-slate-800">
        ダッシュボード
      </h1>

      {data.total_customers === 0 ? (
        <EmptyState
          title="まだデータがありません"
          description="顧客を登録すると、件数や活動の集計が表示されます。"
          action={
            <Link
              to="/customers"
              className="text-sm font-medium text-[#1D4ED8] hover:underline"
            >
              顧客一覧へ
            </Link>
          }
        />
      ) : (
        <>
          {/* ── KPI カード ── */}
          <div className="grid gap-4 md:grid-cols-3">
            {/* 顧客総数 */}
            <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-slate-600">
                  顧客総数
                </p>
                <Users aria-hidden="true" className="h-5 w-5 text-slate-500" strokeWidth={2} />
              </div>
              <p className="text-[36px] font-bold leading-none tracking-[-0.02em] text-slate-800">
                {data.total_customers}
              </p>
              <p className="mt-2 text-[12px] text-slate-600">件</p>
            </div>

            {/* 今月の活動 */}
            <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-slate-600">
                  今月の活動
                </p>
                <ClipboardList aria-hidden="true" className="h-5 w-5 text-slate-500" strokeWidth={2} />
              </div>
              <p className="text-[36px] font-bold leading-none tracking-[-0.02em] text-slate-800">
                {data.visits_this_month}
              </p>
              <p className="mt-2 text-[12px] text-slate-600">件</p>
            </div>

            {/* 入力漏れ */}
            <div
              className={`rounded-[10px] p-5 ${
                data.unrecorded_count > 0
                  ? 'border border-amber-200 bg-amber-50 shadow-[0_1px_4px_rgba(245,158,11,0.12)]'
                  : 'border border-slate-200/80 bg-white shadow-[0_1px_4px_rgba(30,41,59,0.06)]'
              }`}
            >
              <div className="mb-3 flex items-center justify-between">
                <p
                  className={`text-[11px] font-semibold uppercase tracking-[0.07em] ${
                    data.unrecorded_count > 0 ? 'text-amber-700' : 'text-slate-600'
                  }`}
                >
                  入力漏れ
                </p>
                <span className="text-xl">
                  {data.unrecorded_count > 0 ? '⚠️' : '✅'}
                </span>
              </div>
              <p
                className={`text-[36px] font-bold leading-none tracking-[-0.02em] ${
                  data.unrecorded_count > 0 ? 'text-amber-800' : 'text-slate-800'
                }`}
              >
                {data.unrecorded_count}
              </p>
              {data.unrecorded_count > 0 ? (
                <Link
                  to="/visits?unrecorded=true"
                  aria-label="入力漏れを確認する"
                  className="mt-2 inline-block text-[12px] font-semibold text-amber-700 hover:underline"
                >
                  確認する →
                </Link>
              ) : (
                <p className="mt-2 text-[12px] text-slate-600">件（問題なし）</p>
              )}
            </div>
          </div>

          {/* ── 今日の予定 ── */}
          <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-[13px] font-semibold text-slate-700">今日の予定</h2>
              {data.today_visits.length > 0 && (
                <span className="rounded-full bg-[#1D4ED8] px-2.5 py-0.5 text-[10px] font-bold text-white">
                  {data.today_visits.length}件
                </span>
              )}
            </div>
            {data.today_visits.length === 0 ? (
              <p className="text-sm text-slate-600">今日の予定はありません</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {data.today_visits.map((visit) => {
                  const suppressLink =
                    me.data?.role === 'sales' && visit.owner_id !== me.data.id
                  const content = (
                    <>
                      <div className="h-8 w-[3px] shrink-0 rounded-full bg-[#1D4ED8]" />
                      <div className="min-w-0">
                        <p className="truncate text-[13px] font-semibold text-slate-800">
                          {visit.customer_name}
                        </p>
                        <p className="text-[11px] text-slate-600">
                          {formatDateTimeJst(visit.visited_at)}
                        </p>
                      </div>
                    </>
                  )
                  return (
                    <li key={visit.visit_id}>
                      {suppressLink ? (
                        <div className="flex items-center gap-3 rounded-[8px] border border-slate-100 bg-[#F8FAFF] px-4 py-2.5">
                          {content}
                        </div>
                      ) : (
                        <Link
                          to={`/customers/${visit.customer_id}`}
                          className="flex items-center gap-3 rounded-[8px] border border-slate-100 bg-[#F8FAFF] px-4 py-2.5 transition-colors hover:border-[#1D4ED8]/30 hover:bg-[#EEF3FF]"
                        >
                          {content}
                          <span className="ml-auto text-[11px] font-medium text-[#1D4ED8]">
                            詳細 →
                          </span>
                        </Link>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </div>

          {/* ── チャート行 ── */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
              <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.07em] text-slate-600">
                エリア別の顧客件数
              </h2>
              <BarList
                title="エリア別の顧客件数"
                items={CUSTOMER_AREA.map((area) => ({
                  label: customerAreaLabels[area],
                  count:
                    data.by_area.find((entry) => entry.area === area)?.count ?? 0,
                }))}
              />
            </div>
            <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
              <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.07em] text-slate-600">
                担当者別の顧客件数
              </h2>
              <BarList
                title="担当者別の顧客件数"
                items={data.by_owner.map((entry) => ({
                  label: entry.owner_name,
                  count: entry.count,
                }))}
              />
            </div>
          </div>

          <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
            <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.07em] text-slate-600">
              月次の活動件数（直近6ヶ月）
            </h2>
            <TrendChart title="月次の活動件数の推移" points={data.visits_trend} />
          </div>
        </>
      )}
    </section>
  )
}
