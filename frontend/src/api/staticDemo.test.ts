import { describe, expect, test } from 'vitest'

import {
  handleStaticDemoRequest,
  handleStaticDemoTextRequest,
} from './staticDemo'
import type {
  AgentApprovalOut,
  AgentArtifactOut,
  AgentRunCreateResponse,
  AgentRunSourceOut,
  CustomerOut,
  CustomersListResponse,
  UserOut,
} from './client'

async function jsonBody<T>(response: Response): Promise<T> {
  return response.json() as Promise<T>
}

describe('static demo api', () => {
  test('固定ユーザーと顧客一覧を返す', async () => {
    const meResponse = handleStaticDemoRequest('/api/me')
    expect(meResponse?.status).toBe(200)
    await expect(jsonBody<UserOut>(meResponse!)).resolves.toMatchObject({
      id: 1,
      role: 'manager',
    })

    const customersResponse = handleStaticDemoRequest('/api/customers?page_size=2')
    expect(customersResponse?.status).toBe(200)
    const customers = await jsonBody<CustomersListResponse>(customersResponse!)
    expect(customers.items).toHaveLength(2)
    expect(customers.total).toBeGreaterThanOrEqual(5)
  })

  test('顧客登録はブラウザ内の合成データだけを更新する', async () => {
    const response = handleStaticDemoRequest('/api/customers', {
      method: 'POST',
      body: JSON.stringify({
        name: 'デモ商事',
        address: '東京都中央区',
        area: 'tokyo',
        status: 'prospect',
        owner_id: 1,
      }),
    })

    expect(response?.status).toBe(201)
    const created = await jsonBody<CustomerOut>(response!)
    expect(created).toMatchObject({ name: 'デモ商事', owner_id: 1 })

    const listResponse = handleStaticDemoRequest('/api/customers?search=デモ商事')
    const list = await jsonBody<CustomersListResponse>(listResponse!)
    expect(list.items[0].name).toBe('デモ商事')
  })

  test('AgentイベントをSSEテキストで返す', () => {
    const text = handleStaticDemoTextRequest('/api/agent-runs/1/events')
    expect(text).toContain('safe_message_key":"run_created"')
    expect(text).toContain('safe_message_key":"waiting_for_approval"')
  })

  test('Agent新規実行は提案本文、承認候補、根拠を作成する', async () => {
    const response = handleStaticDemoRequest('/api/customers/1/agent-runs', {
      method: 'POST',
      body: JSON.stringify({
        objective: '新規実行の表示確認',
        workflow_type: 'meeting_prep',
      }),
    })

    expect(response?.status).toBe(202)
    const created = await jsonBody<AgentRunCreateResponse>(response!)
    const runId = created.run_id

    const artifactsResponse = handleStaticDemoRequest(`/api/agent-runs/${runId}/artifacts`)
    const artifacts = await jsonBody<AgentArtifactOut[]>(artifactsResponse!)
    expect(artifacts).toHaveLength(1)
    expect(artifacts[0].content_json).toMatchObject({
      customer_summary: {
        text: expect.stringContaining('株式会社アオバ製作所'),
      },
    })

    const approvalsResponse = handleStaticDemoRequest(`/api/agent-runs/${runId}/approvals`)
    const approvals = await jsonBody<AgentApprovalOut[]>(approvalsResponse!)
    expect(approvals.map((approval) => approval.action_type)).toEqual(['email_draft', 'task'])

    const sourcesResponse = handleStaticDemoRequest(`/api/agent-runs/${runId}/sources`)
    const sources = await jsonBody<AgentRunSourceOut[]>(sourcesResponse!)
    expect(sources.map((source) => source.source_type)).toEqual(['customer', 'activity', 'activity'])
  })
})
