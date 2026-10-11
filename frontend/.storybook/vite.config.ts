import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from "vite"
// Storybook is independent of the app router and related backend deployment.
export default defineConfig({
  plugins: [tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "../src") } },
  define: { "import.meta.env.VITE_API_URL": JSON.stringify("") },
})
