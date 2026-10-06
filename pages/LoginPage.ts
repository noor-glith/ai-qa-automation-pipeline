import { Page, Locator, expect } from '@playwright/test'

export class LoginPage {
  readonly page: Page
  readonly username: Locator
  readonly password: Locator
  readonly loginButton: Locator
  readonly errorAlert: Locator
  readonly requiredErrors: Locator

  constructor(page: Page) {
    this.page = page
    this.username = page.getByPlaceholder('Username')
    this.password = page.getByPlaceholder('Password')
    this.loginButton = page.getByRole('button', { name: 'Login' })
    this.errorAlert = page.locator('.oxd-alert-content-text')
    this.requiredErrors = page.locator('.oxd-input-field-error-message')
  }

  async open() {
    await this.page.goto('/web/index.php/auth/login')
    await expect(this.username).toBeVisible()
  }

  async login(username: string, password: string) {
    await this.username.fill(username)
    await this.password.fill(password)
    await this.loginButton.click()
  }
}
