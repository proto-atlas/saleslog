import { expect, test } from 'playwright/test'

import { reseed } from './reseed'

// E2E: 顧客詳細の編集 → 一覧/詳細に反映される
test.beforeEach(() => {
  reseed()
})

test('顧客詳細でステータスを変更すると詳細と一覧に反映される', async ({ page }) => {
  // seed 固定: 顧客 id=2 マルヤマ商事は prospect（見込み）
  await page.goto('/customers/2')
  await expect(page.locator('h1')).toHaveText('マルヤマ商事')

  await page.locator('#detail-status').selectOption('negotiating')
  await expect(
    page.getByText('ステータスを「商談中」に更新しました'),
  ).toBeVisible()
  // 詳細ヘッダのバッジに反映
  await expect(page.locator('h1 + span')).toHaveText('商談中')

  // 一覧にも反映
  await page.goto('/customers?search=マルヤマ')
  const row = page.getByRole('row').filter({ hasText: 'マルヤマ商事' })
  await expect(row.getByText('商談中')).toBeVisible()
})
