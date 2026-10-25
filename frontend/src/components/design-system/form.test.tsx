import userEvent from "@testing-library/user-event"
import { useForm } from "react-hook-form"
import { describe, expect, test } from "vitest"
import { Form } from "@/components/design-system"
import { FormInputField } from "@/components/design-system/form"
import { render, screen } from "@/test/test-utils"

function PasswordForm() {
  const form = useForm({ defaultValues: { password: "" } })
  return (
    <Form {...form}>
      <FormInputField
        control={form.control}
        name="password"
        label="Password"
        placeholder="Password"
        required
        passwordToggle
      />
    </Form>
  )
}

describe("shared password field", () => {
  test("keeps the value and required state when revealing and hiding a password", async () => {
    const user = userEvent.setup()
    render(<PasswordForm />)
    const field = screen.getByLabelText(/Password/)
    expect(field).toBeRequired()
    expect(field).toHaveAttribute("type", "password")
    await user.type(field, "my-secret-password")
    await user.click(screen.getByRole("button", { name: "Show password" }))
    expect(field).toHaveAttribute("type", "text")
    expect(field).toHaveValue("my-secret-password")
    await user.click(screen.getByRole("button", { name: "Hide password" }))
    expect(field).toHaveAttribute("type", "password")
    expect(field).toHaveValue("my-secret-password")
  })
})
