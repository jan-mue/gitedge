import type { Meta, StoryObj } from "@storybook/react-vite"
import { Button } from "./button"
import { ButtonGroup, ButtonGroupText } from "./button-group"

const meta = { title: "Components/Button group" } satisfies Meta
export default meta
type Story = StoryObj
export const Actions: Story = {
  render: () => (
    <ButtonGroup aria-label="Repository actions">
      <Button variant="repository" size="compact">
        Star
      </Button>
      <ButtonGroupText>128</ButtonGroupText>
    </ButtonGroup>
  ),
}
export const Disabled: Story = {
  render: () => (
    <ButtonGroup aria-label="Unavailable actions">
      <Button variant="repository" size="compact" disabled>
        Star
      </Button>
      <ButtonGroupText>128</ButtonGroupText>
    </ButtonGroup>
  ),
}
