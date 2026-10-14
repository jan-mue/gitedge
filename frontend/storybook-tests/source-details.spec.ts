import { expect, test } from "@playwright/test"

const themeFor = (project: string) => (project.startsWith("dark") ? "dark" : "light")

test("source details keep the clone field unfocusable while the copy button works", async ({ page }, testInfo) => {
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"])
  const theme = themeFor(testInfo.project.name)
  await page.goto(`/iframe.html?id=patterns-repository-statistics--statistics&viewMode=story&globals=theme:${theme}`)
  const input = page.getByTestId("clone-url")
  await expect(input).toBeDisabled()
  const before = await input.evaluate((element) => {
    const style = getComputedStyle(element)
    return { border: style.borderColor, shadow: style.boxShadow }
  })
  await input.scrollIntoViewIfNeeded()
  const bounds = await input.boundingBox()
  if (!bounds) throw new Error("Clone field is not visible")
  await page.mouse.click(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)
  await expect(input).not.toBeFocused()
  await expect(input).toHaveCSS("border-color", before.border)
  await expect(input).toHaveCSS("box-shadow", before.shadow)
  await page.getByRole("button", { name: "Copy clone URL" }).click()
  await expect(page.getByRole("status").filter({ hasText: "Copied to clipboard" })).toBeVisible()
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(await input.inputValue())
})

test("source details show per-entry commit subjects and dates in directory rows", async ({ page }, testInfo) => {
  const theme = themeFor(testInfo.project.name)
  await page.goto(`/iframe.html?id=patterns-repository-files--file-tree&viewMode=story&globals=theme:${theme}`)
  const directory = page.getByTestId("tree-entry-frontend")
  const readme = page.getByTestId("tree-entry-README.md")
  await expect(directory).toContainText("Improve repository browsing")
  await expect(readme).toContainText("Document development commands")
  await expect(directory.locator("time")).toHaveAttribute("datetime", "2026-10-10T20:26:33.000Z")
  await expect(readme.locator("time")).toHaveAttribute("datetime", "2026-10-11T22:00:00.000Z")
  await expect(readme).not.toContainText("4.0 KB")
  await page.screenshot({ path: `visual-review/file-commit-rows-${testInfo.project.name}.png`, fullPage: true })
})

test("source details show the file change above code and preserve revision links", async ({ page }, testInfo) => {
  const theme = themeFor(testInfo.project.name)
  await page.goto(
    `/iframe.html?id=patterns-repository-file-contents--source-file&viewMode=story&globals=theme:${theme}`,
  )
  await expect(page.getByTestId("last-commit-header")).toContainText("Initialize the application")
  await expect(page.getByTestId("last-commit-sha")).toHaveAttribute(
    "href",
    "/jan-mue/gitedge/commit/77ddec2ecc829b765bef3ee2674b42246d1d6fba",
  )
  await expect(page.getByRole("link", { name: "Permalink", exact: true })).toHaveAttribute(
    "href",
    "/jan-mue/gitedge/src/commit/ce65263abc12345678901234567890123456789012/src/main.ts",
  )
  await page.screenshot({ path: `visual-review/file-commit-header-${testInfo.project.name}.png`, fullPage: true })
  await page.getByRole("button", { name: "Escape tabs", exact: true }).focus()
  await page.keyboard.press("Tab")
  await expect(page.getByRole("region", { name: "File contents", exact: true })).toBeFocused()
})
