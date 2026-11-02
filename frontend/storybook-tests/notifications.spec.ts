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

test("repository dropdowns save star lists and notification categories", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  await page.goto(`/iframe.html?id=patterns-repository-header--header&viewMode=story&globals=theme:${theme}`)
  await page.getByRole("button", { name: "Add to list", exact: true }).click()
  await expect(page.getByRole("textbox", { name: "New list name" })).toBeVisible()
  await page.getByRole("textbox", { name: "New list name" }).fill("My projects")
  await page.getByRole("button", { name: "Create list", exact: true }).click()
  await expect(page.getByRole("button", { name: "My projects 1", exact: true })).toHaveAttribute("aria-pressed", "true")
  await expect(page.getByTestId("star-button").getByRole("button", { name: "Starred", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  )
  await page.keyboard.press("Escape")
  await page.getByRole("button", { name: "Notification settings", exact: true }).click()
  const issues = page.getByRole("switch", { name: "Issues", exact: true })
  await expect(issues).toBeChecked()
  await issues.click()
  await expect(issues).not.toBeChecked()
  await page.keyboard.press("Escape")
  await page.getByRole("button", { name: "Notification settings", exact: true }).click()
  await expect(page.getByRole("switch", { name: "Issues", exact: true })).not.toBeChecked()
  await expect(page.getByRole("link", { name: "Open notifications" })).toHaveAttribute("href", "/notifications")
  await page.keyboard.press("Escape")
  await page.reload()
  await page.getByRole("button", { name: "Add to list", exact: true }).click()
  await expect(page.getByRole("button", { name: "My projects 1", exact: true })).toHaveAttribute("aria-pressed", "true")
})

test("notification inbox filters and category settings match the reference layout", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  await page.goto(`/iframe.html?id=patterns-notifications-inbox--inbox&viewMode=story&globals=theme:${theme}`)
  await expect(page.getByRole("link", { name: /Security vulnerability/ })).toBeVisible()
  await expect(page.getByRole("listitem")).toHaveCount(9)
  await page
    .getByRole("button", { name: "Mentioned 1", exact: true })
    .or(page.getByRole("button", { name: "Mentioned", exact: true }))
    .filter({ visible: true })
    .click()
  await expect(page.getByRole("listitem")).toHaveCount(1)
  await page.getByRole("button", { name: "Manage", exact: true }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await expect(page.getByRole("switch", { name: "Pull requests", exact: true })).toBeChecked()
  await page.getByRole("switch", { name: "Pull requests", exact: true }).click()
  await expect(page.getByRole("switch", { name: "Pull requests", exact: true })).not.toBeChecked()
  const overflowing = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  expect(overflowing).toBe(false)
})

test("isolated watch and star controls place the dropdown after the count", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  for (const [story, count, label] of [
    ["watch-control", "watch-count", "Notification settings"],
    ["star-control", "star-count", "Add to list"],
  ]) {
    await page.goto(`/iframe.html?id=patterns-repository-header--${story}&viewMode=story&globals=theme:${theme}`)
    const dropdown = page.getByRole("button", { name: label, exact: true })
    await expect(dropdown).toBeEnabled()
    const countBounds = await page.getByTestId(count).boundingBox()
    const dropdownBounds = await dropdown.boundingBox()
    expect(countBounds).not.toBeNull()
    expect(dropdownBounds).not.toBeNull()
    expect(dropdownBounds!.x).toBeGreaterThanOrEqual(countBounds!.x + countBounds!.width)
    expect(dropdownBounds!.y).toBe(countBounds!.y)
    await dropdown.focus()
    await page.keyboard.press("Enter")
    await expect(page.getByRole(story === "watch-control" ? "switch" : "textbox").first()).toBeVisible()
    await page.keyboard.press("Escape")
    await expect(dropdown).toBeFocused()
  }
})

test("four notification columns keep actor and time separate and return without a blue border", async ({
  page,
}, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  await page.goto(`/iframe.html?id=patterns-notifications-inbox--inbox&viewMode=story&globals=theme:${theme}`)
  const row = page.getByRole("listitem").first()
  await expect(row.locator("[data-notification-column]")).toHaveCount(4)
  await expect(row.locator('[data-notification-column="subject"]')).toContainText("Security vulnerability")
  await expect(row.locator('[data-notification-column="subject"]')).toContainText("Opened this issue")
  await expect(row.locator('[data-notification-column="event"]')).toHaveText("Opened")
  await expect(row.locator('[data-notification-column="actor"] a')).toHaveAttribute("href", "/profile/alice")
  await expect(row.locator('[data-notification-column="time"] time')).toContainText("min ago")
  if (testInfo.project.use.viewport!.width >= 640) {
    const positions = await row
      .locator("[data-notification-column]")
      .evaluateAll((cells) => cells.map((cell) => cell.getBoundingClientRect().x))
    expect(positions).toEqual([...positions].sort((left, right) => left - right))
  }
  await page.getByRole("button", { name: "unread", exact: true }).click()
  await page.getByRole("link", { name: /Security vulnerability/ }).click()
  await page.getByRole("link", { name: "Back to notifications" }).click()
  await expect(page.getByRole("link", { name: /Security vulnerability/ })).toBeVisible()
  const decoration = await row.evaluate((element) => {
    const style = getComputedStyle(element)
    return { shadow: style.boxShadow, border: style.borderWidth }
  })
  expect(decoration).toEqual({ shadow: "none", border: "0px" })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
})
