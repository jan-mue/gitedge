import AxeBuilder from "@axe-core/playwright"
import { expect, test } from "@playwright/test"

test("repository filters combine, reset, sort, and support keyboard menus", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  const open = async (id: string) => {
    await page.goto(`/iframe.html?id=${id}&viewMode=story&globals=theme:${theme}`)
    await expect(page.locator(".story-canvas")).toBeVisible()
  }
  await open("patterns-repository-issues--populated-issues")
  const issues = page.getByTestId(/^issue-\d/)
  await expect(issues).toHaveCount(2)
  await expect(issues.first()).toHaveAttribute("data-testid", "issue-2")
  const author = page.getByRole("combobox", { name: "Author: All authors" })
  await author.focus()
  await page.keyboard.press("Enter")
  await expect(page.getByRole("option", { name: "All authors" })).toBeFocused()
  await page.keyboard.press("ArrowDown")
  await expect(page.getByRole("option", { name: "alice", exact: true })).toBeFocused()
  await page.keyboard.press("Enter")
  await expect(issues).toHaveCount(1)
  await expect(issues.first()).toHaveAttribute("data-testid", "issue-1")
  await page.getByRole("searchbox").fill("#3")
  await expect(page.getByText("No matching issues")).toBeVisible()
  await page.getByRole("button", { name: "1 Closed" }).click()
  await expect(page.getByTestId("issue-3")).toBeVisible()
  await page.getByRole("button", { name: "Clear filters" }).click()
  await expect(issues).toHaveCount(2)
  await expect(page.getByRole("searchbox")).toHaveValue("")
  await page.getByRole("combobox", { name: "Sort: Newest" }).click()
  await page.getByRole("option", { name: "Recently updated", exact: true }).click()
  await expect(issues.first()).toHaveAttribute("data-testid", "issue-1")
  await page.getByRole("combobox", { name: "Author: All authors" }).click()
  await page.screenshot({ path: `visual-review/issues-author-${testInfo.project.name}.png`, fullPage: true })
  await page.keyboard.press("Escape")
  await expect(page.getByRole("combobox", { name: "Author: All authors" })).toBeFocused()
  await expect(page.getByRole("listbox")).not.toBeVisible()

  await open("patterns-repository-pull-requests--populated-pull-requests")
  await expect(page.getByTestId(/^pr-\d/)).toHaveCount(2)
  await page.getByRole("combobox", { name: "Branch: All target branches" }).click()
  await page.getByRole("option", { name: "main", exact: true }).click()
  await expect(page.getByTestId("pr-1")).toBeVisible()
  await expect(page.getByTestId("pr-2")).not.toBeVisible()
  await page.getByRole("button", { name: "1 Merged" }).click()
  await expect(page.getByTestId("pr-3")).toBeVisible()
  await page.screenshot({ path: `visual-review/pulls-merged-${testInfo.project.name}.png`, fullPage: true })
  await page.getByRole("button", { name: "Clear filters" }).click()
  await expect(page.getByTestId(/^pr-\d/)).toHaveCount(2)
  await expect(page.getByRole("combobox", { name: "Branch: All target branches" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false)
})

test("settings stories save through generated API mocks", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  await page.goto(`/iframe.html?id=patterns-repository-settings--settings&viewMode=story&globals=theme:${theme}`)
  const description = page.getByLabel("Description", { exact: true })
  await expect(description).toHaveValue("Git hosting at the edge")
  await description.fill("Updated repository description")
  const response = page.waitForResponse(
    (response) => response.request().method() === "PATCH" && response.url().includes("/repositories/"),
  )
  await page.getByRole("button", { name: "Save settings", exact: true }).click()
  expect((await response).status()).toBe(200)
  await expect(page.getByRole("button", { name: "Save settings", exact: true })).toBeDisabled()
  await expect(description).toHaveValue("Updated repository description")
})

test("Activity sidebar switches all views; settings keep delete confirmation", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  await page.goto(`/iframe.html?id=patterns-repository-activity--activity&viewMode=story&globals=theme:${theme}`)
  await expect(page.getByText("Overview", { exact: true })).toBeVisible()
  for (const label of ["Pulse", "Contributors", "Code frequency", "Recent commits"]) {
    const button = page.getByRole("button", { name: label, exact: true })
    await button.click()
    await expect(button).toHaveAttribute("aria-pressed", "true")
    await expect(page.locator("nav button[aria-pressed=true]")).toHaveCount(1)
    await page.screenshot({
      path: `visual-review/activity-${label.toLowerCase().replace(/ /g, "-")}-${testInfo.project.name}.png`,
      fullPage: true,
    })
  }
  await page.goto(`/iframe.html?id=patterns-repository-settings--settings&viewMode=story&globals=theme:${theme}`)
  await expect(page.getByRole("heading", { name: "Danger zone" })).toBeVisible()
  const trigger = page.getByRole("button", { name: "Delete this repository", exact: true })
  await page.screenshot({ path: `visual-review/settings-${testInfo.project.name}.png`, fullPage: true })
  await trigger.click()
  const confirm = page.getByRole("button", { name: "Delete repository", exact: true })
  await expect(confirm).toBeDisabled()
  await page.getByLabel("Repository full name").fill("jan-mue/gitedge")
  await expect(confirm).toBeEnabled()
  await page.getByRole("button", { name: "Cancel", exact: true }).click()
  await expect(page.getByRole("dialog")).not.toBeVisible()
  await expect(trigger).toBeFocused()
  await trigger.click()
  await expect(page.getByLabel("Repository full name")).toHaveValue("")
  await expect(confirm).toBeDisabled()
  const results = await new AxeBuilder({ page })
    .include("[role=dialog]")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze()
  expect(results.violations.filter((violation) => violation.id !== "color-contrast")).toEqual([])
  await page.keyboard.press("Escape")
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false)
})
