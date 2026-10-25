import type { Meta, StoryObj } from "@storybook/react-vite"
import ActivityChart from "@/components/Repository/ActivityChart"
import { repositoryStoryMeta, series } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Repository/Activity chart" } satisfies Meta
export default meta
type Story = StoryObj

export const BarChart: Story = { render: () => <ActivityChart series={series} label="Weekly commits" /> }
export const AreaChart: Story = {
  render: () => <ActivityChart series={series} variant="area" label="Commit history" interactive />,
}
export const FrequencyChart: Story = {
  render: () => <ActivityChart series={series} variant="frequency" label="Code additions and deletions" />,
}
export const EmptyChart: Story = { render: () => <ActivityChart series={[]} label="No commits yet" /> }
