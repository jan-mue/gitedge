import fs from "node:fs"
import path from "node:path"
import AxeBuilder from "@axe-core/playwright"
import { test as baseTest, expect, type Page } from "@playwright/test"

// Keep a browser page per worker; each story still reloads in a fresh document.
// Reusing the context avoids repeatedly installing MSW for every catalog entry.
const test = baseTest.extend<object, { catalogPage: Page }>({
  catalogPage: [
    async ({ browser }, use, workerInfo) => {
      const context = await browser.newContext({
        baseURL: workerInfo.project.use.baseURL,
        viewport: workerInfo.project.use.viewport,
      })
      const theme = workerInfo.project.name.startsWith("dark") ? "dark" : "light"
      await context.addInitScript((theme) => {
        const apply = () => document.documentElement?.classList.add(theme)
        if (document.documentElement) apply()
        else {
          const observer = new MutationObserver(() => {
            if (document.documentElement) {
              apply()
              observer.disconnect()
            }
          })
          observer.observe(document, { childList: true })
        }
      }, theme)
      const page = await context.newPage()
      await use(page)
      await context.close()
    },
    { scope: "worker" },
  ],
  page: async ({ catalogPage }, use) => {
    catalogPage.removeAllListeners("pageerror")
    await use(catalogPage)
  },
})

const index = JSON.parse(
  fs.readFileSync(path.resolve(import.meta.dirname, "../storybook-static/index.json"), "utf8"),
) as {
  entries: Record<string, { id: string; type: string; name: string; title: string }>
}
for (const story of Object.values(index.entries).filter((entry) => entry.type === "story")) {
  test(`${story.title} / ${story.name}`, async ({ page }, testInfo) => {
    const errors: string[] = []
    page.on("pageerror", (error) => errors.push(error.message))
    const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
    await page.goto(`/iframe.html?id=${story.id}&viewMode=story&globals=theme:${theme}`)
    await expect(page.locator("#storybook-root .story-canvas")).toBeAttached()
    await expect(page.locator(".sb-errordisplay")).not.toBeVisible()
    if (/components-overlays--(dialog-open|compact-dialog|sheet-(right|left|top|bottom))$/.test(story.id)) {
      await expect(page.getByRole("dialog")).toBeVisible()
    }
    if (story.id === "components-overlays--menu-open") await expect(page.getByRole("menu")).toBeVisible()
    if (story.id === "components-navigation-and-data--select-open")
      await expect(page.getByRole("listbox")).toBeVisible()
    await page.evaluate(async () => {
      await document.fonts.ready
      // Theme decorators and overlays can start a transition after the first render.
      await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
      await Promise.all(
        document
          .getAnimations()
          .filter(
            (animation) =>
              animation.playState === "running" && Number.isFinite(animation.effect?.getComputedTiming().iterations),
          )
          .map((animation) => animation.finished.catch(() => {})),
      )
    })
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            document
              .getAnimations()
              .filter(
                (animation) =>
                  animation.playState === "running" &&
                  Number.isFinite(animation.effect?.getComputedTiming().iterations),
              ).length,
        ),
      )
      .toBe(0)
    // Wait for async patterns to settle; loading stories deliberately never resolve.
    if (story.id === "patterns-repository--header" || story.id === "patterns-repository--selected-actions") {
      await expect(page.getByTestId("star-count")).toHaveText(/128|129/)
    }
    if (story.id === "patterns-repository--statistics")
      await expect(page.getByText("255", { exact: true })).toBeVisible()
    if (story.id === "patterns-repository--empty-issues")
      await expect(page.getByTestId("issues-empty-state")).toBeVisible()
    if (story.id === "patterns-repository--issues-error") await expect(page.getByRole("alert")).toBeVisible()
    if (story.id === "patterns-repository--empty-pull-requests")
      await expect(page.getByTestId("pulls-empty-state")).toBeVisible()
    expect(errors).toEqual([])
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    expect(overflow, "The story should fit the viewport without page-level horizontal scrolling").toBe(false)
    const results = await new AxeBuilder({ page })
      .include(".story-canvas, [role=dialog], [role=menu], [role=listbox]")
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .disableRules(["region"])
      .analyze()
    expect(
      results.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        nodes: v.nodes.map((n) => ({ target: n.target, reason: n.failureSummary })),
      })),
    ).toEqual([])
  })
}

test("keyboard, hover, password, validation, tabs, and dialogs", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  const open = async (id: string) => {
    await page.goto(`/iframe.html?id=${id}&viewMode=story&globals=theme:${theme}`)
    await expect(page.locator(".story-canvas")).toBeVisible()
  }
  await open("components-button--primary")
  const button = page.getByRole("button", { name: "Create repository", exact: true })
  const normal = await button.evaluate((el) => getComputedStyle(el).backgroundColor)
  await button.hover()
  await expect.poll(() => button.evaluate((el) => getComputedStyle(el).backgroundColor)).not.toBe(normal)
  await page.mouse.move(0, 0)
  await page.keyboard.press("Tab")
  await expect(button).toBeFocused()
  await expect.poll(() => button.evaluate((el) => getComputedStyle(el).boxShadow)).not.toBe("none")
  await open("components-fields--password")
  await page.getByRole("button", { name: "Show password" }).click()
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute("type", "text")
  await page.getByRole("button", { name: "Hide password" }).click()
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute("type", "password")
  await open("components-form--default")
  await page.getByRole("button", { name: "Create repository" }).click()
  await expect(page.getByText("Repository name is required")).toBeVisible()
  await expect(page.getByRole("textbox")).toHaveAttribute("aria-invalid", "true")
  await open("components-navigation-and-data--tab-navigation")
  await page.getByRole("tab", { name: "Code", exact: true }).focus()
  await page.keyboard.press("ArrowRight")
  await expect(page.getByRole("tab", { name: "Issues", exact: true })).toBeFocused()
  await page.keyboard.press("Enter")
  await expect(page.getByText("Track bugs and feature requests.")).toBeVisible()
  await open("components-overlays--dialog-closed")
  const trigger = page.getByRole("button", { name: "New repository", exact: true })
  await trigger.click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(page.getByRole("dialog")).not.toBeVisible()
  await expect(trigger).toBeFocused()
})

test("repository actions and navigation use real API and router state", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  await page.goto(`/iframe.html?id=patterns-repository--header&viewMode=story&globals=theme:${theme}`)
  await expect(page.getByTestId("star-count")).toHaveText("128")
  await page.getByRole("button", { name: "Star", exact: true }).click()
  await expect(page.getByRole("button", { name: "Starred", exact: true })).toHaveAttribute("aria-pressed", "true")
  await expect(page.getByTestId("star-count")).toHaveText("129")
  await page.getByRole("button", { name: "Starred", exact: true }).click()
  await expect(page.getByTestId("star-count")).toHaveText("128")
  await page.getByRole("button", { name: "Watch", exact: true }).click()
  await expect(page.getByRole("button", { name: "Unwatch", exact: true })).toHaveAttribute("aria-pressed", "true")
  await expect(page.getByTestId("watch-count")).toHaveText("33")
  await page.getByRole("link", { name: "Issues", exact: true }).click()
  await expect(page.getByRole("link", { name: "Issues", exact: true })).toHaveAttribute("data-active", "true")
})

test("notification variants render with the shared theme", async ({ page }, testInfo) => {
  const theme = testInfo.project.name.startsWith("dark") ? "dark" : "light"
  await page.goto(`/iframe.html?id=components-notifications--toast-states&viewMode=story&globals=theme:${theme}`)
  for (const [button, message] of [
    ["Success", "Repository created"],
    ["Error", "Unable to save changes"],
    ["Information", "Copied clone URL"],
    ["Warning", "This action cannot be undone"],
    ["Loading", "Creating repository…"],
  ]) {
    await page.getByRole("button", { name: button, exact: true }).click()
    await expect(page.getByText(message, { exact: true })).toBeVisible()
  }
  const results = await new AxeBuilder({ page })
    .include("[data-sonner-toaster]")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze()
  expect(
    results.violations.map((violation) => ({
      id: violation.id,
      nodes: violation.nodes.map((node) => node.failureSummary),
    })),
  ).toEqual([])
})
