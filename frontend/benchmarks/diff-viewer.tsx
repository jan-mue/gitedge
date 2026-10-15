import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useEffect } from "react"
import { createRoot } from "react-dom/client"
import { DiffViewer } from "../src/components/Repository/DiffViewer"
import "../src/index.css"

declare global {
  interface Window {
    benchmark?: { ready: boolean; mountMs: number; nodes: number }
  }
}

const params = new URLSearchParams(location.search)
const count = Number(params.get("files") ?? 500)
const lines = Number(params.get("lines") ?? 40)
const files = Array.from({ length: count }, (_, file) => ({
  path: `src/file-${String(file).padStart(4, "0")}.ts`,
  change_type: "modify" as const,
  additions: lines,
  deletions: lines,
  patch: "",
  hunks: [
    {
      header: `@@ -1,${lines} +1,${lines} @@`,
      lines: Array.from({ length: lines * 2 }, (_, i) => ({
        kind: i < lines ? "delete" : "add",
        old_line: i < lines ? i + 1 : null,
        new_line: i >= lines ? i - lines + 1 : null,
        tokens: [
          { text: "export ", syntax: "keyword" },
          { text: "const ", syntax: "keyword" },
          { text: `value_${i % lines}`, syntax: "name" },
          { text: " = ", syntax: "operator" },
          { text: i < lines ? "12" : "42", syntax: "literal-number", changed: true },
          { text: "; // configuration", syntax: "comment" },
        ],
      })),
      rows: Array.from({ length: lines }, (_, i) => ({ old: i, new: i + lines })),
    },
  ],
}))
const client = new QueryClient()
const started = performance.now()
function App() {
  useEffect(() => {
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        window.benchmark = {
          ready: true,
          mountMs: performance.now() - started,
          nodes: document.querySelectorAll("*").length,
        }
      }),
    )
  }, [])
  return (
    <QueryClientProvider client={client}>
      <div style={{ padding: 24 }}>
        <DiffViewer files={files} additions={count * lines} deletions={count * lines} />
      </div>
    </QueryClientProvider>
  )
}
createRoot(document.getElementById("root")!).render(<App />)
