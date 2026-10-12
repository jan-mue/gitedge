import type { Meta, StoryObj } from "@storybook/react-vite"
import { Button, Tooltip, TooltipContent, TooltipTrigger } from "@/components/design-system"

const meta = { title: "Components/Tooltip" } satisfies Meta
export default meta
type Story = StoryObj

export const TooltipClosed: Story = {
  render: () => (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="outline">Copy URL</Button>
      </TooltipTrigger>
      <TooltipContent>Copy the HTTPS clone URL</TooltipContent>
    </Tooltip>
  ),
}
export const TooltipOpen: Story = {
  render: () => (
    <Tooltip defaultOpen>
      <TooltipTrigger asChild>
        <Button variant="outline">Copy URL</Button>
      </TooltipTrigger>
      <TooltipContent>Copy the HTTPS clone URL</TooltipContent>
    </Tooltip>
  ),
}
