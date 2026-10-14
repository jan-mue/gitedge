import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import { msw } from "msw/vite"
import { defineConfig } from "vite"
export default defineConfig({
  plugins: [tailwindcss(), msw({ mode: "worker-only" })],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "../src") } },
  define: { "import.meta.env.VITE_API_URL": JSON.stringify("") },
})
