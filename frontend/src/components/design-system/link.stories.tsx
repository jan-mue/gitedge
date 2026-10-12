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
export const Contexts: Story = {
  render: () => (
    <div className="grid gap-4 sm:grid-cols-2">
      {(
        [
          "avatar",
          "author",
          "strong",
          "target",
          "preview",
          "comments",
          "listRow",
          "body",
          "repositoryStrong",
          "repository",
          "codeAction",
          "repositoryEntry",
          "truncated",
          "commitPreview",
          "hash",
          "branch",
          "revision",
          "title",
          "commitHash",
          "successAction",
          "formAction",
          "caption",
          "icon",
          "row",
          "item",
        ] as const
      ).map((appearance) => (
        <div key={appearance} className="space-y-2">
          <p className="text-xs text-muted-foreground">{appearance}</p>
          <ExternalLink href="#repository" appearance={appearance}>
            {appearance === "avatar" ? "JM" : "GitEdge repository"}
          </ExternalLink>
        </div>
      ))}
    </div>
  ),
}
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
