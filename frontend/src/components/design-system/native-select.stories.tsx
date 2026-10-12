import type { Meta, StoryObj } from "@storybook/react-vite"
import { NativeSelect } from "@/components/design-system"

const meta = { title: "Components/Native Select" } satisfies Meta
export default meta
type Story = StoryObj

export const NativeSelection: Story = {
  render: () => (
    <NativeSelect aria-label="Branch">
      <option>main</option>
      <option>develop</option>
    </NativeSelect>
  ),
}
export const NativeDisabled: Story = {
  render: () => (
    <NativeSelect aria-label="Branch" disabled>
      <option>main</option>
    </NativeSelect>
  ),
}
export const CompactSelection: Story = {
  render: () => (
    <NativeSelect aria-label="Sort order" compact>
      <option>Newest</option>
      <option>Oldest</option>
    </NativeSelect>
  ),
}
