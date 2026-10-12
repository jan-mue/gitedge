import type { Meta, StoryObj } from "@storybook/react-vite"
import { Logo } from "@/components/design-system"

const meta = { title: "Foundations/Logo" } satisfies Meta
export default meta
type Story = StoryObj

export const Brand: Story = {
  render: () => (
    <div className="flex items-center gap-6">
      <Logo asLink={false} />
      <Logo variant="icon" asLink={false} />
      <Logo size="hero" asLink={false} />
    </div>
  ),
}
