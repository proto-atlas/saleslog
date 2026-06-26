import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError } from './client'

import {
  api,
  buildQuery,
  type CustomerCreate,
  type CustomerOut,
  type CustomerPatch,
  type CustomersListResponse,
} from './client'
import type { CustomerArea, CustomerStatus } from './enums'

export const CUSTOMER_SORT_KEYS = [
  'name',
  '-name',
  'created_at',
  '-created_at',
  'updated_at',
  '-updated_at',
] as const
export type CustomerSort = (typeof CUSTOMER_SORT_KEYS)[number]

export type CustomerListParams = {
  search?: string
  area?: CustomerArea
  status?: CustomerStatus
  owner_id?: number
  sort?: CustomerSort
  page?: number
  page_size?: number
}

type UseCustomersListOptions = {
  enabled?: boolean
}

// queryKey 階層: ["customers", <view>, <params>]。
// 書き込み後は prefix ["customers"] の一括 invalidate で list/detail を無効化する
export const customersKeys = {
  all: ['customers'] as const,
  list: (params: CustomerListParams) => ['customers', 'list', params] as const,
  detail: (id: number) => ['customers', 'detail', id] as const,
}

export function fetchCustomers(
  params: CustomerListParams,
): Promise<CustomersListResponse> {
  return api.get<CustomersListResponse>(`/api/customers${buildQuery(params)}`)
}

export function useCustomersList(
  params: CustomerListParams,
  options: UseCustomersListOptions = {},
) {
  return useQuery({
    queryKey: customersKeys.list(params),
    queryFn: () => fetchCustomers(params),
    enabled: options.enabled ?? true,
  })
}

export function useCreateCustomer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CustomerCreate) =>
      api.post<CustomerOut>('/api/customers', body),
    onSuccess: () => {
      // 顧客の作成 → customers / dashboard を無効化
      void queryClient.invalidateQueries({ queryKey: ['customers'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useCustomer(id: number | undefined) {
  return useQuery({
    queryKey: customersKeys.detail(id ?? -1),
    queryFn: () => api.get<CustomerOut>(`/api/customers/${id}`),
    enabled: id !== undefined,
    retry: (failureCount, error) =>
      // 404 は再試行しない（存在しない id の表示に直行する）
      !(error instanceof ApiError && error.status === 404) && failureCount < 2,
  })
}

// 顧客の更新・削除は customers / dashboard に加え visits も無効化する
// （顧客名・owner_id が活動記録一覧の表示とリンク判定に使われるため。仕様）
export function useUpdateCustomer(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CustomerPatch) =>
      api.patch<CustomerOut>(`/api/customers/${id}`, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['customers'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      void queryClient.invalidateQueries({ queryKey: ['visits'] })
    },
  })
}

export function useDeleteCustomer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/api/customers/${id}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['customers'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      void queryClient.invalidateQueries({ queryKey: ['visits'] })
    },
  })
}
