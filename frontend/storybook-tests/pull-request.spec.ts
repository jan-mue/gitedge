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
  const activeTab = page.getByRole("tab", { name: "Conversation", exact: true })
  const geometry = await activeTab.evaluate((element) => {
    const style = getComputedStyle(element)
    return {
      border: style.borderBottomColor,
      primary: getComputedStyle(document.documentElement).getPropertyValue("--primary"),
      top: style.borderTopWidth,
      left: style.borderLeftWidth,
      right: style.borderRightWidth,
      bottom: style.borderBottomWidth,
      background: style.backgroundColor,
      height: element.getBoundingClientRect().height,
    }
  })
  expect(geometry.top).toBe("0px")
  expect(geometry.left).toBe("0px")
  expect(geometry.right).toBe("0px")
  expect(geometry.bottom).toBe("2px")
  expect(geometry.background).toBe("rgba(0, 0, 0, 0)")
  expect(geometry.height).toBe(42)
  const primaryColor = await page.evaluate(() => {
    const probe = document.createElement("span")
    probe.style.color = "var(--primary)"
    document.body.append(probe)
    const color = getComputedStyle(probe).color
    probe.remove()
    return color
  })
  expect(geometry.border).toBe(primaryColor)
  await page.screenshot({ path: `visual-review/pr-conversation-${testInfo.project.name}.png`, fullPage: true })
  await page.getByRole("tab", { name: /^Commits/ }).click()
  await expect(page.getByTestId("pr-commits")).toBeVisible()
  await expect(page.getByRole("link", { name: "Preserve focus when switching files" })).toHaveAttribute(
    "href",
    /\/commit\/a{40}$/,
  )
  await page.screenshot({ path: `visual-review/pr-commits-${testInfo.project.name}.png`, fullPage: true })
  await page.getByRole("tab", { name: "Files Changed", exact: true }).click()
  await page.getByTestId("pr-tab-diff-stats").scrollIntoViewIfNeeded()
  await expect(page.getByTestId("pr-tab-diff-stats")).toBeVisible()
  await page.screenshot({ path: `visual-review/pr-files-${testInfo.project.name}.png`, fullPage: true })
})

test("tablet layouts keep metadata to the right of the conversation", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name.endsWith("mobile"), "Tablet widths are checked in both desktop theme projects")
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  for (const width of [768, 820, 1024, 1180]) {
    await page.setViewportSize({ width, height: 1180 })
    await page.goto(
      `/iframe.html?id=patterns-repository-pull-request-detail--review-statuses&viewMode=story&globals=theme:${theme}`,
    )
    const conversation = page.getByTestId("comments-section")
    const sidebar = page.getByRole("complementary", { name: "Pull request details" })
    await expect(sidebar).toBeVisible()
    const contentBounds = (await conversation.boundingBox())!
    const sidebarBounds = (await sidebar.boundingBox())!
    expect(sidebarBounds.x).toBeGreaterThanOrEqual(contentBounds.x + contentBounds.width)
    expect(Math.abs(sidebarBounds.y - contentBounds.y)).toBeLessThan(2)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await page.screenshot({ path: `visual-review/pr-tablet-${width}-${theme}.png`, fullPage: true })
  }
})

test("review events use Gitea's check and diff markers, and merged PRs have no reopen action", async ({
  page,
}, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  await page.goto(
    `/iframe.html?id=patterns-repository-pull-request-detail--merged&viewMode=story&globals=theme:${theme}`,
  )
  await expect(page.getByTestId("pr-state")).toContainText("Merged")
  await expect(page.getByTestId("reopen-pr")).toHaveCount(0)
  await expect(page.getByTestId("close-pr")).toHaveCount(0)
  const timeline = page.getByTestId("comments-section")
  await expect(timeline.locator('[data-review-state="approved"]')).toHaveClass(/lucide-check/)
  await expect(timeline.locator('[data-review-state="changes_requested"]')).toHaveClass(/lucide-diff/)
  await expect(timeline.locator('[data-review-state="merged"]').first()).toHaveClass(/lucide-git-merge/)
  await page.screenshot({ path: `visual-review/pr-merged-${testInfo.project.name}.png`, fullPage: true })
  await page.goto(
    `/iframe.html?id=patterns-repository-pull-request-detail--closed&viewMode=story&globals=theme:${theme}`,
  )
  await expect(page.getByTestId("reopen-pr")).toBeVisible()
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
