import type { Meta, StoryObj } from "@storybook/react-vite"
import { Input } from "@/components/design-system"

const meta = {
  title: "Components/Input",
  component: Input,
  args: { placeholder: "Repository name", "aria-label": "Repository name" },
} satisfies Meta<typeof Input>
export default meta
type Story = StoryObj

export const Default: Story = {}
export const Filled: Story = { args: { defaultValue: "gitedge" } }
export const Disabled: Story = { args: { disabled: true } }
export const ReadOnly: Story = {
  args: { readOnly: true, value: "https://gitedge-app.vercel.app/jan/gitedge.git" },
}
export const CloneURL: Story = {
  args: {
    disabled: true,
    value: "https://gitedge-app.vercel.app/jan/gitedge.git",
    appearance: "clone",
    "aria-label": "HTTPS clone URL",
  },
}
export const Invalid: Story = {
  args: { "aria-invalid": true, "aria-describedby": "field-error", defaultValue: "invalid name" },
  render: (args) => (
    <div className="space-y-2">
      <Input {...args} />
      <p id="field-error" className="text-sm text-destructive">
        Use letters, numbers, dots, underscores, or hyphens.
      </p>
    </div>
  ),
}
export const Title: Story = { args: { appearance: "title", defaultValue: "Make branch selection accessible" } }
export const Compact: Story = { args: { appearance: "compact" } }
export const Search: Story = { args: { type: "search", appearance: "search", placeholder: "Search issues…" } }
