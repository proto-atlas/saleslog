import AxeBuilder from '@axe-core/playwright'
import { expect, test } from 'playwright/test'

// アクセシビリティ自動検査: serious / critical 違反 0 件。
// seed済みの主要8画面を対象にする。サインイン画面は認証有効時のみ表示されるため対象外。
const TARGET_PATHS = [
  '/',
  '/customers',
  '/customers/1',
  '/visits',
  '/visits/new',
  '/visits/1/edit',
  '/map',
  '/admin/users',
]
const A11Y_TEST_TIMEOUT_MS = 60_000 // seed済み一覧画面のaxe解析が30秒を超えることがあるため

for (const path of TARGET_PATHS) {
  test(`axe 検査: ${path} で serious / critical 違反がない`, async ({ page }) => {
    test.setTimeout(A11Y_TEST_TIMEOUT_MS)
    await page.goto(path)
    // データ取得完了後の画面を検査する（ローディングのまま検査しない）
    await page.waitForLoadState('networkidle')
    await expect(page.getByRole('navigation', { name: 'メイン' })).toBeVisible()
    await expect(page.locator('main')).toBeVisible()

    const results = await new AxeBuilder({ page }).include('nav, main').analyze()
    const severe = results.violations.filter(
      (violation) =>
        violation.impact === 'serious' || violation.impact === 'critical',
    )
    expect(
      severe.map((violation) => ({
        id: violation.id,
        impact: violation.impact,
        nodes: violation.nodes.map((node) => node.target),
      })),
    ).toEqual([])
  })
}
