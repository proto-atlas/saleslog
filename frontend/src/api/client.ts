import type { components } from './generated/schema'
import { staticDemoEnabled } from '../demoMode'
import {
  handleStaticDemoRequest,
  handleStaticDemoTextRequest,
} from './staticDemo'

export type CustomerOut = components['schemas']['CustomerOut']
export type CustomerListItem = components['schemas']['CustomerListItem']
export type CustomerCreate = components['schemas']['CustomerCreate']
export type CustomerPatch = components['schemas']['CustomerPatch']
export type CustomersListResponse =
  components['schemas']['ListResponse_CustomerListItem_']
export type UserOut = components['schemas']['UserOut']
export type UsersResponse = components['schemas']['UsersResponse']
export type UserCreate = components['schemas']['UserCreate']
export type UserPatch = components['schemas']['UserPatch']
export type VisitOut = components['schemas']['VisitOut']
export type VisitCreate = components['schemas']['VisitCreate']
export type VisitPatch = components['schemas']['VisitPatch']
export type VisitListItem = components['schemas']['VisitListItem']
export type VisitsListResponse = components['schemas']['ListResponse_VisitListItem_']
export type DashboardSummary = components['schemas']['DashboardSummary']
export type TodayVisit = components['schemas']['TodayVisit']
export type AgentRunCreate = components['schemas']['AgentRunCreate']
export type AgentRunCreateResponse = components['schemas']['AgentRunCreateResponse']
export type AgentRunOut = components['schemas']['AgentRunOut']
export type AgentArtifactOut = components['schemas']['AgentArtifactOut']
export type AgentRunSourceOut = components['schemas']['AgentRunSourceOut']
export type AgentApprovalOut = components['schemas']['AgentApprovalOut']
export type AgentApprovalPatch = components['schemas']['AgentApprovalPatch']
export type AgentApprovalDecision = components['schemas']['AgentApprovalDecision']
export type AgentApprovalDecisionResponse =
  components['schemas']['AgentApprovalDecisionResponse']
export type AgentApprovalDecisionErrorResponse =
  components['schemas']['AgentApprovalDecisionErrorResponse']
export type HTTPValidationError = components['schemas']['HTTPValidationError']
export type AgentWorkflowType = components['schemas']['AgentWorkflowType']
export type AgentRunStatus = components['schemas']['AgentRunStatus']
export type AgentApprovalStatus = components['schemas']['AgentApprovalStatus']
export type ApiResponse<T> = {
  status: number
  body: T
}

// 422 detail の公開項目。input / url はサーバ側で除去済み。
export type ValidationErrorItem = {
  loc: (string | number)[]
  msg: string
  type: string
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: string | ValidationErrorItem[]

  constructor(status: number, detail: string | ValidationErrorItem[]) {
    super(typeof detail === 'string' ? detail : '入力内容を確認してください')
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }

  get fieldErrors(): ValidationErrorItem[] {
    return Array.isArray(this.detail) ? this.detail : []
  }
}

type QueryValue = string | number | undefined

export function buildQuery(params: Record<string, QueryValue>): string {
  const sp = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      sp.set(key, String(value))
    }
  }
  const qs = sp.toString()
  return qs ? `?${qs}` : ''
}

// 認証有効時に Bearer token を供給する（AuthProvider が登録する。認証仕様）
let tokenProvider: (() => Promise<string | null>) | null = null

export function setTokenProvider(
  provider: (() => Promise<string | null>) | null,
): void {
  tokenProvider = provider
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await requestRaw(path, init, { 'Content-Type': 'application/json' })
  if (res.status === 204) {
    return undefined as T
  }
  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) {
    throw new ApiError(res.status, extractErrorDetail(body))
  }
  return body as T
}

async function requestWithStatus<T>(
  path: string,
  init?: RequestInit,
): Promise<ApiResponse<T>> {
  const res = await requestRaw(path, init, { 'Content-Type': 'application/json' })
  if (res.status === 204) {
    return { status: res.status, body: undefined as T }
  }
  const body: unknown = await res.json().catch(() => null)
  return { status: res.status, body: body as T }
}

async function requestRaw(
  path: string,
  init: RequestInit | undefined,
  defaultHeaders: Record<string, string>,
): Promise<Response> {
  if (staticDemoEnabled) {
    const demoResponse = handleStaticDemoRequest(path, init)
    if (demoResponse !== null) return demoResponse
  }
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  for (const [key, value] of Object.entries(defaultHeaders)) {
    headers[key] = value
  }
  if (tokenProvider !== null) {
    const token = await tokenProvider()
    if (token !== null) {
      headers.Authorization = `Bearer ${token}`
    }
  }
  const res = await fetch(path, {
    ...init,
    headers: { ...headers, ...init?.headers },
  })
  return res
}

async function requestText(path: string, init?: RequestInit): Promise<string> {
  if (staticDemoEnabled) {
    const demoText = handleStaticDemoTextRequest(path)
    if (demoText !== null) return demoText
  }
  const headers: Record<string, string> = { Accept: 'text/event-stream' }
  if (tokenProvider !== null) {
    const token = await tokenProvider()
    if (token !== null) {
      headers.Authorization = `Bearer ${token}`
    }
  }
  const res = await fetch(path, {
    ...init,
    headers: { ...headers, ...init?.headers },
  })
  if (!res.ok) {
    const body: unknown = await res.json().catch(() => null)
    throw new ApiError(res.status, extractErrorDetail(body))
  }
  return res.text()
}

function extractErrorDetail(body: unknown): string | ValidationErrorItem[] {
  const record = getRecord(body)
  const detail = record.detail
  if (typeof detail === 'string' || isValidationErrorList(detail)) {
    return detail
  }
  const error = getRecord(record.error)
  const messageKey = error.message_key
  if (typeof messageKey === 'string') {
    return messageKey
  }
  const code = error.code
  return typeof code === 'string' ? code : '通信に失敗しました'
}

function isValidationErrorList(value: unknown): value is ValidationErrorItem[] {
  return (
    Array.isArray(value) &&
    value.every((item) => {
      const itemRecord = getRecord(item)
      return (
        Array.isArray(itemRecord.loc) &&
        typeof itemRecord.msg === 'string' &&
        typeof itemRecord.type === 'string'
      )
    })
  )
}

function getRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  getText: (path: string, init?: RequestInit) => requestText(path, init),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  postWithStatus: <T>(path: string, body: unknown) =>
    requestWithStatus<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: (path: string) => request<undefined>(path, { method: 'DELETE' }),
}
