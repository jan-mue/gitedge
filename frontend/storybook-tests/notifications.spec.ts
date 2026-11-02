import { expect, test } from "@playwright/test"

test("notification selection, unread state, and busy actions", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(`/iframe.html?id=components-notification-center--unread&viewMode=story&globals=theme:${theme}`)
  const selection = page.getByRole("checkbox", { name: "Select notification", exact: true })
  await selection.check()
  await expect(page.getByRole("checkbox", { name: "Select repository", exact: true })).toBeChecked()
  await expect(page.getByText("Unread", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: /Add keyboard navigation/ }).click()
  await expect(page.getByText("Unread", { exact: true })).toHaveCount(0)
  await page.goto(`/iframe.html?id=components-notification-center--busy&viewMode=story&globals=theme:${theme}`)
  await expect(page.getByRole("button", { name: "Dismiss", exact: true })).toBeDisabled()
  await expect(page.getByRole("checkbox", { name: "Select notification", exact: true })).toBeDisabled()
  expect(errors).toEqual([])
})
