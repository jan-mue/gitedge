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
const NotificationSelect = ({ open = false, disabled = false }: { open?: boolean; disabled?: boolean }) => (
  <Select defaultValue="participating" defaultOpen={open} disabled={disabled}>
    <SelectTrigger aria-label="Notifications">
      <SelectValue placeholder="Choose notifications" />
    </SelectTrigger>
    <SelectContent>
      <SelectGroup>
        <SelectLabel>Notifications</SelectLabel>
        <SelectItem value="all">All activity</SelectItem>
        <SelectItem value="participating">Participating and mentions</SelectItem>
        <SelectItem value="mentions">Mentions only</SelectItem>
        <SelectItem value="custom" disabled>
          Custom notifications
        </SelectItem>
      </SelectGroup>
      <SelectSeparator />
      <SelectGroup>
        <SelectLabel>Quiet mode</SelectLabel>
        <SelectItem value="none">No notifications</SelectItem>
      </SelectGroup>
    </SelectContent>
  </Select>
)
export const SelectClosed: Story = { render: () => <NotificationSelect /> }
export const SelectOpen: Story = { render: () => <NotificationSelect open /> }
export const SelectDisabled: Story = { render: () => <NotificationSelect disabled /> }
