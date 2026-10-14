import type { Meta, StoryObj } from "@storybook/react-vite"
import { type ComponentProps, useState } from "react"
import { FilterDropdown } from "@/components/design-system"

const InteractiveFilter = (args: ComponentProps<typeof FilterDropdown>) => {
  const [value, setValue] = useState(args.value)
  return <FilterDropdown {...args} value={value} onChange={setValue} />
}

const meta = {
  title: "Components/Filter dropdown",
  component: FilterDropdown,
  argTypes: {
    options: {
      control: false,
      table: { type: { summary: "FilterOption[]" }, defaultValue: { summary: "All authors, alice, bob" } },
      description: "The available values and their display labels.",
    },
    onChange: { control: false, description: "Called when a menu option is selected." },
  },
  args: {
    label: "Author",
    options: [
      { value: "", label: "All authors" },
      { value: "alice", label: "alice" },
      { value: "bob", label: "bob" },
    ],
    value: "",
    onChange: () => {},
  },
  render: (args) => <InteractiveFilter key={args.value} {...args} />,
} satisfies Meta<typeof FilterDropdown>
export default meta
type Story = StoryObj<typeof meta>
export const All: Story = {}
export const Selected: Story = { args: { value: "alice" } }
export const Empty: Story = { args: { options: [{ value: "", label: "All authors" }] } }
