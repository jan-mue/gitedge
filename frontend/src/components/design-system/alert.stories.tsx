import type { Meta, StoryObj } from "@storybook/react-vite"
import { Info } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/design-system"

const meta = { title: "Components/Alert" } satisfies Meta
export default meta
type Story = StoryObj

export const Information: Story = {
  render: () => (
    <Alert>
      <Info aria-hidden="true" />
      <AlertTitle>Repository visibility</AlertTitle>
      <AlertDescription>This repository is visible to everyone.</AlertDescription>
    </Alert>
  ),
}
export const ErrorAlert: Story = {
  render: () => (
    <Alert variant="destructive">
      <Info aria-hidden="true" />
      <AlertTitle>Unable to save changes</AlertTitle>
      <AlertDescription>Check your connection and try again.</AlertDescription>
    </Alert>
  ),
}
