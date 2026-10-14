import type { Meta, StoryObj } from "@storybook/react-vite"
import { useState } from "react"
import { Checkbox, Label } from "@/components/design-system"

const meta = { title: "Components/Checkbox" } satisfies Meta
export default meta
type Story = StoryObj
const CheckboxStates = () => {
  const [checked, setChecked] = useState<boolean | "indeterminate">(false)
  return (
    <div className="flex flex-wrap gap-6">
      <Label appearance="inline">
        <Checkbox checked={checked} onCheckedChange={setChecked} />
        Unchecked
      </Label>
      <Label appearance="inline">
        <Checkbox defaultChecked />
        Checked
      </Label>
      <Label appearance="inline">
        <Checkbox checked="indeterminate" />
        Indeterminate
      </Label>
      <Label appearance="inline">
        <Checkbox disabled />
        Disabled
      </Label>
    </div>
  )
}
export const Checkboxes: Story = { render: () => <CheckboxStates /> }
