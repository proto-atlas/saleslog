import { expect, test } from 'playwright/test'

import { DRAFT_DEBOUNCE_MS } from '../src/hooks/useFormDraft'

// E2E: 下書き保存 → 再訪問で復元確認 → 復元でフォーム値が戻る
test('下書きが保存され、再訪問時に復元できる', async ({ page }) => {
  await page.goto('/visits/new?customer_id=1')
  await page.evaluate(() => localStorage.clear())

  await page.getByLabel('内容（任意）').fill('下書き本文テスト')
  // debounce（500ms）経過を待って localStorage へ保存させる
  await page.waitForTimeout(DRAFT_DEBOUNCE_MS + 200)

  // dirty 状態のリロードは beforeunload 確認が出るため明示的に受け入れる
  page.on('dialog', (dialog) => void dialog.accept())
  await page.reload()

  await expect(page.getByText('前回の入力内容があります')).toBeVisible()
  await page.getByRole('button', { name: '復元する' }).click()
  await expect(page.getByLabel('内容（任意）')).toHaveValue('下書き本文テスト')
})
