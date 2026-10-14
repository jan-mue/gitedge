import type { Meta, StoryObj } from "@storybook/react-vite"
import { Button, EmptyState } from "@/components/design-system"

const meta = { title: "Components/Layout" } satisfies Meta
export default meta
type Story = StoryObj

export const Empty: Story = {
  render: () => (
    <EmptyState
      title="No repositories yet"
      description="Create a repository or push one to get started"
      actions={<Button>Create repository</Button>}
    />
  ),
}
