import { useState } from 'react'
import { Link } from 'react-router'

import { ApiError } from '../../api/client'
import { USER_ROLE, userRoleLabels, type UserRole } from '../../api/enums'
import { useCreateUser, useMe, useUpdateUser, useUsers } from '../../api/users'
import { Button } from '../../components/Button'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { SelectField } from '../../components/form/SelectField'
import { TextField } from '../../components/form/TextField'
import { useToast } from '../../components/toastContext'

function errorMessage(error: Error): string {
  if (error instanceof ApiError && error.fieldErrors.length > 0) {
    return error.fieldErrors[0].msg
  }
  return '操作に失敗しました。もう一度お試しください'
}

export function AdminUsersPage() {
  const me = useMe()
  const users = useUsers()
  const createUser = useCreateUser()
  const updateUser = useUpdateUser()
  const { showToast } = useToast()

  const [newName, setNewName] = useState('')
  const [newRole, setNewRole] = useState<UserRole>('sales')
  const [linkInputs, setLinkInputs] = useState<Record<number, string>>({})

  if (me.isPending) {
    return <div className="h-40 animate-pulse rounded-[10px] bg-slate-200" aria-busy="true" />
  }
  const meData = me.data
  if (meData === undefined || meData.role !== 'manager') {
    return (
      <EmptyState
        title="ページが見つかりません"
        action={
          <Link to="/" className="text-sm font-medium text-[#1D4ED8] hover:underline">
            ダッシュボードへ戻る
          </Link>
        }
      />
    )
  }

  const handleCreate = () => {
    createUser.mutate(
      { name: newName, role: newRole },
      {
        onSuccess: (user) => {
          setNewName('')
          showToast(`ユーザー「${user.name}」を追加しました`, 'success')
        },
        onError: (error) => showToast(errorMessage(error), 'error'),
      },
    )
  }

  const handleRoleChange = (userId: number, role: UserRole) => {
    updateUser.mutate(
      { id: userId, body: { role } },
      {
        onSuccess: () => showToast('役割を更新しました', 'success'),
        onError: (error) => showToast(errorMessage(error), 'error'),
      },
    )
  }

  const handleLink = (userId: number) => {
    const value = (linkInputs[userId] ?? '').trim()
    updateUser.mutate(
      { id: userId, body: { external_id: value === '' ? null : value } },
      {
        onSuccess: () => {
          setLinkInputs((current) => ({ ...current, [userId]: '' }))
          showToast(value === '' ? '紐付けを解除しました' : '紐付けました', 'success')
        },
        onError: (error) => showToast(errorMessage(error), 'error'),
      },
    )
  }

  return (
    <section className="flex flex-col gap-6">
      <h1 className="text-[22px] font-bold tracking-[-0.02em] text-slate-800">
        ユーザー管理
      </h1>

      {/* ユーザー追加カード */}
      <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
        <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.07em] text-slate-600">
          ユーザーを追加
        </h2>
        <div className="flex flex-wrap items-end gap-4">
          <TextField
            label="名前"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            maxLength={80}
          />
          <SelectField
            label="役割"
            value={newRole}
            onChange={(event) => setNewRole(event.target.value as UserRole)}
          >
            {USER_ROLE.map((role) => (
              <option key={role} value={role}>
                {userRoleLabels[role]}
              </option>
            ))}
          </SelectField>
          <Button
            onClick={handleCreate}
            disabled={createUser.isPending || newName.trim() === ''}
          >
            追加する
          </Button>
        </div>
      </div>

      {/* ユーザーテーブル */}
      {users.isPending ? (
        <div className="h-48 animate-pulse rounded-[10px] bg-slate-200" aria-busy="true" />
      ) : users.isError ? (
        <ErrorState onRetry={() => void users.refetch()} />
      ) : (
        <div className="overflow-x-auto rounded-[10px] border border-slate-200/80 bg-white shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100">
                <th scope="col" className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-600">
                  名前
                </th>
                <th scope="col" className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-600">
                  役割
                </th>
                <th scope="col" className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-600">
                  サインイン紐付け
                </th>
              </tr>
            </thead>
            <tbody>
              {users.data.items.map((user, index) => (
                <tr
                  key={user.id}
                  className={`border-t border-slate-50 ${index % 2 === 1 ? 'bg-slate-50/40' : 'bg-white'}`}
                >
                  <td className="px-4 py-3 text-[13px] font-semibold text-slate-800">
                    {user.name}
                  </td>
                  <td className="px-4 py-3">
                    <label className="sr-only" htmlFor={`role-${user.id}`}>
                      {user.name} の役割
                    </label>
                    <select
                      id={`role-${user.id}`}
                      value={user.role ?? 'sales'}
                      disabled={
                        updateUser.isPending ||
                        user.id === meData.id ||
                        user.role === null ||
                        user.role === undefined
                      }
                      onChange={(event) =>
                        handleRoleChange(user.id, event.target.value as UserRole)
                      }
                      className="rounded-[8px] border-[1.5px] border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-700 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20 disabled:bg-slate-100 disabled:text-slate-600"
                    >
                      {USER_ROLE.map((role) => (
                        <option key={role} value={role}>
                          {userRoleLabels[role]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`inline-block rounded-[5px] px-2 py-0.5 text-[11px] font-semibold ${
                          user.linked
                            ? 'bg-emerald-50 text-emerald-700'
                            : 'bg-slate-200 text-slate-700'
                        }`}
                      >
                        {user.linked ? '紐付け済み' : '未紐付け'}
                      </span>
                      <label className="sr-only" htmlFor={`link-${user.id}`}>
                        {user.name} のサインインID
                      </label>
                      <input
                        id={`link-${user.id}`}
                        type="text"
                        placeholder="サインインIDで紐付け"
                        value={linkInputs[user.id] ?? ''}
                        disabled={user.id === meData.id}
                        onChange={(event) =>
                          setLinkInputs((current) => ({
                            ...current,
                            [user.id]: event.target.value,
                          }))
                        }
                        className="w-56 rounded-[8px] border-[1.5px] border-slate-200 px-2.5 py-1.5 text-sm text-slate-700 placeholder:text-slate-600 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20 disabled:bg-slate-100 disabled:text-slate-600"
                      />
                      <Button
                        variant="secondary"
                        disabled={updateUser.isPending || user.id === meData.id}
                        onClick={() => handleLink(user.id)}
                      >
                        {(linkInputs[user.id] ?? '').trim() === '' ? '解除' : '紐付け'}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
