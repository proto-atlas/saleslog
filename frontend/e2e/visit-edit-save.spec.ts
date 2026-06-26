import { expect, test } from 'playwright/test'

import { reseed } from './reseed'

// 編集の保存成功後は未保存確認を出さずに顧客詳細へ遷移する。
// E2E（form-dirty-block）は「確認が出る側」のみで、保存後の遷移が
// 離脱防止に誤ブロックされる退行を検出できなかったため追加
test.beforeEach(() => {
  reseed()
})

test('活動記録を編集して保存すると確認なしで顧客詳細へ遷移する', async ({ page }) => {
  await page.goto('/visits/1/edit')
  await page.evaluate(() => localStorage.clear())

  // 編集フォームはロード完了後に値が反映される（日時は必須項目のため必ず埋まる）
  await expect(page.getByLabel('日時')).not.toHaveValue('')

  await page.getByLabel('内容（任意）').fill('保存後遷移の確認メモ')
  await page.getByRole('button', { name: '保存する' }).click()

  // 未保存確認を出さずに活動記録一覧へ遷移する
  // （戻り先は一覧に統一。顧客詳細は sales だと他担当顧客の場合 404 になるため）
  await expect(page).toHaveURL(/\/visits$/)
  await expect(page.getByText('未保存の変更があります')).toHaveCount(0)
})
