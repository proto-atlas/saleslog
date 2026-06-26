import { expect, test } from 'playwright/test'

// E2E: 検索 + 絞り込みが効く。URL クエリ同期も確認
// 期待件数は seed の固定値（「商事」=3件 / 「sky」=1件。backend/app/seed.py）
test('検索と絞り込みが効き、URL クエリと同期される', async ({ page }) => {
  await page.goto('/customers')

  await page.getByLabel('検索（顧客名）').fill('商事')
  await expect(page.getByText('全 3 件中')).toBeVisible()

  // URL に検索条件が同期されている
  await expect
    .poll(() => new URL(page.url()).searchParams.get('search'))
    .toBe('商事')

  // エリア絞り込みを重ねる（登録ダイアログ内の同名 select と区別するため id 指定）
  await page.locator('#filter-area').selectOption('saitama')
  await expect(page.getByText('全 1 件中')).toBeVisible()
  await expect(page.getByRole('link', { name: '北関東商事' })).toBeVisible()
  await expect(page.getByRole('button', { name: '北関東商事を開く' })).toBeVisible()
  await expect
    .poll(() => new URL(page.url()).searchParams.get('area'))
    .toBe('saitama')

  // URL 直接アクセスで状態が復元される（大文字小文字を区別しない検索の確認込み）
  await page.goto('/customers?search=SKY')
  await expect(page.getByLabel('検索（顧客名）')).toHaveValue('SKY')
  await expect(page.getByText('全 1 件中')).toBeVisible()
  await expect(
    page.getByRole('link', { name: 'Sky Net Works 株式会社' }),
  ).toBeVisible()
})
