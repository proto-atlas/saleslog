import {
  CUSTOMER_SORT_KEYS,
  type CustomerListParams,
  type CustomerSort,
} from '../api/customers'
import { CUSTOMER_AREA, CUSTOMER_STATUS } from '../api/enums'

// 一覧の既定値。既定値と同じ場合は URL にキーを出さない
export const DEFAULT_PAGE = 1
export const DEFAULT_PAGE_SIZE = 20
const PAGE_SIZE_MAX = 100

function parsePositiveInt(value: string | null): number | undefined {
  if (value === null || !/^\d+$/.test(value)) {
    return undefined
  }
  const n = Number(value)
  return n >= 1 ? n : undefined
}

function parseMember<T extends string>(
  value: string | null,
  allowed: readonly T[],
): T | undefined {
  return value !== null && (allowed as readonly string[]).includes(value)
    ? (value as T)
    : undefined
}

// URL クエリ → 一覧パラメータ。不正値は黙って既定値に落とす（URL は利用者が編集できる入力のため）
export function parseCustomerListParams(
  searchParams: URLSearchParams,
): CustomerListParams {
  const params: CustomerListParams = {}

  const search = searchParams.get('search')
  if (search !== null && search.trim() !== '') {
    params.search = search
  }
  params.area = parseMember(searchParams.get('area'), CUSTOMER_AREA)
  params.status = parseMember(searchParams.get('status'), CUSTOMER_STATUS)
  params.owner_id = parsePositiveInt(searchParams.get('owner_id'))
  params.sort = parseMember<CustomerSort>(
    searchParams.get('sort'),
    CUSTOMER_SORT_KEYS,
  )

  const page = parsePositiveInt(searchParams.get('page'))
  if (page !== undefined && page !== DEFAULT_PAGE) {
    params.page = page
  }
  const pageSize = parsePositiveInt(searchParams.get('page_size'))
  if (
    pageSize !== undefined &&
    pageSize !== DEFAULT_PAGE_SIZE &&
    pageSize <= PAGE_SIZE_MAX
  ) {
    params.page_size = pageSize
  }
  return params
}

// 一覧パラメータ → URL クエリ。空値・既定値はキーを出さない
export function buildCustomerListSearch(
  params: CustomerListParams,
): URLSearchParams {
  const sp = new URLSearchParams()
  if (params.search !== undefined && params.search.trim() !== '') {
    sp.set('search', params.search)
  }
  if (params.area !== undefined) {
    sp.set('area', params.area)
  }
  if (params.status !== undefined) {
    sp.set('status', params.status)
  }
  if (params.owner_id !== undefined) {
    sp.set('owner_id', String(params.owner_id))
  }
  if (params.sort !== undefined) {
    sp.set('sort', params.sort)
  }
  if (params.page !== undefined && params.page !== DEFAULT_PAGE) {
    sp.set('page', String(params.page))
  }
  if (params.page_size !== undefined && params.page_size !== DEFAULT_PAGE_SIZE) {
    sp.set('page_size', String(params.page_size))
  }
  return sp
}
