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

test("review events use clear status markers, and merged PRs have no reopen action", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  await page.goto(
    `/iframe.html?id=patterns-repository-pull-request-detail--merged&viewMode=story&globals=theme:${theme}`,
  )
  await expect(page.getByTestId("pr-state")).toContainText("Merged")
  await expect(page.getByTestId("reopen-pr")).toHaveCount(0)
  await expect(page.getByTestId("close-pr")).toHaveCount(0)
  const timeline = page.getByTestId("comments-section")
  expect((await timeline.locator("article > header").first().boundingBox())!.height).toBeLessThanOrEqual(40)

  await expect(timeline.locator('[data-review-state="approved"] svg')).toHaveClass(/lucide-check/)
  await expect(timeline.locator('[data-review-state="changes_requested"] svg')).toHaveClass(
    /lucide-message-square-warning/,
  )
  await expect(timeline.locator('[data-review-state="merged"] svg').first()).toHaveClass(/lucide-git-merge/)
  if (!testInfo.project.name.endsWith("mobile")) {
    const bounds = await timeline.locator('[data-review-state="approved"]').evaluate((node) => {
      const outer = node.getBoundingClientRect()
      const icon = node.querySelector("svg")!.getBoundingClientRect()
      return {
        outer: outer.width,
        icon: icon.width,
        gap: icon.left - outer.left,
        padding: getComputedStyle(node.querySelector("svg")!).padding,
      }
    })
    expect(bounds).toEqual({ outer: 32, icon: 16, gap: 8, padding: "0px" })
    const alignment = await timeline.locator('[data-review-state="approved"]').evaluate((node) => {
      const icon = node.getBoundingClientRect()
      const row = node
        .closest("[data-timeline-item]")!
        .querySelector('[data-testid^="review-"] > div')!
        .getBoundingClientRect()
      return { gap: row.left - icon.right, center: Math.abs(row.top + row.height / 2 - icon.top - icon.height / 2) }
    })
    expect(alignment.gap).toBeGreaterThanOrEqual(16)
    expect(alignment.center).toBeLessThan(1)
  }
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

test("comments after merging follow the merge event and the timeline ends at the composer border", async ({
  page,
}, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  await page.goto(
    `/iframe.html?id=patterns-repository-pull-request-detail--after-merge&viewMode=story&globals=theme:${theme}`,
  )
  const before = page.getByTestId("comment-before-merge")
  const merge = page.getByTestId("pr-event-pull_request_merge")
  const after = page.getByTestId("comment-after-merge")
  await expect(after).toBeVisible()
  await expect(merge).toBeVisible()
  expect(
    await before.evaluate(
      (node) =>
        !!(
          node.compareDocumentPosition(document.querySelector('[data-testid="pr-event-pull_request_merge"]')!) &
          Node.DOCUMENT_POSITION_FOLLOWING
        ),
    ),
  ).toBe(true)
  expect(
    await merge.evaluate(
      (node) =>
        !!(
          node.compareDocumentPosition(document.querySelector('[data-testid="comment-after-merge"]')!) &
          Node.DOCUMENT_POSITION_FOLLOWING
        ),
    ),
  ).toBe(true)
  const endpoint = await page.locator('[data-timeline-item="composer"]').evaluate((node) => {
    const line = getComputedStyle(node, "::before")
    const elbow = getComputedStyle(node, "::after")
    return {
      display: elbow.display,
      height: line.height,
      right: node.getBoundingClientRect().left + Number.parseFloat(elbow.left) + Number.parseFloat(elbow.width),
      border: node.lastElementChild!.getBoundingClientRect().left,
    }
  })
  if (testInfo.project.name.endsWith("mobile")) expect(endpoint.display).toBe("none")
  else {
    expect(endpoint.height).toBe("25px")
    expect(Math.abs(endpoint.right - endpoint.border)).toBeLessThan(1)
  }
  await page.screenshot({ path: `visual-review/pr-after-merge-${testInfo.project.name}.png`, fullPage: true })
})

test("review comments display highlighted diff context from their original revision", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  const requests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/context")) requests.push(request.url())
  })
  await page.goto(
    `/iframe.html?id=patterns-repository-pull-request-detail--review-comments&viewMode=story&globals=theme:${theme}`,
  )
  const old = page.getByRole("region", { name: "Review comment on src/config.py old line 1", exact: true })
  await old.scrollIntoViewIfNeeded()
  await expect(old.locator('[data-comment-anchor="true"] code')).toHaveText("timeout = 12")
  const current = page.getByRole("region", { name: "Review comment on src/config.py new line 1", exact: true }).first()
  await expect(current.locator('[data-comment-anchor="true"] code')).toHaveText("timeout = 42")
  await expect(current.locator('[data-syntax="literal-number"][data-changed="true"]').first()).toBeVisible()
  const outdated = page.getByRole("region", { name: "Review comment on src/config.py new line 1", exact: true }).last()
  await outdated.scrollIntoViewIfNeeded()
  await expect(outdated.getByText("Outdated", { exact: true })).toBeVisible()
  await expect(outdated.locator('[data-comment-anchor="true"] code')).toHaveText("timeout = 42")
  expect(requests.filter((url) => url.includes("/reviews/outdated-review/comments/0/context"))).toHaveLength(1)
  await expect(old.locator(".review-diff-context .diff-cell:last-child")).toHaveAttribute("data-comment-anchor", "true")
  await expect(current.locator(".review-diff-context .diff-cell:last-child")).toHaveAttribute(
    "data-comment-anchor",
    "true",
  )
  expect(await old.locator(".review-diff-context").evaluate((node) => getComputedStyle(node).paddingBottom)).toBe("0px")
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: `visual-review/pr-review-context-${testInfo.project.name}.png`, fullPage: true })
})

test("conversation loads without inactive Git tabs and review replies stay in their thread", async ({
  page,
}, testInfo) => {
  const requested: string[] = []
  page.on("request", (request) => requested.push(request.url()))
  await page.goto("/iframe.html?id=patterns-repository-pull-request-detail--conversation-and-commits&viewMode=story")
  await expect(page.getByTestId("pr-conversation")).toBeVisible()
  expect(requested.filter((url) => /\/pulls\/1\/(files|commits)(\?|$)/.test(url))).toEqual([])
  await page.getByRole("tab", { name: /^Commits/ }).click()
  await expect(page.getByTestId("pr-commits")).toBeVisible()
  expect(requested.filter((url) => /\/pulls\/1\/commits(\?|$)/.test(url))).toHaveLength(1)
  await page.goto("/iframe.html?id=patterns-repository-pull-request-detail--review-discussion&viewMode=story")
  const thread = page.getByRole("region", { name: "Review comment on src/config.py new line 1", exact: true })
  await thread.getByRole("button", { name: "Reply", exact: true }).click()
  await thread.getByRole("textbox", { name: "Reply to review comment" }).fill("The new test covers this value.")
  await thread.getByRole("button", { name: "Reply", exact: true }).click()
  await expect(thread.getByText("The new test covers this value.", { exact: true })).toBeVisible()
  const compactReply = thread.locator('[data-testid^="review-reply-"]').first()
  expect((await compactReply.locator("header").boundingBox())!.height).toBeLessThanOrEqual(24)
  expect((await compactReply.boundingBox())!.height).toBeLessThan(90)
  expect(await compactReply.locator(".markdown-body").evaluate((node) => getComputedStyle(node).fontSize)).toBe("14px")

  await expect(thread.getByRole("textbox", { name: "Reply to review comment" })).toHaveCount(0)
  await page.screenshot({ path: `visual-review/pr-thread-replies-${testInfo.project.name}.png`, fullPage: true })
})

test("PR merge dropdown supports all strategies with clear descriptions", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  await page.goto(
    `/iframe.html?id=patterns-repository-pull-request-detail--merge-methods&viewMode=story&globals=theme:${theme}`,
  )
  await expect(page.getByTestId("merge-pr")).toBeEnabled()
  await page.getByRole("button", { name: "Choose merge method" }).click()
  await expect(page.getByRole("menuitem")).toHaveCount(3)
  await page.getByRole("menuitem").filter({ hasText: "Squash and merge" }).click()
  await expect(page.getByTestId("merge-pr")).toHaveText("Squash and merge")
  await page.screenshot({ path: `visual-review/pr-merge-dropdown-${testInfo.project.name}.png`, fullPage: true })
})

test("conflicts are visible before merging and keep the merge button disabled", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  const merges: string[] = []
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/merge")) merges.push(request.url())
  })
  await page.goto(
    `/iframe.html?id=patterns-repository-pull-request-detail--merge-conflicts&viewMode=story&globals=theme:${theme}`,
  )
  await expect(page.getByText("This branch has conflicts that must be resolved", { exact: true })).toBeVisible()
  await expect(page.getByRole("list", { name: "Conflicting files" })).toContainText("backend/pyproject.toml")
  await expect(page.getByRole("list", { name: "Conflicting files" })).toContainText("uv.lock")
  await expect(page.getByTestId("merge-pr")).toBeDisabled()
  expect(merges).toEqual([])
  await page.getByRole("button", { name: "Choose merge method" }).click()
  await page.getByRole("menuitem").filter({ hasText: "Rebase and merge" }).click()
  await expect(page.getByTestId("merge-pr")).toHaveText("Rebase and merge")
  await expect(page.getByTestId("merge-pr")).toBeDisabled()
  await page.getByRole("button", { name: "Check again" }).click()
  await expect(page.getByText("This branch has conflicts that must be resolved", { exact: true })).toBeVisible()
  expect(merges).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: `visual-review/pr-merge-conflicts-${testInfo.project.name}.png`, fullPage: true })
})
