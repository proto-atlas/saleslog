import { expect, test } from 'playwright/test'

// E2E: フォーム編集中（dirty）のアプリ内遷移で未保存確認が出る
test('編集中にアプリ内遷移しようとすると未保存確認が出る', async ({ page }) => {
  await page.goto('/visits/new?customer_id=1')
  await page.evaluate(() => localStorage.clear())

  await page.getByLabel('内容（任意）').fill('未保存の内容')
  await page.getByRole('link', { name: '顧客', exact: true }).click()

  // useBlocker による確認ダイアログ
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('未保存の変更があります')).toBeVisible()

  await dialog.getByRole('button', { name: 'とどまる' }).click()
  await expect(page).toHaveURL(/\/visits\/new/)
  // 入力値が保持されている
  await expect(page.getByLabel('内容（任意）')).toHaveValue('未保存の内容')
})
