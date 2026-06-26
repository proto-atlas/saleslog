import type { AgentApprovalOut } from '../../api/client'

export type ParsedSseEvent = {
  eventSeq: number | null
  eventType: string
  safeMessageKey: string
}

export type PayloadDiffRow = {
  key: string
  before: string
  after: string
  changed: boolean
}

export type ApprovalSubmitState = {
  canApproveOriginal: boolean
  canApproveEdited: boolean
  validationErrors: string[]
}

const APPROVAL_TEXT_LIMITS = {
  title: 160,
  subject: 200,
  description: 2000,
  body: 5000,
} as const

export function parseSseEvents(text: string): ParsedSseEvent[] {
  return text
    .split(/\n\s*\n/)
    .map(parseSseEvent)
    .filter((event) => event.safeMessageKey !== '')
}

export function parseSseEventKeys(text: string): string[] {
  return parseSseEvents(text).map((event) => event.safeMessageKey)
}

export function buildPayloadDiffRows(
  originalPayload: Record<string, unknown>,
  editedPayload: Record<string, unknown> | null,
): PayloadDiffRow[] {
  if (editedPayload === null) {
    return []
  }
  const keys = Array.from(
    new Set([...Object.keys(originalPayload), ...Object.keys(editedPayload)]),
  ).sort()
  return keys.map((key) => {
    const before = stringifyJsonValue(originalPayload[key])
    const after = stringifyJsonValue(editedPayload[key])
    return { key, before, after, changed: before !== after }
  })
}

export function hasPayloadChanges(rows: PayloadDiffRow[]): boolean {
  return rows.some((row) => row.changed)
}

export function getApprovalSubmitState(
  canOperate: boolean,
  hasEditedPayload: boolean,
  originalValidationErrors: string[],
  editedValidationErrors: string[],
  serverValidationErrors: string[] = [],
): ApprovalSubmitState {
  const validationErrors = [
    ...(hasEditedPayload ? editedValidationErrors : originalValidationErrors),
    ...serverValidationErrors,
  ]
  return {
    canApproveOriginal:
      canOperate && validationErrors.length === 0 && !hasEditedPayload,
    canApproveEdited:
      canOperate && validationErrors.length === 0 && hasEditedPayload,
    validationErrors,
  }
}

export function stringifyJsonValue(value: unknown): string {
  if (value === null || value === undefined) {
    return ''
  }
  if (typeof value === 'string') {
    return value
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  return JSON.stringify(value)
}

export function buildApprovalPayload(
  actionType: AgentApprovalOut['action_type'],
  title: string,
  description: string,
  claimIds: string[] = [],
  includeClaimIds = claimIds.length > 0,
): Record<string, unknown> {
  const claimFields = includeClaimIds ? { claim_ids: claimIds } : {}
  if (actionType === 'email_draft') {
    return { subject: title, body: description, ...claimFields }
  }
  if (actionType === 'memo') {
    return { title, body: description, ...claimFields }
  }
  if (actionType === 'activity_log') {
    return { description, ...claimFields }
  }
  return { title, description, ...claimFields }
}

export function validateApprovalPayload(
  actionType: AgentApprovalOut['action_type'],
  title: string,
  description: string,
): string[] {
  const errors: string[] = []
  const titleField = titleFieldForAction(actionType)
  const bodyField = bodyFieldForAction(actionType)
  if (titleField !== null) {
    validateRequiredText(titleField, title, errors)
  }
  validateRequiredText(bodyField, description, errors)
  return errors
}

export function isApprovalExpired(expiresAt: string | null, nowMs = Date.now()): boolean {
  if (expiresAt === null) {
    return false
  }
  const expiresAtMs = Date.parse(expiresAt)
  return Number.isFinite(expiresAtMs) && expiresAtMs < nowMs
}

export function getBusinessRecordAnchorId(
  businessRecordType: string | null,
  businessRecordId: number | null,
): string | null {
  if (businessRecordType === null || businessRecordId === null) {
    return null
  }
  return `agent-business-record-${businessRecordType.replaceAll('_', '-')}-${businessRecordId}`
}

export function getBusinessRecordHref(
  businessRecordType: string | null,
  businessRecordId: number | null,
): string | null {
  if (businessRecordType === null || businessRecordId === null) {
    return null
  }
  if (businessRecordType === 'visits' || businessRecordType === 'visit') {
    return `/visits/${businessRecordId}/edit`
  }
  return `#${getBusinessRecordAnchorId(businessRecordType, businessRecordId)}`
}

export function safeMessageLabel(key: string): string {
  const labels: Record<string, string> = {
    run_created: 'Agent実行を開始しました',
    customer_loaded: '顧客情報を確認しました',
    activities_loaded: '活動履歴を確認しました',
    knowledge_search_completed: '社内ナレッジを検索しました',
    drafting_completed: '草案を作成しました',
    citation_verified: '根拠情報を確認しました',
    approval_required: '承認待ちの提案があります',
    waiting_for_approval: '承認待ちです',
    completed: '完了しました',
    failed: '実行に失敗しました',
    cancelled: 'キャンセル済みです',
  }
  return labels[key] ?? key
}

function titleFieldForAction(
  actionType: AgentApprovalOut['action_type'],
): keyof typeof APPROVAL_TEXT_LIMITS | null {
  if (actionType === 'activity_log') {
    return null
  }
  if (actionType === 'email_draft') {
    return 'subject'
  }
  return 'title'
}

function bodyFieldForAction(
  actionType: AgentApprovalOut['action_type'],
): keyof typeof APPROVAL_TEXT_LIMITS {
  if (actionType === 'email_draft' || actionType === 'memo') {
    return 'body'
  }
  return 'description'
}

function validateRequiredText(
  field: keyof typeof APPROVAL_TEXT_LIMITS,
  value: string,
  errors: string[],
): void {
  const trimmed = value.trim()
  if (trimmed === '') {
    errors.push(`${field} は必須です`)
    return
  }
  if (trimmed.length > APPROVAL_TEXT_LIMITS[field]) {
    errors.push(`${field} は${APPROVAL_TEXT_LIMITS[field]}文字以内で入力してください`)
  }
}

function parseSseEvent(block: string): ParsedSseEvent {
  const lines = block.split('\n')
  const idLine = lines.find((line) => line.startsWith('id: '))
  const eventLine = lines.find((line) => line.startsWith('event: '))
  const dataLine = lines.find((line) => line.startsWith('data: '))
  const eventSeq = parseEventSeq(idLine)
  const eventType = eventLine?.replace('event: ', '') ?? ''
  const safeMessageKey = parseSafeMessageKey(dataLine)
  return { eventSeq, eventType, safeMessageKey }
}

function parseEventSeq(line: string | undefined): number | null {
  if (line === undefined) {
    return null
  }
  const value = Number(line.replace('id: ', ''))
  return Number.isInteger(value) ? value : null
}

function parseSafeMessageKey(line: string | undefined): string {
  if (line === undefined) {
    return ''
  }
  try {
    const parsed: unknown = JSON.parse(line.replace('data: ', ''))
    return getString(getRecord(parsed), 'safe_message_key')
  } catch {
    return ''
  }
}

function getRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function getString(record: Record<string, unknown>, key: string): string {
  const value = record[key]
  return typeof value === 'string' ? value : ''
}
