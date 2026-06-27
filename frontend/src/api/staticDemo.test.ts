import { describe, expect, test } from 'vitest'

import {
  handleStaticDemoRequest,
  handleStaticDemoTextRequest,
} from './staticDemo'
import type { CustomerOut, CustomersListResponse, UserOut } from './client'

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
})
