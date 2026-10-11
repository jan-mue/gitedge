import path from "node:path"
import type { StorybookConfig } from "@storybook/react-vite"

const config: StorybookConfig = {
  stories: ["../src/design-system/stories/**/*.mdx", "../src/design-system/stories/**/*.stories.tsx"],
  addons: ["@storybook/addon-docs", "@storybook/addon-a11y", "@storybook/addon-themes", "msw-storybook-addon"],
  framework: {
    name: "@storybook/react-vite",
    options: { builder: { viteConfigPath: path.resolve(import.meta.dirname, "./vite.config.ts") } },
  },
  staticDirs: ["../public"],
  docs: { defaultName: "Documentation" },
  core: { disableTelemetry: true },
}
export default config
