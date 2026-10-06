import { test, expect } from '@playwright/test'
import { LoginPage } from '../pages/LoginPage'

const VALID = { user: 'Admin', pass: 'admin123' }

test.describe('Login', () => {
  let login: LoginPage

  test.beforeEach(async ({ page }) => {
    login = new LoginPage(page)
    await login.open()
  })

  test('TC-001 login with valid credentials', async ({ page }) => {
    await login.login(VALID.user, VALID.pass)
    await expect(page).toHaveURL(/dashboard/)
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  })

  test('TC-002 empty username and password show Required errors', async ({
    page,
  }) => {
    await login.loginButton.click()
    await expect(login.requiredErrors).toHaveCount(2)
    await expect(login.requiredErrors.first()).toHaveText('Required')
    await expect(page).toHaveURL(/auth\/login/)
  })

  test('TC-003 empty password shows Required error', async () => {
    await login.username.fill(VALID.user)
    await login.loginButton.click()
    await expect(login.requiredErrors).toHaveCount(1)
  })

  test('TC-004 empty username shows Required error', async () => {
    await login.password.fill(VALID.pass)
    await login.loginButton.click()
    await expect(login.requiredErrors).toHaveCount(1)
  })

  test('TC-005 wrong password shows Invalid credentials', async ({ page }) => {
    await login.login(VALID.user, 'Wrong@999')
       await expect(login.errorAlert).toHaveText('Invalid credentials')
    await expect(page).toHaveURL(/auth\/login/)
  })

  test('TC-006 unknown user shows the same generic error', async () => {
    await login.login('nobody_here_123', 'Any@1234')
    await expect(login.errorAlert).toHaveText('Invalid credentials')
  })

  test('TC-016 SQL injection and script input are rejected safely', async ({
    page,
  }) => {
    let dialogShown = false
    page.on('dialog', async (d) => {
      dialogShown = true
      await d.dismiss()
    })
    await login.login("' OR '1'='1' --", '<script>alert(1)</script>')
    await expect(login.errorAlert).toHaveText('Invalid credentials')
    expect(dialogShown).toBe(false)
  })

  test('TC-018 dashboard redirects to login when not signed in', async ({
    page,
  }) => {
    await page.goto('/web/index.php/dashboard/index')
    await expect(page).toHaveURL(/auth\/login/)
  })

  test('TC-020 login works with keyboard only', async ({ page }) => {
    await login.username.focus()
    await page.keyboard.type(VALID.user)
    await page.keyboard.press('Tab')
    await expect(login.password).toBeFocused()
    await page.keyboard.type(VALID.pass)
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/dashboard/)
  })
})
