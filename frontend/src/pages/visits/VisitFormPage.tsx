import { useEffect, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useBlocker, useNavigate, useParams, useSearchParams } from 'react-router'

import { ApiError } from '../../api/client'
import { useCustomersList } from '../../api/customers'
import {
  ACTIVITY_TYPE,
  VISIT_STATUS,
  activityTypeLabels,
  visitStatusLabels,
} from '../../api/enums'
import { useMe } from '../../api/users'
import { useCreateVisit, useUpdateVisit, useVisit } from '../../api/visits'
import { authEnabled } from '../../auth/authConfig'
import { Button } from '../../components/Button'
import { Dialog } from '../../components/Dialog'
import { ErrorState } from '../../components/ErrorState'
import { SelectField } from '../../components/form/SelectField'
import { TextField } from '../../components/form/TextField'
import { TextareaField } from '../../components/form/TextareaField'
import { useToast } from '../../components/toastContext'
import { useFormDraft } from '../../hooks/useFormDraft'
import { applyServerFieldErrors } from '../../lib/serverErrors'
import {
  toCreateBody,
  toPatchBody,
  utcIsoToLocalInput,
  visitFormSchema,
  type VisitFormInput,
  type VisitFormOutput,
} from './visitFormSchema'

const FORM_FIELDS = [
  'customer_id',
  'activity_type',
  'status',
  'visited_at',
  'memo',
] as const

const CUSTOMER_OPTIONS_PAGE_SIZE = 100

function newDefaults(customerId: string | null, status: string | null): VisitFormInput {
  return {
    customer_id: customerId !== null && /^\d+$/.test(customerId) ? customerId : '',
    activity_type: 'visit',
    status: status === 'planned' ? 'planned' : 'done',
    visited_at: utcIsoToLocalInput(new Date().toISOString()),
    memo: '',
  } as VisitFormInput
}

export function VisitFormPage() {
  const { id: idParam } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { showToast } = useToast()
  const returnTo = safeReturnTo(searchParams.get('returnTo'))

  const isEdit = idParam !== undefined
  const visitId =
    isEdit && /^\d+$/.test(idParam) ? Number(idParam) : undefined
  const visit = useVisit(visitId)
  const customers = useCustomersList({ page_size: CUSTOMER_OPTIONS_PAGE_SIZE })
  const createVisit = useCreateVisit()
  const updateVisit = useUpdateVisit(visitId ?? -1)

  const [formError, setFormError] = useState<string | null>(null)
  const [savedCustomerId, setSavedCustomerId] = useState<number | null>(null)
  const [savedNavigateTo, setSavedNavigateTo] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    setError,
    reset,
    control,
    formState: { errors, isDirty },
  } = useForm<VisitFormInput, unknown, VisitFormOutput>({
    resolver: zodResolver(visitFormSchema),
    defaultValues: newDefaults(
      searchParams.get('customer_id'),
      searchParams.get('status'),
    ),
  })

  useEffect(() => {
    if (isEdit && visit.data !== undefined) {
      reset({
        customer_id: String(visit.data.customer_id),
        activity_type: visit.data.activity_type,
        status: visit.data.status,
        visited_at: utcIsoToLocalInput(visit.data.visited_at),
        memo: visit.data.memo ?? '',
      } as VisitFormInput)
    }
  }, [isEdit, visit.data, reset])

  const me = useMe()
  const watchedValues = useWatch({ control })
  const draftUserSuffix =
    authEnabled && me.data !== undefined ? `:${me.data.id}` : ''
  const draftKey = isEdit
    ? `draft:visit:${idParam}${draftUserSuffix}`
    : `draft:visit:new${draftUserSuffix}`
  const draft = useFormDraft({
    key: draftKey,
    values: watchedValues,
    enabled:
      isDirty &&
      (!isEdit || visit.data !== undefined) &&
      (!authEnabled || me.data !== undefined),
  })

  const blocker = useBlocker(
    isDirty && savedCustomerId === null && savedNavigateTo === null,
  )
  useEffect(() => {
    if (!isDirty || savedCustomerId !== null || savedNavigateTo !== null) return
    const handler = (event: BeforeUnloadEvent) => { event.preventDefault() }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty, savedCustomerId, savedNavigateTo])

  useEffect(() => {
    if (savedNavigateTo !== null) {
      void navigate(savedNavigateTo)
    }
  }, [savedNavigateTo, navigate])

  if (isEdit && visitId === undefined) {
    return <ErrorState message="活動記録が見つかりません" onRetry={() => void navigate('/visits')} />
  }
  if (isEdit && visit.isError) {
    const notFound = visit.error instanceof ApiError && visit.error.status === 404
    return (
      <ErrorState
        message={notFound ? '活動記録が見つかりません' : undefined}
        onRetry={() => (notFound ? void navigate('/visits') : void visit.refetch())}
      />
    )
  }

  const onSubmit = (values: VisitFormOutput) => {
    setFormError(null)
    const handleError = (error: Error) => {
      if (error instanceof ApiError && error.fieldErrors.length > 0) {
        const rest = applyServerFieldErrors(error.fieldErrors, setError, FORM_FIELDS)
        setFormError(rest)
      } else {
        setFormError('保存に失敗しました。もう一度お試しください')
      }
    }
    if (isEdit) {
      updateVisit.mutate(toPatchBody(values), {
        onSuccess: () => {
          draft.clearDraft()
          reset(undefined, { keepValues: true })
          showToast('活動記録を更新しました', 'success')
          setSavedNavigateTo(returnTo ?? '/visits')
        },
        onError: handleError,
      })
    } else {
      createVisit.mutate(toCreateBody(values), {
        onSuccess: (created) => {
          draft.clearDraft()
          reset(undefined, { keepValues: true })
          setSavedCustomerId(created.customer_id)
        },
        onError: handleError,
      })
    }
  }

  const continueWithPlanned = () => {
    if (savedCustomerId === null) return
    const next = newDefaults(String(savedCustomerId), 'planned')
    reset(next)
    setSavedCustomerId(null)
    void navigate(`/visits/new?customer_id=${savedCustomerId}&status=planned`, { replace: true })
  }

  const isPending = createVisit.isPending || updateVisit.isPending

  return (
    <section className="mx-auto flex max-w-xl flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-[22px] font-bold tracking-[-0.02em] text-slate-800">
          {isEdit ? '活動記録の編集' : '活動記録の登録'}
        </h1>
        {returnTo !== null && (
          <Link
            to={returnTo}
            className="text-sm font-medium text-[#1D4ED8] hover:underline"
          >
            ← Agent結果へ戻る
          </Link>
        )}
      </div>

      {savedCustomerId !== null ? (
        <div className="flex flex-col gap-4 rounded-[10px] border border-emerald-200 bg-emerald-50 p-6">
          <p className="font-semibold text-emerald-800">✓ 活動記録を保存しました</p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void navigate(`/customers/${savedCustomerId}`)}>
              顧客詳細を見る
            </Button>
            <Button variant="secondary" onClick={continueWithPlanned}>
              続けて次回予定を登録
            </Button>
          </div>
        </div>
      ) : (
        <form
          onSubmit={(event) => void handleSubmit(onSubmit)(event)}
          noValidate
          className="flex flex-col gap-4"
        >
          {/* 基本情報カード */}
          <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.05)]">
            <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.07em] text-slate-600">
              基本情報
            </p>
            <div className="flex flex-col gap-4">
              {isEdit ? (
                <div className="flex flex-col gap-1.5">
                  <span className="text-[13px] font-medium text-slate-500">顧客</span>
                  <p className="rounded-[8px] border-[1.5px] border-slate-100 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                    {customers.data?.items.find(
                      (item) => item.id === visit.data?.customer_id,
                    )?.name ?? `ID: ${visit.data?.customer_id ?? ''}`}
                  </p>
                  <input type="hidden" {...register('customer_id')} />
                </div>
              ) : customers.data === undefined ? (
                <SelectField label="顧客" disabled value="">
                  <option value="">読み込み中…</option>
                </SelectField>
              ) : (
                <SelectField
                  label="顧客"
                  error={errors.customer_id?.message}
                  {...register('customer_id')}
                >
                  <option value="">選択してください</option>
                  {customers.data.items.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </SelectField>
              )}

              <div className="grid grid-cols-2 gap-4">
                <SelectField
                  label="活動種別"
                  error={errors.activity_type?.message}
                  {...register('activity_type')}
                >
                  {ACTIVITY_TYPE.map((type) => (
                    <option key={type} value={type}>
                      {activityTypeLabels[type]}
                    </option>
                  ))}
                </SelectField>

                <SelectField
                  label="ステータス"
                  error={errors.status?.message}
                  {...register('status')}
                >
                  {VISIT_STATUS.map((status) => (
                    <option key={status} value={status}>
                      {visitStatusLabels[status]}
                    </option>
                  ))}
                </SelectField>
              </div>

              <TextField
                label="日時"
                type="datetime-local"
                error={errors.visited_at?.message}
                {...register('visited_at')}
              />
            </div>
          </div>

          {/* メモカード */}
          <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.05)]">
            <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.07em] text-slate-600">
              メモ
            </p>
            <TextareaField
              label="内容（任意）"
              error={errors.memo?.message}
              maxLength={2000}
              {...register('memo')}
            />
          </div>

          {formError !== null && (
            <p role="alert" className="rounded-[8px] bg-red-50 px-4 py-3 text-sm text-red-800">
              {formError}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <Link
              to={isEdit ? '/visits' : '/customers'}
              className="rounded-[7px] border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
            >
              キャンセル
            </Link>
            <Button type="submit" disabled={isPending}>
              {isPending ? '保存中…' : '保存する'}
            </Button>
          </div>
        </form>
      )}

      <Dialog
        open={blocker.state === 'blocked'}
        onClose={() => blocker.reset?.()}
        title="未保存の変更があります"
      >
        <div className="flex flex-col gap-5">
          <p className="text-sm text-slate-600">
            このページを離れると入力した内容は失われます。移動しますか？
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => blocker.reset?.()}>
              とどまる
            </Button>
            <Button onClick={() => blocker.proceed?.()}>移動する</Button>
          </div>
        </div>
      </Dialog>

      <Dialog
        open={draft.pendingDraft !== null && savedCustomerId === null}
        onClose={draft.acceptDraft}
        title="前回の入力内容があります"
      >
        <div className="flex flex-col gap-5">
          <p className="text-sm text-slate-600">
            保存されていない前回の入力内容が見つかりました。復元しますか？
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={draft.discardDraft}>
              破棄する
            </Button>
            <Button
              onClick={() => {
                if (draft.pendingDraft !== null) {
                  reset(draft.pendingDraft as VisitFormInput, { keepDefaultValues: true })
                }
                draft.acceptDraft()
              }}
            >
              復元する
            </Button>
          </div>
        </div>
      </Dialog>
    </section>
  )
}

function safeReturnTo(value: string | null): string | null {
  if (value === null || !value.startsWith('/') || value.startsWith('//')) return null
  return value
}
