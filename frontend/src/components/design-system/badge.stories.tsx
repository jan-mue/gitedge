import type { Meta, StoryObj } from "@storybook/react-vite"
import { CircleCheck, CircleDot, GitMerge } from "lucide-react"
import { Badge } from "@/components/design-system"

const meta = {
  title: "Components/Badge",
  component: Badge,
  args: { children: "Open", variant: "success" },
} satisfies Meta<typeof Badge>
export default meta
type Story = StoryObj

export const Badges: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      {(["default", "secondary", "outline", "destructive", "success", "warning", "info", "merged"] as const).map(
        (variant) => (
          <Badge key={variant} variant={variant}>
            {variant}
          </Badge>
        ),
      )}
    </div>
  ),
}
export const RepositoryStates: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      <Badge variant="success">
        <CircleDot aria-hidden="true" />
        Open
      </Badge>
      <Badge variant="secondary">
        <CircleCheck aria-hidden="true" />
        Closed
      </Badge>
      <Badge variant="merged">
        <GitMerge aria-hidden="true" />
        Merged
      </Badge>
      <Badge variant="destructive">Deleted</Badge>
    </div>
  ),
}
