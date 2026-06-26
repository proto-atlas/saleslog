import { expect, test } from 'playwright/test'

import { reseed } from './reseed'

// E2E: 活動記録の登録 → 顧客詳細の履歴に反映される
test.beforeEach(() => {
  reseed()
})

test('活動記録を登録すると顧客詳細の履歴に反映される', async ({ page }) => {
  await page.goto('/customers/1')
  await page.evaluate(() => localStorage.clear())

  await page.getByRole('button', { name: '活動記録を登録' }).click()
  await expect(page).toHaveURL(/\/visits\/new\?customer_id=1/)
  // 顧客が初期選択されている。選択肢ロード前の placeholder select と
  // 区別するため、ロード後にだけ存在する name 属性で特定する（label 経由は差し替わり時にレースする）
  await expect(page.locator('select[name="customer_id"]')).toHaveValue('1')

  await page.getByLabel('活動種別').selectOption('online')
  await page.getByLabel('ステータス').selectOption('done')
  // 未来日時にして履歴の先頭（visited_at 降順）に出す。表示は実行環境の TZ に依存するため日時文字列では検証しない
  await page.getByLabel('日時').fill('2030-01-02T03:04')
  await page.getByLabel('内容（任意）').fill('E2E 登録テスト')
  await page.getByRole('button', { name: '保存する' }).click()

  await expect(page.getByText('活動記録を保存しました')).toBeVisible()
  await page.getByRole('button', { name: '顧客詳細を見る' }).click()
  await expect(page).toHaveURL(/\/customers\/1$/)

  // 履歴の先頭に登録した記録（オンライン会議・完了）が出る
  const firstItem = page.locator('ol > li').first()
  await expect(firstItem).toContainText('オンライン会議')
  await expect(firstItem).toContainText('完了')
})
