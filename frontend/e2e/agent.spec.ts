import { expect, test } from 'playwright/test'

import { reseed } from './reseed'

type AgentApprovalApi = {
  id: number
  business_record_id: number | null
  status: string
}

test.beforeEach(() => {
  reseed()
})

test('顧客詳細のAgentタブで商談準備を生成できる', async ({ page }) => {
  const agentObjective = '次回商談のリスクとフォローを整理する'

  await page.goto('/customers/1')
  await page.getByRole('tab', { name: 'Agent' }).click()

  await page.getByLabel('目的').fill(agentObjective)
  await page.getByLabel('種類').selectOption('meeting_prep')
  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes('/api/customers/1/agent-runs') &&
      response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '実行', exact: true }).click()
  const createResponse = await createResponsePromise
  expect(createResponse.status()).toBe(202)
  const createBody = (await createResponse.json()) as {
    run_id?: number
    id?: number
    reused?: boolean
  }
  const runId = createBody.run_id ?? createBody.id
  expect(runId).toBeGreaterThan(0)
  expect(createBody.reused).toBe(false)
  await expect(page).toHaveURL(new RegExp(`/customers/1\\?tab=agent&agentRunId=${runId}`))

  await expect(page.getByText('Agent実行を開始しました')).toBeVisible()
  await expect
    .poll(async () => {
      const response = await page.request.get(`/api/agent-runs/${runId}`)
      const body = (await response.json()) as { status: string }
      return body.status
    }, { timeout: 20_000 })
    .toBe('waiting_for_approval')
  await expect
    .poll(async () => {
      const response = await page.request.get(`/api/agent-runs/${runId}/artifacts`)
      const body = (await response.json()) as unknown[]
      return body.length
    })
    .toBeGreaterThan(0)
  await expect
    .poll(async () => {
      const response = await page.request.get(`/api/agent-runs/${runId}/approvals`)
      const body = (await response.json()) as unknown[]
      return body.length
    })
    .toBeGreaterThan(0)
  await expect(page.getByRole('heading', { name: '商談ブリーフ', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '確認したいこと', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '次アクション', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '重要な主張', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '根拠', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '保存前に確認する提案', exact: true })).toBeVisible()
  await expect(page.getByText('step_completed')).toHaveCount(0)
  await expect(page.getByText('claim_ids')).toHaveCount(0)
  await expect(page.getByText('関連する主張はありません')).toHaveCount(0)
  await page.getByRole('button', { name: '詳細' }).first().click()
  await expect(page.getByRole('button', { name: '閉じる', exact: true }).first()).toBeVisible()
  await expect(page.getByText('参照ID:').first()).toBeVisible()
  expect(page.url()).toMatch(/\/customers\/1(?:$|[?#])/)
  expect(page.url()).not.toContain('/visits/')
  await page.getByRole('button', { name: '詳細' }).nth(1).click()
  await page.getByRole('link', { name: '元画面を開く' }).first().click()
  await expect(page).toHaveURL(/\/visits\/\d+\/edit\?returnTo=/)
  await expect(page.getByRole('link', { name: 'Agent結果へ戻る' })).toBeVisible()
  await page.getByRole('link', { name: 'Agent結果へ戻る' }).click()
  await expect(page).toHaveURL(new RegExp(`/customers/1\\?tab=agent&agentRunId=${runId}`))
  await expect(page.getByRole('heading', { name: '商談ブリーフ', exact: true })).toBeVisible()

  await page.getByLabel('目的').fill(agentObjective)
  const reuseResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes('/api/customers/1/agent-runs') &&
      response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '実行', exact: true }).click()
  const reuseResponse = await reuseResponsePromise
  const reuseBody = (await reuseResponse.json()) as {
    run_id?: number
    id?: number
    reused?: boolean
  }
  expect(reuseBody.run_id ?? reuseBody.id).toBe(runId)
  expect(reuseBody.reused).toBe(true)
  await expect(page.getByText('未完了の既存実行を表示しました')).toBeVisible()

  const approveButton = page.getByRole('button', { name: '承認', exact: true }).first()
  await expect(approveButton).toBeEnabled()

  const approveResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes(`/api/agent-runs/${runId}/approvals/`) &&
      response.url().endsWith('/approve') &&
      response.request().method() === 'POST',
  )
  await approveButton.click()
  const approveResponse = await approveResponsePromise
  expect(approveResponse.status()).toBe(200)

  await expect
    .poll(async () => {
      const response = await page.request.get(`/api/agent-runs/${runId}/approvals`)
      const body = (await response.json()) as AgentApprovalApi[]
      return body.some(
        (approval) =>
          approval.status !== 'pending' && approval.business_record_id !== null,
      )
    })
    .toBe(true)
  await expect(page.getByText('保存先:').first()).toBeVisible()
})
