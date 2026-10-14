import type { Meta, StoryObj } from "@storybook/react-vite"
import { type ComponentProps, useState } from "react"
import { SelectField } from "@/components/design-system"

const InteractiveField = (args: ComponentProps<typeof SelectField>) => {
  const [value, setValue] = useState(args.value ?? "")
  return <SelectField {...args} value={value} onValueChange={setValue} />
}
const meta = {
  title: "Components/Select field",
  component: SelectField,
  args: {
    "aria-label": "Notification preference",
    value: "all",
    options: [
      { value: "all", label: "All activity" },
      { value: "participating", label: "Participating and mentions" },
      { value: "mentions", label: "Mentions only" },
      { value: "custom", label: "Custom notifications", disabled: true },
    ],
  },
  argTypes: {
    options: {
      control: false,
      table: { type: { summary: "SelectOption[]" }, defaultValue: { summary: "Notification preferences" } },
    },
    ref: { control: false },
    onValueChange: { control: false },
  },
  render: (args) => <InteractiveField key={args.value} {...args} />,
} satisfies Meta<typeof SelectField>
export default meta
type Story = StoryObj<typeof meta>
export const Default: Story = {}
export const Open: Story = { args: { defaultOpen: true } }
export const Placeholder: Story = { args: { value: "" } }
export const Disabled: Story = { args: { disabled: true } }
export const Invalid: Story = { args: { "aria-invalid": true } }
export const Compact: Story = { args: { appearance: "compact" } }
export const Owner: Story = { args: { appearance: "owner" } }
export const Empty: Story = { args: { value: "", options: [], defaultOpen: true } }
