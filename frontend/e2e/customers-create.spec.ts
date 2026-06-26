import { expect, test } from 'playwright/test'

// E2E: 顧客登録 → 一覧に反映される
test('顧客を登録すると一覧に反映される', async ({ page }) => {
  await page.goto('/customers')

  await page.getByRole('button', { name: '顧客を登録' }).first().click()
  // 閉じた状態の dialog も DOM に存在するため、フォーム操作は dialog スコープで行う
  const dialog = page.getByRole('dialog')
  // 実行ごとに一意な名前にして、再実行時の前回データと衝突させない
  const name = `E2Eテスト工業 ${Date.now()}`
  await dialog.getByLabel('顧客名').fill(name)
  await dialog.getByLabel('住所（任意）').fill('東京都港区1-2-3')
  await dialog.getByLabel('エリア').selectOption('tokyo')
  await dialog.getByLabel('ステータス').selectOption('prospect')
  await dialog.getByLabel('担当者').selectOption('2')
  await dialog.getByRole('button', { name: '登録する' }).click()

  // 成功トーストが出る
  await expect(page.getByText(`顧客「${name}」を登録しました`)).toBeVisible()

  // 一覧（検索）に反映されている
  await page.getByLabel('検索（顧客名）').fill(name)
  await expect(page.getByRole('link', { name })).toBeVisible()
  await expect(page.getByText('全 1 件中')).toBeVisible()
})
