import type { Meta, StoryObj } from "@storybook/react-vite"
import { Button, DangerZone, DangerZoneAction } from "@/components/design-system"

const meta = { title: "Components/Danger zone", component: DangerZone } satisfies Meta<typeof DangerZone>
export default meta
type Story = StoryObj<typeof meta>

export const Repository: Story = {
  render: () => (
    <DangerZone>
      <DangerZoneAction
        title="Delete this repository"
        description="Deleting a repository is permanent and cannot be undone."
        action={
          <Button variant="dangerOutline" size="danger">
            Delete this repository
          </Button>
        }
      />
    </DangerZone>
  ),
}
export const MultipleActions: Story = {
  render: () => (
    <DangerZone>
      <DangerZoneAction
        title="Make this repository public"
        description="Anyone will be able to view this repository and its activity."
        action={
          <Button variant="dangerOutline" size="danger">
            Make repository public
          </Button>
        }
      />
      <DangerZoneAction
        title="Delete this repository"
        description="Deleting a repository is permanent and cannot be undone."
        action={
          <Button variant="dangerOutline" size="danger">
            Delete this repository
          </Button>
        }
      />
    </DangerZone>
  ),
}
export const Disabled: Story = {
  render: () => (
    <DangerZone>
      <DangerZoneAction
        title="Delete this repository"
        description="Wait for the current operation to complete."
        action={
          <Button variant="dangerOutline" size="danger" disabled>
            Delete this repository
          </Button>
        }
      />
    </DangerZone>
  ),
}
