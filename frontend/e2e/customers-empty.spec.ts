import { expect, test } from 'playwright/test'

// E2E: 顧客 0 件時に空状態（EmptyState）が表示される。
// この spec は空 DB サーバ（empty-db プロジェクト）でのみ実行される
test('顧客が0件のとき空状態の案内が表示される', async ({ page }) => {
  await page.goto('/customers')

  await expect(page.getByText('まだ顧客が登録されていません')).toBeVisible()
  await expect(
    page.getByRole('button', { name: '顧客を登録' }).nth(1),
  ).toBeVisible()
})

test('エリア別ボードも0件のとき空状態の案内が表示される', async ({ page }) => {
  await page.goto('/map')
  await expect(page.getByRole('heading', { name: 'エリア別ボード' })).toBeVisible()
  await expect(page.getByText('まだ顧客が登録されていません')).toBeVisible()
})
