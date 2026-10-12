import type { Meta, StoryObj } from "@storybook/react-vite"
import { Textarea } from "@/components/design-system"

const meta = { title: "Components/Textarea" } satisfies Meta
export default meta
type Story = StoryObj

export const Multiline: Story = {
  render: () => <Textarea aria-label="Description" placeholder="Leave a comment" rows={5} />,
}
export const MultilineInvalid: Story = {
  render: () => <Textarea aria-label="Description" aria-invalid defaultValue="Invalid description" />,
}
export const MultilineDisabled: Story = { render: () => <Textarea aria-label="Description" disabled /> }
