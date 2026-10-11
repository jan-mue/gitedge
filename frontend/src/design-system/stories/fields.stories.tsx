import type { Meta, StoryObj } from "@storybook/react-vite"
import { useState } from "react"
import { Checkbox, ChoiceInput, Input, Label, NativeSelect, PasswordInput, Textarea } from "@/design-system"

const meta = {
  title: "Components/Fields",
  component: Input,
  args: { placeholder: "Repository name", "aria-label": "Repository name" },
} satisfies Meta<typeof Input>
export default meta
type Story = StoryObj<typeof meta>
export const Default: Story = {}
export const Filled: Story = { args: { defaultValue: "gitedge" } }
export const Disabled: Story = { args: { disabled: true } }
export const ReadOnly: Story = {
  args: { readOnly: true, value: "https://gitedge-app.vercel.app/jan/gitedge.git", appearance: "clone" },
}
export const Invalid: Story = {
  args: { "aria-invalid": true, "aria-describedby": "field-error", defaultValue: "invalid name" },
  render: (args) => (
    <div className="space-y-2">
      <Input {...args} />
      <p id="field-error" className="text-sm text-destructive">
        Use letters, numbers, dots, underscores, or hyphens.
      </p>
    </div>
  ),
}
export const Title: Story = { args: { appearance: "title", defaultValue: "Make branch selection accessible" } }
export const Compact: Story = { args: { appearance: "compact" } }
export const Search: Story = { args: { type: "search", appearance: "search", placeholder: "Search issues…" } }
export const Password: Story = {
  render: () => <PasswordInput aria-label="Password" placeholder="Password" defaultValue="example-password" />,
}
export const PasswordInvalid: Story = {
  render: () => <PasswordInput aria-label="Password" error="Password is too short" placeholder="Password" />,
}
export const PasswordDisabled: Story = { render: () => <PasswordInput aria-label="Password" disabled /> }
export const Multiline: Story = {
  render: () => <Textarea aria-label="Description" placeholder="Leave a comment" rows={5} />,
}
export const MultilineDisabled: Story = {
  render: () => <Textarea aria-label="Description" disabled defaultValue="A read-only description" />,
}
export const MultilineInvalid: Story = {
  render: () => <Textarea aria-label="Description" aria-invalid defaultValue="Invalid description" />,
}
export const NativeSelection: Story = {
  render: () => (
    <NativeSelect aria-label="Branch">
      <option>main</option>
      <option>develop</option>
    </NativeSelect>
  ),
}
export const NativeDisabled: Story = {
  render: () => (
    <NativeSelect aria-label="Branch" disabled>
      <option>main</option>
    </NativeSelect>
  ),
}
export const CompactSelection: Story = {
  render: () => (
    <NativeSelect aria-label="Sort order" compact>
      <option>Newest</option>
      <option>Oldest</option>
    </NativeSelect>
  ),
}
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
