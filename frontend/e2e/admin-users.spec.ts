import { expect, test } from 'playwright/test'

import { reseed } from './reseed'

// 管理画面（fixed モードの固定ユーザー = manager で操作。認証仕様）
test.beforeEach(() => {
  reseed()
})

test('管理画面でユーザーを追加し、役割を変更できる', async ({ page }) => {
  await page.goto('/admin/users')

  // 既存ユーザーが一覧に出る
  await expect(
    page.getByRole('cell', { name: '営業ユーザーA', exact: true }),
  ).toBeVisible()

  // 追加
  const name = `E2E追加 ${Date.now()}`
  await page.getByLabel('名前').fill(name)
  await page.getByLabel('役割', { exact: true }).selectOption('sales')
  await page.getByRole('button', { name: '追加する' }).click()
  await expect(page.getByText(`ユーザー「${name}」を追加しました`)).toBeVisible()
  const row = page.getByRole('row').filter({ hasText: name })
  await expect(row).toBeVisible()

  // 役割変更（営業 → マネージャー）
  await row.getByRole('combobox').selectOption('manager')
  await expect(page.getByText('役割を更新しました')).toBeVisible()

  // 自分自身（id=1）の役割 select は無効
  const selfRow = page.getByRole('row').filter({ hasText: '管理者ユーザー' })
  await expect(selfRow.getByRole('combobox')).toBeDisabled()
})
