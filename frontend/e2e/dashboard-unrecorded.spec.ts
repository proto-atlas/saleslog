import { expect, test } from 'playwright/test'

import { reseed } from './reseed'

// E2E: ダッシュボードの入力漏れ導線 → /visits?unrecorded=true で入力漏れのみ表示、
// URL クエリが復元される
test.beforeEach(() => {
  reseed()
})

test('入力漏れ導線から一覧に遷移し、URL クエリが復元される', async ({ page }) => {
  await page.goto('/')

  // seed には入力漏れ（planned のまま過ぎた予定）が含まれる
  await expect(page.getByText('入力漏れ')).toBeVisible()
  await page.getByRole('link', { name: '入力漏れを確認する' }).click()

  await expect(page).toHaveURL(/\/visits\?unrecorded=true/)
  await expect(page.getByLabel('入力漏れのみ')).toBeChecked()
  // アンカー seed: マルヤマ商事の planned 期限超過が必ず含まれる
  await expect(
    page.getByRole('row').filter({ hasText: 'マルヤマ商事' }).first(),
  ).toBeVisible()
  // 一覧の行はすべて「予定」バッジ（入力漏れ = planned のみ）
  await expect(page.getByRole('row').nth(1).getByText('予定')).toBeVisible()

  // リロードしても URL クエリから状態が復元される
  await page.reload()
  await expect(page.getByLabel('入力漏れのみ')).toBeChecked()
  await expect(
    page.getByRole('row').filter({ hasText: 'マルヤマ商事' }).first(),
  ).toBeVisible()
})
