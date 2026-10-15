import { parsePatchFiles } from "@pierre/diffs"
import { CodeView } from "@pierre/diffs/react"
import { createElement as h, useEffect, useState } from "react"
import { createRoot } from "react-dom/client"

const params = new URLSearchParams(location.search)
const count = Number(params.get("files") ?? 500)
const lines = Number(params.get("lines") ?? 40)
let patch = ""
for (let file = 0; file < count; file++) {
  const path = `src/file-${String(file).padStart(4, "0")}.ts`
  patch += `diff --git a/${path} b/${path}\n--- a/${path}\n+++ b/${path}\n@@ -1,${lines} +1,${lines} @@\n`
  for (let line = 0; line < lines; line++) patch += `-export const value_${line} = 12; // configuration\n`
  for (let line = 0; line < lines; line++) patch += `+export const value_${line} = 42; // configuration\n`
}
const files = parsePatchFiles(patch).flatMap((entry) => entry.files)
const started = performance.now()
function App() {
  const [layout, setLayout] = useState("unified")
  useEffect(() => {
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        window.benchmark = { ready: true, mountMs: performance.now() - started }
      }),
    )
  }, [])
  return h(
    "div",
    null,
    h("button", { type: "button", onClick: () => setLayout("unified") }, "Unified"),
    h("button", { type: "button", onClick: () => setLayout("split") }, "Split"),
    h(CodeView, {
      style: { height: "calc(100vh - 80px)" },
      items: files.map((fileDiff, index) => ({ id: String(index), type: "diff", fileDiff })),
      options: { diffStyle: layout, lineDiffType: "word", theme: "github-dark" },
    }),
  )
}
createRoot(document.getElementById("root")).render(h(App))
