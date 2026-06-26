import { useEffect, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'

import { ApiError, type CustomerOut } from '../../api/client'
import { useCreateCustomer } from '../../api/customers'
import {
  CUSTOMER_AREA,
  CUSTOMER_STATUS,
  customerAreaLabels,
  customerStatusLabels,
} from '../../api/enums'
import { useMe, useUsers } from '../../api/users'
import { Button } from '../../components/Button'
import { Dialog } from '../../components/Dialog'
import { SelectField } from '../../components/form/SelectField'
import { TextField } from '../../components/form/TextField'
import { applyServerFieldErrors } from '../../lib/serverErrors'
import {
  customerFormSchema,
  toCreateBody,
  type CustomerFormInput,
  type CustomerFormOutput,
} from './customerFormSchema'

const FORM_FIELDS = ['name', 'address', 'area', 'status', 'owner_id'] as const

type Props = {
  open: boolean
  onClose: () => void
  onCreated: (customer: CustomerOut) => void
}

export function CustomerCreateDialog({ open, onClose, onCreated }: Props) {
  const me = useMe()
  const isManager = me.data?.role === 'manager'
  const currentUserId = me.data?.id
  const users = useUsers({ enabled: isManager })
  const createCustomer = useCreateCustomer()
  const [formError, setFormError] = useState<string | null>(null)
  const loadingError = me.isError
    ? 'ログイン情報を取得できませんでした'
    : isManager && users.isError
      ? '担当者一覧を取得できませんでした'
      : null
  const canSubmit =
    loadingError === null &&
    me.data !== undefined &&
    !createCustomer.isPending &&
    (!isManager || users.data !== undefined)

  const {
    register,
    handleSubmit,
    setError,
    setValue,
    reset,
    formState: { errors },
  } = useForm<CustomerFormInput, unknown, CustomerFormOutput>({
    resolver: zodResolver(customerFormSchema),
    defaultValues: {
      name: '',
      address: '',
      area: 'tokyo',
      status: 'prospect',
      owner_id: 1,
    },
  })

  useEffect(() => {
    if (open && isManager && currentUserId !== undefined) {
      setValue('owner_id', currentUserId)
    }
  }, [currentUserId, isManager, open, setValue])

  const close = () => {
    reset()
    setFormError(null)
    onClose()
  }

  const onSubmit = (values: CustomerFormOutput) => {
    setFormError(null)
    createCustomer.mutate(toCreateBody(values, { includeOwnerId: isManager }), {
      onSuccess: (customer) => {
        reset()
        onCreated(customer)
      },
      onError: (error) => {
        if (error instanceof ApiError && error.fieldErrors.length > 0) {
          const rest = applyServerFieldErrors(error.fieldErrors, setError, FORM_FIELDS)
          setFormError(rest)
        } else {
          setFormError('保存に失敗しました。もう一度お試しください')
        }
      },
    })
  }

  return (
    <Dialog open={open} onClose={close} title="顧客を登録">
      <form
        onSubmit={(event) => void handleSubmit(onSubmit)(event)}
        noValidate
        className="flex flex-col gap-4"
      >
        <TextField
          label="顧客名"
          error={errors.name?.message}
          {...register('name')}
        />
        <TextField
          label="住所（任意）"
          error={errors.address?.message}
          {...register('address')}
        />
        <SelectField label="エリア" error={errors.area?.message} {...register('area')}>
          {CUSTOMER_AREA.map((area) => (
            <option key={area} value={area}>
              {customerAreaLabels[area]}
            </option>
          ))}
        </SelectField>
        <SelectField
          label="ステータス"
          error={errors.status?.message}
          {...register('status')}
        >
          {CUSTOMER_STATUS.map((status) => (
            <option key={status} value={status}>
              {customerStatusLabels[status]}
            </option>
          ))}
        </SelectField>
        {isManager && (
          <SelectField
            label="担当者"
            error={errors.owner_id?.message}
            {...register('owner_id')}
          >
            {(users.data?.items ?? []).map((user) => (
              <option key={user.id} value={user.id}>
                {user.name}
              </option>
            ))}
          </SelectField>
        )}

        {(loadingError ?? formError) !== null && (
          <p role="alert" className="rounded-[8px] bg-red-50 px-3 py-2.5 text-sm text-red-800">
            {loadingError ?? formError}
          </p>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={close}>
            キャンセル
          </Button>
          <Button type="submit" disabled={!canSubmit}>
            {createCustomer.isPending ? '保存中…' : '登録する'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
