import "@fontsource-variable/inter"
import "@fontsource-variable/jetbrains-mono"
import "../src/index.css"
import "./preview.css"
import { withThemeByClassName } from "@storybook/addon-themes"
import type { Preview } from "@storybook/react-vite"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { mswLoader } from "msw-storybook-addon/csf3"
import { type ReactNode, useState } from "react"
import { TooltipProvider } from "@/components/design-system"
import { ThemedDocsContainer } from "./docs-container"

const StoryProviders = ({ children }: { children: ReactNode }) => {
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false } } }))
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>{children}</TooltipProvider>
    </QueryClientProvider>
  )
}

const preview: Preview = {
  initialGlobals: { theme: "dark" },
  decorators: [
    withThemeByClassName({ themes: { dark: "dark", light: "light" }, defaultTheme: "dark" }),
    (Story, context) => (
      <StoryProviders key={context.id}>
        <div className="story-canvas">
          <Story />
        </div>
      </StoryProviders>
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
