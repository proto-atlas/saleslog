import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  api,
  type UserCreate,
  type UserOut,
  type UserPatch,
  type UsersResponse,
} from './client'

export const usersKeys = {
  all: ['users'] as const,
  list: () => ['users', 'list'] as const,
  me: () => ['users', 'me'] as const,
}
const USERS_API = '/api/users'

type UseUsersOptions = {
  enabled?: boolean
}

function userApiPath(id: number) {
  return `${USERS_API}/${id}`
}

// 自分の id / role（UI の出し分け用。データの強制はサーバ側。認証仕様）
export function useMe() {
  return useQuery({
    queryKey: usersKeys.me(),
    queryFn: () => api.get<UserOut>('/api/me'),
    staleTime: 5 * 60 * 1000,
  })
}

export function useUsers(options: UseUsersOptions = {}) {
  return useQuery({
    queryKey: usersKeys.list(),
    queryFn: () => api.get<UsersResponse>(USERS_API),
    enabled: options.enabled ?? true,
    // 担当者マスタは画面操作中に変わらない前提で再取得を抑える
    staleTime: 5 * 60 * 1000,
  })
}

// --- ユーザー管理（manager のみ。認証仕様） ---

export function useCreateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UserCreate) => api.post<UserOut>(USERS_API, body),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useUpdateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: UserPatch }) =>
      api.patch<UserOut>(userApiPath(id), body),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['users'] }),
  })
}
