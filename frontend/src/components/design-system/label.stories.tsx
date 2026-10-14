import type { Meta, StoryObj } from "@storybook/react-vite"
import { Input } from "./input"
import { Label } from "./label"

const meta = { title: "Components/Label", component: Label } satisfies Meta<typeof Label>
export default meta
type Story = StoryObj<typeof meta>
export const Field: Story = {
  render: () => (
    <div>
      <Label htmlFor="label-repo" appearance="field">
        Repository name
      </Label>
      <Input id="label-repo" />
    </div>
  ),
}
export const DisabledField: Story = {
  render: () => (
    <div>
      <Label htmlFor="label-disabled" appearance="field">
        Repository name
      </Label>
      <Input id="label-disabled" disabled />
    </div>
  ),
}
