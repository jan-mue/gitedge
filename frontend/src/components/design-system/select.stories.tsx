import type { Meta, StoryObj } from "@storybook/react-vite"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/design-system"

const meta = { title: "Components/Select" } satisfies Meta
export default meta
type Story = StoryObj
const BranchSelect = ({ open = false, disabled = false }: { open?: boolean; disabled?: boolean }) => (
  <Select defaultValue="main" defaultOpen={open} disabled={disabled}>
    <SelectTrigger aria-label="Branch">
      <SelectValue placeholder="Select a branch" />
    </SelectTrigger>
    <SelectContent>
      <SelectGroup>
        <SelectLabel>Branches</SelectLabel>
        <SelectItem value="main">main</SelectItem>
        <SelectItem value="develop">develop</SelectItem>
        <SelectItem value="archived" disabled>
          archived
        </SelectItem>
      </SelectGroup>
      <SelectSeparator />
      <SelectGroup>
        <SelectLabel>Tags</SelectLabel>
        <SelectItem value="v1">v1.0.0</SelectItem>
      </SelectGroup>
    </SelectContent>
  </Select>
)
export const SelectClosed: Story = { render: () => <BranchSelect /> }
export const SelectOpen: Story = { render: () => <BranchSelect open /> }
export const SelectDisabled: Story = { render: () => <BranchSelect disabled /> }
