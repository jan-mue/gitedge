import type { Meta, StoryObj } from "@storybook/react-vite"
import { GitFork } from "lucide-react"
import { ExternalLink } from "@/components/design-system"

const meta = {
  title: "Components/Link",
  component: ExternalLink,
  args: { href: "#repository", children: "Repository" },
} satisfies Meta<typeof ExternalLink>
export default meta
type Story = StoryObj<typeof meta>
export const Default: Story = {}
export const Muted: Story = { args: { appearance: "muted" } }
export const Action: Story = { args: { appearance: "action" } }
export const CommitHash: Story = { args: { appearance: "code", children: "7e877ad" } }
export const Settings: Story = { args: { appearance: "settings" } }
export const DangerZone: Story = { args: { appearance: "settingsDanger", children: "Danger zone" } }
export const SocialIcon: Story = {
  args: {
    appearance: "social",
    children: <GitFork aria-hidden="true" />,
    "aria-label": "GitHub",
    target: "_blank",
    rel: "noopener noreferrer",
  },
}
