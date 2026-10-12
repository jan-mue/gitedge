import type { Meta, StoryObj } from "@storybook/react-vite"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/design-system"

const meta = { title: "Components/Tabs" } satisfies Meta
export default meta
type Story = StoryObj

export const TabNavigation: Story = {
  render: () => (
    <Tabs defaultValue="code" appearance="spaced">
      <TabsList>
        <TabsTrigger value="code">Code</TabsTrigger>
        <TabsTrigger value="issues">Issues</TabsTrigger>
        <TabsTrigger value="actions" disabled>
          Actions
        </TabsTrigger>
      </TabsList>
      <TabsContent value="code">Browse your repository files.</TabsContent>
      <TabsContent value="issues">Track bugs and feature requests.</TabsContent>
    </Tabs>
  ),
}
