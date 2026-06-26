import { expect, test } from 'playwright/test'

// E2E: 保存失敗時にエラー表示と再試行ができ、エラー表示に送信した生値を含まない
test('保存失敗時にエラーが表示され、再試行で保存できる', async ({ page }) => {
  await page.goto('/visits/new?customer_id=1')
  await page.evaluate(() => localStorage.clear())

  // 最初の POST だけ 500 を返し、2回目以降は実サーバへ通す
  let failedOnce = false
  await page.route('**/api/visits', async (route) => {
    if (route.request().method() === 'POST' && !failedOnce) {
      failedOnce = true
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' }),
      })
      return
    }
    await route.fallback()
  })

  await page.getByLabel('ステータス').selectOption('done')
  await page.getByLabel('内容（任意）').fill('機密メモ123')
  await page.getByRole('button', { name: '保存する' }).click()

  const alert = page.getByRole('alert')
  await expect(alert).toContainText('保存に失敗しました')
  // 送信した生値がエラー表示に反射しないこと
  await expect(alert).not.toContainText('機密メモ123')

  // 再試行 → 成功
  await page.getByRole('button', { name: '保存する' }).click()
  await expect(page.getByText('活動記録を保存しました')).toBeVisible()
})
