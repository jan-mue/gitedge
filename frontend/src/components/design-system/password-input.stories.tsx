import type { Meta, StoryObj } from "@storybook/react-vite"
import { PasswordInput } from "@/components/design-system"

const meta = { title: "Components/Password Input" } satisfies Meta
export default meta
type Story = StoryObj

export const Password: Story = {
  render: () => <PasswordInput aria-label="Password" placeholder="Password" defaultValue="example-password" />,
}
export const PasswordInvalid: Story = {
  render: () => <PasswordInput aria-label="Password" error="Password is too short" placeholder="Password" />,
}
export const PasswordDisabled: Story = { render: () => <PasswordInput aria-label="Password" disabled /> }
