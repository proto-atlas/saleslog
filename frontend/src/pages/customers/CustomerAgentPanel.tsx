import { Building2, FileText, UserRound } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router'

import {
  useAgentApprovals,
  useAgentArtifacts,
  useAgentRun,
  useAgentSources,
  useApproveAgentApproval,
  useCreateAgentRun,
  useCustomerAgentRuns,
  useEditAgentApproval,
  useRejectAgentApproval,
  isAgentApprovalDecisionSuccess,
  type AgentApprovalDecisionHttpResult,
} from '../../api/agent'
import type {
  AgentApprovalOut,
  AgentArtifactOut,
  AgentRunOut,
  AgentRunSourceOut,
  AgentWorkflowType,
} from '../../api/client'
import { ApiError, api } from '../../api/client'
import { Button } from '../../components/Button'
import { ErrorState } from '../../components/ErrorState'
import { useToast } from '../../components/toastContext'
import {
  buildApprovalPayload,
  buildPayloadDiffRows,
  getApprovalSubmitState,
  getBusinessRecordAnchorId,
  getBusinessRecordHref,
  hasPayloadChanges,
  isApprovalExpired,
  parseSseEvents,
  safeMessageLabel,
  validateApprovalPayload,
} from './customerAgentPanelHelpers'

const WORKFLOW_OPTIONS: { value: AgentWorkflowType; label: string }[] = [
  { value: 'meeting_prep', label: '商談準備' },
  { value: 'follow_up', label: 'フォローアップ作成' },
  { value: 'risk_review', label: '失注リスク確認' },
]

const RUN_STATUS_LABELS: Record<AgentRunOut['status'], string> = {
  pending: '準備中',
  running: '実行中',
  waiting_for_approval: '承認待ち',
  completed: '完了',
  failed: '失敗',
  cancelled: 'キャンセル済み',
}

const RUN_STATUS_COLORS: Record<AgentRunOut['status'], string> = {
  pending:              'bg-slate-100 text-slate-600',
  running:              'bg-blue-50 text-[#1D4ED8]',
  waiting_for_approval: 'bg-amber-50 text-amber-700',
  completed:            'bg-emerald-50 text-emerald-700',
  failed:               'bg-red-50 text-red-700',
  cancelled:            'bg-slate-100 text-slate-500',
}

const APPROVAL_STATUS_LABELS: Record<AgentApprovalOut['status'], string> = {
  pending:            '承認待ち',
  approved:           '承認済み',
  edited_and_approved:'編集承認済み',
  rejected:           '却下済み',
  persisted:          '保存済み',
  persist_failed:     '保存失敗',
  expired:            '期限切れ',
  cancelled:          'キャンセル済み',
}

const ACTION_TYPE_LABELS: Record<AgentApprovalOut['action_type'], string> = {
  activity_log: '活動記録',
  task:         'タスク',
  memo:         'メモ',
  email_draft:  'メール草案',
}

type AgentEventSummary = {
  eventSeq: number | null
  eventType: string
  safeMessageKey: string
}

type Props = {
  customerId: number
  runId: number | undefined
  onRunIdChange: (runId: number | undefined, options?: { replace?: boolean }) => void
}

export function CustomerAgentPanel({ customerId, runId, onRunIdChange }: Props) {
  const { showToast } = useToast()
  const [objective, setObjective] = useState('次回商談の準備をしたい')
  const [workflowType, setWorkflowType] = useState<AgentWorkflowType>('meeting_prep')
  const [eventSummariesByRunId, setEventSummariesByRunId] = useState<
    Record<number, AgentEventSummary[]>
  >({})
  const createRun = useCreateAgentRun(customerId)
  const runHistory = useCustomerAgentRuns(customerId)
  const run = useAgentRun(runId)
  const artifacts = useAgentArtifacts(runId)
  const approvals = useAgentApprovals(runId)
  const sources = useAgentSources(runId)

  const latestArtifact = useMemo(
    () => artifacts.data?.[artifacts.data.length - 1],
    [artifacts.data],
  )
  const displayRunStatus = useMemo(() => {
    const runStatus = run.data?.status
    if (
      (runStatus === 'pending' || runStatus === 'running') &&
      (approvals.data ?? []).some((approval) => approval.status === 'pending')
    ) {
      return 'waiting_for_approval'
    }
    return runStatus
  }, [approvals.data, run.data?.status])

  const eventSummaries = runId === undefined ? [] : (eventSummariesByRunId[runId] ?? [])

  useEffect(() => {
    if (runId !== undefined || runHistory.data === undefined || runHistory.data.length === 0) return
    onRunIdChange(runHistory.data[0].id, { replace: true })
  }, [onRunIdChange, runHistory.data, runId])

  useEffect(() => {
    if (runId === undefined) return
    let closed = false
    let lastSeq = 0
    const loadEvents = async () => {
      const text = await api
        .getText(`/api/agent-runs/${runId}/events`, {
          headers: { 'Last-Event-ID': String(lastSeq) },
        })
        .catch(() => '')
      if (closed) return
      const parsedEvents = parseSseEvents(text)
      if (parsedEvents.length === 0) return
      setEventSummariesByRunId((current) => ({
        ...current,
        [runId]: mergeEventsBySeq(current[runId] ?? [], parsedEvents),
      }))
      const numericSeqs = parsedEvents
        .map((event) => event.eventSeq)
        .filter((eventSeq): eventSeq is number => eventSeq !== null)
      if (numericSeqs.length > 0) lastSeq = Math.max(lastSeq, ...numericSeqs)
    }
    void loadEvents()
    const intervalId = window.setInterval(() => void loadEvents(), 1000)
    return () => { closed = true; window.clearInterval(intervalId) }
  }, [runId])

  const handleRun = () => {
    createRun.mutate(
      { objective, workflow_type: workflowType },
      {
        onSuccess: (created) => {
          const createdRunId = created.run_id ?? created.id
          setEventSummariesByRunId((current) => ({ ...current, [createdRunId]: [] }))
          onRunIdChange(createdRunId)
          showToast(
            created.reused ? '未完了の既存実行を表示しました' : 'Agent実行を開始しました',
            'success',
          )
        },
        onError: () => showToast('Agent実行を開始できませんでした', 'error'),
      },
    )
  }

  return (
    <section className="flex flex-col gap-5">
      {/* ── 実行パネル ── */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-[16px] font-semibold tracking-[-0.01em] text-slate-800">
            商談アシスタント
          </h2>
          <p className="mt-1 text-[13px] text-slate-600">
            活動履歴と社内ナレッジをもとに、次回商談の準備メモと承認候補を作成します。
          </p>
        </div>
      </div>

      <div className="grid gap-3 rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)] md:grid-cols-[1fr_14rem_auto]">
        <label className="flex flex-col gap-1.5 text-[13px] font-medium text-slate-500">
          目的
          <input
            value={objective}
            onChange={(event) => setObjective(event.target.value)}
            className="rounded-[8px] border-[1.5px] border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-[13px] font-medium text-slate-500">
          種類
          <select
            value={workflowType}
            onChange={(event) => setWorkflowType(event.target.value as AgentWorkflowType)}
            className="rounded-[8px] border-[1.5px] border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20"
          >
            {WORKFLOW_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <div className="flex items-end">
          <Button
            onClick={handleRun}
            disabled={createRun.isPending || objective.trim() === ''}
          >
            {createRun.isPending ? (
              '実行中…'
            ) : (
              <>
                <span aria-hidden="true">▶</span> 実行
              </>
            )}
          </Button>
        </div>
      </div>

      {/* ── 実行履歴 ── */}
      <AgentRunHistorySelect
        runs={runHistory.data ?? []}
        selectedRunId={runId}
        loading={runHistory.isPending}
        onSelect={onRunIdChange}
      />

      {run.isError ? (
        <ErrorState onRetry={() => void run.refetch()} />
      ) : run.data ? (
        <div className="grid gap-5 lg:grid-cols-[1fr_20rem]">
          <div className="flex flex-col gap-5">
            <RunSummary
              run={run.data}
              displayStatus={displayRunStatus ?? run.data.status}
              eventSummaries={eventSummaries}
            />
            {latestArtifact ? <ArtifactView artifact={latestArtifact} /> : null}
            <ApprovalList
              runId={run.data.id}
              runStatus={displayRunStatus ?? run.data.status}
              approvals={approvals.data ?? []}
              sources={sources.data ?? []}
              artifact={latestArtifact}
            />
          </div>
          <SourcesList sources={sources.data ?? []} artifact={latestArtifact} />
        </div>
      ) : null}
    </section>
  )
}

function mergeEventsBySeq(
  current: AgentEventSummary[],
  incoming: AgentEventSummary[],
) {
  const byKey = new Map<string, (typeof current)[number]>()
  for (const event of current) {
    byKey.set(event.eventSeq === null ? `${event.eventType}-${byKey.size}` : String(event.eventSeq), event)
  }
  for (const event of incoming) {
    byKey.set(event.eventSeq === null ? `${event.eventType}-${byKey.size}` : String(event.eventSeq), event)
  }
  return [...byKey.values()].sort((a, b) => {
    if (a.eventSeq === null || b.eventSeq === null) return 0
    return a.eventSeq - b.eventSeq
  })
}

// ── 実行履歴セレクタ（カードリスト形式） ──
function AgentRunHistorySelect({
  runs,
  selectedRunId,
  loading,
  onSelect,
}: {
  runs: AgentRunOut[]
  selectedRunId: number | undefined
  loading: boolean
  onSelect: (runId: number | undefined, options?: { replace?: boolean }) => void
}) {
  if (loading) {
    return <p className="text-sm text-slate-600">実行履歴を読み込み中です…</p>
  }
  if (runs.length === 0) {
    return <p className="text-sm text-slate-600">まだ実行履歴はありません</p>
  }
  return (
    <div>
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-slate-600">
        実行履歴
      </p>
      <div className="flex flex-col gap-2">
        {runs.map((historyRun) => {
          const isSelected = historyRun.id === selectedRunId
          return (
            <button
              key={historyRun.id}
              type="button"
              onClick={() => onSelect(historyRun.id)}
              className={`flex w-full items-center justify-between rounded-[9px] border px-4 py-3 text-left transition-colors ${
                isSelected
                  ? 'border-[#1D4ED8] bg-[#F0F4FF] shadow-[0_0_0_2px_rgba(61,111,255,0.12)]'
                  : 'border-slate-200/80 bg-white hover:border-[#1D4ED8]/40 hover:bg-[#F8FAFF]'
              }`}
            >
              <div>
                <span className="text-[13px] font-semibold text-slate-800">
                  #{historyRun.id} {historyRun.objective}
                </span>
              </div>
              <span
                className={`shrink-0 rounded-[5px] px-2 py-0.5 text-[11px] font-semibold ${RUN_STATUS_COLORS[historyRun.status]}`}
              >
                {RUN_STATUS_LABELS[historyRun.status]}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── 実行サマリー（プログレスステップ付き） ──
function RunSummary({
  run,
  displayStatus,
  eventSummaries,
}: {
  run: AgentRunOut
  displayStatus: AgentRunOut['status']
  eventSummaries: AgentEventSummary[]
}) {
  const isRunning = displayStatus === 'running' || displayStatus === 'pending'
  const providerLabel = run.provider === 'mock' ? 'サンプル生成' : '通常生成'

  return (
    <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-[13px] font-bold text-slate-800">実行 #{run.id}</p>
          <span className={`rounded-[5px] px-2 py-0.5 text-[11px] font-semibold ${RUN_STATUS_COLORS[displayStatus]}`}>
            {RUN_STATUS_LABELS[displayStatus]}
          </span>
          <span className="rounded-[5px] bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500">
            {providerLabel}
          </span>
        </div>
      </div>

      {/* プログレスバー（実行中のみ） */}
      {isRunning && eventSummaries.length > 0 && (
        <div className="mb-4">
          <div className="mb-1.5 flex items-center justify-between text-[11px] text-slate-600">
            <span>進行中...</span>
            <span>{eventSummaries.length} ステップ</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-[#1D4ED8] transition-all duration-500"
              style={{ width: `${Math.min(90, eventSummaries.length * 15)}%` }}
            />
          </div>
        </div>
      )}

      {/* ステップリスト */}
      {eventSummaries.length > 0 && (
        <ol className="flex flex-col gap-2">
          {eventSummaries.map((event, index) => {
            const isDone = !isRunning || index < eventSummaries.length - 1
            return (
              <li
                key={`${event.safeMessageKey}-${event.eventSeq ?? index}`}
                className="flex items-center gap-3 rounded-[7px] bg-slate-50 px-3 py-2"
              >
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                    isDone
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-[#EEF3FF] text-[#1D4ED8]'
                  }`}
                >
                  {isDone ? '✓' : (event.eventSeq ?? index + 1)}
                </span>
                <span className="text-[13px] font-medium text-slate-700">
                  {safeMessageLabel(event.safeMessageKey)}
                </span>
                {!isDone && isRunning && (
                  <span className="ml-auto text-[11px] text-slate-600">処理中…</span>
                )}
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}

function ArtifactView({ artifact }: { artifact: AgentArtifactOut }) {
  const summary = getSectionText(artifact.content_json, 'customer_summary')
  const brief = getSectionText(artifact.content_json, 'meeting_brief')
  const risks = getSectionItems(artifact.content_json, 'risks')
  const opportunities = getSectionItems(artifact.content_json, 'opportunities')
  const questions = getSectionItems(artifact.content_json, 'suggested_questions')
  const nextActions = getSectionItems(artifact.content_json, 'suggested_next_actions')
  const emailDraft = getRecord(artifact.content_json.follow_up_email_draft)
  const subject = getString(emailDraft, 'subject')
  const body = getString(emailDraft, 'body')

  return (
    <div className="grid gap-4">
      <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-[15px] font-bold tracking-[-0.01em] text-slate-800">
            商談準備メモ
          </h3>
          <span className="text-[11px] text-slate-600">根拠付きの準備メモ</span>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <ResultBlock title="顧客サマリー" body={summary} />
          <ResultBlock title="商談ブリーフ" body={brief} />
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <ResultItems title="注意点" items={risks} emptyMessage="注意点はありません" />
        <ResultItems title="機会" items={opportunities} />
      </div>
      <ResultItems title="確認したいこと" items={questions} emptyMessage="確認質問はありません" />
      <ResultItems title="次アクション" items={nextActions} emptyMessage="次アクションはありません" />
      <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
        <h3 className="mb-3 text-[13px] font-semibold text-slate-800">フォローアップ草案</h3>
        <p className="text-[13px] font-semibold text-slate-800">{subject}</p>
        <p className="mt-2 whitespace-pre-wrap text-[13px] text-slate-600">{body}</p>
      </div>
      <ClaimsList claims={artifact.claims_json} />
      <CitationList citations={artifact.citations_json} />
      <ResultItems
        title="不確実点"
        items={artifact.uncertainties_json}
        emptyMessage="不確実点はありません"
      />
    </div>
  )
}

function ApprovalList({
  runId,
  runStatus,
  approvals,
  sources,
  artifact,
}: {
  runId: number
  runStatus: AgentRunOut['status']
  approvals: AgentApprovalOut[]
  sources: AgentRunSourceOut[]
  artifact: AgentArtifactOut | undefined
}) {
  if (approvals.length === 0) return null
  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.07em] text-slate-600">
        保存前に確認する提案
      </h3>
      {approvals.map((approval) => (
        <ApprovalCard
          key={approval.id}
          runId={runId}
          runStatus={runStatus}
          approval={approval}
          sources={sources}
          artifact={artifact}
        />
      ))}
    </div>
  )
}

function ApprovalCard({
  runId,
  runStatus,
  approval,
  sources,
  artifact,
}: {
  runId: number
  runStatus: AgentRunOut['status']
  approval: AgentApprovalOut
  sources: AgentRunSourceOut[]
  artifact: AgentArtifactOut | undefined
}) {
  const { showToast } = useToast()
  const initialPayload = approval.edited_payload_json ?? approval.original_payload_json
  const initialTitle = getPayloadTitle(initialPayload)
  const initialDescription = getPayloadBody(initialPayload)
  const claimIds = getStringArray(approval.original_payload_json, 'claim_ids')
  const keepsClaimIds = Object.prototype.hasOwnProperty.call(
    approval.original_payload_json,
    'claim_ids',
  )
  const [title, setTitle] = useState(initialTitle)
  const [description, setDescription] = useState(initialDescription)
  const [approvalError, setApprovalError] = useState<string | null>(null)
  const edit = useEditAgentApproval(runId, approval.id)
  const approve = useApproveAgentApproval(runId, approval.id)
  const reject = useRejectAgentApproval(runId, approval.id)
  const expired = isApprovalExpired(approval.expires_at)
  const canOperate =
    approval.status === 'pending' && runStatus === 'waiting_for_approval' && !expired
  const validationErrors = validateApprovalPayload(approval.action_type, title, description)
  const serverValidationErrors = [approval.persist_error, approvalError].filter(
    (error): error is string => error !== null,
  )
  const originalTitle = getPayloadTitle(approval.original_payload_json)
  const originalDescription = getPayloadBody(approval.original_payload_json)
  const originalValidationErrors = validateApprovalPayload(
    approval.action_type,
    originalTitle,
    originalDescription,
  )
  const currentPayload = buildApprovalPayload(
    approval.action_type,
    title,
    description,
    claimIds,
    keepsClaimIds,
  )
  const diffRows = buildPayloadDiffRows(approval.original_payload_json, currentPayload)
  const hasEditedPayload = hasPayloadChanges(diffRows)
  const submitState = getApprovalSubmitState(
    canOperate,
    hasEditedPayload,
    originalValidationErrors,
    validationErrors,
    serverValidationErrors,
  )
  const businessHref = getBusinessRecordHref(
    approval.business_record_type,
    approval.business_record_id,
  )
  const businessAnchorId = getBusinessRecordAnchorId(
    approval.business_record_type,
    approval.business_record_id,
  )

  const handleApprove = (edited: boolean) => {
    setApprovalError(null)
    const approvePayload = {
      idempotency_key: crypto.randomUUID(),
      version: edited ? approval.version + 1 : approval.version,
    }
    const handleApproveSuccess = (result: AgentApprovalDecisionHttpResult, message: string) => {
      if (result.status === 200 && isAgentApprovalDecisionSuccess(result.body)) {
        showToast(message, 'success')
        return
      }
      const errorMessage = approvalDecisionErrorMessage(result)
      setApprovalError(errorMessage)
      showToast(errorMessage, 'error')
    }
    const handleApproveError = (error: Error) => {
      if (error instanceof ApiError && error.status === 422) setApprovalError(error.message)
      showToast('承認に失敗しました', 'error')
    }
    if (!edited) {
      approve.mutate(approvePayload, {
        onSuccess: (result) => handleApproveSuccess(result, '承認して保存しました'),
        onError: handleApproveError,
      })
      return
    }
    edit.mutate(
      { version: approval.version, edited_payload_json: currentPayload },
      {
        onSuccess: () =>
          approve.mutate(approvePayload, {
            onSuccess: (result) =>
              handleApproveSuccess(result, '編集内容を承認して保存しました'),
            onError: handleApproveError,
          }),
        onError: (error) => {
          if (error instanceof ApiError && error.status === 422) setApprovalError(error.message)
          showToast('編集内容を保存できませんでした', 'error')
        },
      },
    )
  }

  return (
    <div
      className={`rounded-[10px] border bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)] ${
        approval.status === 'pending' && !expired
          ? 'border-[#1D4ED8]/30'
          : 'border-slate-200/80'
      }`}
    >
      {/* ヘッダ行 */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-[13px] font-bold text-slate-800">
            {ACTION_TYPE_LABELS[approval.action_type]}
          </p>
          <span className="rounded-[5px] bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
            {APPROVAL_STATUS_LABELS[approval.status]}
          </span>
          {hasEditedPayload && (
            <span className="rounded-[5px] bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
              編集あり
            </span>
          )}
        </div>
        {approval.business_record_id !== null && approval.business_record_id !== undefined ? (
          <p id={businessAnchorId ?? undefined} className="text-[11px] text-slate-500">
            保存先:{' '}
            {businessHref === null ? (
              <span>{approval.business_record_type} #{approval.business_record_id}</span>
            ) : businessHref.startsWith('#') ? (
              <a href={businessHref} className="text-[#1D4ED8] hover:underline">
                {approval.business_record_type} #{approval.business_record_id}
              </a>
            ) : (
              <Link to={businessHref} className="text-[#1D4ED8] hover:underline">
                {approval.business_record_type} #{approval.business_record_id}
              </Link>
            )}
          </p>
        ) : null}
      </div>

      {/* 期限切れ警告 */}
      {expired && (
        <p className="mb-4 rounded-[8px] bg-red-50 px-4 py-3 text-[13px] text-red-700">
          承認期限が切れています。新しい提案を作成してください。
        </p>
      )}

      {/* 件名/タイトル入力 */}
      {approval.action_type !== 'activity_log' && (
        <label className="mb-3 flex flex-col gap-1.5 text-[13px] font-medium text-slate-500">
          {approval.action_type === 'email_draft' ? '件名' : 'タイトル'}
          <input
            value={title}
            disabled={!canOperate || edit.isPending || approve.isPending}
            onChange={(event) => { setApprovalError(null); setTitle(event.target.value) }}
            className="rounded-[8px] border-[1.5px] border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20 disabled:bg-slate-50 disabled:text-slate-600"
          />
        </label>
      )}

      {/* 本文入力 */}
      <label className="mb-4 flex flex-col gap-1.5 text-[13px] font-medium text-slate-500">
        {approval.action_type === 'email_draft' ? '本文' : '内容'}
        <textarea
          value={description}
          disabled={!canOperate || edit.isPending || approve.isPending}
          onChange={(event) => { setApprovalError(null); setDescription(event.target.value) }}
          className="min-h-24 rounded-[8px] border-[1.5px] border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20 disabled:bg-slate-50 disabled:text-slate-600"
        />
      </label>

      {/* プレビュー比較 */}
      <div className="mb-4 grid gap-3 md:grid-cols-2">
        <PayloadPreview title="元の提案" payload={approval.original_payload_json} />
        <PayloadPreview
          title={hasEditedPayload ? '編集後の内容' : '保存される内容'}
          payload={hasEditedPayload ? currentPayload : approval.original_payload_json}
        />
      </div>

      <PayloadDiff rows={diffRows} />
      <ValidationErrors
        errors={submitState.validationErrors}
        serverError={approval.persist_error}
      />
      <ApprovalSources approval={approval} sources={sources} artifact={artifact} />

      {/* ── アクションボタン（優先度順） ── */}
      <div className="mt-4 flex flex-wrap justify-end gap-2">
        {/* 却下: ghost danger */}
        <button
          type="button"
          disabled={!canOperate || reject.isPending}
          onClick={() =>
            reject.mutate(undefined, {
              onSuccess: () => showToast('提案を却下しました', 'success'),
              onError: () => showToast('却下に失敗しました', 'error'),
            })
          }
          className="rounded-[7px] px-4 py-2 text-sm font-semibold tracking-[0.01em] text-red-700 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          却下
        </button>
        {/* 編集して承認: secondary */}
        <Button
          variant="secondary"
          disabled={!submitState.canApproveEdited || edit.isPending || approve.isPending}
          onClick={() => handleApprove(true)}
        >
          編集して承認
        </Button>
        {/* 承認: primary */}
        <Button
          disabled={!submitState.canApproveOriginal || approve.isPending}
          onClick={() => handleApprove(false)}
        >
          承認
        </Button>
      </div>
    </div>
  )
}

function approvalDecisionErrorMessage(result: AgentApprovalDecisionHttpResult): string {
  const body = result.body
  if (!('error' in body)) return '承認に失敗しました'
  if (body.error.requires_reconciliation) return '承認状態を確認できませんでした。画面を更新してください'
  if (body.error.retry_with_new_idempotency_key) return '承認処理が完了していません。少し待って再実行してください'
  if (result.status === 202) return '承認処理中です。少し待ってから再実行してください'
  return '承認に失敗しました'
}

function ApprovalSources({
  approval,
  sources,
  artifact,
}: {
  approval: AgentApprovalOut
  sources: AgentRunSourceOut[]
  artifact: AgentArtifactOut | undefined
}) {
  const citations = artifact?.citations_json ?? []
  const claimIds = getStringArray(approval.original_payload_json, 'claim_ids')
  const proposalCitations =
    claimIds.length === 0
      ? citations
      : citations.filter((citation) => claimIds.includes(getString(citation, 'claim_id')))
  const proposalSources =
    proposalCitations.length === 0
      ? sources
      : sources.filter((source) =>
          proposalCitations.some((citation) => citationMatchesSource(citation, source)),
        )
  return (
    <div className="mt-4 rounded-[8px] border border-slate-200 bg-slate-50 p-4">
      <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-slate-600">
        関連根拠
      </h4>
      {proposalSources.length === 0 ? (
        <p className="text-[13px] text-slate-600">根拠情報はまだありません</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {proposalSources.slice(0, 5).map((source) => (
            <li key={source.id} className="flex items-start gap-2 text-[13px] text-slate-700">
              <SourceTypeIcon sourceType={source.source_type} className="mt-[1px]" />
              <div className="min-w-0">
                <span className="font-medium">{source.label}</span>
                <span className="ml-2">
                  <SourceDetailsToggle source={source} compact />
                </span>
                {proposalCitations.some((citation) => citationMatchesSource(citation, source)) && (
                  <span className="ml-2 text-[11px] text-slate-600">引用あり</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function SourcesList({
  sources,
  artifact,
}: {
  sources: AgentRunSourceOut[]
  artifact: AgentArtifactOut | undefined
}) {
  const citations = artifact?.citations_json ?? []
  const claims = artifact?.claims_json ?? []
  return (
    <aside className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
      <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.07em] text-slate-600">
        根拠
      </h3>
      <div className="flex flex-col gap-4">
        {sources.length === 0 ? (
          <p className="text-[13px] text-slate-600">根拠情報はまだありません</p>
        ) : (
          sources.map((source, index) => (
            <div
              key={`${source.label}-${index}`}
              id={`agent-source-${source.id}`}
              className="border-t border-slate-100 pt-4 first:border-t-0 first:pt-0"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <SourceTypeIcon sourceType={source.source_type} />
                  <p className="text-[13px] font-semibold text-slate-800">{source.label}</p>
                </div>
                <SourceDetailsToggle source={source} />
              </div>
              <p className="mt-1.5 text-[12px] text-slate-500">
                {source.source_excerpt ?? '根拠本文は保持期限切れ'}
              </p>
              <RelatedClaims source={source} citations={citations} claims={claims} />
            </div>
          ))
        )}
      </div>
    </aside>
  )
}

function CitationList({ citations }: { citations: Record<string, unknown>[] }) {
  return (
    <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
      <h3 className="mb-3 text-[13px] font-semibold text-slate-800">引用</h3>
      {citations.length === 0 ? (
        <p className="text-[13px] text-slate-600">引用はありません</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {citations.map((citation, index) => (
            <li key={getString(citation, 'citation_id') || index} className="text-[13px] text-slate-700">
              <span className="font-semibold">引用{index + 1}</span>
              <span className="ml-2 text-slate-500">
                {sourceTypeLabel(getString(citation, 'source_type'))}
                {getString(citation, 'source_id') ? ` #${getString(citation, 'source_id')}` : ''}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function PayloadPreview({
  title,
  payload,
}: {
  title: string
  payload: Record<string, unknown>
}) {
  const payloadTitle = getPayloadTitle(payload)
  const payloadBody = getPayloadBody(payload)
  return (
    <div className="rounded-[8px] bg-slate-50 p-4">
      <h4 className="mb-2 text-[11px] font-semibold text-slate-500">{title}</h4>
      {payloadTitle && (
        <p className="text-[13px] font-semibold text-slate-800">{payloadTitle}</p>
      )}
      <p className="mt-1 whitespace-pre-wrap text-[13px] text-slate-600">
        {payloadBody || '内容はありません'}
      </p>
    </div>
  )
}

function PayloadDiff({ rows }: { rows: ReturnType<typeof buildPayloadDiffRows> }) {
  const visibleRows = rows.filter((row) =>
    ['title', 'subject', 'description', 'body'].includes(row.key),
  )
  const changedRows = visibleRows.filter((row) => row.changed)
  if (changedRows.length === 0) return null
  return (
    <div className="mb-4 rounded-[8px] border border-amber-200 bg-amber-50 p-4">
      <h4 className="mb-2 text-[11px] font-semibold text-amber-700">編集内容</h4>
      <ul className="flex flex-col gap-2">
        {changedRows.map((row) => (
          <li key={row.key} className="text-[13px] text-amber-800">
            <span className="font-semibold">{payloadFieldLabel(row.key)}</span>
            <span className="ml-2">{row.before || '空'} → {row.after || '空'}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ValidationErrors({
  errors,
  serverError,
}: {
  errors: string[]
  serverError: string | null
}) {
  if (errors.length === 0 && serverError === null) return null
  return (
    <div className="mb-4 rounded-[8px] border border-red-200 bg-red-50 p-4">
      <h4 className="mb-2 text-[11px] font-semibold text-red-700">入力を確認してください</h4>
      <ul className="flex flex-col gap-1">
        {errors.map((error) => (
          <li key={error} className="text-[13px] text-red-700">{error}</li>
        ))}
        {serverError !== null && (
          <li className="text-[13px] text-red-700">保存エラー: {serverError}</li>
        )}
      </ul>
    </div>
  )
}

function SourceDetailsToggle({
  source,
  compact = false,
}: {
  source: AgentRunSourceOut
  compact?: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const location = useLocation()
  const returnTo = `${location.pathname}${location.search}`
  const sourceHref = getSourceOriginalHref(source, returnTo)
  return (
    <span className={compact ? 'inline-block' : 'block'}>
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
        className="text-[11px] font-medium text-[#1D4ED8] hover:underline"
      >
        {expanded ? '閉じる' : '詳細'}
      </button>
      {expanded && (
        <span className="mt-2 block rounded-[7px] border border-blue-100 bg-blue-50 p-3 text-[11px] text-slate-700">
          <span className="grid gap-1">
            <span>
              <span className="font-medium text-slate-500">種別: </span>
              {sourceTypeLabel(source.source_type)}
            </span>
            <span>
              <span className="font-medium text-slate-500">参照ID: </span>
              {source.source_id}
            </span>
          </span>
          {source.source_excerpt && (
            <span className="mt-2 block text-slate-600">{source.source_excerpt}</span>
          )}
          {sourceHref && (
            <Link
              to={sourceHref}
              className="mt-2 inline-block font-medium text-[#1D4ED8] hover:underline"
            >
              元画面を開く →
            </Link>
          )}
        </span>
      )}
    </span>
  )
}

function RelatedClaims({
  source,
  citations,
  claims,
}: {
  source: AgentRunSourceOut
  citations: Record<string, unknown>[]
  claims: Record<string, unknown>[]
}) {
  const relatedClaims = citations
    .filter((citation) => citationMatchesSource(citation, source))
    .map((citation) => claimTextForCitation(citation, claims))
    .filter(Boolean)
  const uniqueRelatedClaims = [...new Set(relatedClaims)]
  if (uniqueRelatedClaims.length === 0) return null
  return (
    <div className="mt-2">
      <p className="text-[10px] font-semibold uppercase tracking-[0.07em] text-slate-600">
        この根拠で支えている内容
      </p>
      <ul className="mt-1 flex flex-col gap-1">
        {uniqueRelatedClaims.map((claim) => (
          <li key={claim} className="text-[12px] text-slate-500">{claim}</li>
        ))}
      </ul>
    </div>
  )
}

function ResultBlock({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-[8px] bg-slate-50 p-4">
      <h3 className="mb-2 text-[12px] font-semibold text-slate-700">{title}</h3>
      <p className="text-[13px] text-slate-600">{body}</p>
    </div>
  )
}

function ResultItems({
  title,
  items,
  emptyMessage = '項目はありません',
}: {
  title: string
  items: Record<string, unknown>[]
  emptyMessage?: string
}) {
  return (
    <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
      <h3 className="mb-3 text-[13px] font-semibold text-slate-800">{title}</h3>
      {items.length === 0 ? (
        <p className="text-[13px] text-slate-600">{emptyMessage}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((item, index) => (
            <li key={index} className="text-[13px] text-slate-700">
              {getDisplayTitle(item) && (
                <span className="font-semibold">{getDisplayTitle(item)} </span>
              )}
              <span>{getDisplayBody(item)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ClaimsList({ claims }: { claims: Record<string, unknown>[] }) {
  return (
    <div className="rounded-[10px] border border-slate-200/80 bg-white p-5 shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
      <h3 className="mb-3 text-[13px] font-semibold text-slate-800">重要な主張</h3>
      {claims.length === 0 ? (
        <p className="text-[13px] text-slate-600">抽出された主張はありません</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {claims.map((claim, index) => (
            <li key={getString(claim, 'claim_id') || index} className="text-[13px] text-slate-700">
              {getString(claim, 'text') || '内容はありません'}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── ユーティリティ ──

function getRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}
function getString(record: Record<string, unknown>, key: string): string {
  const value = record[key]
  return typeof value === 'string' ? value : ''
}
function getStringArray(record: Record<string, unknown>, key: string): string[] {
  const value = record[key]
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}
function getSectionText(content: Record<string, unknown>, key: string): string {
  return getString(getRecord(content[key]), 'text')
}
function getSectionItems(content: Record<string, unknown>, key: string): Record<string, unknown>[] {
  const value = content[key]
  return Array.isArray(value) ? value.map(getRecord) : []
}
function getDisplayTitle(item: Record<string, unknown>): string {
  return getString(item, 'title') || getString(item, 'question') || getString(item, 'action')
}
function getDisplayBody(item: Record<string, unknown>): string {
  return getString(item, 'reason') || getString(item, 'text') || getString(item, 'description') || getString(item, 'detail')
}
function getPayloadTitle(payload: Record<string, unknown>): string {
  return getString(payload, 'title') || getString(payload, 'subject')
}
function getPayloadBody(payload: Record<string, unknown>): string {
  return getString(payload, 'description') || getString(payload, 'body')
}
function payloadFieldLabel(key: string): string {
  if (key === 'subject') return '件名'
  if (key === 'title') return 'タイトル'
  if (key === 'body' || key === 'description') return '本文'
  return key
}
function sourceTypeLabel(sourceType: string): string {
  if (sourceType === 'customer') return '顧客'
  if (sourceType === 'activity') return '活動履歴'
  return '社内ナレッジ'
}
function SourceTypeIcon({ sourceType, className = '' }: { sourceType: string; className?: string }) {
  const Icon = sourceType === 'customer'
    ? UserRound
    : sourceType === 'activity'
      ? FileText
      : Building2
  return (
    <Icon
      aria-hidden="true"
      className={`h-4 w-4 shrink-0 text-slate-500 ${className}`}
      strokeWidth={2}
    />
  )
}
function getSourceOriginalHref(source: AgentRunSourceOut, returnTo: string): string | null {
  if (source.source_type === 'activity') {
    return `/visits/${source.source_id}/edit?returnTo=${encodeURIComponent(returnTo)}`
  }
  return null
}
function citationMatchesSource(citation: Record<string, unknown>, source: AgentRunSourceOut): boolean {
  return (
    getString(citation, 'source_type') === source.source_type &&
    getString(citation, 'source_id') === source.source_id
  )
}
function claimTextForCitation(citation: Record<string, unknown>, claims: Record<string, unknown>[]): string {
  const claimId = getString(citation, 'claim_id')
  const claim = claims.find((item) => getString(item, 'claim_id') === claimId)
  return claim === undefined ? claimId : getString(claim, 'text') || claimId
}
