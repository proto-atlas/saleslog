import { expect, test, type Page } from 'playwright/test'

async function openMobileNavigation(page: Page) {
  await page.setViewportSize({ width: 375, height: 667 })
  await page.goto('/')
  await page.getByRole('button', { name: 'メニューを開く' }).click()
}

test('モバイルナビを閉じているとナビリンクを操作対象から外す', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 })
  await page.goto('/')

  const customerLinkReceivedFocus = await page.getByRole('link', { name: '顧客' }).evaluate((link) => {
    link.focus()
    return document.activeElement === link
  })

  expect(customerLinkReceivedFocus).toBe(false)
})

test('Escapeキーでモバイルナビを閉じると開くボタンへフォーカスを戻す', async ({ page }) => {
  await openMobileNavigation(page)
  await page.keyboard.press('Escape')

  await expect(page.getByRole('button', { name: 'メニューを開く' })).toBeFocused()
})

test('背景を選択してモバイルナビを閉じると開くボタンへフォーカスを戻す', async ({ page }) => {
  await openMobileNavigation(page)
  await page.locator('button.fixed[aria-label="メニューを閉じる"]').click()

  await expect(page.getByRole('button', { name: 'メニューを開く' })).toBeFocused()
})

test('閉じるボタンでモバイルナビを閉じると開くボタンへフォーカスを戻す', async ({ page }) => {
  await openMobileNavigation(page)
  await page.locator('aside').getByRole('button', { name: 'メニューを閉じる' }).click()

  await expect(page.getByRole('button', { name: 'メニューを開く' })).toBeFocused()
})

test('ナビリンクを選択すると開くボタンへフォーカスを戻す', async ({ page }) => {
  await openMobileNavigation(page)
  await page.getByRole('link', { name: '顧客' }).click()

  await expect(page.getByRole('button', { name: 'メニューを開く' })).toBeFocused()
})
