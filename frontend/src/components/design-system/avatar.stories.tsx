import type { Meta, StoryObj } from "@storybook/react-vite"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/design-system"

const meta = { title: "Components/Avatar" } satisfies Meta
export default meta
type Story = StoryObj

export const Avatars: Story = {
  render: () => (
    <div className="flex items-center gap-4">
      <Avatar>
        <AvatarFallback>JM</AvatarFallback>
      </Avatar>
      <Avatar appearance="profile">
        <AvatarFallback appearance="profile">JM</AvatarFallback>
      </Avatar>
      <Avatar>
        <AvatarImage src="/missing-avatar.png" alt="Jan" />
        <AvatarFallback>J</AvatarFallback>
      </Avatar>
    </div>
  ),
}
