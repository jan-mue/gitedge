import userEvent from "@testing-library/user-event"
import { describe, expect, test } from "vitest"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/design-system"
import { DialogActionFooter } from "@/components/design-system/dialog"
import { render, screen } from "@/test/test-utils"

function DeleteDialog({ pending = false }: { pending?: boolean }) {
  return (
    <Dialog defaultOpen>
      <DialogContent>
        <DialogTitle>Delete account</DialogTitle>
        <DialogDescription>Confirm permanent deletion.</DialogDescription>
        <DialogActionFooter destructive pending={pending} />
      </DialogContent>
    </Dialog>
  )
}

describe("shared delete dialog actions", () => {
  test("labels the destructive action and closes on cancel", async () => {
    const user = userEvent.setup()
    render(<DeleteDialog />)
    expect(screen.getByRole("button", { name: "Delete" })).toHaveAttribute("type", "submit")
    await user.click(screen.getByRole("button", { name: "Cancel" }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  test("disables cancellation and submission while deletion is pending", () => {
    render(<DeleteDialog pending />)
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled()
  })
})
