import { expect, test } from "@playwright/test"

test("diff stories render, collapse viewed files and show an accessible skeleton", async ({ page }) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  await page.goto("/iframe.html?id=repository-diff-viewer--default&viewMode=story")
  await expect(page.getByTestId("diff-viewer")).toBeVisible()
  await page.goto("/iframe.html?id=repository-diff-viewer--review&viewMode=story")
  await expect(page.getByRole("button", { name: "Expand tests/test_config.py", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Expand tests/test_config.py", exact: true }).click()
  await expect(page.getByRole("button", { name: "Collapse tests/test_config.py", exact: true })).toBeVisible()
  await page.goto("/iframe.html?id=repository-diff-viewer--loading&viewMode=story")
  await expect(page.getByRole("status", { name: "Loading file diff" }).first()).toBeVisible()
  await page.emulateMedia({ reducedMotion: "reduce" })
  expect(
    await page
      .locator(".code-skeleton")
      .first()
      .evaluate((element) => getComputedStyle(element, "::after").animationName),
  ).toBe("none")
  expect(errors).toEqual([])
})

test("PR conversation and commits follow the reference layout", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  await page.goto(
    `/iframe.html?id=patterns-repository-pull-request-detail--conversation-and-commits&viewMode=story&globals=theme:${theme}`,
  )
  await expect(page.getByTestId("pr-conversation")).toBeVisible()
  await expect(page.getByRole("complementary", { name: "Pull request details" })).toBeVisible()
  await expect(page.getByText("Thanks for adding keyboard support.", { exact: true })).toBeVisible()
  await page.screenshot({ path: `visual-review/pr-conversation-${testInfo.project.name}.png`, fullPage: true })
  await page.getByRole("tab", { name: /^Commits/ }).click()
  await expect(page.getByTestId("pr-commits")).toBeVisible()
  await expect(page.getByRole("link", { name: "Preserve focus when switching files" })).toHaveAttribute(
    "href",
    /\/commit\/a{40}$/,
  )
  await page.screenshot({ path: `visual-review/pr-commits-${testInfo.project.name}.png`, fullPage: true })
})

test("review opens below its trigger, saves on Escape and restores focus", async ({ page }) => {
  await page.goto("/iframe.html?id=patterns-repository-pull-request-detail--review-dropdown&viewMode=story")
  const trigger = page.getByRole("button", { name: "Review", exact: true })
  await trigger.click()
  const dropdown = page.getByRole("dialog", { name: "Submit review" })
  await expect(dropdown).toBeVisible()
  const triggerBounds = await trigger.boundingBox()
  const menuBounds = await dropdown.boundingBox()
  expect(menuBounds!.y).toBeGreaterThanOrEqual(triggerBounds!.y + triggerBounds!.height)
  await page.getByRole("textbox", { name: "Review comment" }).fill("Keep this draft")
  await page.keyboard.press("Escape")
  await expect(dropdown).not.toBeVisible()
  await expect(trigger).toBeFocused()
  await expect(trigger).toBeEnabled()
  await trigger.click()
  await expect(page.getByRole("textbox", { name: "Review comment" })).toHaveValue("Keep this draft")
})
