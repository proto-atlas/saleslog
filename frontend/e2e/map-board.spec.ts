import { expect, test } from 'playwright/test'

const areaEntries = [
  ['tokyo', '東京'],
  ['kanagawa', '神奈川'],
  ['saitama', '埼玉'],
  ['chiba', '千葉'],
  ['other', 'その他'],
] as const

type Area = (typeof areaEntries)[number][0]

// エリア別ボードの通常表示と詳細遷移
test('エリア別ボードが表示され、カードから顧客詳細へ遷移できる', async ({ page }) => {
  await page.goto('/map')

  await expect(page.getByRole('heading', { name: 'エリア別ボード' })).toBeVisible()

  const response = await page.request.get('/api/customers?page_size=100')
  expect(response.ok()).toBeTruthy()
  const data = (await response.json()) as {
    items: Array<{ area: Area }>
  }
  const counts = new Map<Area, number>()
  for (const customer of data.items) {
    counts.set(customer.area, (counts.get(customer.area) ?? 0) + 1)
  }

  // 5 エリアの列ヘッダと件数バッジが表示される
  for (const [area, label] of areaEntries) {
    const count = counts.get(area) ?? 0
    const column = page.getByRole('group', { name: `${label} ${count}件` })
    await expect(column.getByText(label, { exact: true })).toBeVisible()
    await expect(column.getByText(String(count), { exact: true })).toBeVisible()
  }

  // アンカー seed の顧客カード → 詳細遷移
  await page
    .getByRole('link', { name: /株式会社アオバ製作所/ })
    .first()
    .click()
  await expect(page).toHaveURL(/\/customers\/1$/)
  await expect(page.locator('h1')).toHaveText('株式会社アオバ製作所')
})
