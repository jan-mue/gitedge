import type { Meta, StoryObj } from "@storybook/react-vite"
import { ChoiceInput, Label } from "@/components/design-system"

const meta = { title: "Components/Choice Input" } satisfies Meta
export default meta
type Story = StoryObj

export const Choices: Story = {
  render: () => (
    <div className="flex flex-wrap gap-6">
      <Label appearance="inline">
        <ChoiceInput type="radio" name="visibility" defaultChecked />
        Public
      </Label>
      <Label appearance="inline">
        <ChoiceInput type="radio" name="visibility" />
        Private
      </Label>
      <Label appearance="inline">
        <ChoiceInput type="checkbox" defaultChecked />
        Watch repository
      </Label>
    </div>
  ),
}
