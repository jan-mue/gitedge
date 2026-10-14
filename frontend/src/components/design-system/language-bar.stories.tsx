import type { Meta, StoryObj } from "@storybook/react-vite"
import { LanguageBar } from "@/components/design-system"

const meta = { title: "Components/Language bar" } satisfies Meta
export default meta
type Story = StoryObj

export const LanguageDistribution: Story = {
  render: () => (
    <LanguageBar
      languages={[
        { name: "Python", size: 650, percentage: 65 },
        { name: "TypeScript", size: 300, percentage: 30 },
        { name: "Other", size: 50, percentage: 5 },
      ]}
    />
  ),
}
export const EmptyLanguages: Story = { render: () => <LanguageBar languages={[]} /> }
