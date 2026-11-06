import { expect, test } from "@playwright/test"

const themeFor = (project: string) => (project.startsWith("dark") ? "dark" : "light")

test("repository admin settings preserve visibility edits and owner restrictions", async ({ page }, testInfo) => {
  await page.goto(
    `/iframe.html?id=patterns-repository-settings--admin&viewMode=story&globals=theme:${themeFor(testInfo.project.name)}`,
  )
  const visibility = page.getByRole("checkbox", { name: "Private repository" })
  await expect(visibility).not.toBeChecked()
  await expect(page.getByRole("button", { name: "Delete this repository" })).toHaveCount(0)
  await visibility.check()
  const saved = page.waitForResponse((response) => response.request().method() === "PATCH")
  await page.getByRole("button", { name: "Save settings" }).click()
  const response = await saved
  expect(response.status()).toBe(200)
  expect(response.request().postDataJSON().is_private).toBe(true)
  await expect(visibility).toBeChecked()
  await page.getByRole("button", { name: "Add people", exact: true }).click()
  await page.getByRole("combobox", { name: "Role", exact: true }).click()
  await expect(page.getByRole("option", { name: "Owner", exact: true })).toHaveCount(0)
  await page.keyboard.press("Escape")
})

test("collaborator controls support keyboard grants and protect owner roles", async ({ page }, testInfo) => {
  await page.goto(
    `/iframe.html?id=patterns-repository-collaborators--admin&viewMode=story&globals=theme:${themeFor(testInfo.project.name)}`,
  )
  await expect(page.getByRole("combobox", { name: "Role for alice" })).toBeDisabled()
  await expect(page.getByRole("button", { name: "Remove alice" })).toBeDisabled()
  await page.screenshot({ path: `visual-review/access-table-${testInfo.project.name}.png`, fullPage: true })
  await page.getByRole("button", { name: "Add people" }).click()
  const dialog = page.getByRole("dialog")
  await expect(dialog.getByRole("button", { name: "Add to repository" })).toBeDisabled()
  await dialog.getByLabel("Search by username, full name, or email").fill("garrett")
  const candidate = dialog.getByRole("button", { name: /Garrett Yan/ })
  await expect(candidate).toBeVisible()
  await page.screenshot({ path: `visual-review/access-dialog-${testInfo.project.name}.png`, fullPage: true })
  await candidate.focus()
  await page.keyboard.press("Enter")
  await expect(candidate).toHaveAttribute("aria-pressed", "true")
  await dialog.getByRole("combobox", { name: "Role" }).click()
  await page.getByRole("option", { name: "Write", exact: true }).click()
  const granted = page.waitForResponse((response) => response.request().method() === "PUT")
  await dialog.getByRole("button", { name: "Add to repository" }).click()
  const response = await granted
  expect(response.status()).toBe(200)
  expect(response.request().postDataJSON()).toEqual({ user_id: "00000000-0000-0000-0000-000000000005", role: "write" })
  await expect(page.getByRole("combobox", { name: "Role for garrett" })).toHaveText("Write")
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false)
})

test("organization members use the shared access table and preserve the last admin", async ({ page }, testInfo) => {
  await page.goto(
    `/iframe.html?id=patterns-organization-members--admin&viewMode=story&globals=theme:${themeFor(testInfo.project.name)}`,
  )
  await expect(page.getByRole("combobox", { name: "Role for jan-mue" })).toBeDisabled()
  await expect(page.getByRole("button", { name: "Remove jan-mue" })).toBeDisabled()
  await page.screenshot({ path: `visual-review/organization-access-${testInfo.project.name}.png`, fullPage: true })
  await page.getByRole("button", { name: "Add people" }).click()
  const dialog = page.getByRole("dialog")
  await dialog.getByLabel("Search by username, full name, or email").fill("alice")
  await dialog.getByRole("button", { name: /Alice Example/ }).click()
  const added = page.waitForResponse((response) => response.request().method() === "PUT")
  await dialog.getByRole("button", { name: "Add to organization" }).click()
  expect((await added).status()).toBe(200)
  await expect(page.getByRole("combobox", { name: "Role for alice" })).toHaveText("Member")
  await page.getByRole("textbox", { name: "Find a member" }).fill("alice")
  await page.getByRole("checkbox", { name: "Select all", exact: true }).check()
  await page.getByRole("button", { name: "Remove selected" }).click()
  const removed = page.waitForResponse((response) => response.request().method() === "DELETE")
  await page.getByRole("button", { name: "Remove access", exact: true }).click()
  expect((await removed).status()).toBe(204)
  await expect(page.getByRole("combobox", { name: "Role for alice" })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false)
})

test("token controls preserve scopes, expiry, and show-once secrets", async ({ page }, testInfo) => {
  await page.goto(
    `/iframe.html?id=patterns-account-personal-access-tokens--tokens&viewMode=story&globals=theme:${themeFor(testInfo.project.name)}`,
  )
  await page.getByLabel("Token name").fill("Workstation")
  await page.getByRole("checkbox", { name: "jan/gitedge" }).check()
  await page.getByRole("checkbox", { name: "Push commits (includes clone and fetch)" }).check()
  await page.getByRole("combobox", { name: "Expiration" }).click()
  await page.getByRole("option", { name: "No expiration" }).click()
  const created = page.waitForResponse((response) => response.request().method() === "POST")
  await page.getByRole("button", { name: "Create token" }).click()
  const response = await created
  expect(response.status()).toBe(201)
  expect(response.request().postDataJSON()).toEqual({
    name: "Workstation",
    scopes: ["repository:read", "git:write"],
    repository_ids: ["00000000-0000-0000-0000-000000000003"],
    expires_at: null,
  })
  const issued = page.getByLabel("New personal access token")
  await expect(issued).toHaveValue(/^gitedge_pat_live_v1_/)
  await page.screenshot({ path: `visual-review/access-tokens-${testInfo.project.name}.png`, fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false)
  const secret = await issued.inputValue()
  await page.getByRole("button", { name: "I've saved my token" }).click()
  await expect(issued).toHaveCount(0)
  await expect(page.locator("body")).not.toContainText(secret)
  const token = page.getByRole("listitem").filter({ hasText: "Workstation" })
  const revoked = page.waitForResponse((response) => response.request().method() === "POST")
  await token.getByRole("button", { name: "Revoke" }).click()
  expect((await revoked).status()).toBe(204)
  await expect(token).toContainText("Revoked")
})
