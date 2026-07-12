import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import {
  api,
  buildQuery,
  type VisitCreate,
  type VisitOut,
  type VisitPatch,
  type VisitListItem,
  type VisitsListResponse,
} from './client'
import type { VisitStatus } from './enums'

// 顧客詳細の履歴は 10 件ずつ表示する
export const DETAIL_PAGE_SIZE = 10

export const visitsKeys = {
  all: ['visits'] as const,
  byCustomer: (customerId: number) => ['visits', 'byCustomer', customerId] as const,
  nextByCustomer: (customerId: number) => ['visits', 'nextByCustomer', customerId] as const,
  detail: (id: number) => ['visits', 'detail', id] as const,
  list: (params: VisitListApiParams) => ['visits', 'list', params] as const,
}

// API へ渡す形（from / to は ISO 8601 UTC。仕様）
export type VisitListApiParams = {
  customer_id?: number
  user_id?: number
  status?: VisitStatus
  from?: string
  to?: string
  unrecorded?: boolean
  page?: number
  page_size?: number
}

type UseVisitsListOptions = {
  enabled?: boolean
}

export function useVisitsList(
  params: VisitListApiParams,
  options: UseVisitsListOptions = {},
) {
  return useQuery({
    queryKey: visitsKeys.list(params),
    queryFn: () =>
      api.get<VisitsListResponse>(
        `/api/visits${buildQuery({
          ...params,
          unrecorded: params.unrecorded === true ? 'true' : undefined,
        })}`,
      ),
    enabled: options.enabled ?? true,
  })
}

export function useCustomerVisits(customerId: number | undefined) {
  return useInfiniteQuery({
    queryKey: visitsKeys.byCustomer(customerId ?? -1),
    queryFn: ({ pageParam }) =>
      api.get<VisitsListResponse>(
        `/api/customers/${customerId}/visits?page=${pageParam}&page_size=${DETAIL_PAGE_SIZE}`,
      ),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page * lastPage.page_size < lastPage.total
        ? lastPage.page + 1
        : undefined,
    enabled: customerId !== undefined,
  })
}

export function useCustomerNextVisit(customerId: number | undefined) {
  return useQuery({
    queryKey: visitsKeys.nextByCustomer(customerId ?? -1),
    queryFn: () =>
      api.get<VisitListItem | null>(`/api/customers/${customerId}/next-visit`),
    enabled: customerId !== undefined,
  })
}

export function useVisit(id: number | undefined) {
  return useQuery({
    queryKey: visitsKeys.detail(id ?? -1),
    queryFn: () => api.get<VisitOut>(`/api/visits/${id}`),
    enabled: id !== undefined,
  })
}

// 活動記録の書き込みは visits / dashboard / customers(last_visited_at) を無効化する
function useInvalidateAfterVisitWrite() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: ['visits'] })
    void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    void queryClient.invalidateQueries({ queryKey: ['customers'] })
  }
}

export function useCreateVisit() {
  const invalidate = useInvalidateAfterVisitWrite()
  return useMutation({
    mutationFn: (body: VisitCreate) => api.post<VisitOut>('/api/visits', body),
    onSuccess: invalidate,
  })
}

export function useUpdateVisit(id: number) {
  const invalidate = useInvalidateAfterVisitWrite()
  return useMutation({
    mutationFn: (body: VisitPatch) =>
      api.patch<VisitOut>(`/api/visits/${id}`, body),
    onSuccess: invalidate,
  })
}

export function useDeleteVisit() {
  const invalidate = useInvalidateAfterVisitWrite()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/api/visits/${id}`),
    onSuccess: invalidate,
  })
}
