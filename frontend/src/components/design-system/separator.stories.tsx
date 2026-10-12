import type { Meta, StoryObj } from "@storybook/react-vite"
import { Separator } from "./separator"

const meta = { title: "Components/Separator" } satisfies Meta
export default meta
type Story = StoryObj
export const Horizontal: Story = {
  render: () => (
    <div className="space-y-4">
      <p>Repository details</p>
      <Separator />
      <p>Recent activity</p>
    </div>
  ),
}
export const Vertical: Story = {
  render: () => (
    <div className="flex h-6 items-center gap-4">
      <span>Code</span>
      <Separator orientation="vertical" />
      <span>Issues</span>
    </div>
  ),
}
