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
  await page.getByRole("combobox", { name: "Role", exact: true }).click()
  await expect(page.getByRole("option", { name: "Owner", exact: true })).toHaveCount(0)
  await page.keyboard.press("Escape")
})

test("collaborator controls support keyboard grants and protect owner roles", async ({ page }, testInfo) => {
  await page.goto(
    `/iframe.html?id=patterns-repository-collaborators--admin&viewMode=story&globals=theme:${themeFor(testInfo.project.name)}`,
  )
  const owner = page.getByRole("listitem").filter({ hasText: "alice" })
  await expect(owner.getByRole("combobox", { name: "Role for alice" })).toBeDisabled()
  await expect(owner.getByRole("button", { name: "Remove" })).toBeDisabled()
  await page.getByRole("combobox", { name: "Collaborator type" }).click()
  await page.getByRole("option", { name: "Organization team" }).click()
  await page.getByRole("combobox", { name: "Team", exact: true }).click()
  await page.getByRole("option", { name: "developers", exact: true }).click()
  const role = page.getByRole("combobox", { name: "Role", exact: true })
  await role.focus()
  await page.keyboard.press("Enter")
  await expect(page.getByRole("option", { name: "Read", exact: true })).toBeFocused()
  await page.keyboard.press("ArrowDown")
  await expect(page.getByRole("option", { name: "Write", exact: true })).toBeFocused()
  await page.keyboard.press("Enter")
  await expect(role).toHaveText("Write")
  const granted = page.waitForResponse((response) => response.request().method() === "PUT")
  await page.getByRole("button", { name: "Add collaborator" }).click()
  const response = await granted
  expect(response.status()).toBe(200)
  expect(response.request().postDataJSON()).toEqual({ team_id: "00000000-0000-0000-0000-000000000002", role: "write" })
  await expect(page.getByRole("combobox", { name: "Role for developers" })).toHaveText("Write")
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false)
})

test("token controls preserve scopes, expiry, and show-once secrets", async ({ page }, testInfo) => {
  await page.goto(
    `/iframe.html?id=patterns-account-personal-access-tokens--tokens&viewMode=story&globals=theme:${themeFor(testInfo.project.name)}`,
  )
  await page.getByLabel("Token name").fill("Workstation")
  await page.getByRole("combobox", { name: "Git access" }).click()
  await page.getByRole("option", { name: "Read and write — clone, fetch, and push" }).click()
  await page.getByRole("combobox", { name: "Expiration" }).click()
  await page.getByRole("option", { name: "No expiration" }).click()
  const created = page.waitForResponse((response) => response.request().method() === "POST")
  await page.getByRole("button", { name: "Create token" }).click()
  const response = await created
  expect(response.status()).toBe(201)
  expect(response.request().postDataJSON()).toEqual({
    name: "Workstation",
    scopes: ["git:read", "git:write"],
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
