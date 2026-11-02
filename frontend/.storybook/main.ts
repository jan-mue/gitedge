import path from "node:path"
import type { StorybookConfig } from "@storybook/react-vite"

const config: StorybookConfig = {
  stories: ["../src/components/**/*.mdx", "../src/components/**/*.stories.tsx"],
  addons: ["@storybook/addon-docs", "@storybook/addon-mcp", "@storybook/addon-themes", "msw-storybook-addon"],
  framework: {
    name: "@storybook/react-vite",
    options: { builder: { viteConfigPath: path.resolve(import.meta.dirname, "./vite.config.ts") } },
  },
  staticDirs: ["../public"],
  docs: { defaultName: "Documentation" },
  features: { componentsManifest: true },
  core: { disableTelemetry: true },
}
export default config
