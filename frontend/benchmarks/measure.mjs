import { chromium } from "@playwright/test"

const target = process.argv[2] ?? "http://127.0.0.1:5175/benchmarks/diff-viewer.html"
const browser = await chromium.launch({
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
    : {}),
  headless: true,
})
try {
  for (const files of [100, 500]) {
    for (let sample = 0; sample < 3; sample++) {
      const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
      const errors = []
      page.on("pageerror", (error) => errors.push(error.message))
      const url = new URL(target)
      url.searchParams.set("files", String(files))
      url.searchParams.set("lines", "40")
      await page.goto(url.toString())
      await page.waitForFunction(() => window.benchmark?.ready)
      const result = await page.evaluate(async () => {
        const start = performance.now()
        Array.from(document.querySelectorAll("button"))
          .find((button) => button.textContent === "Split")
          .click()
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
        const splitMs = performance.now() - start
        const countNodes = (root) =>
          Array.from(root.querySelectorAll("*")).reduce(
            (count, node) => count + 1 + (node.shadowRoot ? countNodes(node.shadowRoot) : 0),
            0,
          )
        return { mountMs: window.benchmark.mountMs, splitMs, nodes: countNodes(document) }
      })
      if (errors.length) throw new Error(errors.join("\n"))
      console.log(JSON.stringify({ files, sample, ...result }))
      await page.close()
    }
  }
} finally {
  await browser.close()
}
