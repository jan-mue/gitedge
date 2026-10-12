import type { Meta, StoryObj } from "@storybook/react-vite"
import { Copy, GitFork, GitMerge, Star } from "lucide-react"
import { Button, ButtonGroup, ButtonGroupText } from "@/components/design-system"

const meta = {
  title: "Components/Button",
  component: Button,
  args: { children: "Create repository", variant: "default", size: "default" },
  argTypes: {
    variant: {
      control: "select",
      options: [
        "default",
        "success",
        "destructive",
        "outline",
        "repository",
        "create",
        "secondary",
        "ghost",
        "link",
        "quiet",
        "avatar",
        "notification",
        "tab",
        "row",
        "menu",
      ],
    },
    size: {
      control: "select",
      options: [
        "default",
        "sm",
        "compact",
        "form",
        "create",
        "file-row",
        "xs",
        "lg",
        "icon",
        "icon-sm",
        "icon-xs",
        "icon-lg",
      ],
    },
    children: { control: "text" },
  },
  parameters: {
    docs: {
      description: {
        component:
          "A shared action with semantic intent, size, grouping and busy state. Icon actions require an accessible label. Spacing belongs to the surrounding layout.",
      },
    },
  },
} satisfies Meta<typeof Button>
export default meta
type Story = StoryObj<typeof meta>
export const Primary: Story = {}
export const Success: Story = { args: { variant: "success" } }
export const Destructive: Story = { args: { variant: "destructive", children: "Delete repository" } }
export const Outline: Story = { args: { variant: "outline", children: "Cancel" } }
export const Secondary: Story = { args: { variant: "secondary" } }
export const Ghost: Story = { args: { variant: "ghost" } }
export const Link: Story = { args: { variant: "link", children: "View repository" } }
export const Quiet: Story = { args: { variant: "quiet", children: "All issues" } }
export const Selected: Story = { args: { variant: "tab", "aria-pressed": true, children: "Repositories" } }
export const Unselected: Story = { args: { variant: "tab", "aria-pressed": false, children: "Starred" } }
export const Row: Story = { args: { variant: "row", size: "file-row", children: "README.md" } }
export const Menu: Story = { args: { variant: "menu", children: "Switch to main" } }
export const Disabled: Story = { args: { disabled: true } }
export const Loading: Story = { args: { loading: true, children: "Creating repository…" } }
export const Icon: Story = {
  args: { size: "icon-sm", variant: "outline", children: <Copy aria-hidden="true" />, "aria-label": "Copy clone URL" },
}
export const FullWidth: Story = { args: { fullWidth: true } }
export const Sizes: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      {(["xs", "sm", "default", "lg"] as const).map((size) => (
        <Button key={size} size={size}>
          {size}
        </Button>
      ))}
    </div>
  ),
}
export const AllStates: Story = {
  render: () => (
    <div className="space-y-5">
      {(
        [
          "default",
          "success",
          "destructive",
          "outline",
          "repository",
          "create",
          "secondary",
          "ghost",
          "link",
          "quiet",
          "avatar",
          "notification",
          "tab",
          "row",
          "menu",
        ] as const
      ).map((variant) => (
        <div key={variant} className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">{variant}</p>
          <div className="flex flex-wrap gap-3">
            <Button variant={variant}>Default</Button>
            <Button variant={variant} disabled>
              Disabled
            </Button>
            <Button variant={variant} loading>
              Loading
            </Button>
            <Button variant={variant} aria-pressed>
              Selected
            </Button>
          </div>
        </div>
      ))}
    </div>
  ),
}
export const RepositoryActions: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      <ButtonGroup aria-label="Star repository">
        <Button variant="outline" size="sm" aria-pressed>
          <Star aria-hidden="true" />
          Starred
        </Button>
        <ButtonGroupText>128</ButtonGroupText>
      </ButtonGroup>
      <ButtonGroup aria-label="Fork repository">
        <Button variant="outline" size="sm">
          <GitFork aria-hidden="true" />
          Fork
        </Button>
        <ButtonGroupText>24</ButtonGroupText>
      </ButtonGroup>
      <Button variant="success" size="sm">
        <GitMerge aria-hidden="true" />
        Merge
      </Button>
    </div>
  ),
}

export const AnchorAction: Story = { args: { asChild: true, children: <a href="#repository">View repository</a> } }
export const DisabledAnchor: Story = {
  args: { asChild: true, disabled: true, children: <a href="#repository">View repository</a> },
}
