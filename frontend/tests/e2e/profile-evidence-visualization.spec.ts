import { expect, test } from '@playwright/test'
import { installStableApiMocks, seedAuthenticatedSession } from './support/pathfy-fixtures'

test.beforeEach(async ({ page }) => {
  await seedAuthenticatedSession(page)
  await installStableApiMocks(page)
})

test('primary view owns the editorial note and no longer renders the evidence journey card', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))

  await page.goto('/profile')

  await expect(page.getByRole('heading', { name: '画像形成过程' })).toHaveCount(0)
  await expect(page.locator('canvas.profile-evidence-canvas')).toHaveCount(0)
  await expect(page.getByText('编辑批注 / OVERALL', { exact: true })).toBeVisible()
  await expect(page.getByText('02 · Supporting Evidence', { exact: true })).toBeVisible()

  const annotationFollowsPrimaryCard = await page.locator('.profile-page').evaluate((root) => {
    const primaryCard = root.querySelector('.profile-top-grid')
    const annotation = root.querySelector('.profile-primary-verdict')
    return Boolean(primaryCard && annotation && (primaryCard.compareDocumentPosition(annotation) & Node.DOCUMENT_POSITION_FOLLOWING))
  })
  expect(annotationFollowsPrimaryCard).toBe(true)
  expect(pageErrors).toEqual([])
})
