import "@fontsource-variable/inter"
import "@fontsource-variable/jetbrains-mono"
import "../src/index.css"
import "./preview.css"
import { withThemeByClassName } from "@storybook/addon-themes"
import type { Preview } from "@storybook/react-vite"
import { mswLoader } from "msw-storybook-addon/csf3"
import { TooltipProvider } from "@/components/design-system"
import { ThemedDocsContainer } from "./docs-container"

const preview: Preview = {
  initialGlobals: { theme: "dark" },
  decorators: [
    withThemeByClassName({ themes: { dark: "dark", light: "light" }, defaultTheme: "dark" }),
    (Story) => (
      <TooltipProvider>
        <div className="story-canvas">
          <Story />
        </div>
      </TooltipProvider>
    ),
  ],
  tags: ["autodocs"],
  loaders: [mswLoader()],
  parameters: {
    layout: "padded",
    backgrounds: { disable: true },
    docs: { container: ThemedDocsContainer },
    controls: { matchers: { color: /(background|color)$/i, date: /Date$/i } },
    options: { storySort: { order: ["Foundations", "Components", "Patterns"] } },
  },
}
export default preview
