import type { Meta, StoryObj } from "@storybook/react-vite"
import { toast } from "sonner"
import { Button, Toaster } from "@/components/design-system"

const meta = { title: "Components/Notifications" } satisfies Meta
export default meta
type Story = StoryObj
export const ToastStates: Story = {
  render: () => (
    <>
      <Toaster />
      <div className="flex flex-wrap gap-3">
        <Button onClick={() => toast.success("Repository created", { description: "Your project is ready to push." })}>
          Success
        </Button>
        <Button variant="destructive" onClick={() => toast.error("Unable to save changes")}>
          Error
        </Button>
        <Button variant="outline" onClick={() => toast.info("Copied clone URL")}>
          Information
        </Button>
        <Button variant="outline" onClick={() => toast.warning("This action cannot be undone")}>
          Warning
        </Button>
        <Button variant="outline" onClick={() => toast.loading("Creating repository…")}>
          Loading
        </Button>
      </div>
    </>
  ),
}
