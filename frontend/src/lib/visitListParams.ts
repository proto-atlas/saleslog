import type { VisitListApiParams } from '../api/visits'
import { VISIT_STATUS, type VisitStatus } from '../api/enums'
import { DEFAULT_PAGE, DEFAULT_PAGE_SIZE } from './customerListParams'

// 活動記録一覧の URL 状態。期間は日付（YYYY-MM-DD）で持ち、API へは JST の日界で変換する
export type VisitListUrlParams = {
  customer_id?: number
  user_id?: number
  status?: VisitStatus
  from?: string
  to?: string
  unrecorded?: boolean
  page?: number
}

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/

function parsePositiveInt(value: string | null): number | undefined {
  if (value === null || !/^\d+$/.test(value)) {
    return undefined
  }
  const n = Number(value)
  return n >= 1 ? n : undefined
}

function parseDate(value: string | null): string | undefined {
  return value !== null && DATE_PATTERN.test(value) ? value : undefined
}

export function parseVisitListParams(
  searchParams: URLSearchParams,
): VisitListUrlParams {
  const params: VisitListUrlParams = {}
  params.customer_id = parsePositiveInt(searchParams.get('customer_id'))
  params.user_id = parsePositiveInt(searchParams.get('user_id'))
  const status = searchParams.get('status')
  params.status =
    status !== null && (VISIT_STATUS as readonly string[]).includes(status)
      ? (status as VisitStatus)
      : undefined
  params.from = parseDate(searchParams.get('from'))
  params.to = parseDate(searchParams.get('to'))
  params.unrecorded = searchParams.get('unrecorded') === 'true' ? true : undefined
  const page = parsePositiveInt(searchParams.get('page'))
  if (page !== undefined && page !== DEFAULT_PAGE) {
    params.page = page
  }
  return params
}

export function buildVisitListSearch(params: VisitListUrlParams): URLSearchParams {
  const sp = new URLSearchParams()
  if (params.customer_id !== undefined) {
    sp.set('customer_id', String(params.customer_id))
  }
  if (params.user_id !== undefined) {
    sp.set('user_id', String(params.user_id))
  }
  if (params.status !== undefined) {
    sp.set('status', params.status)
  }
  if (params.from !== undefined) {
    sp.set('from', params.from)
  }
  if (params.to !== undefined) {
    sp.set('to', params.to)
  }
  if (params.unrecorded === true) {
    sp.set('unrecorded', 'true')
  }
  if (params.page !== undefined && params.page !== DEFAULT_PAGE) {
    sp.set('page', String(params.page))
  }
  return sp
}

// JST の日付として [当日0:00, 当日23:59:59.999] を UTC ISO へ変換して API パラメータにする
export function toVisitListApiParams(
  params: VisitListUrlParams,
): VisitListApiParams {
  return {
    customer_id: params.customer_id,
    user_id: params.user_id,
    status: params.status,
    from:
      params.from !== undefined
        ? new Date(`${params.from}T00:00:00+09:00`).toISOString()
        : undefined,
    to:
      params.to !== undefined
        ? new Date(`${params.to}T23:59:59.999+09:00`).toISOString()
        : undefined,
    unrecorded: params.unrecorded,
    page: params.page,
    page_size: DEFAULT_PAGE_SIZE,
  }
}
